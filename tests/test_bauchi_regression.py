"""Regression guarantee: adding 11 states must not change a single Bauchi output.

tests/fixtures/bauchi_baseline.json was taken from the single-state build (commit 4e7ca52)
before any multi-state change: a SHA-256 over every facility-month's queue, tag, confidence,
risk, ranks and top domain, over the LGA roll-up and over every quality flag.

test_bauchi_rebuild_reproduces_baseline re-runs the Bauchi simulator and pipeline from the
committed GRID3 files into a temporary directory (about 3 minutes). Skip it with -m "not slow".
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from sentinel import config

BASELINE = json.loads((Path(__file__).parent / "fixtures" / "bauchi_baseline.json").read_text())
FM_COLS = ["facility_id", "analysis_month", "queue", "tag", "data_confidence", "operational_risk",
           "rank_state", "rank_lga", "top_domain"]


def fingerprints(marts: Path) -> dict:
    fm = pd.read_parquet(marts / "mart_facility_month.parquet")
    lga = pd.read_parquet(marts / "mart_lga_month.parquet")
    fl = pd.read_parquet(marts / "fact_quality_flags.parquet")
    h = lambda df: hashlib.sha256(df.astype(str).to_csv(index=False).encode()).hexdigest()  # noqa: E731
    return {
        "facility_month_sha256": h(fm[FM_COLS].sort_values(["analysis_month", "facility_id"])),
        "lga_month_sha256": h(lga.sort_values(["analysis_month", "lga_id"])),
        "quality_flags_sha256": h(fl[["facility_id", "analysis_month", "rule_id", "severity"]]
                                  .sort_values(["analysis_month", "facility_id", "rule_id"])),
        "facility_months": len(fm),
        "flags_rows": len(fl),
        "sep_2026": fm[fm["analysis_month"] == "2026-09"]["tag"].value_counts().to_dict(),
    }


def check(fp: dict) -> None:
    assert fp["sep_2026"] == {"MONITOR": 613, "DO NOT ASSUME SAFE": 581, "ACT NOW": 188, "VERIFY THEN ACT": 72}
    assert fp["facility_months"] == BASELINE["facility_months"]
    assert fp["flags_rows"] == BASELINE["flags_rows"]
    for k in ("facility_month_sha256", "lga_month_sha256", "quality_flags_sha256"):
        assert fp[k] == BASELINE[k], k


def test_bauchi_build_matches_baseline():
    marts = config.StatePaths("bauchi").marts
    if not (marts / "mart_facility_month.parquet").exists():
        pytest.skip("Bauchi not built (python -m sentinel all --state bauchi)")
    check(fingerprints(marts))


def test_baseline_sep_2026_by_month_is_recorded():
    assert BASELINE["tags_by_month"]["2026-09"] == {"MONITOR": 613, "DO NOT ASSUME SAFE": 581, "ACT NOW": 188,
                                                    "VERIFY THEN ACT": 72}


@pytest.mark.slow
def test_bauchi_rebuild_reproduces_baseline(tmp_path, monkeypatch):
    """Full rebuild from the committed GRID3 layers with today's multi-state code."""
    from sentinel import pipeline, simulator
    from sentinel.facility import grid3

    monkeypatch.setattr(config, "STATES_DIR", tmp_path)
    grid3.build("bauchi")
    simulator.run("bauchi")
    pipeline.run("bauchi")
    check(fingerprints(config.StatePaths("bauchi").marts))
    shutil.rmtree(tmp_path, ignore_errors=True)
