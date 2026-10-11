"""Action-layer API: people, cases, messages, replies, resupply, live status, simulated clock.

Every write goes through sentinel.actions.service (one code path for people and the simulated clock) and
is checked by sentinel.actions.scope against the acting persona. People, messages and replies are SYNTHETIC.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, Query

from ..config import actions_cfg, states
from .common import one, q, state_info

router = APIRouter()
CODE = Path(..., description="State code, e.g. bauchi")


@router.get("/meta/roles", tags=["people"])
def meta_roles():
    rows = q("SELECT role_code, level, title, responsibilities, owns_playbooks FROM dim_role ORDER BY level_order, role_code")
    return {"roles": rows, "quick_picks": actions_cfg().get("persona_quick_picks", [])}


PERSON_COLS = """p.person_id, p.name, p.gender, p.role_code, r.title AS role_title, p.level, p.state_code, p.lga_id,
                 p.lga, p.facility_id, p.facility, p.phone_display, p.email, p.preferred_channel,
                 p.responsiveness, p.active, p.synthetic"""


@router.get("/state/{code}/people", tags=["people"])
def state_people(code: str = CODE, role: str | None = None, lga_id: str | None = None, level: str | None = None,
                 q_: str | None = Query(None, alias="q"), limit: int = Query(200, le=2000), offset: int = 0):
    """Synthetic directory for a state. Filter by role, LGA, level or a name search."""
    state_info(code)
    where = ["p.state_code = :s"]
    params: dict = {"s": code, "n": limit, "o": offset}
    if role:
        where.append("p.role_code = :role"); params["role"] = role
    if lga_id:
        where.append("p.lga_id = :lga"); params["lga"] = lga_id
    if level:
        where.append("p.level = :lvl"); params["lvl"] = level
    if q_:
        where.append("(p.name ILIKE :q OR p.facility ILIKE :q OR p.lga ILIKE :q)"); params["q"] = f"%{q_}%"
    w = " AND ".join(where)
    total = one(f"SELECT count(*) n FROM dim_person p WHERE {w}", **params)["n"]
    rows = q(f"""SELECT {PERSON_COLS},
                   (SELECT count(*) FROM case_file c WHERE (c.owner_person_id = p.person_id OR c.escalated_to_person_id = p.person_id)
                      AND c.status NOT IN ('resolved','closed_no_action','closed_duplicate')) AS open_cases
                 FROM dim_person p JOIN dim_role r USING (role_code) WHERE {w}
                 ORDER BY r.level_order, p.lga NULLS FIRST, p.facility NULLS FIRST, p.role_code, p.name
                 LIMIT :n OFFSET :o""", **params)
    return {"state": state_info(code), "total": total, "people": rows, "synthetic": True}


SIGNIN_ROLE = {"national": "nat_director_phc", "state": "st_dir_phc", "lga": "lga_phc_coord"}


@router.get("/meta/signin", tags=["people"])
def signin_person(role: str = Query(..., pattern="^(national|state|lga)$"), state: str | None = None, lga: str | None = None):
    """Demo sign-in: the synthetic person who 'signs in' to a portal. National: the Director of PHC Systems
    Development; a state board: that state's Director of PHC Services; an LGA: its PHC Coordinator.
    There is no password; a pilot replaces this with real accounts."""
    where, params = ["p.role_code = :r"], {"r": SIGNIN_ROLE[role]}
    if role in ("state", "lga"):
        if not state:
            raise HTTPException(422, "state is required for a state board or LGA sign-in")
        state_info(state)
        where.append("p.state_code = :s"); params["s"] = state
    if role == "lga":
        if not lga:
            raise HTTPException(422, "lga is required for an LGA sign-in")
        where.append("p.lga_id = :l"); params["l"] = lga
    row = one(f"""SELECT {PERSON_COLS} FROM dim_person p JOIN dim_role r USING (role_code)
                  WHERE {' AND '.join(where)} ORDER BY p.person_id LIMIT 1""", **params)
    if row is None:
        raise HTTPException(404, "no one to sign in as for that choice")
    return {"person": row, "portal": role, "synthetic": True}


@router.get("/people/{person_id}", tags=["people"])
def person(person_id: str):
    p = one(f"SELECT {PERSON_COLS} FROM dim_person p JOIN dim_role r USING (role_code) WHERE p.person_id = :p", p=person_id)
    if p is None:
        raise HTTPException(404, f"unknown person {person_id}")
    cases = q("""SELECT case_id, case_ref, level, facility_id, rule_id, playbook_id, priority, status, due_at,
                        escalation_level, owner_person_id = :p AS is_owner
                 FROM case_file WHERE (owner_person_id = :p OR escalated_to_person_id = :p)
                   AND status NOT IN ('resolved','closed_no_action','closed_duplicate')
                 ORDER BY priority, due_at LIMIT 200""", p=person_id)
    return {"person": p, "open_cases": cases, "synthetic": True}


@router.get("/meta/personas", tags=["people"])
def personas(state: str | None = None):
    """Quick-pick personas for the 'Acting as' switcher: national roles plus, for a state, its Director of PHC,
    one LGA PHC Coordinator and one facility OIC (the first in the demo LGA when a demo is seeded)."""
    out = q("""SELECT p.person_id, p.name, p.role_code, r.title AS role_title, p.level, p.state_code, p.lga, p.facility
               FROM dim_person p JOIN dim_role r USING (role_code) WHERE p.level = 'national' ORDER BY p.role_code""")
    codes = [state] if state else [s["code"] for s in states()]
    for c in codes:
        out += q("""(SELECT p.person_id, p.name, p.role_code, r.title AS role_title, p.level, p.state_code, p.lga, p.facility
                     FROM dim_person p JOIN dim_role r USING (role_code)
                     WHERE p.state_code = :s AND p.role_code IN ('st_dir_phc', 'st_lmcu') ORDER BY p.role_code)
                    UNION ALL
                    (SELECT p.person_id, p.name, p.role_code, r.title, p.level, p.state_code, p.lga, p.facility
                     FROM dim_person p JOIN dim_role r USING (role_code)
                     LEFT JOIN (SELECT lga_id, count(*) n FROM case_file WHERE demo GROUP BY lga_id) d USING (lga_id)
                     WHERE p.state_code = :s AND p.role_code = 'lga_phc_coord' ORDER BY d.n DESC NULLS LAST, p.lga LIMIT 1)""", s=c)
    return {"personas": out, "synthetic": True}
