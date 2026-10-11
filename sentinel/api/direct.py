"""Direct, two-way messaging between the people in charge: from a facility page you can see who is in charge at
the facility, LGA and state, write to them, and they can write back. Everything is SIMULATED: the sender
presses Send (that is the approval), the provider only records it as delivered, and replies from the
synthetic recipient are simulated on the clock. View-as rules apply: you can only write to people inside your view.
"""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy import text

from .. import viewas
from ..actions import scope, service as svc, simulate
from ..actions.service import ActionError
from .cases import _tx
from .common import one, q, state_info

router = APIRouter()
CODE = Path(..., description="State code, e.g. kano")

CANNED = [
    "Received, thank you. I will look into it today.",
    "Noted. We are checking stock and will update you.",
    "Thanks. Please send the exact counts and we will act on them.",
    "Understood. I will raise it with the team and revert.",
    "Done. Please confirm that you can see the change.",
]
PERSON = """p.person_id, p.name, p.role_code, r.title AS role_title, p.level, p.state_code, p.lga_id, p.lga, p.facility_id,
            p.facility, p.phone_display, p.email, p.preferred_channel, p.responsiveness"""


class ComposeBody(BaseModel):
    actor_person_id: str
    to_person_ids: list[str] = Field(..., min_length=1, max_length=20)
    text: str = Field(..., min_length=1, max_length=600)
    facility_id: str | None = None
    thread_id: str | None = None


def _in_view(state: str | None, lga_id: str | None) -> None:
    if not viewas.can_see(state, lga_id):
        raise viewas.ScopeDenied("that conversation or facility is outside this view")


@router.get("/state/{code}/facility/{facility_id}/people", tags=["messages"])
def facility_people(code: str = CODE, facility_id: str = Path(...)):
    """The people in charge for one facility, by tier: the facility, its LGA and its state.
    An LGA view sees the facility and LGA tiers only; the state tier belongs to the state and national views."""
    state_info(code)
    f = one("SELECT facility_id, name, lga_id, lga FROM dim_facility WHERE facility_id = :f AND state_code = :s", f=facility_id, s=code)
    if f is None:
        raise HTTPException(404, "unknown facility in that state")
    sc = viewas.current()
    tiers = [("facility", "In charge at the facility", "p.facility_id = :f", {"f": facility_id}),
             ("lga", f"LGA team: {f['lga']}", "p.level = 'lga' AND p.lga_id = :l AND p.state_code = :s", {"l": f["lga_id"], "s": code})]
    if sc is None or sc.level != "lga":
        tiers.append(("state", "State board", "p.level = 'state' AND p.state_code = :s", {"s": code}))
    out = []
    for key, title, where, params in tiers:
        rows = q(f"""SELECT {PERSON} FROM dim_person p JOIN dim_role r USING (role_code)
                     WHERE p.active AND {where} ORDER BY r.level_order, r.role_code, p.name""", **params)
        out.append({"tier": key, "title": title, "people": rows})
    return {"facility": f, "tiers": out, "synthetic": True}


@router.get("/threads", tags=["messages"])
def threads(state: str | None = None, lga_id: str | None = None, facility_id: str | None = None,
            person_id: str | None = None, limit: int = Query(100, le=500)):
    """Direct conversations, newest first, each with its messages in order. Clamped to the view."""
    state, lga_id = viewas.clamp(state, lga_id)
    w, p = ["m.kind = 'direct'"], {"n": limit * 12}
    if state:
        w.append("m.state_code = :s"); p["s"] = state
    if lga_id:
        w.append("m.lga_id = :l"); p["l"] = lga_id
    if facility_id:
        w.append("m.facility_id = :f"); p["f"] = facility_id
    if person_id:
        w.append("m.thread_id IN (SELECT thread_id FROM message WHERE kind = 'direct' AND (sender_person_id = :pp OR to_person_id = :pp))")
        p["pp"] = person_id
    msgs = q(f"""SELECT m.message_id, m.thread_id, m.sender_person_id, sp.name AS from_name, sp.role_code AS from_role,
                        m.to_person_id, tp.name AS to_name, tp.role_code AS to_role, m.facility_id, f.name AS facility,
                        m.state_code, m.lga_id, m.channel, m.body, m.chars, m.status, m.created_at, m.delivered_at
                 FROM message m LEFT JOIN dim_person sp ON sp.person_id = m.sender_person_id
                 LEFT JOIN dim_person tp ON tp.person_id = m.to_person_id
                 LEFT JOIN dim_facility f ON f.facility_id = m.facility_id
                 WHERE {' AND '.join(w)} ORDER BY m.created_at, m.message_id LIMIT :n""", **p)
    by: dict[str, list[dict]] = {}
    for m in msgs:
        by.setdefault(m["thread_id"], []).append(m)
    out = []
    for tid, ms in by.items():
        people: dict[str, dict] = {}
        for m in ms:
            people[m["sender_person_id"]] = {"person_id": m["sender_person_id"], "name": m["from_name"], "role_code": m["from_role"]}
            people[m["to_person_id"]] = {"person_id": m["to_person_id"], "name": m["to_name"], "role_code": m["to_role"]}
        out.append({"thread_id": tid, "facility_id": ms[0]["facility_id"], "facility": ms[0]["facility"],
                    "last_at": str(ms[-1]["created_at"]), "last_message_id": ms[-1]["message_id"],
                    "people": list(people.values()), "messages": ms})
    out.sort(key=lambda t: (t["last_at"], int(t["last_message_id"][1:])), reverse=True)
    return {"threads": out[:limit], "simulated": True, "notice": "Simulated, not sent"}


@router.post("/messages/compose", tags=["messages"])
def compose(body: ComposeBody):
    """Write to one or more people (or reply in a thread). The sender pressing Send is the approval; delivery is simulated."""
    def run(conn):
        me = scope.persona(body.actor_person_id)
        today = svc.clock(conn)
        ppl = svc.people(conn)
        text_ = body.text.strip()
        if not text_:
            raise ActionError("write a message first", 422)
        root = None
        if body.thread_id:
            root = svc.row(conn, "SELECT * FROM message WHERE message_id = :t AND kind = 'direct'", t=body.thread_id)
            if root is None:
                raise ActionError("unknown conversation", 404)
            _in_view(root["state_code"], root["lga_id"])
            part = {r["pid"] for r in svc.rows(conn, """SELECT sender_person_id AS pid FROM message WHERE thread_id = :t
                                                       UNION SELECT to_person_id FROM message WHERE thread_id = :t""", t=body.thread_id)}
            if me["person_id"] not in part:
                raise scope.ScopeError("only people in this conversation can reply to it")
            if any(t not in part for t in body.to_person_ids):
                raise scope.ScopeError("you can reply only to people in this conversation")
        recips = []
        for pid in dict.fromkeys(body.to_person_ids):
            if pid == me["person_id"]:
                raise ActionError("you cannot write to yourself", 422)
            p = ppl.get(pid)
            viewas.check_person(p)                      # recipients must sit inside the view you chose
            if not p.get("active", True):
                raise ActionError(f"{p['name']} is not active", 422)
            recips.append(p)
        fid = body.facility_id or (root["facility_id"] if root else None)
        fac = None
        if fid:
            fac = svc.row(conn, "SELECT facility_id, state_code, lga_id FROM dim_facility WHERE facility_id = :f", f=fid)
            if fac is None:
                raise ActionError("unknown facility", 404)
            _in_view(fac["state_code"], fac["lga_id"])
        mids = svc.next_ids(conn, "message_seq", len(recips))
        cap = svc.cfg()["messaging"]["sms_max_chars"]
        made = []
        for n, p in zip(mids, recips):
            mid = f"M{n}"
            msg_text = f"Sentinel (DEMO) from {me['name']}: {text_}"
            if p["preferred_channel"] == "sms" and len(msg_text) > cap:
                raise ActionError(f"SMS to {p['name']} would be {len(msg_text)} characters; the limit is {cap}. Shorten the message.", 422)
            thread = root["message_id"] if root else mid
            res = svc.provider().send({"message_id": mid}, today, False)
            when, reply = _plan(mid, p, today)
            conn.execute(text("""INSERT INTO message (message_id, case_id, to_person_id, state_code, lga_id, channel, template_id,
                                   kind, priority, body, chars, status, created_at, approved_by, approved_at, scheduled_for, sent_at,
                                   delivered_at, synthetic, sender_person_id, facility_id, thread_id, planned_reply_at, planned_reply_text)
                                 VALUES (:id, NULL, :to, :st, :lga, :ch, 'direct', 'direct', 'P3', :b, :n, :status, :t, :me, :t, :t,
                                   :sent, :dlv, true, :me, :fid, :th, :wa, :wt)"""),
                         {"id": mid, "to": p["person_id"], "st": (fac or {}).get("state_code") or p["state_code"] or me["state_code"] or "national",
                          "lga": (fac or {}).get("lga_id") or p["lga_id"], "ch": p["preferred_channel"], "b": msg_text, "n": len(msg_text),
                          "status": res["status"], "t": today, "me": me["person_id"], "sent": res["sent_at"], "dlv": res["delivered_at"],
                          "fid": fid, "th": thread, "wa": when, "wt": reply})
            made.append({"message_id": mid, "thread_id": thread, "to": p["name"], "status": res["status"]})
        return {"sent": made, "simulated": True}
    return _tx(run)


def _plan(mid: str, person: dict, today) -> tuple:
    """Whether and when the synthetic recipient writes back (deterministic per message)."""
    rng = simulate._rng(mid, 17)
    resp = float(person.get("responsiveness") or 0)
    if person.get("never_replies") or rng.random() > 0.35 + 0.6 * resp:
        return None, None
    return today + timedelta(days=1 + int(rng.integers(0, 3))), CANNED[int(rng.integers(len(CANNED)))]
