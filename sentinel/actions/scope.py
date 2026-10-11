"""Who may do what. The demo has no login: an "acting as" persona (a synthetic person) stands in for a
signed-in user. This module is the single place scope is decided, so a pilot replaces persona lookup with
real authentication and keeps these rules.

    national  view everything; act on state cases; request state responses
    state     act on any case in its state; approve its messages and resupply
    lga       act on cases in its LGA (facility and LGA level)
    facility  act on cases at its own facility (reply, note); cannot approve messages or resupply
"""
from __future__ import annotations

from fastapi import HTTPException

from .service import ActionError, people


class ScopeError(HTTPException):
    def __init__(self, msg: str):
        super().__init__(403, msg)


def persona(actor_person_id: str | None) -> dict:
    if not actor_person_id:
        raise HTTPException(422, "actor_person_id is required: choose who you are acting as")
    try:
        return people().get(actor_person_id)
    except ActionError:
        raise HTTPException(404, f"unknown persona {actor_person_id}") from None


def can_act_on_case(p: dict, case: dict) -> bool:
    lvl = p["level"]
    if lvl == "national":
        return case["level"] == "state"
    if lvl == "state":
        return case["state_code"] == p["state_code"]
    if lvl == "lga":
        return case["state_code"] == p["state_code"] and case.get("lga_id") == p["lga_id"] and case["level"] in ("facility", "lga")
    if lvl == "facility":
        return case.get("facility_id") == p["facility_id"]
    return False


def require_case(p: dict, case: dict, action: str) -> None:
    if action in ("approve_messages", "approve_resupply", "assign") and p["level"] == "facility":
        raise ScopeError(f"{p['name']} ({p['role_code']}) cannot {action.replace('_', ' ')}: facility staff reply, they do not approve")
    if not can_act_on_case(p, case):
        where = {"national": "state-level cases", "state": f"cases in {p['state_code']}",
                 "lga": f"cases in {p.get('lga')} LGA", "facility": f"cases at {p.get('facility')}"}[p["level"]]
        raise ScopeError(f"{p['name']} ({p['role_code']}) can act only on {where}; case {case['case_ref']} is out of scope")


def require_state(p: dict, state_code: str, action: str) -> None:
    if p["level"] == "national":
        return
    if p["state_code"] != state_code:
        raise ScopeError(f"{p['name']} can {action} only in {p['state_code']}")


def require_national(p: dict, action: str) -> None:
    if p["level"] != "national":
        raise ScopeError(f"only a national persona can {action}")


def visible_filter(p: dict | None) -> tuple[str, dict]:
    """SQL WHERE fragment for 'my scope' lists."""
    if p is None or p["level"] == "national":
        return "TRUE", {}
    if p["level"] == "state":
        return "c.state_code = :ps", {"ps": p["state_code"]}
    if p["level"] == "lga":
        return "c.lga_id = :pl", {"pl": p["lga_id"]}
    return "c.facility_id = :pf", {"pf": p["facility_id"]}
