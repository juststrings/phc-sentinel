"""Reporting layer, fault injection and export writers.

Truth -> what facilities actually submit -> files in the DHIS2 data value set,
DHIS2 complete-registration, DHIS2 org unit and NHLMIS bimonthly report formats.
The answer key (data/eval) records every injected fault and planted scenario;
the engines never read it.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from ..config import StatePaths, mapping, settings
from ..facility.grid3 import synthetic_uid
from .. import periods as P
from .truth import COMMODITIES, Truth

NUMERIC_FIELDS = ["opd", "confirmed_malaria", "anc1", "deliveries", "penta1", "penta3",
                  "sessions_planned", "sessions_conducted", "vaccine_stock_balance"]
BOOL_FIELDS = ["vaccine_stockout_flag", "refrigerator_functional"]


def _ts(d) -> str:
    return pd.Timestamp(d).strftime("%Y-%m-%dT%H:%M:%S.000")


def _submission_dates(period_end: pd.Series, on_time: np.ndarray, deadline_days: int,
                      rng: np.random.Generator) -> pd.Series:
    n = len(period_end)
    on_time_days = rng.integers(1, deadline_days + 1, n)
    late_days = deadline_days + 1 + np.round(rng.exponential(12, n)).astype(int)
    offs = np.where(on_time, on_time_days, late_days)
    hours = rng.integers(8, 17, n)
    return pd.to_datetime(period_end) + pd.to_timedelta(offs, unit="D") + pd.to_timedelta(hours, unit="h")


def simulate_reporting(truth: Truth, dim: pd.DataFrame, rng: np.random.Generator, state_name: str) -> dict:
    s = settings()
    rep = s["reporting"]
    mult = s["simulator"]["strain_silence_multiplier"]
    attrs = truth.facilities.set_index("facility_id")
    m = truth.monthly.copy()
    m["period_end"] = [p.end_time.normalize() for p in m["period"]]
    F, T = len(attrs), len(truth.months)

    # ---- DHIS2 monthly report submission -------------------------------------
    # Natural silent runs (Markov) on top of per-facility Bernoulli reporting.
    run = np.zeros(F, dtype=bool)
    natural_silent = np.zeros((T, F), dtype=bool)
    for t in range(T):
        enter = rng.random(F) < 0.008
        leave = rng.random(F) < 0.35
        run = np.where(run, ~leave, enter)
        natural_silent[t] = run
    p_miss = 1 - attrs.loc[m["facility_id"], "p_report"].values
    p_miss = np.where(m["strain"].values, np.minimum(p_miss * mult, 0.95), p_miss)   # A3
    missed = (rng.random(len(m)) < p_miss) | natural_silent.ravel() | m["silenced"].values
    m["submitted"] = ~missed
    on_time = rng.random(len(m)) < attrs.loc[m["facility_id"], "p_on_time"].values
    m["submission_date"] = _submission_dates(m["period_end"], on_time, rep["dhis2_deadline_days"], rng)
    m.loc[~m["submitted"], "submission_date"] = pd.NaT
    m["on_time"] = m["submitted"] & on_time

    faults: list[dict] = []

    def fault(kind, row, field, original, injected, source="dhis2"):
        faults.append({"fault_type": kind, "facility_id": row.facility_id, "period": P.dhis2_period(row.period),
                       "source": source, "field": field, "original_value": original, "injected_value": injected})

    reported = m.copy()
    for c in NUMERIC_FIELDS:
        reported[c] = reported[c].astype(float)

    # Extreme spikes (data-entry errors).
    sub = reported[reported["submitted"] & (reported["t"] >= 8)]
    spikes = sub.sample(frac=0.003, random_state=int(rng.integers(1e9)))
    for i, row in spikes.iterrows():
        field = rng.choice(["opd", "confirmed_malaria"], p=[0.6, 0.4])
        orig = reported.at[i, field]
        new = float(np.round(max(orig, 10) * rng.uniform(5, 10)))
        reported.at[i, field] = new
        fault("extreme_spike", row, field, orig, new)

    # Repeated identical values (copy-forward) for 4 consecutive months.
    rep_fac = rng.choice(attrs.index.values, size=max(3, F // 200), replace=False)
    for fid in rep_fac:
        t0 = int(rng.integers(8, T - 4))
        rows = reported[(reported["facility_id"] == fid) & reported["t"].between(t0, t0 + 3) & reported["submitted"]]
        if len(rows) < 3:
            continue
        val = max(reported.at[rows.index[0], "opd"], 20.0)
        for i in rows.index:
            orig = reported.at[i, "opd"]
            reported.at[i, "opd"] = val
            fault("repeated_values", reported.loc[i], "opd", orig, val)

    # Negative values (keying errors).
    neg = sub.sample(frac=0.0005, random_state=int(rng.integers(1e9)))
    for i, row in neg.iterrows():
        field = rng.choice(["anc1", "deliveries", "penta1", "opd"])
        orig = reported.at[i, field]
        reported.at[i, field] = -max(orig, 1.0)
        fault("negative_value", row, field, orig, -max(orig, 1.0))

    # ---- Long DHIS2 data value set ------------------------------------------
    mp = mapping()["dhis2"]
    de = {d["field"]: d for d in mp["data_elements"]}
    ou = dim.set_index("facility_id")["dhis2_orgunit_uid"]
    lga_of = dim.set_index("facility_id")["lga"]
    subm = reported[reported["submitted"]].copy()
    long = subm.melt(id_vars=["facility_id", "period", "submission_date", "fi"],
                     value_vars=NUMERIC_FIELDS + BOOL_FIELDS, var_name="field", value_name="value")
    p_field = attrs.loc[long["facility_id"], "p_field_missing"].values
    long = long[rng.random(len(long)) >= p_field]
    long["value"] = [("true" if v else "false") if f in BOOL_FIELDS else str(int(v))
                     for f, v in zip(long["field"], long["value"])]
    ts = long["submission_date"].map(_ts)
    dv = pd.DataFrame({
        "dataelement": long["field"].map(lambda f: de[f]["uid"]),
        "period": long["period"].map(P.dhis2_period),
        "orgunit": long["facility_id"].map(ou),
        "categoryoptioncombo": mp["default_category_option_combo"],
        "attributeoptioncombo": mp["default_category_option_combo"],
        "value": long["value"],
        "storedby": "lga_me_" + long["facility_id"].map(lga_of).str.lower().str.replace(r"[^a-z]", "", regex=True),
        "created": ts, "lastupdated": ts, "comment": "", "followup": "false",
    }).sort_values(["period", "orgunit", "dataelement"])

    reg = pd.DataFrame({
        "dataset": mp["dataset"]["uid"],
        "period": subm["period"].map(P.dhis2_period),
        "orgunit": subm["facility_id"].map(ou),
        "attributeoptioncombo": mp["default_category_option_combo"],
        "date": subm["submission_date"].map(_ts),
        "storedby": "lga_me",
        "completed": "true",
    })

    # ---- NHLMIS bimonthly facility reports ------------------------------------
    cal = s["calendar"]
    starts = [p for p in P.bimonthly_periods(cal["first_period"], cal["last_period"])
              if p >= pd.Period(cal["first_period"]) and P.bimonthly_end(p) <= pd.Period(cal["last_period"])]
    st = truth.stock
    st["bstart"] = st["period"].map(P.bimonthly_start)
    agg = (st[st["bstart"].isin(starts)].sort_values("t")
           .groupby(["facility_id", "commodity_code", "bstart"])
           .agg(opening=("opening", "first"), received=("received", "sum"), dispensed=("dispensed", "sum"),
                losses=("losses", "sum"), closing=("closing", "last"), days_out=("days_out", "sum"),
                days=("days_in_month", "sum"), months=("t", "count"), end_t=("t", "max"))
           .reset_index())
    agg = agg[agg["months"] == 2]
    agg["adjusted_consumption"] = np.where(
        agg["days_out"] < agg["days"],
        np.round(agg["dispensed"] * agg["days"] / (agg["days"] - agg["days_out"])), agg["dispensed"])
    agg = agg.sort_values(["facility_id", "commodity_code", "bstart"])
    n_amc = s["commodity"]["amc_periods"]
    agg["amc"] = (agg.groupby(["facility_id", "commodity_code"])["adjusted_consumption"]
                  .transform(lambda x: x.rolling(n_amc, min_periods=1).mean()) / 2).round(1)
    agg["quantity_required"] = np.maximum(np.round(s["commodity"]["max_months"] * agg["amc"] - agg["closing"]), 0)
    agg["physical_count"] = agg["closing"].astype(float)

    # Submission: one report per facility per period covering all commodities.
    fp = agg[["facility_id", "bstart", "end_t"]].drop_duplicates().reset_index(drop=True)
    mi = m.set_index(["t", "fi"])
    fi_of = pd.Series(np.arange(F), index=attrs.index)
    key = list(zip(fp["end_t"], fp["facility_id"].map(fi_of)))
    stopped = mi.loc[key, "lmis_stopped"].values | mi.loc[key, "silenced"].values
    strained = mi.loc[key, "strain"].values
    p_rep = attrs.loc[fp["facility_id"], "p_lmis_report"].values
    p_rep = np.where(strained, 1 - np.minimum((1 - p_rep) * mult, 0.95), p_rep)
    fp["submitted"] = (rng.random(len(fp)) < p_rep) & ~stopped
    lm_on_time = rng.random(len(fp)) < 0.75
    pend = fp["bstart"].map(lambda b: P.bimonthly_end(b).end_time.normalize())
    fp["submission_date"] = _submission_dates(pend, lm_on_time, rep["nhlmis_deadline_days"], rng)
    agg = agg.merge(fp[["facility_id", "bstart", "submitted", "submission_date"]], on=["facility_id", "bstart"])
    lm = agg[agg["submitted"]].copy().reset_index(drop=True)

    # Broken stock identity and negative stock faults.
    brk = lm.sample(frac=0.01, random_state=int(rng.integers(1e9))).index
    for i in brk:
        orig = lm.at[i, "physical_count"]
        new = float(np.round(orig * rng.uniform(1.3, 1.8) + rng.integers(10, 60)))
        lm.at[i, "physical_count"] = new
        faults.append({"fault_type": "broken_stock_identity", "facility_id": lm.at[i, "facility_id"],
                       "period": lm.at[i, "bstart"].strftime("%Y%m") + "B", "source": "nhlmis",
                       "field": f"physical_count:{lm.at[i, 'commodity_code']}", "original_value": orig, "injected_value": new})
    negi = lm.drop(brk).sample(frac=0.0005, random_state=int(rng.integers(1e9))).index
    for i in negi:
        orig = lm.at[i, "physical_count"]
        lm.at[i, "physical_count"] = -max(orig, 1.0)
        faults.append({"fault_type": "negative_value", "facility_id": lm.at[i, "facility_id"],
                       "period": lm.at[i, "bstart"].strftime("%Y%m") + "B", "source": "nhlmis",
                       "field": f"physical_count:{lm.at[i, 'commodity_code']}", "original_value": orig, "injected_value": -max(orig, 1.0)})

    cols = {v: k for k, v in mapping()["nhlmis"]["columns"].items()}
    lmis_code = dim.set_index("facility_id")["lmis_facility_code"]
    nhlmis = pd.DataFrame({
        cols["facility_code"]: lm["facility_id"].map(lmis_code),
        cols["period_start"]: lm["bstart"].map(lambda b: b.start_time.date().isoformat()),
        cols["period_end"]: lm["bstart"].map(lambda b: P.bimonthly_end(b).end_time.date().isoformat()),
        cols["commodity_code"]: lm["commodity_code"],
        cols["opening_balance"]: lm["opening"].astype(int),
        cols["quantity_received"]: lm["received"].astype(int),
        cols["quantity_consumed"]: lm["dispensed"].astype(int),
        cols["losses_adjustments"]: (-lm["losses"]).astype(int),
        cols["physical_stock"]: lm["physical_count"].astype(int),
        cols["days_out_of_stock"]: lm["days_out"].astype(int),
        cols["adjusted_consumption"]: lm["adjusted_consumption"].astype(int),
        cols["amc"]: lm["amc"],
        cols["quantity_to_order"]: lm["quantity_required"].astype(int),
        cols["submission_date"]: lm["submission_date"].dt.date.astype(str),
    }).sort_values([cols["period_start"], cols["facility_code"], cols["commodity_code"]])

    # ---- Org unit metadata -----------------------------------------------------
    lgas = dim[["lga_id", "lga"]].drop_duplicates()
    lga_uid = {r.lga: synthetic_uid("lga:" + r.lga) for r in lgas.itertuples()}
    state_uid = synthetic_uid("state:" + state_name)
    orgunits = pd.concat([
        pd.DataFrame([{"id": state_uid, "name": f"{state_name} State", "code": "", "level": 2, "parent": "", "openingDate": "1990-01-01"}]),
        pd.DataFrame({"id": lgas["lga"].map(lga_uid), "name": lgas["lga"] + " Local Government Area",
                      "code": lgas["lga_id"], "level": 3, "parent": state_uid, "openingDate": "1990-01-01"}),
        pd.DataFrame({"id": dim["dhis2_orgunit_uid"], "name": dim["name"], "code": dim["facility_id"], "level": 5,
                      "parent": dim["lga"].map(lga_uid), "openingDate": "2015-01-01"}),
    ], ignore_index=True)

    reporting_truth = m[["facility_id", "period", "submitted", "submission_date", "on_time", "strain", "silenced", "lmis_stopped"]].copy()
    reporting_truth["period"] = reporting_truth["period"].map(P.dhis2_period)
    lmis_truth = fp[["facility_id", "bstart", "submitted", "submission_date"]].copy()
    lmis_truth["bstart"] = lmis_truth["bstart"].astype(str)

    return {"datavalues": dv, "registrations": reg, "orgunits": orgunits, "nhlmis": nhlmis,
            "faults": pd.DataFrame(faults), "reporting_truth": reporting_truth, "lmis_truth": lmis_truth}


def realism_report(truth: Truth, out: dict) -> dict:
    """Compare generated rates with the calibration sources (proposal Phase 2, task 6)."""
    rt = out["reporting_truth"].copy()
    rt["as_of"] = rt["period"].map(lambda p: pd.Timestamp(P.as_of_date(P.parse_dhis2_period(p))))
    visible = rt["submitted"] & (rt["submission_date"] <= rt["as_of"])
    act = truth.stock[truth.stock["commodity_code"] == "ACT_AL_ADULT"]
    rep = {
        "facility_months": int(len(rt)),
        "dhis2_completeness_final": round(float(rt["submitted"].mean()), 3),
        "dhis2_completeness_at_analysis": round(float(visible.mean()), 3),
        "dhis2_timeliness": round(float(rt["on_time"].mean()), 3),
        "nhlmis_reporting_rate": round(float(out["lmis_truth"]["submitted"].mean()), 3),
        "act_stockout_facility_month_rate": round(float((act["days_out"] > 0).mean()), 3),
        "negative_stock_flows_in_truth": int((truth.stock["closing"] < 0).sum()),
        "datavalue_rows": int(len(out["datavalues"])),
        "nhlmis_rows": int(len(out["nhlmis"])),
        "faults_injected": out["faults"]["fault_type"].value_counts().to_dict() if len(out["faults"]) else {},
        "scenarios_planted": pd.Series([e["event_type"] for e in truth.events]).value_counts().to_dict(),
        "calibration_targets": {
            "dhis2_completeness": "0.71 (weak Bauchi LGA, [14]) to ~0.95",
            "dhis2_timeliness": "0.65 (weak Bauchi LGA, [14]) to ~0.90",
        },
    }
    rep["checks"] = {
        "no_impossible_stock_flows": rep["negative_stock_flows_in_truth"] == 0,
        "completeness_in_range": 0.65 <= rep["dhis2_completeness_final"] <= 0.97,
        "timeliness_in_range": 0.55 <= rep["dhis2_timeliness"] <= 0.92,
    }
    return rep


def write_outputs(truth: Truth, out: dict, paths: StatePaths) -> dict:
    paths.ensure()
    EXPORTS_DIR, EVAL_DIR = paths.exports, paths.eval
    out["datavalues"].to_csv(EXPORTS_DIR / "dhis2_datavalues.csv.gz", index=False)
    out["registrations"].to_csv(EXPORTS_DIR / "dhis2_complete_registrations.csv", index=False)
    out["orgunits"].to_csv(EXPORTS_DIR / "dhis2_orgunits.csv", index=False)
    out["nhlmis"].to_csv(EXPORTS_DIR / "nhlmis_facility_reports.csv", index=False)

    events = pd.DataFrame(truth.events)
    for c in ("start_period", "target_period", "stockout_period"):
        if c in events:
            events[c] = events[c].map(lambda p: P.dhis2_period(p) if isinstance(p, pd.Period) else None)
    # The answer key carries the state code so state keys can be combined nationally.
    events.insert(0, "state_code", paths.code)
    events.to_csv(EVAL_DIR / "answer_key_scenarios.csv", index=False)
    out["faults"].insert(0, "state_code", paths.code)
    out["faults"].to_csv(EVAL_DIR / "answer_key_faults.csv", index=False)
    out["reporting_truth"].to_csv(EVAL_DIR / "reporting_truth.csv", index=False)
    out["lmis_truth"].to_csv(EVAL_DIR / "nhlmis_reporting_truth.csv", index=False)
    tm = truth.monthly.drop(columns=["t", "fi"]).copy()
    tm["period"] = tm["period"].map(P.dhis2_period)
    tm.to_parquet(EVAL_DIR / "truth_monthly.parquet", index=False)
    ts = truth.stock.drop(columns=["t", "fi", "bstart"], errors="ignore").copy()
    ts["period"] = ts["period"].map(P.dhis2_period)
    ts.to_parquet(EVAL_DIR / "truth_stock.parquet", index=False)

    rep = realism_report(truth, out)
    (EVAL_DIR / "realism_report.json").write_text(json.dumps(rep, indent=2, default=str), encoding="utf-8")
    return rep
