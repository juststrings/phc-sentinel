"""Load staging tables and marts into PostgreSQL + PostGIS (proposal §8.1).

Each state's tables are bulk-loaded with COPY into one shared table per name, with a
state_code column, one state at a time (memory stays flat). Then post_load() adds
geometry, JSONB, indexes and the PostGIS coordinate check, and the precomputed
national marts are loaded.
"""
from __future__ import annotations

import io
import json
import os
import time

import pandas as pd
from sqlalchemy import create_engine, text

from .config import NATIONAL_DIR, RAW_DIR, StatePaths, states

DEFAULT_URL = "postgresql+psycopg://sentinel:sentinel@localhost:5433/sentinel"

# Per-state tables: name -> (sub-directory, file).
STATE_TABLES = {
    "dim_facility": ("staging", "dim_facility.parquet"),
    "stg_dhis2_values": ("staging", "stg_dhis2_values.parquet"),
    "fact_dhis2_monthly": ("staging", "fact_dhis2_monthly.parquet"),
    "fact_nhlmis_bimonthly": ("staging", "fact_nhlmis_bimonthly.parquet"),
    "fact_quality_flags": ("marts", "fact_quality_flags.parquet"),
    "fact_domain_results": ("marts", "fact_domain_results.parquet"),
    "mart_facility_month": ("marts", "mart_facility_month.parquet"),
    "mart_queue": ("marts", "mart_queue.parquet"),
    "mart_commodity_month": ("marts", "mart_commodity_month.parquet"),
    "mart_service_baseline": ("marts", "mart_service_baseline.parquet"),
    "mart_lga_month": ("marts", "mart_lga_month.parquet"),
}
NATIONAL_TABLES = ["mart_state_month", "mart_zone_month", "mart_national_month"]
JSONB = {"fact_domain_results": ["evidence"], "mart_queue": ["explanation"], "mart_facility_month": ["confidence_reasons"]}

# Every table is labelled real / synthetic mirror / derived (proposal §6.5).
DATA_LABELS = [
    ("dim_facility", "real", "GRID3 Nigeria Health Facilities v3.0 (CC BY 4.0); DHIS2/LMIS linkage keys are synthetic"),
    ("dim_lga", "real", "GRID3 LGA boundaries"),
    ("dim_state_geo", "real", "GRID3 state boundaries (all 36 states + FCT), simplified for the national map"),
    ("stg_dhis2_values", "synthetic", "Simulated DHIS2 data value set export"),
    ("fact_dhis2_monthly", "synthetic", "Simulated monthly NHMIS / RI reports, read through the DHIS2 adapter"),
    ("fact_nhlmis_bimonthly", "synthetic", "Simulated NHLMIS bimonthly facility stock reports"),
    ("fact_quality_flags", "derived", "WHO-aligned DQR rule results"),
    ("fact_domain_results", "derived", "Commodity, vaccine and service-pressure domain severities"),
    ("mart_facility_month", "derived", "Operational risk, data confidence and queue per facility-month"),
    ("mart_queue", "derived", "Ranked action and verification queues with explanations"),
    ("mart_commodity_month", "derived", "Latest NHLMIS record per commodity at each analysis date"),
    ("mart_service_baseline", "derived", "Seasonal robust baselines and z-scores"),
    ("mart_lga_month", "derived", "LGA roll-up"),
    ("mart_state_month", "derived", "State roll-up: queue counts, rates, main risk domain, status (sum of facilities)"),
    ("mart_zone_month", "derived", "Geopolitical-zone roll-up (sum of states)"),
    ("mart_national_month", "derived", "National roll-up across covered states (sum of states)"),
]


def engine():
    return create_engine(os.environ.get("DATABASE_URL", DEFAULT_URL), pool_pre_ping=True)


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in df.columns:
        if df[c].dtype == object:
            sample = df[c].dropna().head(1)
            if len(sample) and isinstance(sample.iloc[0], (list, dict)):
                df[c] = df[c].map(lambda v: json.dumps(v, default=str) if v is not None else None)
            elif len(sample) and isinstance(sample.iloc[0], pd.Period):
                df[c] = df[c].astype(str)
    return df


def copy_df(conn, df: pd.DataFrame, table: str, append: bool = False) -> None:
    df = _prepare(df)
    if not append:
        df.head(0).to_sql(table, conn, if_exists="replace", index=False)
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False, na_rep="\\N")
    buf.seek(0)
    raw = conn.connection.dbapi_connection
    cols = ", ".join(f'"{c}"' for c in df.columns)
    with raw.cursor() as cur:
        with cur.copy(f'COPY "{table}" ({cols}) FROM STDIN WITH (FORMAT csv, NULL \'\\N\')') as cp:
            while chunk := buf.read(1 << 20):
                cp.write(chunk)


def _with_state(df: pd.DataFrame, code: str) -> pd.DataFrame:
    if "state_code" not in df:
        df.insert(0, "state_code", code)
    return df


def post_load(conn) -> None:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    for table, cols in JSONB.items():
        for c in cols:
            conn.execute(text(f'ALTER TABLE {table} ALTER COLUMN "{c}" TYPE jsonb USING "{c}"::jsonb'))
    conn.execute(text("""
        ALTER TABLE dim_facility ADD PRIMARY KEY (facility_id);
        ALTER TABLE dim_facility ADD COLUMN geom geometry(Point, 4326);
        UPDATE dim_facility SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326);
        CREATE INDEX ON dim_facility USING gist (geom);
        CREATE INDEX ON dim_facility (state_code, lga_id);
        CREATE INDEX ON fact_quality_flags (facility_id, analysis_month);
        CREATE INDEX ON fact_domain_results (facility_id, analysis_month);
        CREATE UNIQUE INDEX ON mart_facility_month (facility_id, analysis_month);
        CREATE INDEX ON mart_facility_month (state_code, analysis_month, lga_id);
        CREATE UNIQUE INDEX ON mart_queue (facility_id, analysis_month);
        CREATE INDEX ON mart_queue (state_code, analysis_month, queue, rank_state);
        CREATE INDEX ON mart_queue (analysis_month, lga_id, queue, rank_lga);
        CREATE INDEX ON mart_commodity_month (facility_id, analysis_month);
        CREATE INDEX ON mart_service_baseline (facility_id, analysis_month);
        CREATE INDEX ON fact_dhis2_monthly (facility_id, period);
        CREATE INDEX ON fact_nhlmis_bimonthly (facility_id, period_start);
        CREATE UNIQUE INDEX ON mart_lga_month (analysis_month, lga_id);
        CREATE INDEX ON mart_lga_month (state_code, analysis_month, lga_rank);
        CREATE UNIQUE INDEX ON mart_state_month (state_code, analysis_month);
        CREATE UNIQUE INDEX ON mart_zone_month (zone, analysis_month);
        CREATE UNIQUE INDEX ON mart_national_month (analysis_month);
    """))
    # Phase 1 gate in PostGIS: does each facility fall inside its own LGA polygon, and how far off is it?
    conn.execute(text("""
        CREATE OR REPLACE VIEW v_facility_lga_check AS
        SELECT f.facility_id, f.name, f.state_code, f.lga, f.coord_status,
               ST_Contains(l.geom, f.geom) AS inside_own_lga,
               round(ST_Distance(l.geom::geography, f.geom::geography)) AS distance_m
        FROM dim_facility f JOIN dim_lga l USING (lga_id)
    """))


def load() -> None:
    t0 = time.time()
    eng = engine()
    with eng.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        conn.execute(text("DROP VIEW IF EXISTS v_facility_lga_check"))
        for table, (sub, name) in STATE_TABLES.items():
            files = [(st["code"], getattr(StatePaths(st["code"]), sub) / name) for st in states()]
            # Column types from a sample of every state, so a column that is integer in one
            # state and float (has NULLs) in another gets one compatible type.
            sample = _prepare(pd.concat([_with_state(pd.read_parquet(f).head(500), c) for c, f in files], ignore_index=True))
            sample.head(0).to_sql(table, conn, if_exists="replace", index=False)
            cols, total = list(sample.columns), 0
            for code, f in files:
                df = _with_state(pd.read_parquet(f), code).reindex(columns=cols)
                df = df.astype({c: t for c, t in sample.dtypes.items() if t.kind == "f" and df[c].dtype.kind in "iub"})
                copy_df(conn, df, table, append=True)
                total += len(df)
            print(f"  {table:<24} {total:>10,} rows")

        conn.execute(text("DROP TABLE IF EXISTS dim_lga"))
        conn.execute(text("CREATE TABLE dim_lga (lga_id text PRIMARY KEY, lga text, state text, state_code text, "
                          "geom geometry(MultiPolygon, 4326))"))
        for st in states():
            lga = json.loads((StatePaths(st["code"]).staging / "dim_lga.geojson").read_text(encoding="utf-8"))
            for f in lga["features"]:
                p = f["properties"]
                conn.execute(text("INSERT INTO dim_lga VALUES (:id, :lga, :state, :code, "
                                  "ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:g), 4326)))"),
                             {"id": p["lga_id"], "lga": p["lga"], "state": p["state"], "code": st["code"],
                              "g": json.dumps(f["geometry"])})
        conn.execute(text("CREATE INDEX ON dim_lga (state_code)"))

        # National map: every state, covered or not.
        conn.execute(text("DROP TABLE IF EXISTS dim_state_geo"))
        conn.execute(text("CREATE TABLE dim_state_geo (grid3_code text PRIMARY KEY, name text, state_code text, "
                          "geom geometry(MultiPolygon, 4326))"))
        by_grid3 = {st["grid3_code"]: st["code"] for st in states()}
        geo = json.loads((RAW_DIR / "grid3" / "nga_state_boundaries.geojson").read_text(encoding="utf-8"))
        for f in geo["features"]:
            p = f["properties"]
            conn.execute(text("INSERT INTO dim_state_geo VALUES (:g3, :name, :code, "
                              "ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:g), 4326)))"),
                         {"g3": p["grid3_code"], "name": p["name"], "code": by_grid3.get(p["grid3_code"]),
                          "g": json.dumps(f["geometry"])})

        for table in NATIONAL_TABLES:
            df = pd.read_parquet(NATIONAL_DIR / f"{table}.parquet")
            copy_df(conn, df, table)
            print(f"  {table:<24} {len(df):>10,} rows")

        copy_df(conn, pd.DataFrame(DATA_LABELS, columns=["table_name", "data_class", "description"]), "meta_data_labels")
        post_load(conn)
        chk = conn.execute(text("SELECT state_code, coord_status, inside_own_lga, count(*) FROM v_facility_lga_check "
                                "GROUP BY 1, 2, 3 ORDER BY 1, 2, 3")).fetchall()
    # Fresh planner statistics for the API's queries (ANALYZE needs no large shared memory).
    with eng.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("ANALYZE"))
    eng.dispose()
    print(f"Database loaded in {time.time() - t0:.0f}s. PostGIS coordinate check (state, tag, inside own LGA, n):")
    for r in chk:
        print("  ", tuple(r))
