"""Phases 3-6: ingest exports -> monthly spine -> DQR -> risk -> confidence -> queues.

Runs one state at a time. Reads ONLY that state's exports (the same files a state
would supply) and its facility master. Never reads the answer key (eval/).
"""
from __future__ import annotations

import json
import time

import pandas as pd

from . import periods as P
from .config import StatePaths, state
from .engines import decision, dqr, risk
from .engines.baseline import robust_z
from .ingest import dhis2, nhlmis
from .spine import build_month


def ingest(dim: pd.DataFrame, paths: StatePaths) -> tuple[pd.DataFrame, pd.DataFrame]:
    LOGS_DIR, STAGING_DIR = paths.logs, paths.staging
    rejections: list = []
    stg, monthly = dhis2.load(paths.exports, dim, rejections)
    lm = nhlmis.load(paths.exports, dim, rejections)
    rej = pd.concat(rejections, ignore_index=True) if rejections else pd.DataFrame(columns=["source", "reason", "row"])
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    rej.to_csv(LOGS_DIR / "rejections.csv", index=False)
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    stg.to_parquet(STAGING_DIR / "stg_dhis2_values.parquet", index=False)
    monthly.to_parquet(STAGING_DIR / "fact_dhis2_monthly.parquet", index=False)
    lm.assign(period_start=lm["period_start"].astype(str)).to_parquet(STAGING_DIR / "fact_nhlmis_bimonthly.parquet", index=False)
    print(f"Ingest {paths.code}: {len(stg):,} DHIS2 rows -> {len(monthly):,} facility-months; "
          f"{len(lm):,} NHLMIS rows; {len(rej):,} rejected ({rej['reason'].value_counts().to_dict() if len(rej) else {}})")
    return monthly, lm


def evaluate_month(month: pd.Period, dim, monthly, lm) -> dict:
    mv = build_month(month, dim, monthly, lm)
    z = robust_z(mv.spine, mv.history, month, dqr.DQR_INDICATORS)
    flags = dqr.run(mv, z)
    domains = risk.run(mv, z)
    fm, q = decision.decide(mv, flags, domains, dim)
    cm = mv.commodity.assign(period_start=mv.commodity["period_start"].astype(str),
                             nhlmis_period_end=mv.commodity["nhlmis_period_end"].astype(str))
    return {"flags": flags, "domains": domains, "facility_month": fm, "queue": q, "commodity": cm, "z": z.assign(analysis_month=str(month))}


def run(code: str, months: list[pd.Period] | None = None) -> None:
    t0 = time.time()
    paths = StatePaths(code).ensure()
    MARTS_DIR = paths.marts
    dim = pd.read_parquet(paths.staging / "dim_facility.parquet")
    monthly, lm = ingest(dim, paths)
    months = months or P.analysis_months()
    acc: dict[str, list] = {}
    for m in months:
        for k, v in evaluate_month(m, dim, monthly, lm).items():
            acc.setdefault(k, []).append(v)
    out = {k: pd.concat(v, ignore_index=True) for k, v in acc.items()}

    MARTS_DIR.mkdir(parents=True, exist_ok=True)
    out["flags"].to_parquet(MARTS_DIR / "fact_quality_flags.parquet", index=False)
    dom = out["domains"].assign(evidence=out["domains"]["evidence"].map(lambda e: json.dumps(e, default=str)))
    dom.to_parquet(MARTS_DIR / "fact_domain_results.parquet", index=False)
    fm = out["facility_month"]
    fm.assign(confidence_reasons=fm["confidence_reasons"].map(json.dumps)).to_parquet(MARTS_DIR / "mart_facility_month.parquet", index=False)
    out["queue"].to_parquet(MARTS_DIR / "mart_queue.parquet", index=False)
    out["commodity"].to_parquet(MARTS_DIR / "mart_commodity_month.parquet", index=False)
    out["z"].to_parquet(MARTS_DIR / "mart_service_baseline.parquet", index=False)
    lga = decision.lga_rollup(fm)
    lga.to_parquet(MARTS_DIR / "mart_lga_month.parquet", index=False)

    last = fm[fm["analysis_month"] == str(months[-1])]
    print(f"Pipeline {state(code)['name']}: {len(months)} months in {time.time() - t0:.0f}s. Latest month {months[-1]}:")
    print("  queues     ", last["queue"].value_counts().to_dict())
    print("  tags       ", last["tag"].value_counts().to_dict())
    print("  confidence ", last["data_confidence"].value_counts().to_dict())
    print("  risk       ", last["operational_risk"].value_counts().to_dict())
