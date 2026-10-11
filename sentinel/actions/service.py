"""Action-layer service: the ONE code path for every change to a case, message, reply, verification or
resupply request. The API (a person clicking) and the simulated clock (synthetic actors) both call these
functions, and every change writes a case_event. Nothing here touches the monthly marts.

All functions take an open SQLAlchemy connection inside a transaction (`with engine().begin() as conn`).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache

import pandas as pd
from sqlalchemy import text

from ..config import actions_cfg, settings, state as state_cfg
from . import live as live_mod
from . import replies, rules as rules_mod, templates as tpl

TERMINAL = set(actions_cfg()["terminal"])
OPEN_SQL = "status NOT IN ('resolved','closed_no_action','closed_duplicate')"


class ActionError(ValueError):
    """A request the action layer refuses (bad transition, missing approval, ...). The API maps it to 4xx."""
    def __init__(self, msg: str, code: int = 409):
        super().__init__(msg)
        self.code = code


# ---- small helpers ---------------------------------------------------------------------------
def cfg() -> dict:
    return actions_cfg()


def rows(conn, sql: str, **p) -> list[dict]:
    return [dict(r._mapping) for r in conn.execute(text(sql), p)]


def row(conn, sql: str, **p) -> dict | None:
    r = rows(conn, sql, **p)
    return r[0] if r else None


def clock(conn) -> date:
    r = row(conn, "SELECT sim_date FROM sim_clock WHERE id = 1")
    if r is None:
        raise ActionError("simulation clock not initialised: run `python -m sentinel actions reset`", 503)
    return r["sim_date"]


def baseline_month(conn) -> str:
    return row(conn, "SELECT baseline_month FROM sim_clock WHERE id = 1")["baseline_month"]


def next_ids(conn, seq: str, n: int = 1) -> list[int]:
    if n <= 0:
        return []
    return [r[0] for r in conn.execute(text(f"SELECT nextval('{seq}') FROM generate_series(1, :n)"), {"n": n})]


def fmt_day(d: date) -> str:
    return f"{d.day} {d:%b}"


def month_label(m: str) -> str:
    y, mo = m.split("-")
    return pd.Timestamp(int(y), int(mo), 1).strftime("%b %Y")


# ---- people ------------------------------------------------------------------------------------
@dataclass
class People:
    df: pd.DataFrame

    def __post_init__(self):
        d = self.df
        self.by_id = d.set_index("person_id")
        self.fac = {(r.facility_id, r.role_code): r.person_id for r in d[d.level == "facility"].itertuples()}
        self.lga = {(r.lga_id, r.role_code): r.person_id for r in d[d.level == "lga"].itertuples()}
        self.state = {(r.state_code, r.role_code): r.person_id for r in d[d.level == "state"].itertuples()}
        self.nat = {r.role_code: r.person_id for r in d[d.level == "national"].itertuples()}

    def find(self, role: str, state_code: str | None, lga_id: str | None = None, facility_id: str | None = None) -> str | None:
        level = cfg()["roles"][role]["level"]
        if level == "facility":
            return self.fac.get((facility_id, role))
        if level == "lga":
            return self.lga.get((lga_id, role))
        if level == "state":
            return self.state.get((state_code, role))
        return self.nat.get(role)

    def get(self, pid: str) -> dict:
        if pid not in self.by_id.index:
            raise ActionError(f"unknown person {pid}", 404)
        return {"person_id": pid, **self.by_id.loc[pid].to_dict()}


@lru_cache(maxsize=1)
def _people_cached(stamp: str) -> People:
    from ..db import engine
    with engine().connect() as c:
        return People(pd.read_sql(text("SELECT * FROM dim_person"), c))


def people(conn=None) -> People:
    from ..db import engine
    with engine().connect() as c:
        stamp = str(c.execute(text("SELECT count(*) FROM dim_person")).scalar())
    return _people_cached(stamp)


# ---- events and status ---------------------------------------------------------------------------
def event(conn, case_id: str, at: date, actor: str | None, event_type: str, from_status=None, to_status=None,
          payload: dict | None = None, synthetic: bool = False) -> None:
    conn.execute(text("""INSERT INTO case_event (case_id, at, actor_person_id, actor, event_type, from_status, to_status,
                                                 payload, synthetic_actor)
                         VALUES (:c, :at, :a, :an, :t, :f, :to, CAST(:p AS jsonb), :s)"""),
                 {"c": case_id, "at": at, "a": actor, "an": actor or ("simulation" if synthetic else "system"),
                  "t": event_type, "f": from_status, "to": to_status, "p": json.dumps(payload or {}, default=str), "s": synthetic})


def get_case(conn, case_id: str) -> dict:
    c = row(conn, "SELECT * FROM case_file WHERE case_id = :c FOR UPDATE", c=case_id)
    if c is None:
        raise ActionError(f"unknown case {case_id}", 404)
    return c


def set_status(conn, case: dict, to: str, at: date, actor: str | None, synthetic=False, payload=None,
               event_type: str = "status_changed") -> dict:
    fr = case["status"]
    if to == fr:
        return case
    allowed = cfg()["transitions"].get(fr, [])
    if to not in allowed:
        raise ActionError(f"case {case['case_ref']}: cannot move from {fr} to {to}")
    extra = ", resolved_at = :at" if to in TERMINAL else ""
    conn.execute(text(f"UPDATE case_file SET status = :to, last_activity_at = :at{extra} WHERE case_id = :c"),
                 {"to": to, "at": at, "c": case["case_id"]})
    event(conn, case["case_id"], at, actor, event_type, fr, to, payload, synthetic)
    case = {**case, "status": to, "last_activity_at": at}
    return case


# ---- building cases --------------------------------------------------------------------------------
def rule_by_id(rid: str) -> dict:
    for r in rules_mod.rules():
        if r["id"] == rid:
            return r
    raise ActionError(f"unknown rule {rid}", 404)


def playbook(pid: str) -> dict:
    return cfg()["playbooks"][pid]


def evidence_snapshot(rec: dict) -> dict:
    """The facility explanation at open time, with its source dates (proposal: explain before act)."""
    expl = rec.get("explanation")
    if isinstance(expl, str):
        expl = json.loads(expl)
    keep = ["facility", "ward", "queue", "tag", "operational_risk", "data_confidence", "top_domain", "evidence_summary", "next_action",
            "nhlmis_age_days", "consecutive_missing", "analysis_month", "as_of", "report_received", "nhlmis_stale",
            "status", "pct_act_now", "pct_verification", "facilities", "verification", "lga"]
    snap = {k: (None if pd.isna(rec[k]) else rec[k]) if not isinstance(rec.get(k), (list, dict)) else rec[k]
            for k in keep if k in rec}
    if expl:
        snap["explanation"] = expl
    p1, p3 = rec.get("penta1"), rec.get("penta3")
    if p1 is not None and not pd.isna(p1):
        snap["_penta_need"] = 2 * (float(p1) + float(0 if p3 is None or pd.isna(p3) else p3))
    return json.loads(json.dumps(snap, default=str))


def unit_of(level: str, rec: dict) -> str:
    return {"facility": rec.get("facility_id"), "lga": rec.get("lga_id"), "state": rec.get("state_code")}[level]


def build_case(rule: dict, rec: dict, seq: int, today: date, ppl: People, priority: str | None = None,
               notes: list[str] | None = None, raised_by: str | None = None, demo: bool = False) -> dict:
    level = rule["level"]
    owner = ppl.find(rule["owner_role"], rec.get("state_code"), rec.get("lga_id"), rec.get("facility_id"))
    return {
        "case_id": f"C{seq}", "case_ref": f"C-{seq}", "level": level, "state_code": rec["state_code"],
        "lga_id": rec.get("lga_id"), "facility_id": rec.get("facility_id"), "unit_id": unit_of(level, rec),
        "rule_id": rule["id"], "playbook_id": rule["playbook"], "priority": priority or rule["priority"],
        "base_priority": rule["priority"], "priority_notes": notes or [], "status": "open",
        "owner_person_id": owner, "owner_role": rule["owner_role"], "raised_by_person_id": raised_by,
        "opened_at": today, "due_at": today + timedelta(days=int(rule["due_days"])), "last_activity_at": today,
        "current_step": 0, "escalation_level": 0, "escalation_ladder": rule["escalation"],
        "evidence_snapshot": evidence_snapshot(rec), "baseline_month": rec.get("analysis_month") or rec.get("_month"),
        "synthetic_actor": False, "demo": demo,
    }


def template_ctx(case: dict, rec: dict | None = None, extra: dict | None = None) -> dict:
    st = state_cfg(case["state_code"])
    snap = case.get("evidence_snapshot") or {}
    if isinstance(snap, str):
        snap = json.loads(snap)
    fac = (rec or {}).get("facility") or snap.get("facility") or ""
    lga = (rec or {}).get("lga") or snap.get("lga") or ""
    return {"facility": fac or lga or st["name"], "lga": lga, "state": st["name"].replace(" (Abuja)", ""),
            "case_ref": case["case_ref"], "due": fmt_day(case["due_at"]), "priority": case["priority"],
            "playbook": playbook(case["playbook_id"])["title"], "period": month_label(case["baseline_month"]),
            **(extra or {})}


def message_row(case: dict, tid: str, pid: str, ppl: People, kind: str, today: date, mid: int, ctx: dict,
                step_id: str | None = None) -> dict:
    p = ppl.get(pid)
    body, ch = tpl.render(tid, p["preferred_channel"], ctx)
    immediate = case["priority"] in cfg()["messaging"]["digest"]["immediate_priorities"]
    status = "digest_pending" if kind in ("notice", "escalation") and not immediate else "draft"
    return {"message_id": f"M{mid}", "case_id": case["case_id"], "to_person_id": pid, "state_code": case["state_code"],
            "lga_id": case.get("lga_id"), "channel": ch, "template_id": tid, "kind": kind, "priority": case["priority"],
            "body": body, "chars": len(body), "status": status, "created_at": today, "step_id": step_id,
            "expects": ",".join(tpl.expects(tid)), "synthetic": True}


def step_outputs(case: dict, step_idx: int, rec: dict, ppl: People, today: date, mids: list[int],
                 basis: pd.DataFrame | None = None, rq_ids: list[int] | None = None) -> tuple[list, list, str | None]:
    """What entering a playbook step produces: messages to draft, resupply requests, and a status (for
    resupply steps; message steps change status when the message is actually sent)."""
    book = playbook(case["playbook_id"])
    if step_idx >= len(book["steps"]):
        return [], [], None
    step = book["steps"][step_idx]
    msgs, reqs, status = [], [], None
    if step["kind"] in ("message", "await") and step.get("template") and step.get("to"):
        for role in step["to"]:
            pid = ppl.find(role, case["state_code"], case.get("lga_id"), case.get("facility_id"))
            if pid:
                msgs.append(message_row(case, step["template"], pid, ppl, "step", today, mids.pop(0),
                                        template_ctx(case, rec), step["id"]))
    if step["kind"] == "resupply":
        reqs = resupply_rows(case, basis, today, rq_ids or [], status="pending_approval")
        status = step.get("then_status")
    return msgs, reqs, status


def resupply_rows(case: dict, basis: pd.DataFrame | None, today: date, ids: list[int], status: str) -> list[dict]:
    """Pre-filled from NHLMIS quantity_to_order where current, else AMC x the 4-month maximum minus last stock.
    Vaccine playbooks request Penta doses: twice the month's Penta doses given (DESIGN, A24)."""
    out = []
    fid = case.get("facility_id")
    if case["playbook_id"] == "PB_VACCINE_RESUPPLY":
        snap = case.get("evidence_snapshot") or {}
        need = float(snap.get("_penta_need") or 40)
        out.append(("PENTA", max(20.0, need), "twice the month's Penta doses given"))
    else:
        b = basis[basis["facility_id"] == fid] if basis is not None and len(basis) else pd.DataFrame()
        maxm = settings()["commodity"]["max_months"]
        groups = cfg()["verification"]["commodity_map"]
        for item, codes in groups.items():
            sub = b[b["commodity_code"].isin(codes)] if len(b) else b
            if len(sub) and not sub["stale_flag"].fillna(True).all() and sub["quantity_to_order"].notna().any():
                qty, why = float(sub["quantity_to_order"].fillna(0).sum()), "NHLMIS quantity_to_order"
            elif len(sub) and sub["amc"].notna().any():
                qty = float(max(0.0, maxm * sub["amc"].fillna(0).sum() - sub["physical_stock"].fillna(0).clip(lower=0).sum()))
                why = f"AMC x {maxm} months minus last reported stock"
            else:
                continue
            out.append((item, max(qty, 1.0), why))
    rows_ = []
    for (item, qty, why) in out:
        rid = ids.pop(0) if ids else 0
        rows_.append({"request_id": f"RQ{rid}", "case_id": case["case_id"], "facility_id": fid,
                      "state_code": case["state_code"], "lga_id": case.get("lga_id"), "commodity_code": item,
                      "qty_requested": round(qty), "basis": why, "status": status, "requested_at": today,
                      "requested_by": case.get("owner_person_id"), "synthetic": True})
    return rows_


def notice_rows(case: dict, rule: dict, rec: dict, ppl: People, today: date, mids: list[int]) -> list[dict]:
    out = []
    for role in rule.get("notify_roles", []):
        pid = ppl.find(role, case["state_code"], case.get("lga_id"), case.get("facility_id"))
        if pid and pid != case.get("owner_person_id"):
            out.append(message_row(case, "T_CASE_NOTICE", pid, ppl, "notice", today, mids.pop(0), template_ctx(case, rec)))
    if case.get("owner_person_id"):
        out.append(message_row(case, "T_CASE_NOTICE", case["owner_person_id"], ppl, "notice", today, mids.pop(0),
                               template_ctx(case, rec)))
    return out


def priorities_with_modifiers(df: pd.DataFrame, fired: pd.DataFrame, level: str) -> pd.DataFrame:
    """Apply modifier rules (R11, R12) to fired open rules in the groups they name."""
    order = cfg()["priorities"]
    rl = {r["id"]: r for r in rules_mod.rules()}
    fired = fired.copy()
    fired["priority"] = fired["rule_id"].map(lambda r: rl[r]["priority"])
    fired["notes"] = [[] for _ in range(len(fired))]
    for mod, m in rules_mod.modifiers(df, level):
        hits = set(df.index[m])
        if not hits:
            continue
        for i, fr in fired.iterrows():
            if fr["rec"] in hits and rl[fr["rule_id"]].get("group") in mod.get("applies_to_groups", []):
                fired.at[i, "priority"] = rules_mod.raise_priority(fired.at[i, "priority"], mod["raise_priority"], order)
                rec = df.loc[fr["rec"]].to_dict()
                tmpl = mod.get("note", mod["description"])
                for field, alt in (mod.get("note_if_missing") or {}).items():
                    if pd.isna(rec.get(field)):
                        tmpl = alt
                try:
                    note = tmpl.format(**{k: (0 if pd.isna(v) else v) if isinstance(v, float) else v
                                                                         for k, v in rec.items()})
                except (KeyError, ValueError):
                    note = mod["description"]
                fired.at[i, "notes"] = fired.at[i, "notes"] + [f"{mod['id']}: {note}"]
    return fired


# ---- opening cases (single; used by API, replies and the clock) -----------------------------------------
def open_case(conn, rule_id: str, rec: dict, actor: str | None, today: date | None = None, priority: str | None = None,
              notes: list[str] | None = None, raised_by: str | None = None, synthetic: bool = False,
              demo: bool = False, skip_dedupe: bool = False) -> dict | None:
    """Opens one case unless an open case already exists for the same unit and playbook (dedupe), or one was
    resolved within the cool-down and the new priority is not higher."""
    today = today or clock(conn)
    rule = rule_by_id(rule_id)
    ppl = people(conn)
    unit = unit_of(rule["level"], rec)
    order = cfg()["priorities"]
    prio = priority or rule["priority"]
    if not skip_dedupe:
        dup = row(conn, f"SELECT case_id, case_ref FROM case_file WHERE unit_id = :u AND playbook_id = :p AND {OPEN_SQL}",
                  u=unit, p=rule["playbook"])
        if dup:
            return None
        cool = cfg()["dedupe"]["cooldown_days"]
        recent = row(conn, """SELECT priority FROM case_file WHERE unit_id = :u AND playbook_id = :p AND status = 'resolved'
                              AND resolved_at >= :since ORDER BY resolved_at DESC LIMIT 1""",
                     u=unit, p=rule["playbook"], since=today - timedelta(days=cool))
        if recent and order.index(prio) >= order.index(recent["priority"]):
            return None
    seq = next_ids(conn, "case_seq")[0]
    rec = {**rec, "_month": baseline_month(conn)}
    case = build_case(rule, rec, seq, today, ppl, prio, notes, raised_by, demo)
    _insert_case(conn, case)
    event(conn, case["case_id"], today, actor, "opened", None, "open",
          {"rule_id": rule_id, "priority": prio, "notes": notes or [], "manual": actor is not None and not synthetic},
          synthetic)
    _enter_step(conn, case, 0, rec, ppl, today, actor, synthetic)
    if rule.get("draft_resupply"):
        basis = _basis(conn, case)
        reqs = resupply_rows(case, basis, today, next_ids(conn, "resupply_seq", 3), status="draft")
        _insert_rows(conn, "resupply_request", reqs)
    mids = next_ids(conn, "message_seq", 6)
    _insert_rows(conn, "message", notice_rows(case, rule, rec, ppl, today, mids))
    return case


def _basis(conn, case: dict) -> pd.DataFrame:
    from .records import resupply_basis
    if not case.get("facility_id"):
        return pd.DataFrame()
    return resupply_basis(conn, case["baseline_month"], [case["facility_id"]])


def _insert_case(conn, case: dict) -> None:
    c = {**case, "priority_notes": json.dumps(case["priority_notes"]),
         "evidence_snapshot": json.dumps(case["evidence_snapshot"], default=str)}
    cols = list(c)
    conn.execute(text(f"""INSERT INTO case_file ({', '.join(cols)}) VALUES ({', '.join(':' + k for k in cols)})"""), c)


def _insert_rows(conn, table: str, rs: list[dict]) -> None:
    if not rs:
        return
    cols = list(rs[0])
    conn.execute(text(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(':' + k for k in cols)})"), rs)


def _enter_step(conn, case: dict, idx: int, rec: dict | None, ppl: People, today: date, actor, synthetic) -> dict:
    book = playbook(case["playbook_id"])
    if idx >= len(book["steps"]):
        return case
    mids = next_ids(conn, "message_seq", 4)
    basis = _basis(conn, case) if book["steps"][idx]["kind"] == "resupply" else None
    rqids = next_ids(conn, "resupply_seq", 3) if basis is not None else None
    if basis is not None:
        # promote a parallel draft (R04) instead of creating a second request
        drafts = rows(conn, "SELECT request_id FROM resupply_request WHERE case_id = :c AND status = 'draft'", c=case["case_id"])
        if drafts:
            conn.execute(text("UPDATE resupply_request SET status = 'pending_approval', requested_at = :t WHERE case_id = :c AND status = 'draft'"),
                         {"t": today, "c": case["case_id"]})
            msgs, reqs, st = [], [], book["steps"][idx].get("then_status")
        else:
            msgs, reqs, st = step_outputs(case, idx, rec or {}, ppl, today, mids, basis, rqids)
    else:
        msgs, reqs, st = step_outputs(case, idx, rec or {}, ppl, today, mids)
    conn.execute(text("UPDATE case_file SET current_step = :i, last_activity_at = :t WHERE case_id = :c"),
                 {"i": idx, "t": today, "c": case["case_id"]})
    case = {**case, "current_step": idx}
    if idx > 0:
        event(conn, case["case_id"], today, actor, "step_entered", payload={"step": book["steps"][idx]["id"],
              "title": book["steps"][idx]["title"]}, synthetic=synthetic)
    _insert_rows(conn, "message", msgs)
    _insert_rows(conn, "resupply_request", reqs)
    if reqs:
        event(conn, case["case_id"], today, actor, "resupply_requested",
              payload={"requests": [{k: r[k] for k in ("request_id", "commodity_code", "qty_requested", "basis")} for r in reqs]},
              synthetic=synthetic)
    if st and st != case["status"]:
        case = set_status(conn, case, st, today, actor, synthetic)
    return case


# ---- case actions (API) --------------------------------------------------------------------------------
def acknowledge(conn, case_id: str, actor: str, synthetic: bool = False) -> dict:
    today = clock(conn)
    case = get_case(conn, case_id)
    if case["status"] in TERMINAL:
        raise ActionError(f"case {case['case_ref']} is closed")
    if case["acknowledged_at"] is not None:
        return case
    conn.execute(text("UPDATE case_file SET acknowledged_at = :t, last_activity_at = :t WHERE case_id = :c"),
                 {"t": today, "c": case_id})
    if case["status"] == "open":
        case = set_status(conn, case, "acknowledged", today, actor, synthetic, event_type="acknowledged")
    else:
        event(conn, case_id, today, actor, "acknowledged", synthetic=synthetic)
    return {**case, "acknowledged_at": today}


def assign(conn, case_id: str, actor: str, person_id: str) -> dict:
    today = clock(conn)
    case = get_case(conn, case_id)
    p = people(conn).get(person_id)
    if p["state_code"] not in (case["state_code"], None):
        raise ActionError("cannot assign a case to a person in another state", 403)
    conn.execute(text("UPDATE case_file SET owner_person_id = :p, owner_role = :r, last_activity_at = :t WHERE case_id = :c"),
                 {"p": person_id, "r": p["role_code"], "t": today, "c": case_id})
    event(conn, case_id, today, actor, "assigned", payload={"from": case["owner_person_id"], "to": person_id, "role": p["role_code"]})
    return get_case(conn, case_id)


def advance(conn, case_id: str, actor: str, synthetic: bool = False) -> dict:
    today = clock(conn)
    case = get_case(conn, case_id)
    if case["status"] in TERMINAL:
        raise ActionError(f"case {case['case_ref']} is closed")
    n = len(playbook(case["playbook_id"])["steps"])
    if case["current_step"] + 1 >= n:
        raise ActionError("already at the last step; resolve the case with an outcome")
    if case["status"] in ("open", "acknowledged"):
        case = set_status(conn, case, "in_progress", today, actor, synthetic)
    rec = _rec_for(conn, case)
    return _enter_step(conn, case, case["current_step"] + 1, rec, people(conn), today, actor, synthetic)


def resolve(conn, case_id: str, actor: str | None, outcome_code: str, note: str | None = None,
            synthetic: bool = False, close_status: str = "resolved") -> dict:
    today = clock(conn)
    case = get_case(conn, case_id)
    if outcome_code not in cfg()["outcome_codes"]:
        raise ActionError(f"unknown outcome code {outcome_code}; allowed {sorted(cfg()['outcome_codes'])}", 422)
    if case["status"] in TERMINAL:
        raise ActionError(f"case {case['case_ref']} is already {case['status']}")
    conn.execute(text("UPDATE case_file SET outcome_code = :o, outcome_note = :n WHERE case_id = :c"),
                 {"o": outcome_code, "n": note, "c": case_id})
    conn.execute(text("""UPDATE message SET status = 'cancelled' WHERE case_id = :c AND status IN ('draft', 'digest_pending')"""),
                 {"c": case_id})
    conn.execute(text("""UPDATE resupply_request SET status = 'cancelled' WHERE case_id = :c AND status IN ('draft', 'pending_approval')"""),
                 {"c": case_id})
    return set_status(conn, case, close_status, today, actor, synthetic, {"outcome": outcome_code, "note": note},
                      event_type="resolved" if close_status == "resolved" else "closed")


def note(conn, case_id: str, actor: str, text_: str, kind: str = "note") -> dict:
    today = clock(conn)
    case = get_case(conn, case_id)
    if kind == "response_lead":
        conn.execute(text("UPDATE case_file SET response_lead = :v, last_activity_at = :t WHERE case_id = :c"),
                     {"v": text_, "t": today, "c": case_id})
    elif kind == "response_plan":
        conn.execute(text("UPDATE case_file SET response_plan = :v, last_activity_at = :t WHERE case_id = :c"),
                     {"v": text_, "t": today, "c": case_id})
    else:
        conn.execute(text("UPDATE case_file SET last_activity_at = :t WHERE case_id = :c"), {"t": today, "c": case_id})
    event(conn, case_id, today, actor, kind, payload={"text": text_})
    return case


def _rec_for(conn, case: dict) -> dict:
    from .records import facility_records
    if case.get("facility_id"):
        df = facility_records(conn, case["baseline_month"], [case["facility_id"]])
        if len(df):
            return df.iloc[0].to_dict()
    snap = case.get("evidence_snapshot") or {}
    return {"facility": snap.get("lga") or "", "lga": snap.get("lga") or "", "state_code": case["state_code"]}


# ---- messages -------------------------------------------------------------------------------------------
def approve_messages(conn, ids: list[str], actor: str) -> int:
    today = clock(conn)
    ms = rows(conn, "SELECT message_id, case_id, status FROM message WHERE message_id = ANY(:ids) FOR UPDATE", ids=ids)
    bad = [m["message_id"] for m in ms if m["status"] != "draft"]
    if bad:
        raise ActionError(f"only drafts can be approved; not drafts: {bad[:5]}")
    if len(ms) != len(set(ids)):
        raise ActionError("unknown message id in request", 404)
    conn.execute(text("""UPDATE message SET status = 'approved', approved_by = :a, approved_at = :t, scheduled_for = :t
                         WHERE message_id = ANY(:ids)"""), {"a": actor, "t": today, "ids": ids})
    for cid in {m["case_id"] for m in ms if m["case_id"]}:
        n = sum(1 for m in ms if m["case_id"] == cid)
        event(conn, cid, today, actor, "message_approved", payload={"count": n, "ids": [m["message_id"] for m in ms if m["case_id"] == cid]})
        conn.execute(text("UPDATE case_file SET last_activity_at = :t WHERE case_id = :c"), {"t": today, "c": cid})
    return len(ms)


def edit_message(conn, mid: str, actor: str, body: str) -> dict:
    m = row(conn, "SELECT * FROM message WHERE message_id = :m FOR UPDATE", m=mid)
    if m is None:
        raise ActionError(f"unknown message {mid}", 404)
    if m["status"] != "draft":
        raise ActionError("only drafts can be edited")
    if "DEMO" not in body:
        raise ActionError("the body must keep the 'Sentinel (DEMO)' label", 422)
    cap = cfg()["messaging"]["sms_max_chars"]
    if m["channel"] == "sms" and len(body) > cap:
        raise ActionError(f"SMS body is {len(body)} characters; the limit is {cap}", 422)
    conn.execute(text("UPDATE message SET body = :b, chars = :n WHERE message_id = :m"), {"b": body, "n": len(body), "m": mid})
    if m["case_id"]:
        event(conn, m["case_id"], clock(conn), actor, "message_edited", payload={"message_id": mid})
    return {**m, "body": body, "chars": len(body)}


def provider():
    """The configured message provider. Only `simulated` exists; anything else is refused."""
    from .providers import get_provider
    return get_provider(cfg()["messaging"]["provider"])


# ---- replies ---------------------------------------------------------------------------------------------
def record_reply(conn, message: dict | None, from_pid: str, raw: str, today: date, case_id: str | None,
                 synthetic: bool = True) -> dict:
    exp = (message or {}).get("expects")
    parsed = replies.parse(raw, exp.split(",") if exp else None)
    rid = f"R{next_ids(conn, 'response_seq')[0]}"
    st = state_of_person(conn, from_pid)
    conn.execute(text("""INSERT INTO inbound_response (response_id, message_id, case_id, from_person_id, state_code, received_at,
                                                       raw_text, parsed, parse_status, review_status, synthetic)
                         VALUES (:r, :m, :c, :p, :s, :t, :raw, CAST(:j AS jsonb), :ps, :rv, :syn)"""),
                 {"r": rid, "m": (message or {}).get("message_id"), "c": case_id, "p": from_pid, "s": st, "t": today,
                  "raw": raw, "j": json.dumps(parsed), "ps": parsed["status"],
                  "rv": "needs_review" if parsed["status"] == "unparseable" else "none", "syn": synthetic})
    if message:
        conn.execute(text("UPDATE message SET status = 'replied' WHERE message_id = :m"), {"m": message["message_id"]})
    resp = {"response_id": rid, "parsed": parsed, "case_id": case_id, "from_person_id": from_pid, "received_at": today}
    if case_id:
        event(conn, case_id, today, from_pid, "reply_received",
              payload={"response_id": rid, "raw": raw, "parse_status": parsed["status"], "fields": parsed["fields"]},
              synthetic=synthetic)
        conn.execute(text("UPDATE case_file SET last_activity_at = :t WHERE case_id = :c"), {"t": today, "c": case_id})
        if parsed["status"] == "unparseable":
            conn.execute(text("UPDATE case_file SET review_task = true WHERE case_id = :c"), {"c": case_id})
            event(conn, case_id, today, None, "reply_needs_review", payload={"response_id": rid}, synthetic=synthetic)
        else:
            apply_reply(conn, case_id, resp, from_pid, today, synthetic)
    return resp


def state_of_person(conn, pid: str) -> str:
    p = people(conn).get(pid)
    return p["state_code"] or "national"


def classify(case: dict, fields: dict, amc: dict) -> str | None:
    """Turn parsed reply fields into the playbook's reply outcome."""
    if fields.get("RECEIVED"):
        return "received"
    if fields.get("REPORT_SENT"):
        return "report_sent"
    if case["playbook_id"] == "PB_COLD_CHAIN_INSPECT" and fields.get("FRIDGE") == 1:
        return "fridge_ok"
    if "PENTA" in fields:
        return "shortage" if fields["PENTA"] <= cfg()["verification"]["penta_stockout_doses"] else "adequate"
    sev = [live_mod.commodity_severity(fields[k], amc.get(k)) for k in ("ACT", "RDT") if k in fields]
    sev = [s for s in sev if s is not None]
    if sev:
        return "shortage" if max(sev) >= live_mod.SEV["HIGH"] else "adequate"
    return None


def amc_for(conn, facility_id: str, month: str) -> dict:
    out = {}
    for item, codes in cfg()["verification"]["commodity_map"].items():
        r = row(conn, """SELECT sum(amc) a FROM mart_commodity_month WHERE facility_id = :f AND analysis_month = :m
                         AND commodity_code = ANY(:c)""", f=facility_id, m=month, c=codes)
        out[item] = float(r["a"]) if r and r["a"] is not None else None
    return out


def apply_reply(conn, case_id: str, resp: dict, from_pid: str, today: date, synthetic: bool) -> None:
    case = get_case(conn, case_id)
    if case["status"] in TERMINAL:
        return
    fields = resp["parsed"]["fields"]
    fid = case.get("facility_id")
    if fid:
        vids = next_ids(conn, "verification_seq", 6)
        vrows = []
        for item in ("ACT", "RDT", "PENTA"):
            if item in fields:
                vrows.append({"verification_id": f"V{vids.pop(0)}", "facility_id": fid, "state_code": case["state_code"],
                              "verified_at": today, "source": "sms_reply", "commodity_code": item,
                              "quantity": fields[item], "fridge_functional": None, "reports_submitted": None,
                              "by_person_id": from_pid, "case_id": case_id, "response_id": resp["response_id"], "synthetic": True})
        if "FRIDGE" in fields:
            vrows.append({"verification_id": f"V{vids.pop(0)}", "facility_id": fid, "state_code": case["state_code"],
                          "verified_at": today, "source": "sms_reply", "commodity_code": None, "quantity": None,
                          "fridge_functional": bool(fields["FRIDGE"]), "reports_submitted": None, "by_person_id": from_pid,
                          "case_id": case_id, "response_id": resp["response_id"], "synthetic": True})
        if fields.get("REPORT_SENT"):
            vrows.append({"verification_id": f"V{vids.pop(0)}", "facility_id": fid, "state_code": case["state_code"],
                          "verified_at": today, "source": "sms_reply", "commodity_code": None, "quantity": None,
                          "fridge_functional": None, "reports_submitted": True, "by_person_id": from_pid,
                          "case_id": case_id, "response_id": resp["response_id"], "synthetic": True})
        if vrows:
            _insert_rows(conn, "field_verification", vrows)
            event(conn, case_id, today, None, "field_verification", payload={"items": [
                {k: v for k, v in r.items() if k in ("commodity_code", "quantity", "fridge_functional", "reports_submitted")}
                for r in vrows]}, synthetic=synthetic)
            before = row(conn, "SELECT live_queue, live_tag FROM mart_facility_live WHERE facility_id = :f", f=fid)
            refresh_live(conn, [fid], today)
            after = row(conn, "SELECT live_queue, live_tag, live_confidence, live_risk FROM mart_facility_live WHERE facility_id = :f", f=fid)
            if before and after and (before["live_queue"], before["live_tag"]) != (after["live_queue"], after["live_tag"]):
                event(conn, case_id, today, None, "live_status_changed",
                      payload={"from": before, "to": after}, synthetic=synthetic)
        if fields.get("FRIDGE") == 0:
            rec = _rec_for(conn, case)
            opened = open_case(conn, "R03_fridge_down", rec, None, today, synthetic=synthetic)
            if opened:
                event(conn, case_id, today, None, "linked_case_opened", payload={"case_id": opened["case_id"], "rule": "R03"},
                      synthetic=synthetic)
    outcome = classify(case, fields, amc_for(conn, fid, case["baseline_month"]) if fid else {})
    action = (playbook(case["playbook_id"]).get("on_reply") or {}).get(outcome)
    if action is None:
        return
    if action.startswith("resolve_"):
        code = action.removeprefix("resolve_")
        resolve(conn, case_id, None, code, f"Resolved on reply {resp['response_id']}", synthetic=True)
    elif action == "await_ingest":
        lag = cfg()["simulation"]["report_ingest_lag_days"]
        conn.execute(text("UPDATE case_file SET report_ingest_due = :d WHERE case_id = :c"),
                     {"d": today + timedelta(days=int(lag[0])), "c": case_id})
        if case["status"] in ("open", "acknowledged", "awaiting_response"):
            set_status(conn, case, "in_progress", today, None, synthetic)
    else:
        idx = next((i for i, s in enumerate(playbook(case["playbook_id"])["steps"]) if s["id"] == action), None)
        if idx is not None and idx > case["current_step"]:
            if case["status"] in ("open", "acknowledged"):
                case = set_status(conn, case, "in_progress", today, None, synthetic)
            _enter_step(conn, case, idx, _rec_for(conn, case), people(conn), today, None, synthetic)


def review_response(conn, response_id: str, actor: str, corrected_text: str | None, dismiss: bool = False) -> dict:
    """A person resolves an unparseable reply: re-parse a corrected reading, or dismiss it."""
    today = clock(conn)
    r = row(conn, "SELECT * FROM inbound_response WHERE response_id = :r FOR UPDATE", r=response_id)
    if r is None:
        raise ActionError(f"unknown response {response_id}", 404)
    if dismiss or not corrected_text:
        conn.execute(text("UPDATE inbound_response SET review_status = 'dismissed', reviewed_by = :a WHERE response_id = :r"),
                     {"a": actor, "r": response_id})
    else:
        parsed = replies.parse(corrected_text)
        conn.execute(text("""UPDATE inbound_response SET review_status = 'reviewed', reviewed_by = :a, parsed = CAST(:j AS jsonb),
                             parse_status = :ps WHERE response_id = :r"""),
                     {"a": actor, "r": response_id, "j": json.dumps({**parsed, "corrected_from": r["raw_text"]}), "ps": parsed["status"]})
        if r["case_id"] and parsed["status"] != "unparseable":
            apply_reply(conn, r["case_id"], {"response_id": response_id, "parsed": parsed}, r["from_person_id"], today, False)
    if r["case_id"]:
        conn.execute(text("""UPDATE case_file SET review_task = EXISTS (SELECT 1 FROM inbound_response
                             WHERE case_id = :c AND review_status = 'needs_review') WHERE case_id = :c"""), {"c": r["case_id"]})
        event(conn, r["case_id"], today, actor, "reply_reviewed", payload={"response_id": response_id, "dismissed": dismiss,
                                                                           "corrected": corrected_text})
    return row(conn, "SELECT * FROM inbound_response WHERE response_id = :r", r=response_id)


# ---- resupply ---------------------------------------------------------------------------------------------
def approve_resupply(conn, request_id: str, actor: str) -> dict:
    import numpy as np
    today = clock(conn)
    r = row(conn, "SELECT * FROM resupply_request WHERE request_id = :r FOR UPDATE", r=request_id)
    if r is None:
        raise ActionError(f"unknown resupply request {request_id}", 404)
    if r["status"] not in ("pending_approval", "draft"):
        raise ActionError(f"request {request_id} is {r['status']}")
    lo, hi = cfg()["simulation"]["resupply_lead_time_days"]
    rng = np.random.default_rng(int(request_id.removeprefix("RQ")) + 7)   # deterministic lead time per request
    lead = int(rng.integers(lo, hi + 1))
    conn.execute(text("""UPDATE resupply_request SET status = 'approved', approved_by = :a, approved_at = :t,
                         expected_delivery = :d WHERE request_id = :r"""),
                 {"a": actor, "t": today, "d": today + timedelta(days=lead), "r": request_id})
    if r["case_id"]:
        event(conn, r["case_id"], today, actor, "resupply_approved",
              payload={"request_id": request_id, "commodity": r["commodity_code"], "qty": r["qty_requested"],
                       "expected_delivery": str(today + timedelta(days=lead))})
        conn.execute(text("UPDATE case_file SET last_activity_at = :t WHERE case_id = :c"), {"t": today, "c": r["case_id"]})
    return row(conn, "SELECT * FROM resupply_request WHERE request_id = :r", r=request_id)


# ---- live layer --------------------------------------------------------------------------------------------
LIVE_COLS = ["facility_id", "state_code", "lga_id", "analysis_month", "baseline_queue", "baseline_tag", "baseline_risk",
             "baseline_confidence", "live_queue", "live_tag", "live_risk", "live_confidence", "field_verified",
             "verified_at", "verification_source", "live_reasons", "changed", "live_field_driven", "nhlmis_stale"]


def build_live(conn, month: str) -> int:
    """mart_facility_live = baseline for every facility of the latest month (no verifications yet)."""
    conn.execute(text("DROP TABLE IF EXISTS mart_facility_live"))
    conn.execute(text("""
        CREATE TABLE mart_facility_live AS
        SELECT facility_id, state_code, lga_id, analysis_month, queue AS baseline_queue, tag AS baseline_tag,
               operational_risk AS baseline_risk, data_confidence AS baseline_confidence,
               queue AS live_queue, tag AS live_tag, operational_risk AS live_risk, data_confidence AS live_confidence,
               false AS field_verified, CAST(NULL AS date) AS verified_at, CAST(NULL AS text) AS verification_source,
               CAST('[]' AS jsonb) AS live_reasons, false AS changed, false AS live_field_driven,
               COALESCE(nhlmis_stale, false) AS nhlmis_stale
        FROM mart_facility_month WHERE analysis_month = :m"""), {"m": month})
    conn.execute(text("ALTER TABLE mart_facility_live ADD PRIMARY KEY (facility_id)"))
    conn.execute(text("CREATE INDEX ON mart_facility_live (state_code, lga_id)"))
    return conn.execute(text("SELECT count(*) FROM mart_facility_live")).scalar()


def refresh_live(conn, facility_ids: list[str], today: date) -> None:
    month = baseline_month(conn)
    base = rows(conn, """SELECT fm.*, (d.vaccine_stockout_flag = 1) AS vaccine_stockout_raw,
                                (d.sessions_planned > 0 AND d.sessions_conducted < 0.75 * d.sessions_planned) AS vaccine_watch
                         FROM mart_facility_month fm
                         LEFT JOIN fact_dhis2_monthly d ON d.facility_id = fm.facility_id AND d.period = replace(:m, '-', '')
                         WHERE fm.analysis_month = :m AND fm.facility_id = ANY(:ids)""", m=month, ids=facility_ids)
    for b in base:
        b["vaccine_stockout"] = bool(b.pop("vaccine_stockout_raw")) if b.get("report_received") else None
        fid = b["facility_id"]
        sev = {r["rule_id"] for r in rows(conn, """SELECT rule_id FROM fact_quality_flags WHERE facility_id = :f
                                                   AND analysis_month = :m AND severity = 'severe'""", f=fid, m=month)}
        ver = rows(conn, "SELECT * FROM field_verification WHERE facility_id = :f", f=fid)
        out = live_mod.live_status(b, sev, amc_for(conn, fid, month), ver, today)
        conn.execute(text("""UPDATE mart_facility_live SET live_queue = :lq, live_tag = :lt, live_risk = :lr,
                             live_confidence = :lc, field_verified = :fv, verified_at = :va, verification_source = :vs,
                             live_reasons = CAST(:rs AS jsonb), changed = :ch, live_field_driven = :fd
                             WHERE facility_id = :f"""),
                     {"lq": out["live_queue"], "lt": out["live_tag"], "lr": out["live_risk"], "lc": out["live_confidence"],
                      "fv": out["field_verified"], "va": out["verified_at"], "vs": out["verification_source"],
                      "rs": json.dumps(out["live_reasons"]), "ch": out["changed"], "fd": out["live_field_driven"], "f": fid})
