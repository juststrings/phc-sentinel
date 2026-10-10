"""Read-only view of config/settings.yaml for the Method page: every threshold with its value and basis.

The basis tag (POLICY, WHO-DQR, STAT, DESIGN) only exists in the YAML comments, so this reads the file text
for the tags and the loaded settings for the values. Nothing here changes or duplicates a threshold.
"""
from __future__ import annotations

import re

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
