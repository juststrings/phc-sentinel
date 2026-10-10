"""Read-only view of config/settings.yaml for the Method page: every threshold with its value and basis.

The basis tag (POLICY, WHO-DQR, STAT, DESIGN) only exists in the YAML comments, so this reads the file text
for the tags and the loaded settings for the values. Nothing here changes or duplicates a threshold.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..config import CONFIG_DIR, settings

BASES = ("POLICY-ALIGNED", "POLICY", "WHO-DQR", "STAT", "DESIGN")
SKIP_SECTIONS = {"state", "simulator", "decision"}      # not thresholds
_KEY = re.compile(r"^(\s*)([A-Za-z0-9_]+):\s*(.*)$")


def thresholds() -> list[dict]:
    values = settings()
    rows: list[dict] = []
    section = None
    for line in (CONFIG_DIR / "settings.yaml").read_text(encoding="utf-8").splitlines():
        m = _KEY.match(line)
        if not m or line.lstrip().startswith("#"):
            continue
        indent, key, rest = len(m.group(1)), m.group(2), m.group(3)
        if indent == 0:
            section = key
            continue
        if section in SKIP_SECTIONS or section not in values or key not in values[section]:
            continue
        note = rest.split("#", 1)[1].strip() if "#" in rest else ""
        basis = next((b for b in BASES if note.startswith(b)), None)
        rows.append({"section": section, "key": key, "value": values[section][key], "basis": basis,
                     "note": note[len(basis):].lstrip(",: ").strip() if basis else note})
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
