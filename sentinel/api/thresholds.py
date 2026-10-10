"""Read-only view of config/settings.yaml for the Method page: every threshold with its value and basis.

The basis tag (POLICY, WHO-DQR, STAT, DESIGN) only exists in the YAML comments, so this reads the file text
for the tags and the loaded settings for the values. Nothing here changes or duplicates a threshold.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..config import CONFIG_DIR, settings

BASES = ("POLICY-ALIGNED", "POLICY", "WHO-DQR", "STAT", "DESIGN")
SKIP_SECTIONS = {"state", "default_state", "zones", "states", "simulator", "decision"}      # not thresholds
SKIP_KEYS = {("calendar", "first_period"), ("calendar", "last_period"),          # the simulated date range
             ("national", "trend_months"), ("national", "top_lgas_in_brief")}      # display settings, not thresholds

# settings.yaml cites sources by bracket number or by proposal section. Bracket 10 is the national min-max
# inventory policy (docs/assumptions.md A2); proposal sections are internal references and are dropped, so a
# note with no readable source keeps only its basis tag.
REF_NAMES = {"10": "the national min-max inventory policy"}
_KEY = re.compile(r"^(\s*)([A-Za-z0-9_]+):\s*(.*)$")


def _clean_note(note: str) -> str:
    """Make a YAML comment readable: drop internal references, name known bracket sources."""
    note = re.sub(r"[,;]?\s*proposal\s*\S*\d[\d.]*", "", note)                       # "proposal section 7.2"
    note = re.sub(r"(against\s+)\[(\d+)\]", lambda m: m.group(1) + REF_NAMES.get(m.group(2), "the source"), note)
    note = re.sub(r"\s*\[(\d+)\]", lambda m: f", per {REF_NAMES[m.group(1)]}" if m.group(1) in REF_NAMES else "", note)
    note = re.sub(r"\s+in Phase \d+", "", note)                                         # build-phase wording
    note = re.sub(r"\s+", " ", note)
    note = re.sub(r"\(\s*\)", "", note)
    return note.strip(" ,:;")


def thresholds() -> list[dict]:
    """One row per threshold. A basis tag can sit in a trailing comment or on a comment line just above the key;
    keys nested one level (national.status) inherit the parent's tag."""
    values = settings()
    rows: list[dict] = []
    section = parent = None
    pending: str | None = None          # basis tag found on a comment line above the next key
    parent_basis: str | None = None
    for line in (CONFIG_DIR / "settings.yaml").read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            tag = next((b for b in BASES if stripped.lstrip("# ").startswith(b)), None)
            pending = tag or pending
            continue
        m = _KEY.match(line)
        if not m:
            continue
        indent, key, rest = len(m.group(1)), m.group(2), m.group(3)
        if indent == 0:
            section, parent, pending, parent_basis = key, None, None, None
            continue
        if section in SKIP_SECTIONS or section not in values or not isinstance(values[section], dict):
            continue
        note = rest.split("#", 1)[1].strip() if "#" in rest else ""
        basis = next((b for b in BASES if note.startswith(b)), None) or pending
        if indent == 2:
            parent, parent_basis = key, basis
            pending = None
            if key not in values[section] or (section, key) in SKIP_KEYS or isinstance(values[section][key], dict):
                continue
            value, name = values[section][key], key
        elif indent == 4 and parent and isinstance(values[section].get(parent), dict) and key in values[section][parent]:
            value, name, basis = values[section][parent][key], f"{parent}_{key}", basis or parent_basis
        else:
            continue
        rows.append({"section": section, "key": name, "value": value, "basis": basis,
                     "note": _clean_note(note[len(basis):] if basis and note.startswith(basis) else note)})
    return rows


def rule_severities() -> dict[str, list[str]]:
    """Severity levels each DQR rule can produce, read from the `_flags(...)` calls in the engine source.

    The engine does not keep severity in its rule table, so this reads the literal severity at each call site
    (a rule whose severity depends on a value, like COMP_MISSING_FIELDS, lists every literal in that argument).
    It never imports or changes engine behaviour, and it works even if a rule has not fired in the data.
    """
    import ast

    from ..engines import dqr

    tree = ast.parse(Path(dqr.__file__).read_text(encoding="utf-8"))
    found: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "_flags" and len(node.args) >= 3
                and isinstance(node.args[1], ast.Constant)):
            rule = node.args[1].value
            lits = {n.value for n in ast.walk(node.args[2]) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
            found.setdefault(rule, set()).update(lits & {"severe", "major", "minor"})
    order = {"severe": 0, "major": 1, "minor": 2}
    return {r: sorted(v, key=order.get) for r, v in found.items()}
