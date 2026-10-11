"""Action layer against the database: reset invariants, the state machine, the demo loop, escalation,
scope and API shapes. Resets the action tables once, then runs every test in a rolled-back transaction.
Skipped when PostgreSQL is not reachable."""
from __future__ import annotations

import json
from datetime import timedelta

import pytest
from sqlalchemy import text

from sentinel import config

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def eng():
    from sentinel.actions import demo
    from sentinel.db import engine
    try:
        with engine().connect() as c:
            if not c.execute(text("SELECT to_regclass('mart_facility_month')")).scalar():
                pytest.skip("marts not loaded")
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"database not reachable: {e}")
    with engine().begin() as c:
        demo.reset(c, quiet=True)
    return engine()


@pytest.fixture
def conn(eng):
    c = eng.connect()
    tx = c.begin()
    yield c
    tx.rollback()
    c.close()


@pytest.fixture(scope="module")
def scenario(eng):
    return json.loads((config.ACTIONS_DIR / "demo_scenario.json").read_text())


def scalar(conn, sql, **p):
    return conn.execute(text(sql), p).scalar()


# ---- reset invariants ----------------------------------------------------------------------------------
def test_reset_invariants(conn):
    assert scalar(conn, "SELECT sim_date FROM sim_clock").isoformat() == "2026-10-30"
    assert scalar(conn, """SELECT count(*) FROM mart_queue q JOIN mart_facility_month f USING (facility_id, analysis_month)
                           WHERE q.analysis_month = (SELECT max(analysis_month) FROM mart_facility_month)
                           AND q.queue IN ('RESOURCE_ACTION', 'DATA_VERIFICATION')
                           AND NOT EXISTS (SELECT 1 FROM case_file c WHERE c.facility_id = q.facility_id)""") == 0
    assert scalar(conn, """SELECT count(*) FROM (SELECT unit_id, playbook_id FROM case_file GROUP BY 1, 2 HAVING count(*) > 1) d""") == 0
    assert scalar(conn, "SELECT count(*) FROM case_file WHERE owner_person_id IS NULL") == 0
    # Nothing is sent at reset: every message waits for a person.
    assert scalar(conn, "SELECT count(*) FROM message WHERE status NOT IN ('draft', 'digest_pending')") == 0
    assert scalar(conn, "SELECT max(chars) FROM message WHERE channel = 'sms'") <= 160
    assert scalar(conn, "SELECT count(*) FROM message WHERE body NOT LIKE '%DEMO%'") == 0


def test_zero_verifications_live_equals_baseline(conn):
    for st in config.state_codes():
        diff = scalar(conn, """SELECT count(*) FROM mart_facility_live l JOIN mart_facility_month m
                                 ON m.facility_id = l.facility_id AND m.analysis_month = l.analysis_month
                               WHERE l.state_code = :s AND (l.live_queue <> m.queue OR l.live_tag <> m.tag
                                 OR l.live_risk <> m.operational_risk OR l.live_confidence <> m.data_confidence
                                 OR l.field_verified OR l.changed)""", s=st)
        assert diff == 0, st


def test_baseline_marts_untouched_by_actions(conn, scenario):
    """The overlay never writes to the decision marts."""
    from sentinel.actions import engine as eng_mod, service as svc
    before = conn.execute(text("SELECT md5(string_agg(facility_id || queue || tag || data_confidence, ',' ORDER BY facility_id)) "
                               "FROM mart_facility_month WHERE state_code = 'bauchi'")).scalar()
    sid = scenario["bauchi"]["shortage"]
    ids = [r[0] for r in conn.execute(text("SELECT message_id FROM message WHERE case_id = :c AND status = 'draft'"), {"c": sid})]
    svc.approve_messages(conn, ids, "test")
    for _ in range(2):
        eng_mod.tick(conn)
    after = conn.execute(text("SELECT md5(string_agg(facility_id || queue || tag || data_confidence, ',' ORDER BY facility_id)) "
                              "FROM mart_facility_month WHERE state_code = 'bauchi'")).scalar()
    assert before == after


# ---- state machine ---------------------------------------------------------------------------------------
def test_transitions_are_validated_and_logged(conn, scenario):
    from sentinel.actions import service as svc
    cid = scenario["bauchi"]["escalate"]
    case = svc.get_case(conn, cid)
    svc.acknowledge(conn, cid, "test")
    assert svc.get_case(conn, cid)["status"] == "acknowledged"
    svc.advance(conn, cid, "test")
    case = svc.get_case(conn, cid)
    assert case["status"] == "in_progress"
    with pytest.raises(svc.ActionError, match="cannot move"):
        svc.set_status(conn, case, "acknowledged", case["opened_at"], "test")
    with pytest.raises(svc.ActionError):
        svc.resolve(conn, cid, "test", "made_up_code")
    svc.resolve(conn, cid, "test", next(iter(config.actions_cfg()["outcome_codes"])))
    assert svc.get_case(conn, cid)["status"] == "resolved"
    assert scalar(conn, "SELECT count(*) FROM message WHERE case_id = :c AND status IN ('draft', 'digest_pending')", c=cid) == 0
    with pytest.raises(svc.ActionError, match="closed|already"):
        svc.acknowledge(conn, cid, "test")
    # Every status change has an event with matching from/to.
    evs = conn.execute(text("""SELECT from_status, to_status FROM case_event WHERE case_id = :c AND from_status IS NOT NULL
                               ORDER BY event_id"""), {"c": cid}).all()
    assert [e[1] for e in evs] == ["acknowledged", "in_progress", "resolved"]
    assert evs[0][0] == "open" and all(evs[i][0] == evs[i - 1][1] for i in range(1, len(evs)))


def test_only_drafts_can_be_approved(conn, scenario):
    from sentinel.actions import service as svc
    ids = [r[0] for r in conn.execute(text("SELECT message_id FROM message WHERE case_id = :c AND status = 'draft'"),
                                      {"c": scenario["bauchi"]["shortage"]})]
    svc.approve_messages(conn, ids, "test")
    with pytest.raises(svc.ActionError, match="only drafts"):
        svc.approve_messages(conn, ids, "test")


def test_edit_must_keep_demo_label_and_length(conn):
    from sentinel.actions import service as svc
    mid = scalar(conn, "SELECT message_id FROM message WHERE status = 'draft' AND channel = 'sms' LIMIT 1")
    with pytest.raises(svc.ActionError):
        svc.edit_message(conn, mid, "test", "Please count your ACT")
    with pytest.raises(svc.ActionError):
        svc.edit_message(conn, mid, "test", "DEMO " + "x" * 200)


# ---- messaging and the demo loop ----------------------------------------------------------------------------
def test_nothing_is_sent_without_approval(conn):
    from sentinel.actions import engine as eng_mod
    eng_mod.tick(conn)
    assert scalar(conn, "SELECT count(*) FROM message WHERE status IN ('sent', 'delivered') AND approved_at IS NULL") == 0


def test_demo_loop_shortage(conn, scenario):
    from sentinel.actions import engine as eng_mod, service as svc
    cid = scenario["bauchi"]["shortage"]
    ids = [r[0] for r in conn.execute(text("SELECT message_id FROM message WHERE case_id = :c AND status = 'draft'"), {"c": cid})]
    assert ids
    svc.approve_messages(conn, ids, "test")
    for _ in range(2):
        eng_mod.tick(conn)
    case = svc.get_case(conn, cid)
    assert case["status"] == "resupply_requested"
    assert scalar(conn, "SELECT raw_text FROM inbound_response WHERE case_id = :c ORDER BY received_at LIMIT 1", c=cid) == \
        "ACT 12 RDT 0 FRIDGE 1"
    live = conn.execute(text("SELECT live_tag, field_verified, live_confidence FROM mart_facility_live WHERE facility_id = :f"),
                        {"f": case["facility_id"]}).one()
    assert live[0] == "ACT NOW" and live[1] and live[2] != "HIGH"
    rq = conn.execute(text("SELECT commodity_code, qty_requested, status FROM resupply_request WHERE case_id = :c"), {"c": cid}).all()
    assert {r[0] for r in rq} >= {"ACT", "RDT"} and all(r[1] > 0 for r in rq)
    assert all(r[2] in ("draft", "pending_approval") for r in rq)            # a person approves stock movement


def test_rate_limit_per_person_per_day(conn):
    from sentinel.actions import engine as eng_mod, service as svc
    cap = config.actions_cfg()["messaging"]["max_per_person_per_day"]
    pid = scalar(conn, """SELECT to_person_id FROM message WHERE status = 'draft' GROUP BY 1 ORDER BY count(*) DESC LIMIT 1""")
    ids = [r[0] for r in conn.execute(text("SELECT message_id FROM message WHERE to_person_id = :p AND status = 'draft'"), {"p": pid})]
    if len(ids) <= cap:
        pytest.skip("no person with more drafts than the daily cap")
    svc.approve_messages(conn, ids, "test")
    eng_mod.tick(conn)
    day = svc.clock(conn)
    assert scalar(conn, "SELECT count(*) FROM message WHERE to_person_id = :p AND sent_at = :d", p=pid, d=day) <= cap


# ---- escalation -----------------------------------------------------------------------------------------------
def test_escalation_one_level_per_breach_and_stops_at_top(conn, scenario):
    from sentinel.actions import engine as eng_mod, service as svc
    cid = scenario["bauchi"]["escalate"]
    ladder = config.actions_cfg()["escalation"][svc.get_case(conn, cid)["escalation_ladder"]]
    seen = []
    for _ in range(len(ladder) + 1):
        conn.execute(text("UPDATE case_file SET last_activity_at = last_activity_at - 30 WHERE case_id = :c"), {"c": cid})
        eng_mod.tick(conn)
        seen.append(svc.get_case(conn, cid)["escalation_level"])
    assert seen[0] == 1 and seen[1] == min(2, len(ladder) - 1)
    assert all(b - a <= 1 for a, b in zip([0] + seen, seen))
    assert max(seen) == len(ladder) - 1 and seen[-1] == seen[-2]
    assert svc.get_case(conn, cid)["escalated_to_role"] == ladder[-1]["role"]


def test_acknowledged_not_overdue_does_not_escalate(conn, scenario):
    from sentinel.actions import engine as eng_mod, service as svc
    cid = scenario["bauchi"]["escalate"]
    svc.acknowledge(conn, cid, "test")
    case = svc.get_case(conn, cid)
    conn.execute(text("UPDATE case_file SET last_activity_at = :a, due_at = :d WHERE case_id = :c"),
                 {"a": case["opened_at"] - timedelta(days=30), "d": case["opened_at"] + timedelta(days=60), "c": cid})
    eng_mod.tick(conn)
    assert svc.get_case(conn, cid)["escalation_level"] == 0


# ---- scope -------------------------------------------------------------------------------------------------
def test_scope_rules(conn, scenario):
    from sentinel.actions import scope, service as svc
    ppl = svc.people(conn)
    toro = ppl.get(ppl.find("lga_phc_coord", "bauchi", scenario["bauchi"]["lga_id"], None))
    kano_case = svc.get_case(conn, scenario["kano"]["shortage"])
    own = svc.get_case(conn, scenario["bauchi"]["shortage"])
    assert scope.can_act_on_case(toro, own) and not scope.can_act_on_case(toro, kano_case)
    with pytest.raises(scope.ScopeError):
        scope.require_case(toro, kano_case, "advance")
    fac = ppl.get(ppl.find("fac_oic", "bauchi", own["lga_id"], own["facility_id"]))
    with pytest.raises(scope.ScopeError, match="cannot approve"):
        scope.require_case(fac, own, "approve_messages")
    nat = ppl.get(conn.execute(text("SELECT person_id FROM dim_person WHERE level = 'national' LIMIT 1")).scalar())
    assert scope.can_act_on_case(nat, {"level": "state", "state_code": "kano"})
    assert not scope.can_act_on_case(nat, own)
    scope.require_state(nat, "kano", "open a state case")                    # national may open state cases
    with pytest.raises(scope.ScopeError):
        scope.require_national(toro, "request a state response")


# ---- API -------------------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def client(eng):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from sentinel.api.main import app
    return TestClient(app)


def test_api_shapes(client, scenario):
    r = client.get("/state/bauchi/cases", params={"limit": 5})
    assert r.status_code == 200 and {"cases", "total"} <= set(r.json())
    d = client.get(f"/cases/{scenario['bauchi']['shortage']}").json()
    assert {"case", "playbook", "events", "messages", "responses", "resupply", "escalation_ladder", "people", "clock"} <= set(d)
    assert client.get("/sim/clock").json()["sim_date"] == "2026-10-30"
    s = client.get("/state/bauchi/actions/summary")
    assert s.status_code == 200
    n = client.get("/national/actions/summary")
    assert n.status_code == 200 and len(n.content) < 60_000
    assert client.get("/cases/C999999").status_code == 404


def test_api_scope_403(client, scenario):
    with client:
        from sentinel.actions import service as svc
        ppl = svc.people()
        toro = ppl.find("lga_phc_coord", "bauchi", scenario["bauchi"]["lga_id"], None)
        r = client.post(f"/cases/{scenario['kano']['shortage']}/advance", json={"actor_person_id": toro})
        assert r.status_code == 403 and "out of scope" in r.json()["detail"]
        r = client.post("/national/states/kano/request-response", json={"actor_person_id": toro})
        assert r.status_code == 403
        r = client.post(f"/cases/{scenario['bauchi']['shortage']}/advance", json={})
        assert r.status_code == 422
