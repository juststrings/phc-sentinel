"""National aggregation: national and zone totals equal the sum of their states, and rates are
recomputed from summed counts (never averaged)."""
from __future__ import annotations

import pandas as pd
import pytest

from sentinel import config, national

COUNTS = national.COUNTS


def _fm(n_act, n_vta, n_ver, n_mon, received, month="2026-09"):
    rows = []
    for queue, tag, n in (("RESOURCE_ACTION", "ACT NOW", n_act), ("RESOURCE_ACTION", "VERIFY THEN ACT", n_vta),
                          ("DATA_VERIFICATION", "DO NOT ASSUME SAFE", n_ver), ("MONITOR", "MONITOR", n_mon)):
        for _ in range(n):
            rows.append({"analysis_month": month, "lga_id": "1", "queue": queue, "tag": tag,
                         "data_confidence": "LOW" if tag in ("VERIFY THEN ACT", "DO NOT ASSUME SAFE") else "HIGH",
                         "operational_risk": "HIGH" if queue == "RESOURCE_ACTION" else "NORMAL",
                         "top_domain": "malaria_commodity" if queue == "RESOURCE_ACTION" else None,
                         "silent_flag": False, "reliable_silence": False, "nhlmis_stale": tag == "DO NOT ASSUME SAFE",
                         "on_time_flag": True})
    df = pd.DataFrame(rows)
    df["report_received"] = [i < received for i in range(len(df))]
    return df


def test_state_month_counts_and_rates():
    dim = pd.DataFrame({"coord_status": ["ok"] * 9 + ["location_unverified"]})
    sm = national.add_rates(national.state_month(_fm(2, 1, 3, 4, received=8), dim))
    r = sm.iloc[0]
    assert (r.facilities, r.action, r.act_now, r.verify_then_act, r.verification, r.monitor) == (10, 3, 2, 1, 3, 4)
    assert r.act_now + r.verify_then_act + r.verification + r.monitor == r.facilities
    assert r.reporting_completeness == 0.8 and r.pct_act_now == 0.2 and r.pct_stale == 0.3
    assert r.location_unverified == 1 and r.main_domain == "malaria_commodity"


def test_status_label_follows_config_thresholds():
    t = config.settings()["national"]["status"]
    base = {c: 0 for c in COUNTS} | {"facilities": 100}

    def status(act_now, verification):
        return national.add_rates(pd.DataFrame([base | {"act_now": act_now, "verification": verification}]))["status"][0]

    hi_a, hi_v = round(t["act_now_share_high"] * 100), round(t["verification_share_high"] * 100)
    assert status(hi_a, hi_v) == "act_and_verify"
    assert status(hi_a, hi_v - 1) == "action_load"
    assert status(hi_a - 1, hi_v) == "evidence_gap"
    assert status(hi_a - 1, hi_v - 1) == "watch"


def test_rates_are_recomputed_not_averaged():
    """A small state with 100% completeness must not pull a large state's rate to the mean."""
    dim = pd.DataFrame({"coord_status": ["ok"]})
    a = national.state_month(_fm(0, 0, 0, 90, received=45), dim).assign(state_code="a", zone="Z")
    b = national.state_month(_fm(0, 0, 0, 10, received=10), dim).assign(state_code="b", zone="Z")
    both = pd.concat([a, b])
    nat = national.add_rates(both.groupby("analysis_month")[COUNTS + ["lgas"]].sum().reset_index())
    assert nat["reporting_completeness"][0] == pytest.approx(55 / 100)   # not (0.5 + 1.0) / 2


def _built():
    p = config.NATIONAL_DIR / "mart_state_month.parquet"
    if not p.exists():
        pytest.skip("national marts not built (python -m sentinel national)")
    return (pd.read_parquet(p), pd.read_parquet(config.NATIONAL_DIR / "mart_zone_month.parquet"),
            pd.read_parquet(config.NATIONAL_DIR / "mart_national_month.parquet"))


def test_built_national_totals_equal_sum_of_states():
    st, zone, nat = _built()
    assert st["state_code"].nunique() == 12
    summed = st.groupby("analysis_month")[COUNTS].sum()
    pd.testing.assert_frame_equal(nat.set_index("analysis_month")[COUNTS].astype("int64"), summed.astype("int64"),
                                  check_names=False)
    zsum = st.groupby(["analysis_month", "zone"])[COUNTS].sum()
    pd.testing.assert_frame_equal(zone.set_index(["analysis_month", "zone"])[COUNTS].sort_index().astype("int64"),
                                  zsum.sort_index().astype("int64"), check_names=False)
    # Rates come from the summed counts.
    n = nat.iloc[-1]
    assert n["reporting_completeness"] == pytest.approx(round(n["reports_received"] / n["facilities"], 4))
    assert n["pct_act_now"] == pytest.approx(round(n["act_now"] / n["facilities"], 4))


def test_built_state_marts_match_facility_marts():
    """Each state row equals a direct count over that state's facility-months."""
    st, _, _ = _built()
    for code in ("bauchi", "bayelsa"):
        fm = pd.read_parquet(config.StatePaths(code).marts / "mart_facility_month.parquet")
        last = fm[fm["analysis_month"] == fm["analysis_month"].max()]
        row = st[(st["state_code"] == code) & (st["analysis_month"] == last["analysis_month"].iloc[0])].iloc[0]
        assert row["facilities"] == len(last)
        assert row["act_now"] == (last["tag"] == "ACT NOW").sum()
        assert row["verification"] == (last["queue"] == "DATA_VERIFICATION").sum()
        assert row["stale_commodity"] == last["nhlmis_stale"].sum()
