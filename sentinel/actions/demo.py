"""Clean start (`reset`), the simulated truth the responders read (`load_truth`), and the curated demo
scenario (`seed_demo`). `reset` opens a case for every queued facility of the latest analysis month using
the same builders as single-case opening, then bulk-loads them.
"""
from __future__ import annotations

import json
import time
from datetime import date

import numpy as np
import pandas as pd
from sqlalchemy import text

from ..config import ACTIONS_DIR, StatePaths, actions_cfg, states
from ..db import copy_df
from . import records, rules as rules_mod, service as svc, store


def load_truth(conn) -> int:
    """sim_truth_facility: what the simulator knows actually happened at each facility in the latest month
    (closing stock, daily demand, fridge, Penta balance, silence). Read ONLY by the simulated responders,
    exactly as the simulator reads its own truth; the engines never read it. SYNTHETIC."""
    parts = []
    for st in states():
        ev = StatePaths(st["code"]).eval
        tm = pd.read_parquet(ev / "truth_monthly.parquet")
        ts = pd.read_parquet(ev / "truth_stock.parquet")
        last = tm["period"].max()
        tm, ts = tm[tm["period"] == last], ts[ts["period"] == last]
        ts = ts.assign(item=ts["commodity_code"].map({"ACT_AL_ADULT": "ACT", "ACT_AL_CHILD": "ACT", "RDT_MAL": "RDT"}))
        g = ts.groupby(["facility_id", "item"]).agg(closing=("closing", "sum"), demand=("demand", "sum"),
                                                     days=("days_in_month", "first")).reset_index()
        g["daily"] = g["demand"] / g["days"]
        w = g.pivot(index="facility_id", columns="item", values=["closing", "daily"])
        w.columns = [f"{b.lower()}_{a}" for a, b in w.columns]
        t = tm.set_index("facility_id")[["refrigerator_functional", "vaccine_stock_balance", "silenced", "penta1", "penta3"]]
        df = t.join(w, how="left").reset_index()
        df.insert(1, "state_code", st["code"])
        df["truth_period"] = last
        parts.append(df)
    truth = pd.concat(parts, ignore_index=True)
    copy_df(conn, truth, "sim_truth_facility")
    conn.execute(text("ALTER TABLE sim_truth_facility ADD PRIMARY KEY (facility_id)"))
    return len(truth)


def load_directory_and_truth(conn) -> None:
    from .directory import load
    roles, people = load()
    store.load_directory(conn, roles, people)
    n = load_truth(conn)
    print(f"Loaded {len(people):,} synthetic people and simulated truth for {n:,} facilities")


DEMO_STATES = ["bauchi", "kano"]


def _pick(conn, state: str, lga_id: str | None) -> dict:
    """Choose one case per scripted role in a single LGA, so one LGA PHC Coordinator persona sees the whole loop."""
    lga_clause = "AND c.lga_id = :l" if lga_id else ""
    def first(sql_extra: str):
        return svc.row(conn, f"""SELECT c.* FROM case_file c WHERE c.state_code = :s {lga_clause} AND c.status = 'open' {sql_extra}
                                 ORDER BY c.case_id LIMIT 1""", s=state, l=lga_id)
    return {
        # Verify then act; the OIC's reply confirms a shortage
        "shortage": first("AND c.rule_id = 'R04_verify_then_act' AND c.facility_id IS NOT NULL"),
        # Do not assume safe ONLY because the NHLMIS report is overdue; the reply confirms adequate stock
        "adequate": first("""AND c.rule_id = 'R06_stale_nhlmis' AND NOT EXISTS (
                               SELECT 1 FROM fact_quality_flags q WHERE q.facility_id = c.facility_id AND q.analysis_month = c.baseline_month
                               AND q.severity = 'severe' AND q.rule_id <> 'FRESH_NHLMIS_STALE')
                             AND EXISTS (SELECT 1 FROM mart_commodity_month m WHERE m.facility_id = c.facility_id
                               AND m.analysis_month = c.baseline_month AND m.amc > 0)"""),
        # Refrigerator failure
        "fridge": first("""AND c.rule_id = 'R03_fridge_down' AND EXISTS (SELECT 1 FROM fact_dhis2_monthly d
                             WHERE d.facility_id = c.facility_id AND d.period = replace(c.baseline_month, '-', '')
                             AND COALESCE(d.vaccine_stockout_flag, 0) = 0)
                           AND EXISTS (SELECT 1 FROM mart_facility_month fm WHERE fm.facility_id = c.facility_id
                             AND fm.analysis_month = c.baseline_month AND fm.top_domain = 'vaccine_cold_chain'
                             AND COALESCE(fm.sev_malaria_commodity, 'NORMAL') NOT IN ('HIGH', 'CRITICAL'))"""),
        # Nobody acts: escalates up the commodity ladder to the State LMCU Coordinator
        "escalate": first("AND c.rule_id = 'R01_act_now_commodity'"),
    }


def _demo_lga(conn, state: str) -> str | None:
    """The LGA in the state that has all four scripted case types (most cases first)."""
    for r in svc.rows(conn, """SELECT lga_id, count(*) n FROM case_file WHERE state_code = :s AND lga_id IS NOT NULL
                               GROUP BY lga_id ORDER BY n DESC, lga_id""", s=state):
        if all(_pick(conn, state, r["lga_id"]).values()):
            return r["lga_id"]
    return None


def seed_demo(conn) -> dict:
    """Curated scenario so the stage loop plays out identically after every reset:
    shortage confirmed (Verify then act), adequate stock confirmed (Do not assume safe), fridge failure, and an
    unacknowledged commodity case that escalates to the State LMCU Coordinator. SYNTHETIC."""
    out = {}
    for code in DEMO_STATES:
        lga = _demo_lga(conn, code)
        picks = _pick(conn, code, lga)
        scripts = {}
        if picks["shortage"]:
            scripts[picks["shortage"]["case_id"]] = {"reply": "ACT 12 RDT 0 FRIDGE 1", "reply_delay": 1, "no_ack": False}
        if picks["adequate"]:
            c = picks["adequate"]
            amc = svc.amc_for(conn, c["facility_id"], c["baseline_month"])
            act = int(round(3.0 * (amc.get("ACT") or 40)))
            rdt = int(round(3.0 * (amc.get("RDT") or 100)))
            scripts[c["case_id"]] = {"reply": f"ACT {act} RDT {rdt} FRIDGE 1", "reply_delay": 1}
        if picks["fridge"]:
            scripts[picks["fridge"]["case_id"]] = {"reply": "FRIDGE 1", "reply_delay": 3}
        if picks["escalate"]:
            scripts[picks["escalate"]["case_id"]] = {"no_ack": True, "no_reply": True}
        for cid, sc in scripts.items():
            conn.execute(text("UPDATE case_file SET demo = true, demo_script = CAST(:j AS jsonb) WHERE case_id = :c"),
                         {"j": json.dumps(sc), "c": cid})
        out[code] = {"lga_id": lga, "lga": svc.row(conn, "SELECT lga FROM dim_lga WHERE lga_id = :l", l=lga)["lga"] if lga else None,
                     **{k: (v["case_id"] if v else None) for k, v in picks.items()}}
    (ACTIONS_DIR / "demo_scenario.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def reset(conn, quiet: bool = False, seed: bool = True) -> dict:
    """Clean start for the latest month; with seed (the default) the curated demo scenario is marked too."""
    t0 = time.time()
    cfg = actions_cfg()
    month = records.latest_month(conn)
    store.recreate(conn)
    today = date.fromisoformat(cfg["simulation"]["clock_start"])
    conn.execute(text("INSERT INTO sim_clock (id, sim_date, started, baseline_month) VALUES (1, :d, :d, :m)"),
                 {"d": today, "m": month})
    svc._people_cached.cache_clear()
    n_live = svc.build_live(conn, month)
    ppl = svc.People(pd.read_sql(text("SELECT * FROM dim_person"), conn))
    order = {s["code"]: i for i, s in enumerate(states())}
    prio_order = {p: i for i, p in enumerate(cfg["priorities"])}

    fac = records.facility_records(conn, month)
    fac["_month"] = month
    fired, missing = rules_mod.assign(fac, "facility")
    fired = svc.priorities_with_modifiers(fac, fired, "facility")
    fired = fired.assign(_s=fired["rec"].map(fac["state_code"]).map(order), _p=fired["priority"].map(prio_order),
                         _r=fired["rec"].map(fac["rank_state"]), _f=fired["rec"].map(fac["facility_id"]))
    fired = fired.sort_values(["_s", "_p", "_r", "_f", "rule_id"]).reset_index(drop=True)

    lga = records.lga_records(conn, month)
    lga["_month"] = month
    lfired, _ = rules_mod.assign(lga, "lga")
    lfired = svc.priorities_with_modifiers(lga, lfired, "lga")

    st = records.state_records(conn, month)
    suggest = [r for r in rules_mod.rules() if r["level"] == "state" and r["mode"] == "suggest"]
    sug_rows = []
    for r in suggest:
        m = rules_mod.mask(st, r["when"])
        for _, s in st[m].iterrows():
            sug_rows.append({"state_code": s["state_code"], "rule_id": r["id"],
                             "reason": f"State status {s['status'].replace('_', ' ')}", "baseline_month": month})

    rl = {r["id"]: r for r in rules_mod.rules()}
    need_basis = fac.loc[fired.loc[fired["rule_id"].map(lambda x: bool(rl[x].get("draft_resupply"))), "rec"], "facility_id"].tolist()
    basis = records.resupply_basis(conn, month, need_basis) if need_basis else pd.DataFrame()

    cases, events, msgs, reqs = [], [], [], []
    seq, mid, rq = [1001], [1], [1]

    def ids(counter, n):
        out = list(range(counter[0], counter[0] + n))
        counter[0] += n
        return out

    def add(rule, rec, prio, notes):
        case = svc.build_case(rule, rec, ids(seq, 1)[0], today, ppl, prio, list(notes))
        cases.append(case)
        events.append({"case_id": case["case_id"], "at": today, "actor_person_id": None, "actor": "system",
                       "event_type": "opened", "from_status": None, "to_status": "open",
                       "payload": {"rule_id": rule["id"], "priority": prio, "notes": list(notes), "manual": False},
                       "synthetic_actor": False})
        m, _, _ = svc.step_outputs(case, 0, rec, ppl, today, ids(mid, 4))
        msgs.extend(m)
        msgs.extend(svc.notice_rows(case, rule, rec, ppl, today, ids(mid, 6)))
        if rule.get("draft_resupply"):
            reqs.extend(svc.resupply_rows(case, basis, today, ids(rq, 3), status="draft"))

    for r in fired.itertuples():
        add(rl[r.rule_id], fac.loc[r.rec].to_dict(), r.priority, r.notes)
    for r in lfired.itertuples():
        rec = lga.loc[r.rec].to_dict()
        rec["facility"] = rec["lga"] + " LGA"
        add(rl[r.rule_id], rec, r.priority, r.notes)

    copy_df(conn, pd.DataFrame(cases), "case_file", append=True)
    copy_df(conn, pd.DataFrame(events), "case_event", append=True)
    if msgs:
        copy_df(conn, pd.DataFrame(msgs), "message", append=True)
    if reqs:
        copy_df(conn, pd.DataFrame(reqs), "resupply_request", append=True)
    if sug_rows:
        copy_df(conn, pd.DataFrame(sug_rows), "action_suggestion", append=True)
    conn.execute(text("SELECT setval('case_seq', :a), setval('message_seq', :b), setval('resupply_seq', :c)"),
                 {"a": seq[0], "b": mid[0], "c": rq[0]})
    summary = {
        "sim_date": str(today), "baseline_month": month, "live_rows": n_live, "cases": len(cases),
        "by_rule": pd.Series([c["rule_id"] for c in cases]).value_counts().to_dict(),
        "by_priority": pd.Series([c["priority"] for c in cases]).value_counts().to_dict(),
        "messages_draft": sum(m["status"] == "draft" for m in msgs),
        "notices_digest_pending": sum(m["status"] == "digest_pending" for m in msgs),
        "resupply_drafts": len(reqs), "state_suggestions": len(sug_rows),
        "fields_not_available": sorted(missing),
    }
    if seed:
        summary["demo"] = seed_demo(conn)
    summary["seconds"] = round(time.time() - t0, 1)
    ACTIONS_DIR.mkdir(parents=True, exist_ok=True)
    (ACTIONS_DIR / "reset_summary.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    if not quiet:
        print("Action layer reset:", json.dumps(summary, default=str))
    return summary
