"""Records the rules evaluate, built from the database marts for the latest analysis month.

facility: mart_facility_month + mart_queue + the month's reported DHIS2 values (fridge, vaccine stockout,
          sessions) + access (if loaded) + hidden burden (if loaded)
lga:      mart_lga_month (+ pct_verification)
state:    mart_state_month (status)
Only reads; nothing here writes to a mart.
"""
from __future__ import annotations

import pandas as pd
from sqlalchemy import text


def _read(conn, sql: str, **p) -> pd.DataFrame:
    return pd.read_sql(text(sql), conn, params=p)


def _exists(conn, table: str) -> bool:
    return bool(conn.execute(text("SELECT to_regclass(:t)"), {"t": table}).scalar())


def latest_month(conn) -> str:
    return conn.execute(text("SELECT max(analysis_month) FROM mart_national_month")).scalar()


def facility_records(conn, month: str, facility_ids: list[str] | None = None) -> pd.DataFrame:
    flt = "AND fm.facility_id = ANY(:ids)" if facility_ids else ""
    p = {"m": month, "period": month.replace("-", ""), **({"ids": facility_ids} if facility_ids else {})}
    df = _read(conn, f"""
        SELECT fm.facility_id, fm.state_code, fm.lga_id, fm.lga, f.name AS facility, f.ward, fm.analysis_month,
               fm.as_of, fm.queue, fm.tag, fm.quadrant, fm.operational_risk, fm.risk_n, fm.data_confidence,
               fm.top_domain, fm.report_received, fm.silent_flag, fm.reliable_silence, fm.reliable_history,
               fm.nhlmis_stale, fm.n_stale_commodities, fm.nhlmis_age_days, fm.consecutive_missing,
               fm.sev_malaria_commodity, fm.sev_vaccine_cold_chain, fm.sev_service_pressure,
               fm.credible_malaria_commodity, fm.credible_vaccine_cold_chain, fm.credible_service_pressure,
               fm.rank_state, fm.rank_lga, fm.signal, fm.corroborating_domains,
               q.evidence_summary, q.next_action, q.explanation,
               d.refrigerator_functional, d.vaccine_stockout_flag, d.sessions_planned, d.sessions_conducted,
               d.penta1, d.penta3
        FROM mart_facility_month fm
        JOIN mart_queue q ON q.facility_id = fm.facility_id AND q.analysis_month = fm.analysis_month
        JOIN dim_facility f ON f.facility_id = fm.facility_id
        LEFT JOIN fact_dhis2_monthly d ON d.facility_id = fm.facility_id AND d.period = :period
        WHERE fm.analysis_month = :m {flt}""", **p)
    rr = df["report_received"].astype(bool)
    df["fridge_nonfunctional"] = rr & (df["refrigerator_functional"] == 0)
    df["vaccine_stockout"] = rr & (df["vaccine_stockout_flag"] == 1)
    df["sessions_ratio"] = (df["sessions_conducted"] / df["sessions_planned"].where(df["sessions_planned"] > 0)).where(rr)
    if _exists(conn, "mart_access_facility"):
        acc = _read(conn, """SELECT facility_id, catchment_pop AS catchment_population, isolated AS access_isolated,
                                    alt_walk_min AS alt_minutes, alt_km, alt_facility_name
                             FROM mart_access_facility WHERE access_computed""")
        df = df.merge(acc, on="facility_id", how="left")
    if _exists(conn, "mart_hidden_burden_facility"):
        hb = _read(conn, """SELECT facility_id, implied_stock_label, act_p_out FROM mart_hidden_burden_facility
                            WHERE analysis_month = :m""", m=month)
        df = df.merge(hb, on="facility_id", how="left")
    return df


def lga_records(conn, month: str) -> pd.DataFrame:
    df = _read(conn, """SELECT state_code, lga_id, lga, facilities, verification, action, act_now, lga_rank
                        FROM mart_lga_month WHERE analysis_month = :m""", m=month)
    df["pct_verification"] = df["verification"] / df["facilities"].where(df["facilities"] > 0)
    return df


def state_records(conn, month: str) -> pd.DataFrame:
    return _read(conn, """SELECT state_code, state, zone, status, pct_act_now, pct_verification, facilities
                          FROM mart_state_month WHERE analysis_month = :m""", m=month)


def resupply_basis(conn, month: str, facility_ids: list[str]) -> pd.DataFrame:
    """Latest NHLMIS line per facility x product at the analysis date: quantity_to_order, AMC, stock."""
    return _read(conn, """SELECT facility_id, commodity_code, quantity_to_order, amc, physical_stock, stale_flag
                          FROM mart_commodity_month WHERE analysis_month = :m AND facility_id = ANY(:ids)""",
                 m=month, ids=facility_ids)
