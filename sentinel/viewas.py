"""View-as scope: the row-level filter for the demo.

There is no login. Like Power BI's "View as", the web app lets you pick who you are viewing the dashboard as, and every API
request carries that choice in a header:

    X-View-As: national              everything (an admin)
    X-View-As: state:kano            one state board: its state and its LGAs
    X-View-As: lga:kano:20021        one LGA team: that LGA and its clinics

Two layers apply it, so a forgotten filter cannot leak another state's numbers:
  1. `authorize()` checks every request path (deny by default for state and LGA viewers).
  2. `clamp()`, `check_case()`, `check_person()` and `check_persona()` filter or refuse rows inside the handlers that list or
     fetch rows by id (directory, search, cases, messages, replies, people).
Code that runs without a request (tests, the CLI) has no scope and is not restricted.

The choice is made on the client, so this is demo-grade separation, not authentication. A pilot replaces `parse()` with a
verified identity and keeps every rule here.
"""
from __future__ import annotations

import os
import re
from contextvars import ContextVar
from dataclasses import dataclass
from functools import lru_cache

from fastapi import HTTPException

from .config import states


class ScopeDenied(HTTPException):
    def __init__(self, msg: str):
        super().__init__(403, msg)


@dataclass(frozen=True)
class Scope:
    level: str                      # national | state | lga
    state: str | None = None
    lga: str | None = None

    @property
    def label(self) -> str:
        return {"national": "National (all states)", "state": f"State board: {self.state}",
                "lga": f"LGA team: {self.state} / {self.lga}"}[self.level]

    @property
    def header(self) -> str:
        return {"national": "national", "state": f"state:{self.state}", "lga": f"lga:{self.state}:{self.lga}"}[self.level]


NATIONAL = Scope("national")
_CURRENT: ContextVar[Scope | None] = ContextVar("view_as", default=None)
# Paths any viewer may call (names, labels, the clock). Everything else is checked.
OPEN_EXACT = {"/health", "/openapi.json", "/docs", "/redoc", "/sim/clock", "/sim/tick"}
OPEN_PREFIX = ("/meta/",)
# Dev convenience: when set, a request without the header is treated as this scope instead of refused.
DEFAULT_HEADER = os.environ.get("SENTINEL_VIEW_AS_DEFAULT")


def parse(value: str | None) -> Scope | None:
    """'national' | 'state:{code}' | 'lga:{code}:{lga_id}' -> Scope. None when absent; raises 400-style ScopeDenied when malformed."""
    if not value:
        return None
    parts = value.strip().split(":")
    if parts == ["national"]:
        return NATIONAL
    codes = {s["code"] for s in states()}
    if len(parts) == 2 and parts[0] == "state" and parts[1] in codes:
        return Scope("state", parts[1])
    if len(parts) == 3 and parts[0] == "lga" and parts[1] in codes and parts[2]:
        return Scope("lga", parts[1], parts[2])
    raise HTTPException(400, f"bad X-View-As {value!r}: use national, state:<code> or lga:<code>:<lga_id>")


def current() -> Scope | None:
    return _CURRENT.get()


def set_current(scope: Scope | None):
    return _CURRENT.set(scope)


def reset_current(token) -> None:
    _CURRENT.reset(token)


# ---- request paths ------------------------------------------------------------------------------------------
@lru_cache(maxsize=20000)
def _facility_home(facility_id: str) -> tuple[str, str] | None:
    from .api.common import one
    r = one("SELECT state_code, lga_id FROM dim_facility WHERE facility_id = :f", f=facility_id)
    return (r["state_code"], r["lga_id"]) if r else None


@lru_cache(maxsize=4000)
def _lga_state(lga_id: str) -> str | None:
    from .api.common import one
    r = one("SELECT state_code FROM dim_lga WHERE lga_id = :l", l=lga_id)
    return r["state_code"] if r else None


# What an LGA team may call under /state/{its state}/...  (lists inside are clamped to its LGA by the handlers)
_LGA_REST = re.compile(r"^/(facilities|cases|people|geo/facilities|geo/lgas|actions/summary)$")


def authorize(scope: Scope, method: str, path: str) -> None:
    """Raise ScopeDenied unless this viewer may call this path. National may call everything."""
    if scope.level == "national":
        return
    if path in OPEN_EXACT or path.startswith(OPEN_PREFIX):
        return
    if path == "/sim/reset":
        raise ScopeDenied("only the national view can reset the simulation")
    if path.startswith("/national"):
        raise ScopeDenied("national views are not available to a state or LGA viewer")
    if path in ("/search", "/facilities"):
        return                                                          # rows are clamped to the viewer's state / LGA
    if path.startswith(("/cases", "/messages", "/responses", "/me/", "/people/", "/resupply-requests/")):
        return                                                          # case, message and person rows are checked by id
    m = re.match(r"^/state/([^/]+)(/.*)?$", path)
    if m and m.group(1) not in ("summary", "top"):
        code, rest = m.group(1), m.group(2) or ""
        if code != scope.state:
            raise ScopeDenied(f"this view cannot open {code}: it is limited to {scope.state}")
        if scope.level == "state":
            return
        lm = re.match(r"^/lga/([^/]+)(/.*)?$", rest)
        if lm:
            if lm.group(1) != scope.lga:
                raise ScopeDenied(f"this view is limited to LGA {scope.lga}")
            return
        fm = re.match(r"^/(?:facility|quality)/([^/]+)(/.*)?$", rest)
        if fm:
            home = _facility_home(fm.group(1))
            if home is None or home[1] != scope.lga:
                raise ScopeDenied(f"that facility is outside LGA {scope.lga}")
            return
        if _LGA_REST.match(rest):
            return
        raise ScopeDenied("an LGA view cannot open state-wide figures")
    # Older single-state aliases: allowed only when the thing they resolve to is in scope.
    lm = re.match(r"^/lga/([^/]+)/queue$", path)
    if lm:
        st = _lga_state(lm.group(1))
        if st == scope.state and (scope.level == "state" or lm.group(1) == scope.lga):
            return
        raise ScopeDenied("that LGA is outside this view")
    fm = re.match(r"^/(?:facility|quality)/([^/]+)$", path)
    if fm:
        home = _facility_home(fm.group(1))
        if home and home[0] == scope.state and (scope.level == "state" or home[1] == scope.lga):
            return
        raise ScopeDenied("that facility is outside this view")
    raise ScopeDenied("not available in this view")


# ---- rows inside handlers -----------------------------------------------------------------------------------
def clamp(state: str | None, lga_id: str | None = None) -> tuple[str | None, str | None]:
    """Narrow a requested (state, LGA) filter to the viewer's scope; refuse a request that names another state or LGA."""
    s = current()
    if s is None or s.level == "national":
        return state, lga_id
    if state and state != s.state:
        raise ScopeDenied(f"this view is limited to {s.state}")
    state = s.state
    if s.level == "lga":
        if lga_id and lga_id != s.lga:
            raise ScopeDenied(f"this view is limited to LGA {s.lga}")
        lga_id = s.lga
    return state, lga_id


def can_see(state_code: str | None, lga_id: str | None) -> bool:
    s = current()
    if s is None or s.level == "national":
        return True
    if state_code != s.state:
        return False
    return s.level == "state" or lga_id == s.lga


def check_case(case: dict) -> None:
    if not can_see(case.get("state_code"), case.get("lga_id")):
        raise ScopeDenied("that case is outside this view")


def check_person(person: dict) -> None:
    """National-level people are visible only to the national view."""
    s = current()
    if s is None or s.level == "national":
        return
    if person.get("level") == "national" or not can_see(person.get("state_code"), person.get("lga_id")):
        raise ScopeDenied("that person is outside this view")


def check_persona(person: dict) -> None:
    """The person you act as must sit inside the view you chose (a state board cannot act as a national officer)."""
    s = current()
    if s is None or s.level == "national":
        return
    if person.get("level") == "national" or person.get("state_code") != s.state:
        raise ScopeDenied(f"{person.get('name', 'that person')} is outside this view: choose someone in {s.state}")
    if s.level == "lga" and (person.get("level") == "state" or person.get("lga_id") != s.lga):
        raise ScopeDenied(f"{person.get('name', 'that person')} is outside this view: choose someone in LGA {s.lga}")
