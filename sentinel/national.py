"""State- and national-level marts, precomputed at build time (National Command Centre).

Reads each state's mart_facility_month and mart_lga_month and writes, to data/national:

  mart_state_month     state x month   counts, rates, Risk x Confidence quadrants, main risk domain, status
  mart_zone_month      zone x month    sums of the state rows
  mart_national_month  month           sums of the state rows
  answer_key_*.csv     every state's answer key, combined (never read by the engines)

Every count is a plain sum, and every rate is recomputed from summed counts
(e.g. reports received / PHCs). National and zone totals therefore always equal
the sum of their states.
"""
from __future__ import annotations

import pandas as pd

from .config import NATIONAL_DIR, StatePaths, settings, states

COUNTS = ["facilities", "action", "act_now", "verify_then_act", "verification", "monitor",
          "reports_received", "on_time", "stale_commodity", "silent", "reliable_silent",
          "low_confidence", "critical", "action_malaria_commodity", "action_vaccine_cold_chain",
          "action_service_pressure", "location_unverified"]
DOMAINS = ["malaria_commodity", "vaccine_cold_chain", "service_pressure"]


def state_month(fm: pd.DataFrame, dim: pd.DataFrame) -> pd.DataFrame:
    """One state's facility-months -> one row per analysis month."""
    unverified = int((dim["coord_status"] == "location_unverified").sum())
    act = fm["queue"] == "RESOURCE_ACTION"
    f = fm.assign(
        action=act, act_now=fm["tag"] == "ACT NOW", verify_then_act=fm["tag"] == "VERIFY THEN ACT",
        verification=fm["queue"] == "DATA_VERIFICATION", monitor=fm["queue"] == "MONITOR",
        reports_received=fm["report_received"].astype(bool), on_time=fm["on_time_flag"].astype(bool),
        stale_commodity=fm["nhlmis_stale"].astype(bool), silent=fm["silent_flag"].astype(bool),
        reliable_silent=fm["reliable_silence"].astype(bool), low_confidence=fm["data_confidence"] == "LOW",
        critical=fm["operational_risk"] == "CRITICAL",
        **{f"action_{d}": act & (fm["top_domain"] == d) for d in DOMAINS})
    cols = [c for c in COUNTS if c not in ("facilities", "location_unverified")]
    g = f.groupby("analysis_month")
    out = g[cols].sum().astype(int)
    out.insert(0, "facilities", g.size())
    out["location_unverified"] = unverified
    out["lgas"] = g["lga_id"].nunique()
    return out.reset_index()


def add_rates(df: pd.DataFrame) -> pd.DataFrame:
    """Shares and rates from counts, plus the main risk domain and the status label."""
    st = settings()["national"]["status"]
    d = df.copy()
    n = d["facilities"].where(d["facilities"] > 0)
    d["pct_act_now"] = (d["act_now"] / n).round(4)
    d["pct_verify_then_act"] = (d["verify_then_act"] / n).round(4)
    d["pct_action"] = (d["action"] / n).round(4)
    d["pct_verification"] = (d["verification"] / n).round(4)
    d["pct_monitor"] = (d["monitor"] / n).round(4)
    d["reporting_completeness"] = (d["reports_received"] / n).round(4)
    d["on_time_rate"] = (d["on_time"] / n).round(4)
    d["pct_stale"] = (d["stale_commodity"] / n).round(4)
    dom = d[[f"action_{x}" for x in DOMAINS]]
    d["main_domain"] = dom.idxmax(axis=1).str.removeprefix("action_").where(dom.max(axis=1) > 0)
    high_act = d["pct_act_now"] >= st["act_now_share_high"]
    gap = d["pct_verification"] >= st["verification_share_high"]
    d["status"] = [
        "act_and_verify" if a and v else "action_load" if a else "evidence_gap" if v else "watch"
        for a, v in zip(high_act, gap)]
    return d


def build() -> dict[str, pd.DataFrame]:
    NATIONAL_DIR.mkdir(parents=True, exist_ok=True)
    rows, faults, scen = [], [], []
    for st in states():
        p = StatePaths(st["code"])
        fm = pd.read_parquet(p.marts / "mart_facility_month.parquet")
        dim = pd.read_parquet(p.staging / "dim_facility.parquet")
        sm = state_month(fm, dim)
        sm.insert(0, "state_code", st["code"])
        sm.insert(1, "state", st["name"])
        sm.insert(2, "zone", st["zone"])
        rows.append(sm)
        for name, acc in (("answer_key_faults.csv", faults), ("answer_key_scenarios.csv", scen)):
            f = p.eval / name
            if f.exists():
                acc.append(pd.read_csv(f))

    order = {st["code"]: i for i, st in enumerate(states())}
    state_m = pd.concat(rows, ignore_index=True)
    state_m = add_rates(state_m).sort_values(["analysis_month", "state_code"], key=lambda s: s.map(order) if s.name == "state_code" else s)

    zone_m = add_rates(state_m.groupby(["analysis_month", "zone"])[COUNTS + ["lgas"]].sum().reset_index())
    zone_m["states"] = state_m.groupby(["analysis_month", "zone"]).size().values
    zorder = {z: i for i, z in enumerate(settings()["zones"])}
    zone_m = zone_m.sort_values(["analysis_month", "zone"], key=lambda s: s.map(zorder) if s.name == "zone" else s)

    nat_m = add_rates(state_m.groupby("analysis_month")[COUNTS + ["lgas"]].sum().reset_index())
    nat_m["states"] = state_m.groupby("analysis_month").size().values

    state_m.to_parquet(NATIONAL_DIR / "mart_state_month.parquet", index=False)
    zone_m.to_parquet(NATIONAL_DIR / "mart_zone_month.parquet", index=False)
    nat_m.to_parquet(NATIONAL_DIR / "mart_national_month.parquet", index=False)
    if faults:
        pd.concat(faults, ignore_index=True).to_csv(NATIONAL_DIR / "answer_key_faults.csv", index=False)
    if scen:
        pd.concat(scen, ignore_index=True).to_csv(NATIONAL_DIR / "answer_key_scenarios.csv", index=False)

    last = nat_m.iloc[-1]
    print(f"National marts: {state_m['state_code'].nunique()} states, {int(last['facilities']):,} PHCs in "
          f"{last['analysis_month']}: act now {int(last['act_now'])}, verify then act {int(last['verify_then_act'])}, "
          f"data verification {int(last['verification'])}, monitor {int(last['monitor'])}")
    return {"state": state_m, "zone": zone_m, "national": nat_m}
