"""Shared helpers for the API routers: database access, months, state lookup."""
from __future__ import annotations

from functools import lru_cache

from fastapi import HTTPException
from sqlalchemy import text

from ..config import states
from ..db import engine


@lru_cache
def _engine():
    return engine()


def q(sql: str, **params) -> list[dict]:
    with _engine().connect() as conn:
        return [dict(r._mapping) for r in conn.execute(text(sql), params)]


def one(sql: str, **params) -> dict | None:
    rows = q(sql, **params)
    return rows[0] if rows else None


@lru_cache
def months() -> list[str]:
    return [r["analysis_month"] for r in q("SELECT analysis_month FROM mart_national_month ORDER BY 1")]


def resolve_month(month: str | None) -> str:
    ms = months()
    if month is None:
        return ms[-1]
    if month not in ms:
        raise HTTPException(404, f"no analysis for {month}; available {ms[0]} to {ms[-1]}")
    return month


def state_info(code: str) -> dict:
    for st in states():
        if st["code"] == code:
            return {"code": st["code"], "name": st["name"], "zone": st["zone"]}
    raise HTTPException(404, f"unknown state {code!r}; covered: {[s['code'] for s in states()]}")
