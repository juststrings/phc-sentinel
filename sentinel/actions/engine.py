"""The simulated clock. `tick(conn)` advances one day and, in a fixed order:

  1. bundles yesterday's routine notifications into one digest draft per person (P1 items are immediate)
  2. delivers approved messages through SimulatedProvider, at most N per person per day; a delivered
     step message moves its case on (e.g. to awaiting_response) and plans the recipient's simulated reply
  3. receives simulated replies that are due, parses them and applies them (verification, live layer,
     playbook branch)
  4. delivers approved resupply on its lead time and records the facility's RECEIVED reply
  5. ingests reports promised by REPORT SENT replies (simulated, after a lag)
  6. lets simulated owners acknowledge cases (by responsiveness)
  7. drafts due reminders for unanswered requests
  8. escalates cases with no activity within the SLA of their ladder step (one step per breach)
  9. expires field verifications older than max_age_days from the live layer

Every action by a simulated person is written with synthetic_actor = true. Nothing is approved by the
simulation: approvals stay human.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import date, timedelta

from sqlalchemy import text

from ..config import actions_cfg
from . import service as svc, simulate as sim


def _set_clock(conn, d: date) -> None:
    conn.execute(text("UPDATE sim_clock SET sim_date = :d WHERE id = 1"), {"d": d})


def tick(conn) -> dict:
    cfg = actions_cfg()
    today = svc.clock(conn) + timedelta(days=1)
    _set_clock(conn, today)
    start = conn.execute(text("SELECT started FROM sim_clock")).scalar()
    day_index = (today - start).days
    ppl = svc.people(conn)
    stats: Counter = Counter()

    # 1. Digests of routine notifications (one draft per person per day), in bulk.
    pend = svc.rows(conn, """SELECT to_person_id, state_code, lga_id, array_agg(message_id) ids, count(*) n
                             FROM message WHERE status = 'digest_pending' AND created_at < :t GROUP BY 1, 2, 3""", t=today)
    if pend:
        dids = svc.next_ids(conn, "digest_seq", len(pend))
        mids = svc.next_ids(conn, "message_seq", len(pend))
        new, links = [], []
        for p, did, mid in zip(pend, dids, mids):
            person = ppl.get(p["to_person_id"])
            body, ch = svc.tpl.render("T_DIGEST", person["preferred_channel"], {"count": p["n"]})
            new.append({"message_id": f"M{mid}", "case_id": None, "to_person_id": p["to_person_id"], "state_code": p["state_code"],
                        "lga_id": p["lga_id"], "channel": ch, "template_id": "T_DIGEST", "kind": "digest", "priority": "P3",
                        "body": body, "chars": len(body), "status": "draft", "created_at": today, "digest_id": f"D{did}",
                        "expects": "", "synthetic": True})
            links += [{"d": f"D{did}", "m": i} for i in p["ids"]]
        svc._insert_rows(conn, "message", new)
        conn.execute(text("UPDATE message SET status = 'bundled', digest_id = :d WHERE message_id = :m"), links)
        stats["digests_drafted"] += len(new)

    # 2. Deliver approved messages (simulated), with a per-person daily cap.
    prov = svc.provider()
    cap = cfg["messaging"]["max_per_person_per_day"]
    due = svc.rows(conn, """SELECT m.*, c.facility_id, c.status AS case_status, c.demo_script, c.case_ref
                            FROM message m LEFT JOIN case_file c USING (case_id)
                            WHERE m.status = 'approved' AND m.scheduled_for <= :t
                            ORDER BY m.priority, m.approved_at, m.message_id""", t=today)
    sent_today: Counter = Counter()
    for m in due:
        if sent_today[m["to_person_id"]] >= cap:
            conn.execute(text("UPDATE message SET scheduled_for = :n WHERE message_id = :m"),
                         {"n": today + timedelta(days=1), "m": m["message_id"]})
            stats["deferred_rate_limit"] += 1
            continue
        sent_today[m["to_person_id"]] += 1
        res = prov.send(m, today, sim.delivery_fails(m["message_id"]))
        conn.execute(text("UPDATE message SET status = :s, sent_at = :a, delivered_at = :d WHERE message_id = :m"),
                     {"s": res["status"], "a": res["sent_at"], "d": res["delivered_at"], "m": m["message_id"]})
        stats[res["status"]] += 1
        if not m["case_id"]:
            continue
        case = svc.get_case(conn, m["case_id"])
        svc.event(conn, case["case_id"], today, None, "message_" + res["status"].replace("_simulated", ""),
                  payload={"message_id": m["message_id"], "to": m["to_person_id"], "template": m["template_id"]},
                  synthetic=True)
        if res["status"] != "delivered_simulated" or case["status"] in svc.TERMINAL:
            continue
        book = svc.playbook(case["playbook_id"])
        step = book["steps"][case["current_step"]] if case["current_step"] < len(book["steps"]) else None
        if m["kind"] == "step" and step and step["id"] == m["step_id"]:
            if step.get("then_status") and case["status"] != step["then_status"]:
                case = svc.set_status(conn, case, step["then_status"], today, None, True)
            nxt = case["current_step"] + 1
            if step["kind"] == "message" and nxt < len(book["steps"]) and book["steps"][nxt]["kind"] == "await":
                conn.execute(text("UPDATE case_file SET current_step = :i WHERE case_id = :c"), {"i": nxt, "c": case["case_id"]})
        when, reply = sim.plan_reply(conn, {**m, "facility_id": case.get("facility_id")}, ppl.get(m["to_person_id"]), case, today)
        if when is not None:
            conn.execute(text("UPDATE message SET planned_reply_at = :w, planned_reply_text = :r WHERE message_id = :m"),
                         {"w": when, "r": reply, "m": m["message_id"]})

    # 3. Simulated replies that are due.
    for m in svc.rows(conn, """SELECT * FROM message WHERE planned_reply_at <= :t AND status IN ('delivered_simulated')
                               ORDER BY planned_reply_at, message_id""", t=today):
        svc.record_reply(conn, m, m["to_person_id"], m["planned_reply_text"], today, m["case_id"], synthetic=True)
        conn.execute(text("UPDATE message SET planned_reply_at = NULL WHERE message_id = :m"), {"m": m["message_id"]})
        stats["replies"] += 1

    # 4. Resupply arrives on its lead time; the OIC confirms receipt (simulated).
    for r in svc.rows(conn, """SELECT * FROM resupply_request WHERE status = 'approved' AND expected_delivery <= :t
                               ORDER BY request_id""", t=today):
        conn.execute(text("UPDATE resupply_request SET status = 'delivered', delivered_at = :t WHERE request_id = :r"),
                     {"t": today, "r": r["request_id"]})
        stats["resupply_delivered"] += 1
        if not r["case_id"]:
            continue
        case = svc.get_case(conn, r["case_id"])
        svc.event(conn, case["case_id"], today, None, "resupply_delivered",
                  payload={"request_id": r["request_id"], "commodity": r["commodity_code"], "qty": r["qty_requested"]},
                  synthetic=True)
        others = svc.row(conn, """SELECT count(*) n FROM resupply_request WHERE case_id = :c
                                  AND status IN ('approved', 'pending_approval')""", c=case["case_id"])["n"]
        if others == 0 and case["status"] not in svc.TERMINAL:
            oic = ppl.find("fac_oic", case["state_code"], case.get("lga_id"), case.get("facility_id")) or case["owner_person_id"]
            items = svc.rows(conn, "SELECT commodity_code, qty_requested FROM resupply_request WHERE case_id = :c AND status = 'delivered'",
                             c=case["case_id"])
            raw = "RECEIVED " + " ".join(f"{i['commodity_code']} {int(i['qty_requested'])}" for i in items)
            msg = svc.row(conn, """SELECT * FROM message WHERE case_id = :c AND template_id = 'T_RECEIPT_CHECK'
                                   ORDER BY created_at DESC LIMIT 1""", c=case["case_id"])
            svc.record_reply(conn, msg, oic, raw, today, case["case_id"], synthetic=True)
            stats["receipts"] += 1

    # 5. Reports promised by REPORT SENT arrive (simulated ingestion; the live layer waits for the next assessment).
    for c in svc.rows(conn, f"SELECT * FROM case_file WHERE report_ingest_due <= :t AND {svc.OPEN_SQL}", t=today):
        svc.event(conn, c["case_id"], today, None, "report_ingested_simulated",
                  payload={"note": "Missing report received; confidence recovers at the next monthly assessment"},
                  synthetic=True)
        conn.execute(text("UPDATE case_file SET report_ingest_due = NULL WHERE case_id = :c"), {"c": c["case_id"]})
        svc.resolve(conn, c["case_id"], None, "reports_recovered", "Simulated report ingestion", synthetic=True)
        stats["reports_ingested"] += 1

    # 6. Simulated acknowledgements, in bulk.
    acks = []
    for c in svc.rows(conn, f"""SELECT case_id, status, owner_person_id, escalated_to_person_id, demo_script FROM case_file
                               WHERE acknowledged_at IS NULL AND {svc.OPEN_SQL}"""):
        script = c["demo_script"] or {}
        if isinstance(script, str):
            script = json.loads(script)
        if script.get("no_ack"):
            continue
        pid = c["escalated_to_person_id"] or c["owner_person_id"]
        if pid and sim.acknowledges(c["case_id"], ppl.get(pid), day_index):
            acks.append({"c": c["case_id"], "t": today, "p": pid, "s": c["status"]})
    if acks:
        conn.execute(text("""UPDATE case_file SET acknowledged_at = :t, last_activity_at = :t,
                             status = CASE WHEN status = 'open' THEN 'acknowledged' ELSE status END WHERE case_id = :c"""), acks)
        conn.execute(text("""INSERT INTO case_event (case_id, at, actor_person_id, actor, event_type, from_status, to_status, payload, synthetic_actor)
                             VALUES (:c, :t, :p, :p, 'acknowledged', :s, CASE WHEN :s = 'open' THEN 'acknowledged' ELSE :s END,
                                     CAST('{}' AS jsonb), true)"""), acks)
        stats["acknowledged_simulated"] += len(acks)

    # 7. Reminders for unanswered requests on await steps.
    for c in svc.rows(conn, f"SELECT * FROM case_file WHERE status = 'awaiting_response' AND {svc.OPEN_SQL}"):
        book = svc.playbook(c["playbook_id"])
        step = book["steps"][c["current_step"]] if c["current_step"] < len(book["steps"]) else None
        if not step or step["kind"] != "await" or not step.get("reminder_template"):
            continue
        last = svc.row(conn, """SELECT max(sent_at) s, bool_or(status = 'replied') replied,
                                       count(*) FILTER (WHERE kind = 'reminder') reminders
                                FROM message WHERE case_id = :c AND kind IN ('step', 'reminder')""", c=c["case_id"])
        if last["s"] is None or last["replied"] or last["reminders"] >= 1:
            continue
        if (today - last["s"]).days >= int(step["reminder_days"]):
            prev = svc.row(conn, """SELECT to_person_id FROM message WHERE case_id = :c AND kind = 'step' ORDER BY created_at DESC LIMIT 1""",
                           c=c["case_id"])
            if prev:
                mid = svc.next_ids(conn, "message_seq")[0]
                rec = {"facility": (c["evidence_snapshot"] or {}).get("facility"), "lga": (c["evidence_snapshot"] or {}).get("lga")}
                m = svc.message_row(c, step["reminder_template"], prev["to_person_id"], ppl, "reminder", today, mid,
                                    svc.template_ctx(c, rec), step["id"])
                svc._insert_rows(conn, "message", [m])
                svc.event(conn, c["case_id"], today, None, "reminder_drafted", payload={"message_id": m["message_id"]})
                stats["reminders_drafted"] += 1

    # 8. Escalation: one ladder step per SLA breach, in bulk.
    ups, evs, msgs = [], [], []
    cands = svc.rows(conn, f"""SELECT * FROM case_file WHERE {svc.OPEN_SQL} AND escalation_ladder IS NOT NULL
                              AND last_activity_at <= :t""", t=today - timedelta(days=1))
    for c in cands:
        ladder = cfg["escalation"][c["escalation_ladder"]]
        lvl = c["escalation_level"]
        if lvl >= len(ladder) - 1 or (today - c["last_activity_at"]).days < int(ladder[lvl]["sla_days"]):
            continue
        # Not acknowledged within the SLA escalates; once acknowledged, only an overdue AND idle case escalates (D27).
        if c["acknowledged_at"] is not None and today <= c["due_at"]:
            continue
        nxt = ladder[lvl + 1]
        pid = ppl.find(nxt["role"], c["state_code"], c.get("lga_id"), c.get("facility_id"))
        ups.append({"l": lvl + 1, "r": nxt["role"], "p": pid, "t": today, "c": c["case_id"]})
        evs.append({"c": c["case_id"], "t": today, "j": json.dumps({"level": lvl + 1, "to_role": nxt["role"], "to_person": pid,
                    "reason": f"No action within {ladder[lvl]['sla_days']} days at {ladder[lvl]['role']}"})})
        if pid:
            snap = c["evidence_snapshot"] or {}
            msgs.append((c, pid, {"facility": snap.get("facility") or snap.get("lga"), "lga": snap.get("lga")}))
    if ups:
        conn.execute(text("""UPDATE case_file SET escalation_level = :l, escalated_to_role = :r, escalated_to_person_id = :p,
                             last_activity_at = :t WHERE case_id = :c"""), ups)
        conn.execute(text("""INSERT INTO case_event (case_id, at, actor, event_type, payload, synthetic_actor)
                             VALUES (:c, :t, 'system', 'escalated', CAST(:j AS jsonb), false)"""), evs)
        mids = svc.next_ids(conn, "message_seq", len(msgs))
        svc._insert_rows(conn, "message", [svc.message_row(c, "T_ESCALATION", pid, ppl, "escalation", today, mid,
                                                           svc.template_ctx(c, rec)) for (c, pid, rec), mid in zip(msgs, mids)])
        stats["escalated"] += len(ups)

    # 9. Expire stale verifications from the live layer.
    max_age = cfg["verification"]["max_age_days"]
    exp = [r["facility_id"] for r in svc.rows(conn, """SELECT facility_id FROM mart_facility_live
                                                        WHERE field_verified AND verified_at < :d""",
                                               d=today - timedelta(days=max_age))]
    if exp:
        svc.refresh_live(conn, exp, today)
        stats["verifications_expired"] += len(exp)

    return {"sim_date": str(today), **dict(stats)}
