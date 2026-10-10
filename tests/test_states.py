"""State parameterisation: the state list lives in settings.yaml, every state runs through the
same code with its own labelled parameters, and nothing is state-specific in code."""
from __future__ import annotations

import numpy as np
import pandas as pd

from sentinel import config
from sentinel.simulator.truth import facility_attributes


def test_twelve_states_two_per_zone():
    s = config.settings()
    st = config.states()
    assert len(st) == 12
    assert {x["zone"] for x in st} == set(s["zones"])
    for z in s["zones"]:
        assert sum(x["zone"] == z for x in st) == 2, z
    assert len({x["code"] for x in st}) == 12
    assert len({x["grid3_code"] for x in st}) == 12
    assert s["default_state"] in config.state_codes()


def test_state_parameters_resolve_over_defaults():
    defaults = config.settings()["simulator"]["state_defaults"]
    for st in config.states():
        assert set(defaults) <= set(st["sim"]), st["code"]
        assert st["sim"]["season"] in config.settings()["simulator"]["seasonality"]
        lo, hi = st["sim"]["report_range"]
        assert 0 < lo < hi < 1
    # Bauchi keeps the original calibration exactly (regression guarantee).
    assert config.state("bauchi")["sim"] == defaults
    assert len({st["sim"]["seed_offset"] for st in config.states()}) == 12


def test_each_state_has_its_own_paths():
    roots = {config.StatePaths(c).root for c in config.state_codes()}
    assert len(roots) == 12
    p = config.StatePaths("kano")
    assert p.exports.parent == p.root and p.marts.name == "marts"


def test_unknown_state_raises():
    import pytest
    with pytest.raises(KeyError):
        config.state("lagos")


def _dim(n=200, lgas=4):
    return pd.DataFrame({"facility_id": [f"F{i}" for i in range(n)], "lga": [f"L{i % lgas}" for i in range(n)]})


def test_simulator_parameters_change_the_simulation():
    base = config.state("bauchi")["sim"]
    a1 = facility_attributes(_dim(), np.random.default_rng(1), base)
    a2 = facility_attributes(_dim(), np.random.default_rng(1), base)
    pd.testing.assert_frame_equal(a1, a2)   # same parameters + seed -> identical

    low = {**base, "report_range": [0.40, 0.45], "base_opd_median": 100, "malaria_burden": 0.5}
    b = facility_attributes(_dim(), np.random.default_rng(1), low)
    assert b["p_report"].mean() < a1["p_report"].mean() - 0.3
    assert b["base_opd"].median() < a1["base_opd"].median() / 2
    assert np.allclose(b["malaria_share"], a1["malaria_share"] * 0.5)


def test_default_burden_leaves_draws_unchanged():
    """malaria_burden 1.0 must not perturb the original draws (Bauchi reproducibility)."""
    rng = np.random.default_rng(7)
    a = facility_attributes(_dim(), rng, config.state("bauchi")["sim"])
    rng = np.random.default_rng(7)
    rng.uniform(size=4 * 4)  # the four LGA-level draws
    rng.lognormal(size=200)
    assert np.array_equal(a["malaria_share"].values, rng.beta(5, 15, 200))
