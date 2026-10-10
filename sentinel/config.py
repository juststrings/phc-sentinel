"""Paths and configuration loading. All thresholds and the state list come from config/settings.yaml."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
STATES_DIR = DATA_DIR / "states"       # one sub-directory per state (StatePaths)
NATIONAL_DIR = DATA_DIR / "national"   # state- and national-level marts


@lru_cache
def settings() -> dict:
    return yaml.safe_load((CONFIG_DIR / "settings.yaml").read_text(encoding="utf-8"))


@lru_cache
def mapping() -> dict:
    return yaml.safe_load((CONFIG_DIR / "dhis2_mapping.yaml").read_text(encoding="utf-8"))


def states() -> list[dict]:
    """Covered states in display order, each with its simulator parameters resolved."""
    s = settings()
    out = []
    for st in s["states"]:
        sim = {**s["simulator"]["state_defaults"], **(st.get("sim") or {})}
        out.append({**st, "sim": sim, "lga_aliases": st.get("lga_aliases") or {}})
    return out


def state(code: str) -> dict:
    for st in states():
        if st["code"] == code:
            return st
    raise KeyError(f"unknown state code {code!r}; configured: {[s['code'] for s in states()]}")


def state_codes() -> list[str]:
    return [st["code"] for st in states()]


@dataclass(frozen=True)
class StatePaths:
    """Where one state's pipeline reads and writes."""
    code: str

    @property
    def root(self) -> Path:
        return STATES_DIR / self.code

    @property
    def exports(self) -> Path:      # simulator output, in real export formats
        return self.root / "exports"

    @property
    def eval(self) -> Path:         # answer key; never read by the engines
        return self.root / "eval"

    @property
    def staging(self) -> Path:      # dim_facility and loaded facts
        return self.root / "staging"

    @property
    def marts(self) -> Path:        # engine outputs
        return self.root / "marts"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    def ensure(self) -> "StatePaths":
        for d in (self.exports, self.eval, self.staging, self.marts, self.logs):
            d.mkdir(parents=True, exist_ok=True)
        return self


def ensure_dirs() -> None:
    NATIONAL_DIR.mkdir(parents=True, exist_ok=True)
    for code in state_codes():
        StatePaths(code).ensure()
