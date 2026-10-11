"""PHC Sentinel API (proposal §8.2, extended to 12 states and a national view).

Read-only over the PostgreSQL marts. State endpoints live under /state/{code}/...;
the National Command Centre reads only precomputed state aggregates (/national/...).
The original single-state paths remain as deprecated aliases.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Literal

from fastapi import FastAPI, HTTPException, Path, Query, Request, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import text

from ..config import mapping, settings, states
from ..db import engine
from ..engines.dqr import PRODUCT_LABEL, RULES
from .. import viewas
from . import actions as actions_api
from . import cases as cases_api
from .explain import corroborated_by
from .thresholds import rule_severities, thresholds

app = FastAPI(title="PHC Sentinel API", version="0.2.0",
              description="Operational risk x data confidence for PHCs in 12 Nigerian states, with a national "
                          "roll-up. Facility list and boundaries are real (GRID3); all operational data are SIMULATED.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def view_as(request: Request, call_next):
    """Apply the 'View as' scope (see sentinel/viewas.py) to every request before any handler runs."""
    if request.method == "OPTIONS":
        return await call_next(request)
    path = request.url.path
    try:
        scope = viewas.parse(request.headers.get("x-view-as") or viewas.DEFAULT_HEADER)
        if scope is None:
            if path in viewas.OPEN_EXACT or path.startswith(viewas.OPEN_PREFIX):
                return await call_next(request)
            return JSONResponse({"detail": "No view selected: send X-View-As (national, state:<code> or lga:<code>:<lga_id>)"}, status_code=401)
        viewas.authorize(scope, request.method, path)
    except HTTPException as e:
        return JSONResponse({"detail": e.detail}, status_code=e.status_code)
    token = viewas.set_current(scope)
    try:
        return await call_next(request)
    finally:
        viewas.reset_current(token)


app.include_router(actions_api.router)
app.include_router(cases_api.router)

MONTH = Query(None, pattern=r"^\d{4}-\d{2}$", description="Analysis month YYYY-MM; defaults to the latest")
CODE = Path(..., description="State code from settings.yaml, e.g. bauchi")
BANNER = "Facility list and boundaries are real (GRID3). All operational reporting data are SIMULATED."
CACHE = "public, max-age=300"

# Map metrics for the national view: key -> (label, higher-is-worse). Keep in step with
# the Literal on /national/states.
METRICS = {
    "pct_act_now": ("% Act now", True),
    "pct_verification": ("% in Data Verification", True),
    "reporting_completeness": ("Reporting completeness", False),
    "pct_stale": ("% stale stock reports", True),
}


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


def facility_state(facility_id: str) -> str:
    r = one("SELECT state_code FROM dim_facility WHERE facility_id = :f", f=facility_id)
    if r is None:
        raise HTTPException(404, f"unknown facility {facility_id}")
    return r["state_code"]


def trend_window(month: str, n: int) -> list[str]:
    ms = months()
    i = ms.index(month)
    return ms[max(0, i - n + 1): i + 1]


# ---- Meta ------------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok", "latest_month": months()[-1], "states": len(states())}


@app.get("/meta/months")
def meta_months(response: Response):
    response.headers["Cache-Control"] = CACHE
    return {"months": months(), "latest": months()[-1]}


@app.get("/meta/states")
def meta_states(response: Response):
    """Covered states in display order, grouped by zone."""
    response.headers["Cache-Control"] = CACHE
    return {"default": settings()["default_state"], "zones": settings()["zones"],
            "states": [state_info(st["code"]) for st in states()]}


@app.get("/meta/data-labels")
def data_labels():
    return {"banner": BANNER,
            "tables": q("SELECT table_name, data_class, description FROM meta_data_labels ORDER BY data_class, table_name")}


@app.get("/meta/settings")
def meta_settings():
    return {"settings": settings(), "mapping": mapping()}


@app.get("/meta/lgas")
def meta_lgas(state: str):
    """LGA names for a state: what the View-as switcher offers. Names only, no figures."""
    state_info(state)
    return {"lgas": q("SELECT lga_id, lga FROM dim_lga WHERE state_code = :s ORDER BY lga", s=state)}


@app.get("/meta/thresholds")
def meta_thresholds():
    """Every threshold in config/settings.yaml with its basis tag, for the Method page."""
    return {"thresholds": thresholds(), "dhis2_dataset": mapping()["dhis2"]["dataset"]["name"]}


@app.get("/meta/rules")
def meta_rules():
    """The data quality rules, with the severities each can produce (read from the engine source)."""
    sev = rule_severities()
    return {"rules": [{"rule_id": k, "family": f, "label": lbl, "severities": sev.get(k, [])}
                      for k, (f, lbl) in RULES.items()]}


# ---- National Command Centre (state aggregates only) ------------------------------------
@lru_cache(maxsize=64)
def _national_summary(m: str) -> dict:
    nat = one("SELECT * FROM mart_national_month WHERE analysis_month = :m", m=m)
    zones = q("SELECT * FROM mart_zone_month WHERE analysis_month = :m", m=m)
    order = {z: i for i, z in enumerate(settings()["zones"])}
    zones.sort(key=lambda z: order.get(z["zone"], 99))
    trend = q("""SELECT analysis_month, act_now, verify_then_act, verification, monitor, facilities,
                        reporting_completeness, pct_stale FROM mart_national_month ORDER BY analysis_month""")
    return {"month": m, "banner": BANNER, "kpis": nat, "zones": zones, "trend": trend,
            "metrics": {k: {"label": v[0], "higher_is_worse": v[1]} for k, v in METRICS.items()}}


@app.get("/national/summary")
def national_summary(response: Response, month: str | None = MONTH):
    """Headline numbers for all covered states, the six zones side by side, and the national trend."""
    response.headers["Cache-Control"] = CACHE
    return _national_summary(resolve_month(month))


@lru_cache(maxsize=64)
def _national_states(m: str, metric: str) -> dict:
    rows = q("SELECT * FROM mart_state_month WHERE analysis_month = :m", m=m)
    window = trend_window(m, settings()["national"]["trend_months"])
    tr = q("""SELECT state_code, analysis_month, act_now, verify_then_act, verification, monitor, facilities,
                     pct_act_now, pct_verification, reporting_completeness, pct_stale
              FROM mart_state_month WHERE analysis_month = ANY(:w) ORDER BY analysis_month""", w=window)
    top = q("""SELECT state_code, lga_id, lga, lga_rank, facilities, act_now, verify_then_act, verification,
                      needs_attention, reporting_completeness
               FROM mart_lga_month WHERE analysis_month = :m AND lga_rank <= :n ORDER BY state_code, lga_rank""",
            m=m, n=settings()["national"]["top_lgas_in_brief"])
    worse = METRICS[metric][1]
    order = {st["code"]: i for i, st in enumerate(states())}
    for r in rows:
        r["value"] = r[metric]
        r["trend"] = [t for t in tr if t["state_code"] == r["state_code"]]
        r["top_lgas"] = [t for t in top if t["state_code"] == r["state_code"]]
    rows.sort(key=lambda r: order[r["state_code"]])
    ranked = sorted(rows, key=lambda r: (r["value"] is None, -(r["value"] or 0) if worse else (r["value"] or 0)))
    for i, r in enumerate(ranked, 1):
        r["metric_rank"] = i
    return {"month": m, "metric": metric, "metric_label": METRICS[metric][0], "higher_is_worse": worse,
            "trend_months": window, "status_thresholds": settings()["national"]["status"], "states": rows}


@app.get("/national/states")
def national_states(response: Response, month: str | None = MONTH,
                    metric: Literal["pct_act_now", "pct_verification", "reporting_completeness", "pct_stale"] = "pct_act_now"):
    """One row per covered state: counts, rates, status, a short trend and the top LGAs (the state brief).
    `value` and `metric_rank` follow the selected map metric."""
    response.headers["Cache-Control"] = CACHE
    return _national_states(resolve_month(month), metric)


@lru_cache
def _national_geo() -> dict:
    rows = q("SELECT grid3_code, name, state_code, ST_AsGeoJSON(geom, 3) AS g FROM dim_state_geo")
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": json.loads(r.pop("g")), "properties": {**r, "covered": r["state_code"] is not None}}
        for r in rows]}


@app.get("/national/geo")
def national_geo(response: Response):
    """All 36 states + FCT. `state_code` is null for states not in the demo."""
    response.headers["Cache-Control"] = "public, max-age=86400"
    return _national_geo()


# ---- State portal ------------------------------------------------------------------------
@app.get("/state/{code}/summary")
def state_summary(code: str = CODE, month: str | None = MONTH):
    st = state_info(code)
    m = resolve_month(month)
    lgas = q("SELECT * FROM mart_lga_month WHERE state_code = :s AND analysis_month = :m ORDER BY lga_rank", s=code, m=m)
    kpi = one("SELECT * FROM mart_state_month WHERE state_code = :s AND analysis_month = :m", s=code, m=m)
    kpi["stale_commodity_reports"] = kpi["stale_commodity"]
    matrix = q("""
        SELECT CASE WHEN risk_n >= 2 THEN 'HIGH_OR_CRITICAL' ELSE 'NORMAL_OR_WATCH' END AS risk,
               CASE WHEN data_confidence = 'LOW' THEN 'LOW' ELSE 'HIGH_OR_MODERATE' END AS confidence,
               count(*) AS n
        FROM mart_facility_month WHERE state_code = :s AND analysis_month = :m GROUP BY 1, 2""", s=code, m=m)
    risk = q("""SELECT operational_risk, count(*) n FROM mart_facility_month
                WHERE state_code = :s AND analysis_month = :m GROUP BY 1""", s=code, m=m)
    conf = q("""SELECT data_confidence, count(*) n FROM mart_facility_month
                WHERE state_code = :s AND analysis_month = :m GROUP BY 1""", s=code, m=m)
    domains = q("""SELECT top_domain, count(*) n FROM mart_facility_month
                   WHERE state_code = :s AND analysis_month = :m AND queue = 'RESOURCE_ACTION' GROUP BY 1""", s=code, m=m)
    trend = q("""SELECT analysis_month, action, act_now, verify_then_act, verification, monitor
                 FROM mart_state_month WHERE state_code = :s ORDER BY 1""", s=code)
    # Warm-up: until enough history exists no facility can be classed Monitor, so the leading months are almost
    # entirely Data Verification. Flag them so the UI can start the chart after them.
    warm = True
    for t in trend:
        warm = warm and t["monitor"] == 0
        t["warmup"] = warm
    return {"month": m, "state": st, "kpis": kpi, "matrix": matrix, "risk": risk, "confidence": conf,
            "action_by_domain": domains, "lgas": lgas, "trend": trend}


@app.get("/state/{code}/insights")
def state_insights(code: str = CODE, month: str | None = MONTH):
    """Facts for the 'This week' panel, all computed from the analysis tables."""
    state_info(code)
    m = resolve_month(month)
    most_act = one("""SELECT lga_id, lga, act_now, action FROM mart_lga_month WHERE state_code = :s AND analysis_month = :m
                      ORDER BY act_now DESC, action DESC, lga LIMIT 1""", s=code, m=m)
    lowest_ontime = one("""SELECT lga_id, lga, on_time_rate, facilities FROM mart_lga_month
                           WHERE state_code = :s AND analysis_month = :m ORDER BY on_time_rate ASC, lga LIMIT 1""", s=code, m=m)
    min_months = settings()["commodity"]["min_months"]
    shortage = q("""SELECT c.commodity_code, count(*) AS n FROM mart_commodity_month c
                    JOIN dim_facility f USING (facility_id)
                    WHERE f.state_code = :s AND c.analysis_month = :m AND c.has_record AND NOT c.stale_flag AND c.amc > 0
                      AND c.physical_stock / c.amc < :mn GROUP BY 1 ORDER BY n DESC""", s=code, m=m, mn=min_months)
    for r in shortage:
        r["product"] = PRODUCT_LABEL.get(r["commodity_code"], r["commodity_code"])
    return {"month": m, "most_act_now_lga": most_act, "lowest_on_time_lga": lowest_ontime,
            "shortage_min_months": min_months, "shortage_by_product": shortage}


@app.get("/state/{code}/coords")
def state_coords(code: str = CODE):
    """Facilities with questionable coordinates. 'outside_state' is outside every LGA polygon of the state;
    'unverified' is coord_status = 'location_unverified' (further than geography.near_boundary_km outside the
    facility's own LGA). They are different definitions; neither is substituted for the other."""
    state_info(code)
    return one("""SELECT count(*) AS facilities,
                         sum((coord_status = 'location_unverified')::int) AS unverified,
                         sum((coord_status = 'near_boundary')::int) AS near_boundary,
                         sum((NOT ST_Intersects(geom, (SELECT ST_Union(geom) FROM dim_lga WHERE state_code = :s)))::int)
                             AS outside_state
                  FROM dim_facility WHERE state_code = :s""", s=code)


FACILITY_SORTS = {"name": "f.name", "lga": "f.lga", "queue": "fm.queue", "risk": "fm.risk_n",
                  "confidence": "fm.conf_n", "last_dhis2": "l.last_dhis2", "last_nhlmis": "fm.nhlmis_age_days",
                  "rank": "fm.rank_state", "state": "f.state_code"}


def facility_directory(state: str | None, month: str | None, text_q: str | None = None, lga_id: str | None = None,
                       queue: str | None = None, tag: str | None = None, area: str | None = None,
                       risk: str | None = None, confidence: str | None = None, stale: bool = False,
                       unverified: bool = False, sort: str = "name", dir: str = "asc", page: int = 1,
                       page_size: int = 25) -> dict:
    """PHC directory with its status for the month, for one state or (state=None) all. Filters and sort are whitelisted."""
    state, lga_id = viewas.clamp(state, lga_id)          # a state or LGA view only ever gets its own rows
    m = resolve_month(month)
    if sort not in FACILITY_SORTS:
        raise HTTPException(422, f"sort must be one of {sorted(FACILITY_SORTS)}")
    where = ["fm.analysis_month = :m"]
    p: dict = {"m": m}
    if state:
        where.append("f.state_code = :s")
        p["s"] = state
    if text_q:
        where.append("(f.name ILIKE :q OR f.ward ILIKE :q OR f.facility_id ILIKE :q)")
        p["q"] = f"%{text_q}%"
    for col, val in (("f.lga_id", lga_id), ("fm.queue", queue), ("fm.tag", tag.upper() if tag else None),
                     ("fm.top_domain", area), ("fm.operational_risk", risk.upper() if risk else None),
                     ("fm.data_confidence", confidence.upper() if confidence else None)):
        if val:
            key = col.replace(".", "_")
            where.append(f"{col} = :{key}")
            p[key] = val
    if stale:
        where.append("fm.nhlmis_stale")
    if unverified:
        where.append("f.coord_status = 'location_unverified'")
    base = f"""FROM dim_facility f JOIN mart_facility_month fm ON fm.facility_id = f.facility_id
               LEFT JOIN LATERAL (SELECT max(h.analysis_month) AS last_dhis2 FROM mart_facility_month h
                                  WHERE h.facility_id = f.facility_id AND h.analysis_month <= :m AND h.report_received) l ON true
               WHERE {' AND '.join(where)}"""
    total = one(f"SELECT count(*) AS n {base}", **p)["n"]
    rows = q(f"""SELECT f.facility_id, f.name, f.ward, f.state_code, f.lga_id, f.lga, f.coord_status, fm.queue, fm.tag,
                        fm.operational_risk, fm.data_confidence, fm.top_domain, fm.nhlmis_age_days, fm.nhlmis_stale,
                        fm.report_received, l.last_dhis2
                 {base} ORDER BY {FACILITY_SORTS[sort]} {dir} NULLS LAST, f.facility_id
                 LIMIT :lim OFFSET :off""", lim=page_size, off=(page - 1) * page_size, **p)
    return {"month": m, "total": total, "page": page, "page_size": page_size, "facilities": rows}


@app.get("/state/{code}/facilities")
def state_facilities(code: str = CODE, month: str | None = MONTH, q_: str | None = Query(None, alias="q"),
                     lga_id: str | None = None, queue: str | None = None, tag: str | None = None,
                     area: str | None = None, risk: str | None = None, confidence: str | None = None,
                     stale: bool = False, unverified: bool = False, sort: str = "name",
                     dir: str = Query("asc", pattern="^(asc|desc)$"), page: int = Query(1, ge=1),
                     page_size: int = Query(25, ge=1, le=100)):
    """Directory of every PHC in the state."""
    state_info(code)
    return facility_directory(code, month, q_, lga_id, queue, tag, area, risk, confidence, stale, unverified,
                              sort, dir, page, page_size)


@app.get("/facilities")
def all_facilities(month: str | None = MONTH, state: str | None = None, q_: str | None = Query(None, alias="q"),
                   lga_id: str | None = None, queue: str | None = None, tag: str | None = None,
                   area: str | None = None, risk: str | None = None, confidence: str | None = None,
                   stale: bool = False, unverified: bool = False, sort: str = "name",
                   dir: str = Query("asc", pattern="^(asc|desc)$"), page: int = Query(1, ge=1),
                   page_size: int = Query(25, ge=1, le=100)):
    """Directory of every PHC in every state, or in one state when `state` is given. Each row carries its state_code."""
    if state:
        state_info(state)
    return facility_directory(state, month, q_, lga_id, queue, tag, area, risk, confidence, stale, unverified,
                              sort, dir, page, page_size)


@app.get("/search")
def search(q_: str = Query(..., alias="q", min_length=2), month: str | None = MONTH, limit: int = Query(8, le=25)):
    """Facility search across every state (top-bar search); each hit carries its state_code."""
    return facility_directory(None, month, q_, page_size=limit)


@app.get("/state/{code}/top")
def state_top(code: str = CODE, month: str | None = MONTH, limit: int = Query(10, le=100)):
    """Top of the state-wide action and verification queues."""
    state_info(code)
    m = resolve_month(month)
    sql = """SELECT q.facility_id, f.name, q.lga, q.lga_id, q.queue, q.tag, q.rank_state, q.operational_risk,
                    q.data_confidence, q.top_domain, q.evidence_summary, q.next_action
             FROM mart_queue q JOIN dim_facility f USING (facility_id)
             WHERE q.state_code = :s AND q.analysis_month = :m AND q.queue = :queue ORDER BY q.rank_state LIMIT :n"""
    return {"month": m,
            "action": q(sql, s=code, m=m, queue="RESOURCE_ACTION", n=limit),
            "verification": q(sql, s=code, m=m, queue="DATA_VERIFICATION", n=limit)}


@app.get("/state/{code}/geo/lgas")
def geo_lgas(code: str = CODE, month: str | None = MONTH, lga_id: str | None = None):
    state_info(code)
    _, lga_id = viewas.clamp(code, lga_id)          # an LGA view gets only its own polygon and numbers
    m = resolve_month(month)
    rows = q("""SELECT l.lga_id, l.lga, ST_AsGeoJSON(ST_SimplifyPreserveTopology(l.geom, 0.002), 5) AS g,
                       s.facilities, s.action, s.act_now, s.verify_then_act, s.verification, s.monitor,
                       s.needs_attention, s.lga_rank, s.reporting_completeness
                FROM dim_lga l LEFT JOIN mart_lga_month s ON s.lga_id = l.lga_id AND s.analysis_month = :m
                WHERE l.state_code = :s AND (CAST(:lga AS text) IS NULL OR l.lga_id = :lga)""", s=code, m=m, lga=lga_id)
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": json.loads(r.pop("g")), "properties": r} for r in rows]}


@app.get("/state/{code}/geo/facilities")
def geo_facilities(code: str = CODE, month: str | None = MONTH, lga_id: str | None = None):
    """Facilities drawn on the map. "Location unverified" points are left off (they stay in every queue)."""
    state_info(code)
    _, lga_id = viewas.clamp(code, lga_id)
    m = resolve_month(month)
    rows = q("""SELECT f.facility_id, f.name, f.lga_id, f.longitude, f.latitude, f.coord_status, q.queue, q.tag
                FROM dim_facility f JOIN mart_queue q ON q.facility_id = f.facility_id AND q.analysis_month = :m
                WHERE f.state_code = :s AND f.coord_status <> 'location_unverified'
                  AND (CAST(:lga AS text) IS NULL OR f.lga_id = :lga)""", s=code, m=m, lga=lga_id)
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [r.pop("longitude"), r.pop("latitude")]},
         "properties": r} for r in rows]}


@app.get("/state/{code}/lga/{lga_id}/queue")
def lga_queue(code: str = CODE, lga_id: str = Path(...), month: str | None = MONTH):
    st = state_info(code)
    m = resolve_month(month)
    summary = one("SELECT * FROM mart_lga_month WHERE state_code = :s AND analysis_month = :m AND lga_id = :l",
                  s=code, m=m, l=lga_id)
    if summary is None:
        raise HTTPException(404, f"unknown LGA {lga_id} in {st['name']}")
    n_lgas = one("SELECT count(*) n FROM mart_lga_month WHERE state_code = :s AND analysis_month = :m", s=code, m=m)["n"]
    rows = q("""SELECT q.facility_id, f.name, f.ward, f.coord_status, q.queue, q.tag, q.rank_lga, q.rank_state,
                       q.operational_risk, q.data_confidence, q.top_domain, q.evidence_summary, q.next_action,
                       q.consecutive_missing, q.nhlmis_age_days, fm.late_days, fm.report_received,
                       fm.days_since_deadline_missed, fm.reliable_history, fm.silent_flag, fm.submission_date,
                       fm.overdue_days, lr.last_report_month, q.explanation
                FROM mart_queue q JOIN dim_facility f USING (facility_id)
                LEFT JOIN LATERAL (SELECT max(h.analysis_month) AS last_report_month FROM mart_facility_month h
                                   WHERE h.facility_id = q.facility_id AND h.analysis_month <= q.analysis_month
                                     AND h.report_received) lr ON true
                JOIN mart_facility_month fm ON fm.facility_id = q.facility_id AND fm.analysis_month = q.analysis_month
                WHERE q.analysis_month = :m AND q.lga_id = :l ORDER BY q.queue, q.rank_lga""", m=m, l=lga_id)
    by = {"RESOURCE_ACTION": [], "DATA_VERIFICATION": [], "MONITOR": []}
    for r in rows:
        r["corroborated_by"] = corroborated_by(r.pop("explanation"), r["top_domain"], r["operational_risk"])
        by[r["queue"]].append(r)
    return {"month": m, "state": st, "lgas_in_state": n_lgas, "lga": summary, "action": by["RESOURCE_ACTION"],
            "verification": by["DATA_VERIFICATION"], "monitor": by["MONITOR"]}


@app.get("/state/{code}/facility/{facility_id}")
def facility(code: str = CODE, facility_id: str = Path(...), month: str | None = MONTH):
    st = state_info(code)
    m = resolve_month(month)
    info = one("""SELECT facility_id, name, state, state_code, lga_id, lga, ward, latitude, longitude, facility_type,
                          ownership_type, functional_status, coord_status, dist_to_lga_m, nhfr_code
                   FROM dim_facility WHERE facility_id = :f AND state_code = :s""", f=facility_id, s=code)
    if info is None:
        raise HTTPException(404, f"unknown facility {facility_id} in {st['name']}")
    status = one("""SELECT fm.*, q.explanation FROM mart_facility_month fm
                    JOIN mart_queue q USING (facility_id, analysis_month)
                    WHERE fm.facility_id = :f AND fm.analysis_month = :m""", f=facility_id, m=m)
    if status is None:
        raise HTTPException(404, f"no analysis for facility {facility_id} in {m}")
    explanation = status.pop("explanation")
    status["corroborated_by"] = corroborated_by(explanation, status["top_domain"], status["operational_risk"])
    # Trends up to the analysis month: service volumes vs baseline, commodity position, reporting history.
    services = q("""SELECT analysis_month, indicator, value, expected, z, seasonal FROM mart_service_baseline
                    WHERE facility_id = :f AND analysis_month <= :m AND indicator IN ('opd', 'confirmed_malaria')
                    ORDER BY analysis_month""", f=facility_id, m=m)
    commodity = q("""SELECT period_start, commodity_code, physical_stock, amc, days_out_of_stock, submission_date
                     FROM fact_nhlmis_bimonthly WHERE facility_id = :f
                       AND submission_date < (:m || '-01')::date + interval '1 month' + interval '30 days'
                     ORDER BY period_start""", f=facility_id, m=m)
    reporting = q("""SELECT analysis_month, report_received, late_days, data_confidence, operational_risk, queue
                     FROM mart_facility_month WHERE facility_id = :f AND analysis_month <= :m
                     ORDER BY analysis_month""", f=facility_id, m=m)
    return {"month": m, "state": st, "facility": info, "status": status, "explanation": explanation,
            "trends": {"services": services, "commodity": commodity, "reporting": reporting}}


@app.get("/state/{code}/quality/{facility_id}")
def quality(code: str = CODE, facility_id: str = Path(...), month: str | None = MONTH):
    state_info(code)
    if facility_state(facility_id) != code:
        raise HTTPException(404, f"facility {facility_id} is not in {code}")
    m = resolve_month(month)
    checks = q("""SELECT rule_id, family, severity, source, field, value, explanation, source_date
                  FROM fact_quality_flags WHERE facility_id = :f AND analysis_month = :m
                  ORDER BY CASE severity WHEN 'severe' THEN 0 WHEN 'major' THEN 1 ELSE 2 END""", f=facility_id, m=m)
    fresh = q("""SELECT commodity_code, has_record, period_start, nhlmis_period_end, nhlmis_age_days, stale_flag,
                        next_expected_period FROM mart_commodity_month WHERE facility_id = :f AND analysis_month = :m""",
              f=facility_id, m=m)
    return {"month": m, "checks": checks, "freshness": fresh}


# ---- Deprecated single-state aliases (default state, or resolved from the id) --------------
@app.get("/state/summary", deprecated=True)
def legacy_state_summary(month: str | None = MONTH):
    return state_summary(settings()["default_state"], month)


@app.get("/state/top", deprecated=True)
def legacy_state_top(month: str | None = MONTH, limit: int = Query(10, le=100)):
    return state_top(settings()["default_state"], month, limit)


@app.get("/geo/lgas", deprecated=True)
def legacy_geo_lgas(month: str | None = MONTH):
    return geo_lgas(settings()["default_state"], month)


@app.get("/geo/facilities", deprecated=True)
def legacy_geo_facilities(month: str | None = MONTH, lga_id: str | None = None):
    return geo_facilities(settings()["default_state"], month, lga_id)


@app.get("/lga/{lga_id}/queue", deprecated=True)
def legacy_lga_queue(lga_id: str, month: str | None = MONTH):
    r = one("SELECT state_code FROM dim_lga WHERE lga_id = :l", l=lga_id)
    if r is None:
        raise HTTPException(404, f"unknown LGA {lga_id}")
    return lga_queue(r["state_code"], lga_id, month)


@app.get("/facility/{facility_id}", deprecated=True)
def legacy_facility(facility_id: str, month: str | None = MONTH):
    return facility(facility_state(facility_id), facility_id, month)


@app.get("/quality/{facility_id}", deprecated=True)
def legacy_quality(facility_id: str, month: str | None = MONTH):
    return quality(facility_state(facility_id), facility_id, month)
