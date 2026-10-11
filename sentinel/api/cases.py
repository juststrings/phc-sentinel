"""Action-layer API, part 2: cases, messages, replies, resupply, live status, summaries, simulated clock.

Every write runs in one transaction through sentinel.actions.service and is checked by sentinel.actions.scope
against the acting persona (403 when out of scope). Messages are SIMULATED, never sent.
"""
from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Body, HTTPException, Path, Query, Response
from pydantic import BaseModel, Field

from ..actions import scope, service as svc
from ..actions.service import ActionError
from ..config import actions_cfg, states
from ..db import engine
from .common import one, q, state_info

router = APIRouter()
CODE = Path(..., description="State code, e.g. bauchi")
OPEN = "c.status NOT IN ('resolved','closed_no_action','closed_duplicate')"


class Actor(BaseModel):
    actor_person_id: str = Field(..., description="The synthetic person you are acting as (persona)")


class AssignBody(Actor):
    person_id: str


class ResolveBody(Actor):
    outcome_code: str
    note: str | None = None


class NoteBody(Actor):
    text: str
    kind: str = Field("note", pattern="^(note|response_lead|response_plan)$")


class OpenBody(Actor):
    rule_id: str | None = None
    playbook: str | None = None


class BulkBody(Actor):
    case_ids: list[str] = []
    action: str = Field(..., pattern="^(acknowledge|assign|approve_messages|open_recommended|open_playbook)$")
    person_id: str | None = None
    playbook: str | None = None
    facility_ids: list[str] = []


class ApproveBody(Actor):
    message_ids: list[str]


class EditBody(Actor):
    body: str


class ReviewBody(Actor):
    corrected_text: str | None = None
    dismiss: bool = False


class ReplyBody(Actor):
    text: str
    message_id: str | None = None


class TickBody(BaseModel):
    days: int = Field(1, ge=1, le=30)


def _tx(fn):
    """Run fn(conn) in one transaction; map ActionError to an HTTP status."""
    try:
        with engine().begin() as conn:
            return fn(conn)
    except ActionError as e:
        raise HTTPException(e.code, str(e)) from None


def _clock() -> dict:
    try:
        r = one("SELECT sim_date, started, baseline_month FROM sim_clock WHERE id = 1")
    except Exception:  # noqa: BLE001  (table missing)
        r = None
    if r is None:
        raise HTTPException(503, "action layer not initialised: run `python -m sentinel actions load`")
    return r


CASE_COLS = """c.case_id, c.case_ref, c.level, c.state_code, c.lga_id, c.facility_id, c.rule_id, c.playbook_id, c.priority,
               c.base_priority, c.priority_notes, c.status, c.owner_person_id, c.owner_role, c.opened_at, c.due_at,
               c.acknowledged_at, c.resolved_at, c.last_activity_at, c.current_step, c.escalation_level,
               c.escalated_to_person_id, c.escalated_to_role, c.outcome_code, c.review_task, c.demo,
               COALESCE(f.name, c.evidence_snapshot->>'facility', c.state_code) AS unit_name,
               COALESCE(f.lga, c.evidence_snapshot->>'lga') AS lga, op.name AS owner_name, ep.name AS escalated_to_name,
               (SELECT title FROM dim_role WHERE role_code = c.owner_role) AS owner_role_title,
               c.evidence_snapshot->>'tag' AS tag, c.evidence_snapshot->>'top_domain' AS top_domain,
               c.evidence_snapshot->>'evidence_summary' AS evidence_summary,
               lv.live_tag, lv.live_queue, lv.changed AS live_changed, lv.field_verified,
               (c.due_at < (SELECT sim_date FROM sim_clock) AND c.status NOT IN ('resolved','closed_no_action','closed_duplicate')) AS overdue,
               (SELECT count(*) FROM message m WHERE m.case_id = c.case_id AND m.status = 'draft') AS drafts"""
CASE_FROM = """FROM case_file c LEFT JOIN dim_facility f ON f.facility_id = c.facility_id
               LEFT JOIN dim_person op ON op.person_id = c.owner_person_id
               LEFT JOIN dim_person ep ON ep.person_id = c.escalated_to_person_id
               LEFT JOIN mart_facility_live lv ON lv.facility_id = c.facility_id"""


def _has(table: str) -> bool:
    return bool(one("SELECT to_regclass(:t) AS t", t=table)["t"])


# ---- cases ------------------------------------------------------------------------------------------
@router.get("/state/{code}/cases", tags=["cases"])
def state_cases(code: str = CODE, status: str | None = None, priority: str | None = None, lga_id: str | None = None,
                owner: str | None = None, rule: str | None = None, overdue: bool | None = None, escalated: bool | None = None,
                open_only: bool = True, level: str | None = None, demo: bool | None = None,
                q_: str | None = Query(None, alias="q"),
                sort: str = Query("priority", pattern="^(priority|due|opened|impact)$"),
                limit: int = Query(100, le=1000), offset: int = 0):
    """Case board for a state. `sort=impact` orders by priority, then isolated PHCs first, then catchment population (access layer)."""
    state_info(code)
    clk = _clock()
    w, p = ["c.state_code = :s"], {"s": code, "n": limit, "o": offset}
    if open_only and not status:
        w.append(OPEN)
    if status:
        w.append("c.status = ANY(:st)"); p["st"] = status.split(",")
    if priority:
        w.append("c.priority = ANY(:pr)"); p["pr"] = priority.split(",")
    if lga_id:
        w.append("c.lga_id = :l"); p["l"] = lga_id
    if owner:
        w.append("(c.owner_person_id = :ow OR c.escalated_to_person_id = :ow)"); p["ow"] = owner
    if rule:
        w.append("c.rule_id = ANY(:ru)"); p["ru"] = rule.split(",")
    if level:
        w.append("c.level = :lv"); p["lv"] = level
    if overdue:
        w.append("c.due_at < (SELECT sim_date FROM sim_clock)")
    if escalated:
        w.append("c.escalation_level > 0")
    if demo:
        w.append("c.demo")
    if q_:
        w.append("(f.name ILIKE :q OR c.case_ref ILIKE :q OR f.lga ILIKE :q)"); p["q"] = f"%{q_}%"
    acc = _has("mart_access_facility")
    join = " LEFT JOIN mart_access_facility acc ON acc.facility_id = c.facility_id AND acc.access_computed" if acc else ""
    order = {"priority": "c.priority, c.due_at, c.case_id", "due": "c.due_at, c.priority, c.case_id",
             "opened": "c.opened_at DESC, c.case_id",
             "impact": ("c.priority, acc.isolated DESC NULLS LAST, acc.catchment_pop DESC NULLS LAST, c.case_id" if acc
                        else "c.priority, c.due_at, c.case_id")}[sort]
    extra = ", acc.catchment_pop AS catchment_population, acc.isolated AS access_isolated, acc.alt_walk_min" if acc else ""
    where = " AND ".join(w)
    total = one(f"SELECT count(*) n {CASE_FROM}{join} WHERE {where}", **p)["n"]
    rows = q(f"SELECT {CASE_COLS}{extra} {CASE_FROM}{join} WHERE {where} ORDER BY {order} LIMIT :n OFFSET :o", **p)
    return {"state": state_info(code), "clock": clk, "total": total, "cases": rows, "synthetic": True}


@router.get("/cases/{case_id}", tags=["cases"])
def case_detail(case_id: str):
    c = one(f"""SELECT {CASE_COLS}, c.evidence_snapshot, c.outcome_note, c.response_lead, c.response_plan,
                       c.escalation_ladder, c.raised_by_person_id, rp.name AS raised_by_name, c.baseline_month
                {CASE_FROM} LEFT JOIN dim_person rp ON rp.person_id = c.raised_by_person_id WHERE c.case_id = :c""", c=case_id)
    if c is None:
        raise HTTPException(404, f"unknown case {case_id}")
    cfg = actions_cfg()
    book = cfg["playbooks"][c["playbook_id"]]
    events = q("""SELECT e.event_id, e.at, e.actor_person_id, COALESCE(p.name, e.actor) AS actor, e.event_type,
                         e.from_status, e.to_status, e.payload, e.synthetic_actor
                  FROM case_event e LEFT JOIN dim_person p ON p.person_id = e.actor_person_id
                  WHERE e.case_id = :c ORDER BY e.event_id""", c=case_id)
    msgs = q("""SELECT m.message_id, m.to_person_id, p.name AS to_name, p.role_code AS to_role, p.phone_display, m.channel,
                       m.template_id, m.kind, m.body, m.chars, m.status, m.created_at, m.approved_by, m.approved_at,
                       m.sent_at, m.delivered_at, m.expects
                FROM message m LEFT JOIN dim_person p ON p.person_id = m.to_person_id WHERE m.case_id = :c
                ORDER BY m.created_at, m.message_id""", c=case_id)
    resp = q("""SELECT r.response_id, r.message_id, r.from_person_id, p.name AS from_name, r.received_at, r.raw_text, r.parsed,
                       r.parse_status, r.review_status, r.synthetic
                FROM inbound_response r LEFT JOIN dim_person p ON p.person_id = r.from_person_id WHERE r.case_id = :c
                ORDER BY r.response_id""", c=case_id)
    reqs = q("SELECT * FROM resupply_request WHERE case_id = :c ORDER BY request_id", c=case_id)
    ppl = svc.people()
    ladder = []
    for i, s in enumerate(cfg["escalation"].get(c["escalation_ladder"] or "", [])):
        pid = ppl.find(s["role"], c["state_code"], c["lga_id"], c["facility_id"])
        ladder.append({**s, "level": i, "title": cfg["roles"][s["role"]]["title"], "person_id": pid,
                       "name": ppl.get(pid)["name"] if pid else None})
    live, people_here = None, []
    if c["facility_id"]:
        live = one("SELECT * FROM mart_facility_live WHERE facility_id = :f", f=c["facility_id"])
        people_here = q("""SELECT p.person_id, p.name, p.role_code, r.title AS role_title, p.phone_display, p.preferred_channel, p.level
                           FROM dim_person p JOIN dim_role r USING (role_code)
                           WHERE p.facility_id = :f OR (p.lga_id = :l AND p.level = 'lga') ORDER BY r.level_order DESC, p.role_code""",
                        f=c["facility_id"], l=c["lga_id"])
    elif c["level"] == "lga":
        people_here = q("""SELECT p.person_id, p.name, p.role_code, r.title AS role_title, p.phone_display, p.preferred_channel, p.level
                           FROM dim_person p JOIN dim_role r USING (role_code) WHERE p.lga_id = :l AND p.level = 'lga'
                           ORDER BY p.role_code""", l=c["lga_id"])
    else:
        people_here = q("""SELECT p.person_id, p.name, p.role_code, r.title AS role_title, p.phone_display, p.preferred_channel, p.level
                           FROM dim_person p JOIN dim_role r USING (role_code) WHERE p.state_code = :s AND p.level = 'state'
                           ORDER BY p.role_code""", s=c["state_code"])
    rule = next((r for r in cfg["rules"] if r["id"] == c["rule_id"]), None)
    return {"case": c, "playbook": {"id": c["playbook_id"], **book}, "rule": rule, "events": events, "messages": msgs,
            "responses": resp, "resupply": reqs, "escalation_ladder": ladder, "live": live, "people": people_here,
            "outcome_codes": cfg["outcome_codes"], "clock": _clock(), "synthetic": True}


@router.post("/cases/{case_id}/{action}", tags=["cases"])
def case_action(case_id: str, action: str = Path(..., pattern="^(acknowledge|assign|advance|resolve|close|note)$"),
                body: dict = Body(...)):
    """acknowledge | assign {person_id} | advance | resolve {outcome_code, note} | close {outcome_code} | note {text, kind}.
    Body always carries actor_person_id (the persona)."""
    def run(conn):
        actor = body.get("actor_person_id")
        p = scope.persona(actor)
        case = svc.get_case(conn, case_id)
        scope.require_case(p, case, action)
        if action == "acknowledge":
            svc.acknowledge(conn, case_id, actor)
        elif action == "assign":
            b = AssignBody(**body)
            svc.assign(conn, case_id, actor, b.person_id)
        elif action == "advance":
            svc.advance(conn, case_id, actor)
        elif action == "resolve":
            b = ResolveBody(**body)
            svc.resolve(conn, case_id, actor, b.outcome_code, b.note)
        elif action == "close":
            b = ResolveBody(**{**body, "outcome_code": body.get("outcome_code", "no_action_needed")})
            st = "closed_duplicate" if b.outcome_code == "duplicate" else "closed_no_action"
            svc.resolve(conn, case_id, actor, b.outcome_code, b.note, close_status=st)
        elif action == "note":
            b = NoteBody(**body)
            svc.note(conn, case_id, actor, b.text, b.kind)
    _tx(run)
    return case_detail(case_id)


@router.post("/cases/{case_id}/reply", tags=["cases"])
def case_reply(case_id: str, body: ReplyBody):
    """A facility persona types a reply (as if by SMS). Parsed and applied exactly like a simulated reply."""
    def run(conn):
        p = scope.persona(body.actor_person_id)
        case = svc.get_case(conn, case_id)
        scope.require_case(p, case, "reply")
        msg = svc.row(conn, "SELECT * FROM message WHERE message_id = :m", m=body.message_id) if body.message_id else \
            svc.row(conn, """SELECT * FROM message WHERE case_id = :c AND to_person_id = :p AND expects <> ''
                             ORDER BY created_at DESC, message_id DESC LIMIT 1""", c=case_id, p=body.actor_person_id)
        return svc.record_reply(conn, msg, body.actor_person_id, body.text, svc.clock(conn), case_id, synthetic=False)
    r = _tx(run)
    return {"response": r, **case_detail(case_id)}


@router.post("/state/{code}/facility/{facility_id}/cases", tags=["cases"])
def open_facility_case(code: str, facility_id: str, body: OpenBody):
    """'Take action': open a case on a facility from a rule, from the rule that uses a chosen playbook, or from the
    recommended rule."""
    from ..actions import records, rules as rules_mod

    def run(conn):
        p = scope.persona(body.actor_person_id)
        scope.require_state(p, code, "open cases")
        if p["level"] in ("national", "facility"):
            raise scope.ScopeError(f"{p['name']} ({p['role_code']}) cannot open facility cases")
        rec = records.facility_records(conn, svc.baseline_month(conn), [facility_id])
        if rec.empty or rec.iloc[0]["state_code"] != code:
            raise ActionError(f"unknown facility {facility_id} in {code}", 404)
        r = rec.iloc[0].to_dict()
        if p["level"] == "lga" and r["lga_id"] != p["lga_id"]:
            raise scope.ScopeError(f"{p['name']} can open cases only in {p['lga']} LGA")
        rid = body.rule_id
        if not rid and body.playbook:
            rid = next((x["id"] for x in rules_mod.rules() if x.get("playbook") == body.playbook and x["level"] == "facility"
                        and x["mode"] == "open"), None)
        if not rid:
            fired, _ = rules_mod.assign(rec, "facility")
            if fired.empty:
                raise ActionError("no rule applies to this facility; choose a playbook", 422)
            rid = fired.iloc[0]["rule_id"]
        case = svc.open_case(conn, rid, r, body.actor_person_id)
        if case is None:
            raise ActionError("an open case with this playbook already exists for this facility (or one was resolved recently)")
        return case["case_id"]
    return case_detail(_tx(run))


@router.post("/cases/bulk", tags=["cases"])
def cases_bulk(body: BulkBody):
    """Bulk actions from queue selections: acknowledge, assign, approve all draft messages, or open the recommended
    playbook for selected facilities (`facility_ids`)."""
    from ..actions import records, rules as rules_mod

    def run(conn):
        p = scope.persona(body.actor_person_id)
        if body.action == "open_playbook":
            if not body.facility_ids or not body.playbook:
                raise ActionError("facility_ids and playbook required", 422)
            if p["level"] in ("national", "facility"):
                raise scope.ScopeError(f"{p['name']} ({p['role_code']}) cannot open facility cases")
            rid = next((x["id"] for x in rules_mod.rules() if x.get("playbook") == body.playbook and x["level"] == "facility"
                        and x["mode"] == "open"), None)
            if rid is None:
                raise ActionError(f"no facility rule uses playbook {body.playbook}", 422)
            rec = records.facility_records(conn, svc.baseline_month(conn), body.facility_ids)
            opened, existing = [], 0
            for _, r in rec.iterrows():
                r = r.to_dict()
                scope.require_case(p, {"level": "facility", **r, "case_ref": r["facility_id"]}, "open")
                c = svc.open_case(conn, rid, r, body.actor_person_id)
                if c:
                    opened.append(c["case_id"])
                else:
                    existing += 1
            return {"opened": opened, "already_open": existing}
        if body.action == "open_recommended":
            if not body.facility_ids:
                raise ActionError("facility_ids required", 422)
            if p["level"] in ("national", "facility"):
                raise scope.ScopeError(f"{p['name']} ({p['role_code']}) cannot open facility cases")
            rec = records.facility_records(conn, svc.baseline_month(conn), body.facility_ids)
            fired, _ = rules_mod.assign(rec, "facility")
            opened, existing = [], 0
            for f in fired.itertuples():
                r = rec.loc[f.rec].to_dict()
                scope.require_case(p, {"level": "facility", **r, "case_ref": r["facility_id"]}, "open")
                c = svc.open_case(conn, f.rule_id, r, body.actor_person_id)
                if c:
                    opened.append(c["case_id"])
                else:
                    existing += 1
            return {"opened": opened, "already_open": existing}
        done = 0
        for cid in body.case_ids:
            case = svc.get_case(conn, cid)
            scope.require_case(p, case, body.action)
            if body.action == "acknowledge":
                svc.acknowledge(conn, cid, body.actor_person_id)
            elif body.action == "assign":
                if not body.person_id:
                    raise ActionError("person_id required", 422)
                svc.assign(conn, cid, body.actor_person_id, body.person_id)
            elif body.action == "approve_messages":
                ids = [m["message_id"] for m in svc.rows(conn, "SELECT message_id FROM message WHERE case_id = :c AND status = 'draft'", c=cid)]
                if ids:
                    svc.approve_messages(conn, ids, body.actor_person_id)
            done += 1
        return {"done": done}
    return _tx(run)


@router.get("/me/cases", tags=["cases"])
def my_cases(persona_id: str, limit: int = Query(100, le=500)):
    """'My cases' for the acting persona: owned or escalated to them, plus counts in their scope."""
    p = scope.persona(persona_id)
    w, params = scope.visible_filter(p)
    mine = q(f"""SELECT {CASE_COLS} {CASE_FROM} WHERE (c.owner_person_id = :p OR c.escalated_to_person_id = :p) AND {OPEN}
                 ORDER BY c.priority, c.due_at, c.case_id LIMIT :n""", p=persona_id, n=limit)
    scope_open = one(f"SELECT count(*) n FROM case_file c WHERE {w} AND {OPEN}", **params)["n"]
    drafts = one(f"SELECT count(*) n FROM message m JOIN case_file c USING (case_id) WHERE m.status = 'draft' AND {w}", **params)["n"]
    return {"persona": {k: v for k, v in p.items() if k != "responsiveness"}, "cases": mine, "open_in_scope": scope_open,
            "drafts_in_scope": drafts, "clock": _clock(), "synthetic": True}


# ---- messages and replies -------------------------------------------------------------------------------
@router.get("/messages", tags=["messages"])
def messages(state: str | None = None, status: str | None = None, lga_id: str | None = None, case_id: str | None = None,
             kind: str | None = None, priority: str | None = None, to_person_id: str | None = None,
             limit: int = Query(100, le=1000), offset: int = 0):
    """Outbox / approval tray. Every message is SIMULATED and never sent."""
    w, p = ["TRUE"], {"n": limit, "o": offset}
    if state:
        w.append("m.state_code = :s"); p["s"] = state
    if status:
        w.append("m.status = ANY(:st)"); p["st"] = status.split(",")
    if lga_id:
        w.append("m.lga_id = :l"); p["l"] = lga_id
    if case_id:
        w.append("m.case_id = :c"); p["c"] = case_id
    if kind:
        w.append("m.kind = ANY(:k)"); p["k"] = kind.split(",")
    if priority:
        w.append("m.priority = ANY(:pr)"); p["pr"] = priority.split(",")
    if to_person_id:
        w.append("m.to_person_id = :tp"); p["tp"] = to_person_id
    where = " AND ".join(w)
    total = one(f"SELECT count(*) n FROM message m WHERE {where}", **p)["n"]
    rows = q(f"""SELECT m.message_id, m.case_id, c.case_ref, m.to_person_id, pp.name AS to_name, pp.role_code AS to_role,
                       pp.phone_display, pp.email, m.channel, m.template_id, m.kind, m.priority, m.body, m.chars, m.status,
                       m.created_at, m.approved_by, m.approved_at, m.scheduled_for, m.sent_at, m.delivered_at, m.digest_id,
                       COALESCE(f.name, c.evidence_snapshot->>'facility') AS unit_name,
                       (SELECT r.raw_text FROM inbound_response r WHERE r.message_id = m.message_id ORDER BY r.response_id DESC LIMIT 1) AS reply_text,
                       (SELECT r.parse_status FROM inbound_response r WHERE r.message_id = m.message_id ORDER BY r.response_id DESC LIMIT 1) AS reply_parse
                FROM message m LEFT JOIN dim_person pp ON pp.person_id = m.to_person_id
                LEFT JOIN case_file c ON c.case_id = m.case_id LEFT JOIN dim_facility f ON f.facility_id = c.facility_id
                WHERE {where} ORDER BY m.priority, m.created_at DESC, m.message_id LIMIT :n OFFSET :o""", **p)
    return {"total": total, "messages": rows, "simulated": True, "notice": "Simulated, not sent"}


@router.post("/messages/approve", tags=["messages"])
def approve(body: ApproveBody):
    """A person approves drafts (bulk). Nothing leaves draft without this call."""
    def run(conn):
        p = scope.persona(body.actor_person_id)
        if p["level"] == "facility":
            raise scope.ScopeError("facility staff reply; they do not approve messages")
        for c in svc.rows(conn, "SELECT DISTINCT c.* FROM message m JOIN case_file c USING (case_id) WHERE m.message_id = ANY(:ids)",
                          ids=body.message_ids):
            scope.require_case(p, c, "approve_messages")
        for m in svc.rows(conn, "SELECT state_code FROM message WHERE message_id = ANY(:ids) AND case_id IS NULL", ids=body.message_ids):
            scope.require_state(p, m["state_code"], "approve messages")
        return {"approved": svc.approve_messages(conn, body.message_ids, body.actor_person_id)}
    return _tx(run)


@router.post("/messages/{message_id}/edit", tags=["messages"])
def edit(message_id: str, body: EditBody):
    def run(conn):
        m = svc.row(conn, "SELECT * FROM message WHERE message_id = :m", m=message_id)
        if m is None:
            raise ActionError(f"unknown message {message_id}", 404)
        p = scope.persona(body.actor_person_id)
        if m["case_id"]:
            scope.require_case(p, svc.get_case(conn, m["case_id"]), "approve_messages")
        else:
            scope.require_state(p, m["state_code"], "edit messages")
        return svc.edit_message(conn, message_id, body.actor_person_id, body.body)
    return _tx(run)


@router.get("/responses", tags=["messages"])
def responses(state: str | None = None, lga_id: str | None = None, parse_status: str | None = None,
              review_status: str | None = None, limit: int = Query(100, le=1000)):
    w, p = ["TRUE"], {"n": limit}
    if state:
        w.append("r.state_code = :s"); p["s"] = state
    if lga_id:
        w.append("c.lga_id = :lg"); p["lg"] = lga_id
    if parse_status:
        w.append("r.parse_status = ANY(:ps)"); p["ps"] = parse_status.split(",")
    if review_status:
        w.append("r.review_status = ANY(:rs)"); p["rs"] = review_status.split(",")
    rows = q(f"""SELECT r.*, p.name AS from_name, c.case_ref, COALESCE(f.name, '') AS unit_name
                 FROM inbound_response r LEFT JOIN dim_person p ON p.person_id = r.from_person_id
                 LEFT JOIN case_file c ON c.case_id = r.case_id LEFT JOIN dim_facility f ON f.facility_id = c.facility_id
                 WHERE {' AND '.join(w)} ORDER BY r.received_at DESC, r.response_id DESC LIMIT :n""", **p)
    return {"responses": rows, "synthetic": True}


@router.post("/responses/{response_id}/review", tags=["messages"])
def review(response_id: str, body: ReviewBody):
    """A person resolves an unparseable reply: type the reading they understand, or dismiss it."""
    def run(conn):
        r = svc.row(conn, "SELECT * FROM inbound_response WHERE response_id = :r", r=response_id)
        if r is None:
            raise ActionError(f"unknown response {response_id}", 404)
        p = scope.persona(body.actor_person_id)
        if r["case_id"]:
            scope.require_case(p, svc.get_case(conn, r["case_id"]), "review")
        return svc.review_response(conn, response_id, body.actor_person_id, body.corrected_text, body.dismiss)
    return _tx(run)


# ---- resupply ----------------------------------------------------------------------------------------------
@router.post("/resupply-requests/{request_id}/approve", tags=["resupply"])
def approve_resupply(request_id: str, body: Actor):
    def run(conn):
        r = svc.row(conn, "SELECT * FROM resupply_request WHERE request_id = :r", r=request_id)
        if r is None:
            raise ActionError(f"unknown resupply request {request_id}", 404)
        p = scope.persona(body.actor_person_id)
        scope.require_case(p, svc.get_case(conn, r["case_id"]), "approve_resupply")
        return svc.approve_resupply(conn, request_id, body.actor_person_id)
    return _tx(run)


RQ_SQL = """SELECT r.request_id, c.case_ref, c.case_id, r.facility_id, f.name AS facility, f.lga, f.ward, r.commodity_code,
                   r.qty_requested, r.basis, r.status, r.requested_at, rp.name AS requested_by, ap.name AS approved_by,
                   r.approved_at, r.expected_delivery, r.delivered_at
            FROM resupply_request r JOIN case_file c USING (case_id) JOIN dim_facility f ON f.facility_id = r.facility_id
            LEFT JOIN dim_person rp ON rp.person_id = r.requested_by LEFT JOIN dim_person ap ON ap.person_id = r.approved_by
            WHERE r.state_code = :s AND (CAST(:st AS text) IS NULL OR r.status = :st)
            ORDER BY f.lga, f.name, r.commodity_code"""


@router.get("/state/{code}/resupply-requests", tags=["resupply"])
def resupply_list(code: str = CODE, status: str | None = None):
    return {"state": state_info(code), "requests": q(RQ_SQL, s=code, st=status), "clock": _clock(), "synthetic": True}


@router.get("/state/{code}/resupply-requests.csv", tags=["resupply"])
def resupply_csv(code: str = CODE, status: str | None = None):
    """Export for the State LMCU. Synthetic requests, not real orders."""
    state_info(code)
    rows = q(RQ_SQL, s=code, st=status)
    buf = io.StringIO()
    buf.write("# PHC Sentinel DEMO: synthetic resupply requests, not real orders\n")
    w = csv.DictWriter(buf, fieldnames=list(rows[0]) if rows else ["request_id"])
    w.writeheader()
    w.writerows(rows)
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=sentinel-demo-resupply-{code}.csv"})


# ---- live status --------------------------------------------------------------------------------------------
@router.get("/state/{code}/facility/{facility_id}/live", tags=["live"])
def facility_live(code: str, facility_id: str):
    """Baseline (monthly assessment) vs live status with reasons, verifications, cases, people, recommended playbook."""
    from ..actions import records, rules as rules_mod
    state_info(code)
    lv = one("SELECT * FROM mart_facility_live WHERE facility_id = :f AND state_code = :s", f=facility_id, s=code)
    if lv is None:
        raise HTTPException(404, f"unknown facility {facility_id} in {code}")
    ver = q("""SELECT v.*, p.name AS by_name FROM field_verification v LEFT JOIN dim_person p ON p.person_id = v.by_person_id
               WHERE v.facility_id = :f ORDER BY v.verified_at DESC, v.verification_id DESC""", f=facility_id)
    cases = q(f"SELECT {CASE_COLS} {CASE_FROM} WHERE c.facility_id = :f ORDER BY c.opened_at DESC, c.case_id", f=facility_id)
    people_here = q("""SELECT p.person_id, p.name, p.role_code, r.title AS role_title, p.phone_display, p.preferred_channel, p.level
                       FROM dim_person p JOIN dim_role r USING (role_code)
                       WHERE p.facility_id = :f OR (p.level = 'lga' AND p.lga_id = (SELECT lga_id FROM dim_facility WHERE facility_id = :f))
                       ORDER BY r.level_order DESC, p.role_code""", f=facility_id)
    with engine().connect() as conn:
        rec = records.facility_records(conn, lv["analysis_month"], [facility_id])
    fired, _ = rules_mod.assign(rec, "facility")
    cfg = actions_cfg()
    rl = {r["id"]: r for r in cfg["rules"]}
    recommended = [{"rule_id": r, "playbook": rl[r]["playbook"], "title": cfg["playbooks"][rl[r]["playbook"]]["title"],
                    "owner_role": rl[r]["owner_role"], "owner_title": cfg["roles"][rl[r]["owner_role"]]["title"],
                    "priority": rl[r]["priority"]} for r in fired["rule_id"]]
    manual = [{"playbook": r["playbook"], "title": cfg["playbooks"][r["playbook"]]["title"], "rule_id": r["id"]}
              for r in cfg["rules"] if r["level"] == "facility" and r.get("mode", "open") == "open"]
    seen, manual_u = set(), []
    for m in manual:
        if m["playbook"] not in seen:
            seen.add(m["playbook"]); manual_u.append(m)
    return {"live": lv, "verifications": ver, "cases": cases, "people": people_here, "recommended": recommended,
            "playbooks": manual_u, "clock": _clock(), "synthetic": True}


# ---- summaries ---------------------------------------------------------------------------------------------
def _summary_sql(where: str) -> str:
    return f"""
      SELECT count(*) FILTER (WHERE {OPEN}) AS open_cases,
             count(*) FILTER (WHERE {OPEN} AND c.priority = 'P1') AS p1_open,
             count(*) FILTER (WHERE {OPEN} AND c.due_at < (SELECT sim_date FROM sim_clock)) AS overdue,
             count(*) FILTER (WHERE {OPEN} AND c.escalation_level > 0) AS escalated,
             count(*) FILTER (WHERE {OPEN} AND c.escalation_level > 0 AND c.escalated_to_role LIKE 'st%') AS escalated_to_state,
             count(*) FILTER (WHERE {OPEN} AND c.escalation_level > 0 AND c.escalated_to_role LIKE 'nat%') AS escalated_to_national,
             count(*) AS total_cases,
             count(*) FILTER (WHERE c.status = 'resolved') AS resolved,
             count(*) FILTER (WHERE c.status = 'resolved' AND c.resolved_at <= c.due_at) AS resolved_in_sla,
             count(*) FILTER (WHERE c.acknowledged_at IS NOT NULL) AS acknowledged,
             percentile_cont(0.5) WITHIN GROUP (ORDER BY (c.acknowledged_at - c.opened_at)) AS median_days_to_ack,
             percentile_cont(0.5) WITHIN GROUP (ORDER BY (c.resolved_at - c.opened_at)) FILTER (WHERE c.status = 'resolved') AS median_days_to_resolve,
             count(*) FILTER (WHERE c.review_task AND {OPEN}) AS replies_to_review
      FROM case_file c WHERE {where}"""


def _rates(r: dict) -> dict:
    tot = r["total_cases"] or 0
    r["pct_resolved"] = round(r["resolved"] / tot, 4) if tot else None
    r["pct_resolved_in_sla"] = round(r["resolved_in_sla"] / r["resolved"], 4) if r["resolved"] else None
    r["pct_overdue"] = round(r["overdue"] / r["open_cases"], 4) if r["open_cases"] else 0.0
    r["escalation_rate"] = round(r["escalated"] / r["open_cases"], 4) if r["open_cases"] else 0.0
    return r


@router.get("/state/{code}/actions/summary", tags=["cases"])
def actions_summary(code: str = CODE):
    """Action Centre KPIs and the LGA accountability table."""
    st = state_info(code)
    clk = _clock()
    k = _rates(one(_summary_sql("c.state_code = :s"), s=code))
    k.update(one("""SELECT count(*) FILTER (WHERE status = 'draft') AS awaiting_approval,
                           count(*) FILTER (WHERE status IN ('sent_simulated','delivered_simulated','replied','failed_simulated')) AS sent,
                           count(*) FILTER (WHERE status = 'replied') AS replied,
                           count(*) FILTER (WHERE expects <> '' AND status IN ('delivered_simulated','replied')) AS delivered_expecting_reply
                    FROM message WHERE state_code = :s""", s=code))
    rr = one("SELECT count(*) n, count(*) FILTER (WHERE parse_status = 'unparseable') bad FROM inbound_response WHERE state_code = :s", s=code)
    k["replies"] = rr["n"]
    k["unparseable_rate"] = round(rr["bad"] / rr["n"], 4) if rr["n"] else None
    k["reply_rate"] = round(k["replied"] / k["delivered_expecting_reply"], 4) if k["delivered_expecting_reply"] else None
    k["verifications"] = one("SELECT count(*) n FROM field_verification WHERE state_code = :s", s=code)["n"]
    k["live_changed"] = one("SELECT count(*) n FROM mart_facility_live WHERE state_code = :s AND changed", s=code)["n"]
    k["signals_cleared"] = one("""SELECT count(*) n FROM mart_facility_live WHERE state_code = :s AND changed
                                  AND live_queue = 'MONITOR' AND baseline_queue <> 'MONITOR'""", s=code)["n"]
    k["shortages_confirmed"] = one("""SELECT count(*) n FROM mart_facility_live WHERE state_code = :s AND live_field_driven
                                      AND live_queue = 'RESOURCE_ACTION'""", s=code)["n"]
    k["resupply_pending"] = one("SELECT count(*) n FROM resupply_request WHERE state_code = :s AND status = 'pending_approval'", s=code)["n"]
    lgas = q(f"""
        SELECT c.lga_id, max(COALESCE(f.lga, c.evidence_snapshot->>'lga')) AS lga,
               count(*) FILTER (WHERE {OPEN}) AS open_cases,
               count(*) FILTER (WHERE {OPEN} AND c.priority = 'P1') AS p1_open,
               count(*) FILTER (WHERE {OPEN} AND c.due_at < (SELECT sim_date FROM sim_clock)) AS overdue,
               count(*) FILTER (WHERE c.escalation_level > 0 AND {OPEN}) AS escalated,
               count(*) FILTER (WHERE c.acknowledged_at IS NULL AND {OPEN}) AS unacknowledged,
               count(*) AS total_cases, count(*) FILTER (WHERE c.status = 'resolved') AS resolved,
               count(*) FILTER (WHERE c.status = 'resolved' AND c.resolved_at <= c.due_at) AS resolved_in_sla,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY (c.acknowledged_at - c.opened_at)) AS median_days_to_ack
        FROM case_file c LEFT JOIN dim_facility f ON f.facility_id = c.facility_id
        WHERE c.state_code = :s AND c.lga_id IS NOT NULL GROUP BY c.lga_id""", s=code)
    coord = {r["lga_id"]: r for r in q("""SELECT lga_id, person_id, name FROM dim_person WHERE state_code = :s AND role_code = 'lga_phc_coord'""", s=code)}
    cleared = {r["lga_id"]: r["n"] for r in q("""SELECT lga_id, count(*) n FROM mart_facility_live WHERE state_code = :s AND changed
                                                 AND live_queue = 'MONITOR' AND baseline_queue <> 'MONITOR' GROUP BY 1""", s=code)}
    for l in lgas:
        l["signals_cleared"] = cleared.get(l["lga_id"], 0)
        l["pct_resolved"] = round(l["resolved"] / l["total_cases"], 4) if l["total_cases"] else None
        l["pct_resolved_in_sla"] = round(l["resolved_in_sla"] / l["resolved"], 4) if l["resolved"] else None
        l["coordinator"] = (coord.get(l["lga_id"]) or {}).get("name")
        l["coordinator_id"] = (coord.get(l["lga_id"]) or {}).get("person_id")
    lgas.sort(key=lambda l: (-l["overdue"], -l["unacknowledged"], -l["open_cases"]))
    by_rule = q(f"SELECT rule_id, priority, count(*) n FROM case_file c WHERE c.state_code = :s AND {OPEN} GROUP BY 1, 2 ORDER BY 1, 2", s=code)
    by_status = q("SELECT status, count(*) n FROM case_file WHERE state_code = :s GROUP BY 1 ORDER BY 1", s=code)
    esc = q(f"""SELECT {CASE_COLS} {CASE_FROM} WHERE c.state_code = :s AND {OPEN} AND c.escalation_level > 0
                ORDER BY c.escalation_level DESC, c.priority, c.due_at, c.case_id LIMIT 10""", s=code)
    rules = {r["id"]: r["description"] for r in actions_cfg()["rules"]}
    return {"state": st, "clock": clk, "kpis": k, "lgas": lgas, "by_rule": by_rule, "by_status": by_status,
            "escalations": esc, "rules": rules, "synthetic": True}


def actions_ready() -> bool:
    return _has("case_file")


def state_action_rates() -> dict[str, dict]:
    """Per state, for the national map and brief: open cases, overdue share, escalations, acknowledged share."""
    if not actions_ready():
        return {}
    rows = q(f"""SELECT c.state_code, count(*) FILTER (WHERE {OPEN}) AS open_cases,
                        count(*) FILTER (WHERE {OPEN} AND c.due_at < (SELECT sim_date FROM sim_clock)) AS overdue_cases,
                        count(*) FILTER (WHERE {OPEN} AND c.escalation_level > 0) AS escalated_cases,
                        count(*) FILTER (WHERE c.acknowledged_at IS NOT NULL) AS acknowledged_cases,
                        count(*) FILTER (WHERE c.status = 'resolved') AS resolved_cases, count(*) AS total_cases
                 FROM case_file c GROUP BY c.state_code""")
    sugg = {r["state_code"]: r["reason"] for r in q("SELECT state_code, reason FROM action_suggestion")}
    sc = {r["state_code"]: r for r in q("""SELECT DISTINCT ON (state_code) state_code, case_id AS state_case_id, case_ref AS state_case_ref,
                                                  status AS state_case_status FROM case_file WHERE level = 'state'
                                           ORDER BY state_code, opened_at DESC, case_id DESC""")}
    out = {}
    for r in rows:
        o = r["open_cases"] or 0
        code = r.pop("state_code")
        out[code] = {**r, "pct_cases_overdue": (r["overdue_cases"] / o) if o else 0.0,
                     "pct_cases_acknowledged": (r["acknowledged_cases"] / r["total_cases"]) if r["total_cases"] else 0.0,
                     "response_suggested": sugg.get(code), **{k: v for k, v in (sc.get(code) or {}).items() if k != "state_code"}}
    return out


@router.get("/national/actions/summary", tags=["cases"])
def national_actions_summary():
    """State-level action KPIs (aggregates only) and escalations that reached state or national level."""
    clk = _clock()
    by_state = {r["state_code"]: r for r in q(_summary_sql("TRUE").replace("FROM case_file c WHERE TRUE",
                                                                         "FROM case_file c GROUP BY c.state_code")
                                              .replace("SELECT count(*)", "SELECT c.state_code, count(*)", 1))}
    sugg = {r["state_code"]: r["reason"] for r in q("SELECT state_code, reason FROM action_suggestion")}
    st_cases = {r["state_code"]: r for r in q("""SELECT DISTINCT ON (state_code) state_code, case_id, case_ref, status, acknowledged_at,
                                                        opened_at, due_at, response_lead, response_plan IS NOT NULL AS has_plan
                                                 FROM case_file WHERE level = 'state' ORDER BY state_code, opened_at DESC, case_id DESC""")}
    rows = []
    for st in states():
        r = _rates(dict(by_state.get(st["code"]) or {k: 0 for k in ("open_cases", "p1_open", "overdue", "escalated",
                   "escalated_to_state", "escalated_to_national", "total_cases", "resolved", "resolved_in_sla", "acknowledged",
                   "replies_to_review")} | {"median_days_to_ack": None, "median_days_to_resolve": None}))
        r.pop("state_code", None)
        r.update({"state_code": st["code"], "state": st["name"], "zone": st["zone"], "pct_cases_overdue": r["pct_overdue"],
                  "response_suggested": sugg.get(st["code"]), "state_case": st_cases.get(st["code"])})
        rows.append(r)
    counts = ["open_cases", "p1_open", "overdue", "escalated", "escalated_to_state", "escalated_to_national", "total_cases",
              "resolved", "resolved_in_sla", "acknowledged", "replies_to_review"]
    tot = _rates({k: sum(r[k] for r in rows) for k in counts})
    sc = one("""SELECT count(*) FILTER (WHERE status NOT IN ('resolved','closed_no_action','closed_duplicate')) AS open,
                       percentile_cont(0.5) WITHIN GROUP (ORDER BY (acknowledged_at - opened_at)) AS median_ack
                FROM case_file WHERE level = 'state'""")
    esc = q(f"""SELECT {CASE_COLS} {CASE_FROM} WHERE {OPEN} AND c.escalation_level > 0
                AND (c.escalated_to_role LIKE 'st%' OR c.escalated_to_role LIKE 'nat%')
                ORDER BY (c.escalated_to_role LIKE 'nat%') DESC, c.escalation_level DESC, c.priority, c.due_at, c.case_id LIMIT 12""")
    return {"clock": clk, "kpis": {**tot, "state_cases_open": sc["open"], "state_cases_median_days_to_ack": sc["median_ack"]},
            "states": rows, "escalations": esc, "synthetic": True}


@router.post("/national/states/{code}/request-response", tags=["cases"])
def request_state_response(code: str, body: Actor):
    """A national persona opens an R10 state case: the state acknowledges, names a lead and submits a plan."""
    from ..actions import records

    def run(conn):
        p = scope.persona(body.actor_person_id)
        scope.require_national(p, "request a state response")
        st = records.state_records(conn, svc.baseline_month(conn))
        rec = st[st["state_code"] == code]
        if rec.empty:
            raise ActionError(f"unknown state {code}", 404)
        r = rec.iloc[0].to_dict()
        r["facility"] = r["state"]
        c = svc.open_case(conn, "R10_state_response", r, body.actor_person_id, raised_by=body.actor_person_id)
        if c is None:
            raise ActionError(f"an open state response case already exists for {code}")
        return c["case_id"]
    return case_detail(_tx(run))


@router.get("/national/responses", tags=["cases"])
def national_responses():
    """State response requests (rule R10): each case with its owner, status, response lead and plan, plus the
    states the system suggests a request for but where none is open. National sees the answer here."""
    clk = _clock()
    rows = q(f"""SELECT {CASE_COLS}, c.response_lead, c.response_plan, c.baseline_month,
                        st.name AS state_name, st.zone, st.status AS state_status
                 FROM case_file c LEFT JOIN dim_person op ON op.person_id = c.owner_person_id
                 LEFT JOIN dim_person ep ON ep.person_id = c.escalated_to_person_id
                 LEFT JOIN dim_facility f ON f.facility_id = c.facility_id
                 LEFT JOIN mart_facility_live lv ON lv.facility_id = c.facility_id
                 LEFT JOIN (SELECT state_code, state AS name, zone, status FROM mart_state_month
                            WHERE analysis_month = (SELECT baseline_month FROM sim_clock)) st ON st.state_code = c.state_code
                 WHERE c.level = 'state' ORDER BY c.opened_at DESC, c.case_id DESC""")
    open_states = {r["state_code"] for r in rows if r["status"] not in ("resolved", "closed_no_action", "closed_duplicate")}
    sugg = [r for r in q("""SELECT s.state_code, s.reason, m.state AS state_name, m.zone, m.status
                            FROM action_suggestion s JOIN mart_state_month m ON m.state_code = s.state_code
                            WHERE m.analysis_month = (SELECT baseline_month FROM sim_clock) ORDER BY m.state""")
            if r["state_code"] not in open_states]
    return {"clock": clk, "responses": rows, "suggested": sugg, "synthetic": True}


# ---- simulated clock (demo only) -------------------------------------------------------------------------
@router.get("/sim/clock", tags=["simulation"])
def sim_clock():
    return {**_clock(), "simulated": True}


@router.post("/sim/tick", tags=["simulation"])
def sim_tick(body: TickBody = Body(TickBody())):
    """DEMO ONLY: advance the simulated clock. Simulated people reply, acknowledge and escalate; approvals stay human."""
    from ..actions import engine as eng
    ticks = [_tx(eng.tick) for _ in range(body.days)]
    return {"ticks": ticks, "clock": _clock(), "simulated": True}


@router.post("/sim/reset", tags=["simulation"])
def sim_reset(seed_demo: bool = True):
    """DEMO ONLY: restore the clean, seeded start (and the curated demo scenario)."""
    from ..actions import demo

    def run(conn):
        s = demo.reset(conn, quiet=True, seed=seed_demo)
        return s
    return _tx(run)
