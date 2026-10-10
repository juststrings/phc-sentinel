"""Phase 2: reporting-system simulator. All output is SIMULATED and labelled as such."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from ..config import StatePaths, settings, state
from .reporting import simulate_reporting, write_outputs
from .truth import simulate_truth


def run(code: str) -> dict:
    """Simulate one state. Each state has its own seed (simulator.seed + seed_offset)
    and labelled parameters, so states are independent and individually reproducible."""
    st = state(code)
    paths = StatePaths(code).ensure()
    dim = pd.read_parquet(paths.staging / "dim_facility.parquet")
    rng = np.random.default_rng(settings()["simulator"]["seed"] + st["sim"]["seed_offset"])
    truth = simulate_truth(dim, rng, st["sim"])
    out = simulate_reporting(truth, dim, rng, st["name"])
    rep = write_outputs(truth, out, paths)
    rep = {"state": st["name"], "state_code": code, "parameters": st["sim"], **rep}
    (paths.eval / "realism_report.json").write_text(json.dumps(rep, indent=2, default=str), encoding="utf-8")
    print(f"Simulator {st['name']}: completeness {rep['dhis2_completeness_final']}, timeliness {rep['dhis2_timeliness']}, "
          f"NHLMIS {rep['nhlmis_reporting_rate']}, checks {rep['checks']}")
    return rep
