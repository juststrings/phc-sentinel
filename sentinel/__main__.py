"""PHC Sentinel pipeline CLI. Every command runs for all configured states unless
--state CODE is given (repeatable). States run in parallel (--workers N, default 3).

    python -m sentinel coverage      Step 1: GRID3 coverage check for every configured state
    python -m sentinel fetch-grid3   download raw GRID3 layers (only needed once; committed)
    python -m sentinel facilities    Phase 1: build dim_facility from GRID3
    python -m sentinel simulate      Phase 2: write simulated DHIS2/NHLMIS exports + answer key
    python -m sentinel pipeline      Phases 3-6: ingest exports, DQR, risk, confidence, queues
    python -m sentinel national      state- and national-level marts (all states)
    python -m sentinel load-db       load staging + marts into PostgreSQL/PostGIS
    python -m sentinel all           facilities -> simulate -> pipeline per state, then national marts
"""
from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor

from .config import ensure_dirs, state_codes


def _state_all(code: str) -> str:
    from .facility.grid3 import build
    from .pipeline import run as run_pipeline
    from .simulator import run as run_sim
    t0 = time.time()
    build(code)
    run_sim(code)
    run_pipeline(code)
    return f"{code}: done in {time.time() - t0:.0f}s"


def _state_step(step: str, code: str) -> str:
    if step == "facilities":
        from .facility.grid3 import build
        build(code)
    elif step == "simulate":
        from .simulator import run
        run(code)
    elif step == "pipeline":
        from .pipeline import run
        run(code)
    elif step == "fetch-grid3":
        from .facility.grid3 import fetch
        fetch(code)
    return f"{code}: {step} done"


def _parallel(fn, args: list[tuple], workers: int) -> None:
    if workers <= 1 or len(args) == 1:
        for a in args:
            print(fn(*a), flush=True)
        return
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for msg in ex.map(fn, *zip(*args)):
            print(msg, flush=True)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="python -m sentinel", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", nargs="?", default="all",
                   choices=["coverage", "fetch-grid3", "facilities", "simulate", "pipeline", "national", "load-db", "all"])
    p.add_argument("--state", action="append", help="state code (repeatable); default: all configured states")
    p.add_argument("--workers", type=int, default=int(os.environ.get("SENTINEL_WORKERS", 3)))
    a = p.parse_args(argv)
    ensure_dirs()
    codes = a.state or state_codes()
    unknown = sorted(set(codes) - set(state_codes()))
    if unknown:
        p.error(f"unknown state code(s) {unknown}; configured: {state_codes()}")

    if a.command == "coverage":
        from .facility.grid3 import coverage
        print(json.dumps(coverage(), indent=1))
    elif a.command == "fetch-grid3":
        _parallel(_state_step, [("fetch-grid3", c) for c in codes], 1)
        from .facility.grid3 import fetch_states_geo
        fetch_states_geo()
    elif a.command in ("facilities", "simulate", "pipeline"):
        _parallel(_state_step, [(a.command, c) for c in codes], a.workers)
    elif a.command == "national":
        from .national import build
        build()
    elif a.command == "load-db":
        from .db import load
        load()
    elif a.command == "all":
        t0 = time.time()
        # Largest states first so the pool finishes evenly.
        _parallel(_state_all, [(c,) for c in _by_size(codes)], a.workers)
        from .national import build
        build()
        print(f"All states done in {time.time() - t0:.0f}s")


def _by_size(codes: list[str]) -> list[str]:
    from .facility.grid3 import raw_paths
    return sorted(codes, key=lambda c: -raw_paths(c)[0].stat().st_size if raw_paths(c)[0].exists() else 0)


if __name__ == "__main__":
    main()
