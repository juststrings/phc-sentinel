"""PHC Sentinel API (proposal §8.2). Read-only over the PostgreSQL marts."""
from __future__ import annotations

import json
from functools import lru_cache

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from ..config import mapping, settings
from ..db import engine
from ..engines.dqr import PRODUCT_LABEL, RULES

app = FastAPI(title="PHC Sentinel API", version="0.1.0",
              description="Operational risk x data confidence for Bauchi State PHCs. Operational data are SIMULATED.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])

MONTH = Query(None, pattern=r"^\d{4}-\d{2}$", description="Analysis month YYYY-MM; defaults to the latest")


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
    return [r["analysis_month"] for r in q("SELECT DISTINCT analysis_month FROM mart_lga_month ORDER BY 1")]


def resolve_month(month: str | None) -> str:
    ms = months()
    if month is None:
        return ms[-1]
    if month not in ms:
        raise HTTPException(404, f"no analysis for {month}; available {ms[0]} to {ms[-1]}")
    return month


@app.get("/health")
def health():
    return {"status": "ok", "latest_month": months()[-1]}


@app.get("/meta/months")
def meta_months():
    return {"months": months(), "latest": months()[-1]}


@app.get("/meta/data-labels")
def data_labels():
    return {"banner": "Facility list and boundaries are real (GRID3). All operational reporting data are SIMULATED.",
            "tables": q("SELECT table_name, data_class, description FROM meta_data_labels ORDER BY data_class, table_name")}


@app.get("/meta/settings")
def meta_settings():
    return {"settings": settings(), "mapping": mapping()}


@app.get("/meta/state")
def meta_state():
    return one("""SELECT (SELECT min(state) FROM dim_lga) AS state, (SELECT count(*) FROM dim_lga) AS lgas,
                         (SELECT count(*) FROM dim_facility) AS facilities""")


@app.get("/meta/rules")
def meta_rules():
    """The data quality rules, straight from the engine's rule table."""
    seen: dict[str, list[str]] = {}
    for r in q("SELECT DISTINCT rule_id, severity FROM fact_quality_flags"):
        seen.setdefault(r["rule_id"], []).append(r["severity"])
    return {"rules": [{"rule_id": k, "family": f, "label": lbl, "severities": sorted(seen.get(k, []))}
                      for k, (f, lbl) in RULES.items()]}


@app.get("/meta/coords")
def meta_coords():
    """Facilities with questionable coordinates. 'outside_state' is the D8 count (outside every Bauchi LGA
    polygon); 'outside_lga' is coord_status = 'invalid' (more than 5 km outside the facility's own LGA)."""
    r = one("""SELECT count(*) AS facilities,
                      sum((coord_status = 'invalid')::int) AS outside_lga,
                      sum((coord_status = 'near_boundary')::int) AS near_boundary,
                      sum((NOT ST_Intersects(geom, (SELECT ST_Union(geom) FROM dim_lga)))::int) AS outside_state
               FROM dim_facility""")
    return r


@app.get("/state/insights")
def state_insights(month: str | None = MONTH):
    """Facts for the 'This week' panel, all computed from the analysis tables."""
    m = resolve_month(month)
    most_act = one("""SELECT lga_id, lga, act_now, action FROM mart_lga_month WHERE analysis_month = :m
                      ORDER BY act_now DESC, action DESC, lga LIMIT 1""", m=m)
    lowest_ontime = one("""SELECT lga_id, lga, on_time_rate, facilities FROM mart_lga_month
                           WHERE analysis_month = :m ORDER BY on_time_rate ASC, lga LIMIT 1""", m=m)
    min_months = settings()["commodity"]["min_months"]
    shortage = q("""SELECT commodity_code, count(*) AS n FROM mart_commodity_month
                    WHERE analysis_month = :m AND has_record AND NOT stale_flag AND amc > 0
                      AND physical_stock / amc < :mn GROUP BY 1 ORDER BY n DESC""", m=m, mn=min_months)
    for r in shortage:
        r["product"] = PRODUCT_LABEL.get(r["commodity_code"], r["commodity_code"])
    return {"month": m, "most_act_now_lga": most_act, "lowest_on_time_lga": lowest_ontime,
            "shortage_min_months": min_months, "shortage_by_product": shortage}


@app.get("/facilities")
def facilities(month: str | None = MONTH, q_: str | None = Query(None, alias="q"), lga_id: str | None = None,
               queue: str | None = None, area: str | None = None, risk: str | None = None,
               confidence: str | None = None, stale: bool = False, coords: bool = False,
               sort: str = "name", dir: str = Query("asc", pattern="^(asc|desc)$"),
               page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    """Directory of every PHC with its status for the month. Filters and sort are whitelisted."""
    m = resolve_month(month)
    sort_cols = {"name": "f.name", "lga": "f.lga", "queue": "fm.queue", "risk": "fm.risk_n",
                 "confidence": "fm.conf_n", "last_dhis2": "l.last_dhis2", "last_nhlmis": "fm.nhlmis_age_days",
                 "rank": "fm.rank_state"}
    if sort not in sort_cols:
        raise HTTPException(422, f"sort must be one of {sorted(sort_cols)}")
    where = ["fm.analysis_month = :m"]
    p: dict = {"m": m}
    if q_:
        where.append("(f.name ILIKE :q OR f.ward ILIKE :q OR f.facility_id ILIKE :q)")
        p["q"] = f"%{q_}%"
    for col, val in (("f.lga_id", lga_id), ("fm.queue", queue), ("fm.top_domain", area),
                     ("fm.operational_risk", risk.upper() if risk else None),
                     ("fm.data_confidence", confidence.upper() if confidence else None)):
        if val:
            key = col.replace(".", "_")
            where.append(f"{col} = :{key}")
            p[key] = val
    if stale:
        where.append("fm.nhlmis_stale")
    if coords:
        where.append("f.coord_status = 'invalid'")
    base = f"""FROM dim_facility f JOIN mart_facility_month fm ON fm.facility_id = f.facility_id
               LEFT JOIN LATERAL (SELECT max(h.analysis_month) AS last_dhis2 FROM mart_facility_month h
                                  WHERE h.facility_id = f.facility_id AND h.analysis_month <= :m AND h.report_received) l ON true
               WHERE {' AND '.join(where)}"""
    total = one(f"SELECT count(*) AS n {base}", **p)["n"]
    rows = q(f"""SELECT f.facility_id, f.name, f.ward, f.lga_id, f.lga, f.coord_status, fm.queue, fm.tag,
                        fm.operational_risk, fm.data_confidence, fm.top_domain, fm.nhlmis_age_days, fm.nhlmis_stale,
                        fm.report_received, l.last_dhis2
                 {base} ORDER BY {sort_cols[sort]} {dir} NULLS LAST, f.facility_id
                 LIMIT :lim OFFSET :off""", lim=page_size, off=(page - 1) * page_size, **p)
    return {"month": m, "total": total, "page": page, "page_size": page_size, "facilities": rows}


@app.get("/state/summary")
def state_summary(month: str | None = MONTH):
    m = resolve_month(month)
    lgas = q("SELECT * FROM mart_lga_month WHERE analysis_month = :m ORDER BY lga_rank", m=m)
    kpi = one("""
        SELECT count(*) AS facilities,
               sum((queue = 'RESOURCE_ACTION')::int) AS action,
               sum((tag = 'ACT NOW')::int) AS act_now,
               sum((tag = 'VERIFY THEN ACT')::int) AS verify_then_act,
               sum((queue = 'DATA_VERIFICATION')::int) AS verification,
               sum((queue = 'MONITOR')::int) AS monitor,
               round(avg(report_received::int)::numeric, 3) AS reporting_completeness,
               round(avg(on_time_flag::int)::numeric, 3) AS on_time_rate,
               sum(nhlmis_stale::int) AS stale_commodity_reports,
               sum(silent_flag::int) AS silent
        FROM mart_facility_month WHERE analysis_month = :m""", m=m)
    matrix = q("""
        SELECT CASE WHEN risk_n >= 2 THEN 'HIGH_OR_CRITICAL' ELSE 'NORMAL_OR_WATCH' END AS risk,
               CASE WHEN data_confidence = 'LOW' THEN 'LOW' ELSE 'HIGH_OR_MODERATE' END AS confidence,
               count(*) AS n
        FROM mart_facility_month WHERE analysis_month = :m GROUP BY 1, 2""", m=m)
    risk = q("SELECT operational_risk, count(*) n FROM mart_facility_month WHERE analysis_month = :m GROUP BY 1", m=m)
    conf = q("SELECT data_confidence, count(*) n FROM mart_facility_month WHERE analysis_month = :m GROUP BY 1", m=m)
    domains = q("""SELECT top_domain, count(*) n FROM mart_facility_month
                   WHERE analysis_month = :m AND queue = 'RESOURCE_ACTION' GROUP BY 1""", m=m)
    trend = q("""SELECT analysis_month, sum(action) action, sum(act_now) act_now, sum(verify_then_act) verify_then_act,
                        sum(verification) verification, sum(monitor) monitor
                 FROM mart_lga_month GROUP BY 1 ORDER BY 1""")
    # Warm-up: until enough history exists no facility can be classed Monitor, so the leading months
    # are almost entirely Data Verification. Flag them so the UI can start the chart after them.
    warm = True
    for t in trend:
        warm = warm and t["monitor"] == 0
        t["warmup"] = warm
    return {"month": m, "kpis": kpi, "matrix": matrix, "risk": risk, "confidence": conf,
            "action_by_domain": domains, "lgas": lgas, "trend": trend}


@app.get("/state/top")
def state_top(month: str | None = MONTH, limit: int = Query(10, le=100)):
    """Top of the state-wide action and verification queues."""
    m = resolve_month(month)
    sql = """SELECT q.facility_id, f.name, q.lga, q.queue, q.tag, q.rank_state, q.operational_risk, q.data_confidence,
                    q.top_domain, q.evidence_summary, q.next_action
             FROM mart_queue q JOIN dim_facility f USING (facility_id)
             WHERE q.analysis_month = :m AND q.queue = :queue ORDER BY q.rank_state LIMIT :n"""
    return {"month": m,
            "action": q(sql, m=m, queue="RESOURCE_ACTION", n=limit),
            "verification": q(sql, m=m, queue="DATA_VERIFICATION", n=limit)}


@app.get("/geo/lgas")
def geo_lgas(month: str | None = MONTH):
    m = resolve_month(month)
    rows = q("""SELECT l.lga_id, l.lga, ST_AsGeoJSON(ST_SimplifyPreserveTopology(l.geom, 0.002), 5) AS g,
                       s.facilities, s.action, s.act_now, s.verify_then_act, s.verification, s.monitor, s.needs_attention, s.lga_rank,
                       s.reporting_completeness
                FROM dim_lga l LEFT JOIN mart_lga_month s ON s.lga_id = l.lga_id AND s.analysis_month = :m""", m=m)
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": json.loads(r.pop("g")), "properties": r} for r in rows]}


@app.get("/geo/facilities")
def geo_facilities(month: str | None = MONTH, lga_id: str | None = None):
    m = resolve_month(month)
    rows = q("""SELECT f.facility_id, f.name, f.lga_id, f.longitude, f.latitude, q.queue, q.tag
                FROM dim_facility f JOIN mart_queue q ON q.facility_id = f.facility_id AND q.analysis_month = :m
                WHERE f.coord_status <> 'invalid' AND (CAST(:lga AS text) IS NULL OR f.lga_id = :lga)""", m=m, lga=lga_id)
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [r.pop("longitude"), r.pop("latitude")]},
         "properties": r} for r in rows]}


@app.get("/lga/{lga_id}/queue")
def lga_queue(lga_id: str, month: str | None = MONTH):
    m = resolve_month(month)
    summary = one("SELECT * FROM mart_lga_month WHERE analysis_month = :m AND lga_id = :l", m=m, l=lga_id)
    if summary is None:
        raise HTTPException(404, f"unknown LGA {lga_id}")
    rows = q("""SELECT q.facility_id, f.name, f.ward, q.queue, q.tag, q.rank_lga, q.rank_state, q.operational_risk,
                       q.data_confidence, q.top_domain, q.evidence_summary, q.next_action,
                       q.consecutive_missing, q.nhlmis_age_days, fm.late_days, fm.report_received,
                       fm.days_since_deadline_missed, fm.reliable_history, fm.silent_flag, fm.submission_date,
                       fm.overdue_days, lr.last_report_month
                FROM mart_queue q JOIN dim_facility f USING (facility_id)
                LEFT JOIN LATERAL (SELECT max(h.analysis_month) AS last_report_month FROM mart_facility_month h
                                   WHERE h.facility_id = q.facility_id AND h.analysis_month <= q.analysis_month
                                     AND h.report_received) lr ON true
                JOIN mart_facility_month fm ON fm.facility_id = q.facility_id AND fm.analysis_month = q.analysis_month
                WHERE q.analysis_month = :m AND q.lga_id = :l ORDER BY q.queue, q.rank_lga""", m=m, l=lga_id)
    by = {"RESOURCE_ACTION": [], "DATA_VERIFICATION": [], "MONITOR": []}
    for r in rows:
        by[r["queue"]].append(r)
    return {"month": m, "lga": summary, "action": by["RESOURCE_ACTION"], "verification": by["DATA_VERIFICATION"],
            "monitor": by["MONITOR"]}


@app.get("/facility/{facility_id}")
def facility(facility_id: str, month: str | None = MONTH):
    m = resolve_month(month)
    info = one("""SELECT facility_id, name, state, lga_id, lga, ward, latitude, longitude, facility_type,
                          ownership_type, functional_status, coord_status, nhfr_code
                   FROM dim_facility WHERE facility_id = :f""", f=facility_id)
    if info is None:
        raise HTTPException(404, f"unknown facility {facility_id}")
    status = one("""SELECT fm.*, q.explanation, q.rank_lga FROM mart_facility_month fm
                    JOIN mart_queue q USING (facility_id, analysis_month)
                    WHERE fm.facility_id = :f AND fm.analysis_month = :m""", f=facility_id, m=m)
    if status is None:
        raise HTTPException(404, f"no analysis for facility {facility_id} in {m}")
    explanation = status.pop("explanation")
    # Trends up to the analysis month: service volumes vs baseline, commodity position, reporting history.
    services = q("""SELECT analysis_month, indicator, value, expected, z, seasonal FROM mart_service_baseline
                    WHERE facility_id = :f AND analysis_month <= :m AND indicator IN ('opd', 'confirmed_malaria')
                    ORDER BY analysis_month""", f=facility_id, m=m)
    commodity = q("""SELECT period_start, commodity_code, physical_stock, amc, days_out_of_stock, submission_date
                     FROM fact_nhlmis_bimonthly WHERE facility_id = :f AND submission_date < (:m || '-01')::date + interval '1 month' + interval '30 days'
                     ORDER BY period_start""", f=facility_id, m=m)
    reporting = q("""SELECT analysis_month, report_received, late_days, data_confidence, operational_risk, queue
                     FROM mart_facility_month WHERE facility_id = :f AND analysis_month <= :m
                     ORDER BY analysis_month""", f=facility_id, m=m)
    return {"month": m, "facility": info, "status": status, "explanation": explanation,
            "trends": {"services": services, "commodity": commodity, "reporting": reporting}}


@app.get("/quality/{facility_id}")
def quality(facility_id: str, month: str | None = MONTH):
    m = resolve_month(month)
    checks = q("""SELECT rule_id, family, severity, source, field, value, explanation, source_date
                  FROM fact_quality_flags WHERE facility_id = :f AND analysis_month = :m
                  ORDER BY CASE severity WHEN 'severe' THEN 0 WHEN 'major' THEN 1 ELSE 2 END""", f=facility_id, m=m)
    fresh = q("""SELECT commodity_code, has_record, period_start, nhlmis_period_end, nhlmis_age_days, stale_flag,
                        next_expected_period FROM mart_commodity_month WHERE facility_id = :f AND analysis_month = :m""",
              f=facility_id, m=m)
    return {"month": m, "checks": checks, "freshness": fresh}
