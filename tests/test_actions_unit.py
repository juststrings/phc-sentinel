"""Action layer, pure logic (no database): rules, reply parser, live overlay, templates, providers, directory."""
from __future__ import annotations

import copy
import re
from datetime import date

import pandas as pd
import pytest

from sentinel import config
from sentinel.actions import live, providers, replies, rules, templates


# ---- rules -------------------------------------------------------------------------------------------
def rec(**kw):
    base = {"facility_id": "F1", "state_code": "bauchi", "lga_id": "1", "queue": "MONITOR", "tag": "MONITOR",
            "top_domain": None, "report_received": True, "reliable_silence": False, "nhlmis_stale": False,
            "fridge_nonfunctional": False, "vaccine_stockout": False, "sessions_ratio": 1.0}
    return {**base, **kw}


def fired(r: dict) -> list[str]:
    df = pd.DataFrame([r])
    out, _ = rules.assign(df, "facility")
    return sorted(out["rule_id"])


@pytest.mark.parametrize("r,expected", [
    (rec(queue="RESOURCE_ACTION", tag="ACT NOW", top_domain="malaria_commodity"), ["R01_act_now_commodity"]),
    (rec(queue="RESOURCE_ACTION", tag="ACT NOW", top_domain="vaccine_cold_chain", vaccine_stockout=True), ["R02_act_now_vaccine"]),
    (rec(fridge_nonfunctional=True), ["R03_fridge_down"]),
    (rec(queue="RESOURCE_ACTION", tag="VERIFY THEN ACT", top_domain="vaccine_cold_chain"), ["R04_verify_then_act"]),
    (rec(queue="DATA_VERIFICATION", tag="DO NOT ASSUME SAFE", reliable_silence=True, report_received=False), ["R05_silent_reliable"]),
    (rec(queue="DATA_VERIFICATION", tag="DO NOT ASSUME SAFE", nhlmis_stale=True), ["R06_stale_nhlmis"]),
    (rec(queue="DATA_VERIFICATION", tag="DO NOT ASSUME SAFE"), ["R07_dnas_other"]),
    (rec(sessions_ratio=0.5), ["R08_session_shortfall"]),
    (rec(), []),
])
def test_each_rule_fires(r, expected):
    assert fired(r) == expected


@pytest.mark.parametrize("r", [
    rec(queue="RESOURCE_ACTION", tag="ACT NOW", top_domain="vaccine_cold_chain", vaccine_stockout=False),  # R02 needs a stockout
    rec(sessions_ratio=0.75),                                    # 75% is not below 75%
    rec(sessions_ratio=0.5, report_received=False),              # no report, no session rule
    rec(queue="DATA_VERIFICATION", tag="DO NOT ASSUME SAFE", nhlmis_stale=True, report_received=False),  # R06 needs a report -> R07
])
def test_near_misses(r):
    out = fired(r)
    assert "R02_act_now_vaccine" not in out and "R08_session_shortfall" not in out and "R06_stale_nhlmis" not in out


def test_first_match_within_group_both_groups_fire():
    r = rec(queue="RESOURCE_ACTION", tag="ACT NOW", top_domain="vaccine_cold_chain", vaccine_stockout=True, fridge_nonfunctional=True)
    assert fired(r) == ["R02_act_now_vaccine", "R03_fridge_down"]
    r = rec(queue="DATA_VERIFICATION", tag="DO NOT ASSUME SAFE", reliable_silence=True, nhlmis_stale=True)
    assert fired(r) == ["R05_silent_reliable"]      # R05 before R06 and R07 in the verification group


def test_lga_and_state_rules():
    out, _ = rules.assign(pd.DataFrame([{"state_code": "x", "lga_id": "1", "pct_verification": 0.5},
                                        {"state_code": "x", "lga_id": "2", "pct_verification": 0.49}]), "lga")
    assert list(out["rec"]) == [0]
    st = pd.DataFrame([{"state_code": "a", "status": "evidence_gap"}, {"state_code": "b", "status": "watch"}])
    r10 = next(r for r in rules.rules() if r["id"] == "R10_state_response")
    assert r10["mode"] == "suggest" and list(rules.mask(st, r10["when"])) == [True, False]


def test_modifier_raises_priority_once():
    order = config.actions_cfg()["priorities"]
    assert rules.raise_priority("P3", 1, order) == "P2"
    assert rules.raise_priority("P1", 1, order) == "P1"


@pytest.mark.parametrize("mutate,msg", [
    (lambda r: r.update(when={"all": [{"field": "tag", "op": "regex", "value": "x"}]}), "unknown op"),
    (lambda r: r.update(when={"all": [{"field": "tag", "op": "eq"}]}), "needs a value"),
    (lambda r: r.update(playbook="PB_NOPE"), "unknown playbook"),
    (lambda r: r.update(owner_role="nobody"), "unknown owner_role"),
    (lambda r: r.update(when={"all": []}), "non-empty"),
    (lambda r: r.pop("escalation"), "missing escalation"),
])
def test_malformed_rule_fails_loudly_with_id(mutate, msg):
    cfg = copy.deepcopy(config.actions_cfg())
    mutate(cfg["rules"][0])
    with pytest.raises(rules.RuleError, match=rf"rule R01_act_now_commodity: .*{msg}"):
        rules.validate(cfg)


def test_no_eval_in_rule_engine():
    src = open(rules.__file__, encoding="utf-8").read()
    assert "eval(" not in src and "exec(" not in src


# ---- reply parser (25+ cases) -------------------------------------------------------------------------
STOCK = ["ACT", "RDT", "FRIDGE"]


@pytest.mark.parametrize("text,status,fields", [
    ("ACT 12 RDT 0 FRIDGE 1", "ok", {"ACT": 12, "RDT": 0, "FRIDGE": 1}),
    ("act 12 rdt 0 fridge 1", "ok", {"ACT": 12, "RDT": 0, "FRIDGE": 1}),
    ("act12 rdt0 fridge1", "ok", {"ACT": 12, "RDT": 0, "FRIDGE": 1}),
    ("  ACT   12   RDT 0   FRIDGE 1  ", "ok", {"ACT": 12, "RDT": 0, "FRIDGE": 1}),
    ("FRIDGE 1 RDT 0 ACT 12", "ok", {"ACT": 12, "RDT": 0, "FRIDGE": 1}),
    ("Akt 12, RTD: 0, frigde=1", "ok", {"ACT": 12, "RDT": 0, "FRIDGE": 1}),
    ("ACT: 40; RDT: 120; FRIDGE: ok", "ok", {"ACT": 40, "RDT": 120, "FRIDGE": 1}),
    ("ACT nil RDT none FRIDGE not working", "ok", {"ACT": 0, "RDT": 0, "FRIDGE": 0}),
    ("act 5 rdt 10 fridge spoilt", "ok", {"ACT": 5, "RDT": 10, "FRIDGE": 0}),
    ("12 ACT 30 RDT FRIDGE 1", "ok", {"ACT": 12, "RDT": 30, "FRIDGE": 1}),
    ("pls ACT 12 RDT 0 FRIDGE 1 thanks", "ok", {"ACT": 12, "RDT": 0, "FRIDGE": 1}),
    ("ACT 12 RDT 0 FRIDGE 1 Ref C-1042", "ok", {"ACT": 12, "RDT": 0, "FRIDGE": 1}),
    ("ACTS 12 RDTS 4 FRIDGE YES", "ok", {"ACT": 12, "RDT": 4, "FRIDGE": 1}),
    ("ACT 12", "partial", {"ACT": 12}),
    ("ACT RDT 5 FRIDGE 1", "partial", {"RDT": 5, "FRIDGE": 1}),
    ("ACT 12 RDT 0 FRIDGE 1 banana", "partial", {"ACT": 12, "RDT": 0, "FRIDGE": 1}),
    ("Hello sir we have act 12", "partial", {"ACT": 12}),
    ("pls call me", "unparseable", {}),
    ("blah blah", "unparseable", {}),
    ("", "unparseable", {}),
    ("?????", "unparseable", {}),
])
def test_stock_replies(text, status, fields):
    r = replies.parse(text, STOCK)
    assert r["status"] == status, r
    assert {k: v for k, v in r["fields"].items()} == fields


@pytest.mark.parametrize("text,status,fields,expects", [
    ("REPORT SENT", "ok", {"REPORT_SENT": True}, ["REPORT"]),
    ("report submitted", "ok", {"REPORT_SENT": True}, ["REPORT"]),
    ("sent report", "ok", {"REPORT_SENT": True}, ["REPORT"]),
    ("RECEIVED ACT 200", "ok", {"RECEIVED": {"ACT": 200}}, ["RECEIVED"]),
    ("received 200 act", "ok", {"RECEIVED": {"ACT": 200}}, ["RECEIVED"]),
    ("RECEIVED ACT 200 RDT 300", "ok", {"RECEIVED": {"ACT": 200, "RDT": 300}}, ["RECEIVED"]),
    ("recieved 200", "partial", {"RECEIVED": {"ACT": 200}}, ["RECEIVED"]),
    ("HELP", "ok", {"HELP": True}, STOCK),
    ("PENTA 40 FRIDGE 0", "ok", {"PENTA": 40, "FRIDGE": 0}, ["PENTA", "FRIDGE"]),
    ("fridge working", "ok", {"FRIDGE": 1}, ["FRIDGE"]),
])
def test_other_replies(text, status, fields, expects):
    r = replies.parse(text, expects)
    assert r["status"] == status, r
    assert r["fields"] == fields


def test_ref_is_extracted():
    assert replies.parse("ACT 1 RDT 1 FRIDGE 1 C-1042")["ref"] == "C-1042"


# ---- live overlay ----------------------------------------------------------------------------------------
AS_OF = date(2026, 10, 30)


def base(**kw):
    b = {"facility_id": "F1", "as_of": AS_OF, "queue": "DATA_VERIFICATION", "tag": "DO NOT ASSUME SAFE",
         "operational_risk": "NORMAL", "data_confidence": "LOW", "sev_malaria_commodity": "NORMAL",
         "credible_malaria_commodity": False, "sev_vaccine_cold_chain": "NORMAL", "credible_vaccine_cold_chain": True,
         "sev_service_pressure": "NORMAL", "credible_service_pressure": True, "nhlmis_stale": True,
         "vaccine_stockout": False}
    return {**b, **kw}


def v(item, qty=None, fridge=None, day=date(2026, 11, 1)):
    return {"verified_at": day, "source": "sms_reply", "commodity_code": item, "quantity": qty, "fridge_functional": fridge}


AMC = {"ACT": 40.0, "RDT": 100.0}


def test_no_verification_equals_baseline():
    b = base()
    out = live.live_status(b, {"FRESH_NHLMIS_STALE"}, AMC, [], date(2026, 11, 5))
    assert (out["live_queue"], out["live_tag"], out["live_risk"], out["live_confidence"]) == \
           (b["queue"], b["tag"], b["operational_risk"], b["data_confidence"])
    assert not out["changed"] and not out["field_verified"]


def test_adequate_stock_moves_dnas_to_monitor_with_moderate_at_most():
    out = live.live_status(base(), {"FRESH_NHLMIS_STALE"}, AMC, [v("ACT", 120), v("RDT", 300)], date(2026, 11, 2))
    assert out["live_queue"] == "MONITOR" and out["live_confidence"] == "MODERATE" and out["changed"]
    assert out["nhlmis_stale"]                                      # stale context stays visible


def test_shortage_confirmed_is_act_now_field_verified():
    b = base(queue="RESOURCE_ACTION", tag="VERIFY THEN ACT", operational_risk="HIGH")
    out = live.live_status(b, {"FRESH_NHLMIS_STALE", "COMP_MISSING_REPORT"}, AMC, [v("ACT", 12), v("RDT", 0)], date(2026, 11, 2))
    assert out["live_tag"] == "ACT NOW" and out["live_risk"] == "CRITICAL" and out["live_field_driven"]
    assert out["live_confidence"] == "LOW"           # a missing report is not lifted by a field count


def test_missing_report_keeps_low_confidence():
    out = live.live_status(base(), {"COMP_MISSING_REPORT", "FRESH_NHLMIS_STALE"}, AMC, [v("ACT", 120), v("RDT", 300)], date(2026, 11, 2))
    assert out["live_confidence"] == "LOW" and out["live_queue"] == "DATA_VERIFICATION"


def test_verification_never_produces_high_confidence():
    for sev in ({"FRESH_NHLMIS_STALE"}, set(), {"SIL_SILENT"}):
        for qty in (0, 12, 500):
            out = live.live_status(base(), sev, AMC, [v("ACT", qty), v("RDT", qty)], date(2026, 11, 2))
            assert out["live_confidence"] != "HIGH"


def test_expired_verification_has_no_effect():
    old = v("ACT", 120, day=date(2026, 11, 1))
    out = live.live_status(base(), {"FRESH_NHLMIS_STALE"}, AMC, [old], date(2026, 11, 20))   # 19 days > 14
    assert not out["field_verified"] and not out["changed"]
    before = v("ACT", 120, day=date(2026, 10, 20))                                       # before the baseline date
    assert not live.live_status(base(), set(), AMC, [before], date(2026, 10, 31))["field_verified"]


def test_fridge_down_raises_vaccine_to_high():
    b = base(queue="MONITOR", tag="MONITOR", data_confidence="HIGH", nhlmis_stale=False)
    out = live.live_status(b, set(), AMC, [v(None, fridge=False)], date(2026, 11, 2))
    assert out["live_risk"] == "HIGH" and out["live_tag"] == "ACT NOW"


def test_reports_submitted_changes_nothing():
    r = {"verified_at": date(2026, 11, 2), "source": "sms_reply", "commodity_code": None, "quantity": None,
         "fridge_functional": None, "reports_submitted": True}
    out = live.live_status(base(), {"COMP_MISSING_REPORT"}, AMC, [r], date(2026, 11, 3))
    assert (out["live_queue"], out["live_confidence"]) == ("DATA_VERIFICATION", "LOW")


# ---- templates, providers, messaging config -----------------------------------------------------------------
def test_every_sms_template_fits_160_with_long_names():
    ctx = {"facility": "Comprehensive Primary Health Care Centre Unguwar Sarkin Fawa Extension", "lga": "Ndokwa East Local Government",
           "state": "Cross River", "case_ref": "C-123456", "due": "28 Nov", "priority": "P1", "playbook": "Resupply malaria commodities",
           "period": "Sep 2026", "count": 123}
    for tid, t in config.templates_cfg()["templates"].items():
        if "sms" in t:
            body, ch = templates.render(tid, "sms", ctx)
            assert ch == "sms" and len(body) <= 160, (tid, len(body))
            assert "DEMO" in body


def test_provider_must_be_simulated():
    assert config.actions_cfg()["messaging"]["provider"] == "simulated"
    assert isinstance(providers.get_provider("simulated"), providers.SimulatedProvider)
    with pytest.raises(RuntimeError):
        providers.get_provider("twilio")
    for stub in (providers.AfricasTalkingProvider(), providers.TwilioProvider(), providers.SmtpProvider()):
        with pytest.raises(NotImplementedError):
            stub.send({}, date(2026, 11, 1), False)


def test_approval_is_required_in_config():
    assert config.actions_cfg()["messaging"]["require_approval"] is True
    assert config.actions_cfg()["simulation"]["approve_probability_per_day"] == 0.0


# ---- directory -------------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def people():
    p = config.ACTIONS_DIR / "dim_person.parquet"
    if not p.exists():
        pytest.skip("directory not built (python -m sentinel actions load)")
    return pd.read_parquet(p)


def test_directory_roles_complete(people):
    roles = config.actions_cfg()["roles"]
    assert people["person_id"].is_unique
    assert len(people[people.level == "national"]) == 3
    for st in config.state_codes():
        sp = people[people.state_code == st]
        assert set(sp[sp.level == "state"].role_code) == {r for r, v in roles.items() if v["level"] == "state"}
        dim = pd.read_parquet(config.StatePaths(st).staging / "dim_facility.parquet")
        assert len(sp[sp.level == "facility"]) == 2 * len(dim)
        assert len(sp[sp.level == "lga"]) == 5 * dim["lga_id"].nunique()


def test_contacts_are_not_real(people):
    assert people["phone_display"].str.match(r"^SIM-[A-Z]{2}-\d{6}$").all()
    assert people["email"].str.endswith(".invalid").all()
    assert people["synthetic"].all()


def test_no_blocked_full_names(people):
    blocked = {b.lower() for b in config.name_pools()["blocked_full_names"]}
    full = (people["first_name"] + " " + people["last_name"]).str.lower()
    assert not full.isin(blocked).any()


def test_directory_is_deterministic():
    from sentinel.actions import directory
    st = config.state("bayelsa")
    a = directory._people_for_state(st, directory.roles_table())
    b = directory._people_for_state(st, directory.roles_table())
    assert a == b


def test_every_template_variant_is_labelled_demo():
    for tid, t in config.templates_cfg()["templates"].items():
        for ch in ("sms", "whatsapp", "email"):
            if ch in t:
                assert "DEMO" in t[ch], (tid, ch)
