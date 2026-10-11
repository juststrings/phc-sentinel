"""Simulated field responders. SYNTHETIC: they stand in for Officers-in-Charge and LGA officers so the loop can
be demonstrated. Like the simulator, they read the simulated truth (sim_truth_facility); the engines never do.

A reply reports truth with small reporting noise, after a delay drawn from the person's responsiveness; some
people never reply; a few replies are messy or unparseable. Every draw is seeded by the message id, so a
reset + seed-demo replays identically.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
from sqlalchemy import text

from ..config import actions_cfg

MESSY = [
    lambda f: " ".join(f"{k.lower()}{v}" for k, v in f),                 # act12 rdt0 fridge1
    lambda f: ", ".join(f"{k.title()}: {v}" for k, v in f),              # Act: 12, Rdt: 0
    lambda f: "pls " + " ".join(f"{k} {v}" for k, v in f) + " thanks",
    lambda f: " ".join(f"{k.replace('ACT', 'AKT').replace('RDT', 'RTD')} {v}" for k, v in f),
]
UNPARSEABLE = ["pls call me", "we are trying our best", "ok noted", "who is this", "network bad will send later"]


def _rng(message_id: str, salt: int = 0) -> np.random.Generator:
    return np.random.default_rng(int("".join(ch for ch in message_id if ch.isdigit()) or "0") * 7919 + salt)


def truth_stock(conn, facility_id: str, today: date, truth_end: date) -> dict:
    t = conn.execute(text("SELECT * FROM sim_truth_facility WHERE facility_id = :f"), {"f": facility_id}).mappings().first()
    if t is None:
        return {}
    days = max(0, (today - truth_end).days)
    rec = conn.execute(text("""SELECT commodity_code, sum(qty_requested) q FROM resupply_request
                               WHERE facility_id = :f AND status = 'delivered' AND delivered_at <= :d GROUP BY 1"""),
                       {"f": facility_id, "d": today}).mappings().all()
    got = {r["commodity_code"]: float(r["q"]) for r in rec}
    out = {}
    for item in ("act", "rdt"):
        c, d = t.get(f"{item}_closing"), t.get(f"{item}_daily")
        if c is None or c != c:
            continue
        out[item.upper()] = max(0.0, float(c) - float(d or 0) * days + got.get(item.upper(), 0.0))
    out["FRIDGE"] = int(t["refrigerator_functional"]) if t["refrigerator_functional"] is not None else 1
    out["PENTA"] = max(0.0, float(t["vaccine_stock_balance"] or 0) + got.get("PENTA", 0.0))
    out["silenced"] = bool(t["silenced"])
    return out


def plan_reply(conn, msg: dict, person: dict, case: dict | None, today: date) -> tuple[date | None, str | None]:
    """When (if ever) the recipient replies, and what they say."""
    sim = actions_cfg()["simulation"]
    expects = [e for e in (msg.get("expects") or "").split(",") if e]
    if not expects:
        return None, None
    script = (case or {}).get("demo_script") or {}
    if isinstance(script, str):
        import json
        script = json.loads(script)
    if "reply" in script and msg.get("step_id") == script.get("reply_to_step", msg.get("step_id")):
        return today + timedelta(days=int(script.get("reply_delay", 1))), script["reply"]
    if script.get("no_reply"):
        return None, None
    rng = _rng(msg["message_id"])
    resp = float(person.get("responsiveness") or 0)
    if person.get("never_replies") or rng.random() > 0.30 + 0.65 * resp:
        return None, None
    delay = int(min(sim["reply_delay_days"]["max"], rng.exponential(sim["reply_delay_days"]["mean"] * (1.6 - resp))))
    when = today + timedelta(days=max(0, delay))
    if rng.random() < sim["unparseable_rate"]:
        return when, UNPARSEABLE[int(rng.integers(len(UNPARSEABLE)))]
    fid = msg.get("facility_id") or (case or {}).get("facility_id")
    truth = truth_stock(conn, fid, when, _truth_end(conn)) if fid else {}
    if "REPORT" in expects:
        if truth.get("silenced") and rng.random() > sim["report_recovery_given_silenced"]:
            return None, None
        return when, "REPORT SENT" if rng.random() > sim["typo_rate"] else "report sent pls"
    noise = sim["reply_noise"]
    fields = []
    for k in expects:
        if k in ("ACT", "RDT", "PENTA") and k in truth:
            v = truth[k] * (1 + rng.uniform(-noise, noise))
            fields.append((k, int(round(max(0.0, v)))))
        elif k == "FRIDGE":
            fields.append(("FRIDGE", truth.get("FRIDGE", 1)))
        elif k == "RECEIVED":
            return None, None            # receipt replies come from resupply delivery, not from the check message
    if not fields:
        return None, None
    if rng.random() < sim["typo_rate"]:
        return when, MESSY[int(rng.integers(len(MESSY)))](fields)
    return when, " ".join(f"{k} {v}" for k, v in fields)


def _truth_end(conn) -> date:
    p = conn.execute(text("SELECT max(truth_period) FROM sim_truth_facility")).scalar()
    y, m = int(p[:4]), int(p[4:]) if len(p) == 6 else int(p[5:7])
    import calendar
    return date(y, m, calendar.monthrange(y, m)[1])


def acknowledges(case_id: str, person: dict, day_index: int) -> bool:
    """Does the simulated owner acknowledge an open case today?"""
    sim = actions_cfg()["simulation"]
    rng = np.random.default_rng(int(case_id.removeprefix("C")) * 31 + day_index)
    return rng.random() < sim["ack_probability_per_day"] * float(person.get("responsiveness") or 0)


def delivery_fails(message_id: str) -> bool:
    return _rng(message_id, 3).random() < actions_cfg()["simulation"]["delivery_failure_rate"]
