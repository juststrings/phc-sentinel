"""Declarative rule engine. A rule's `when` is a tree of `all` / `any` lists whose leaves are
`{field, op, value}`; ops: eq ne lt le gt ge in not_in is_true is_false. No eval, no code in config.

Rules are validated when loaded: a malformed rule raises RuleError naming the rule id.
Evaluation is vectorised over a DataFrame of records (one row per facility, LGA or state).
"""
from __future__ import annotations

import pandas as pd

from ..config import actions_cfg

OPS = {"eq", "ne", "lt", "le", "gt", "ge", "in", "not_in", "is_true", "is_false"}
UNARY = {"is_true", "is_false"}
LEVELS = {"facility", "lga", "state"}
MODES = {"open", "suggest", "modifier"}


class RuleError(ValueError):
    pass


def _check_tree(rid: str, node, path: str = "when") -> None:
    if not isinstance(node, dict):
        raise RuleError(f"rule {rid}: {path} must be a mapping, got {type(node).__name__}")
    keys = set(node)
    if keys & {"all", "any"}:
        if len(keys) != 1:
            raise RuleError(f"rule {rid}: {path} must have exactly one of all/any, got {sorted(keys)}")
        (k, children), = node.items()
        if not isinstance(children, list) or not children:
            raise RuleError(f"rule {rid}: {path}.{k} must be a non-empty list")
        for i, c in enumerate(children):
            _check_tree(rid, c, f"{path}.{k}[{i}]")
        return
    if "field" not in node or "op" not in node:
        raise RuleError(f"rule {rid}: {path} needs field and op (or all/any), got {sorted(keys)}")
    if node["op"] not in OPS:
        raise RuleError(f"rule {rid}: {path} has unknown op {node['op']!r}; allowed {sorted(OPS)}")
    if node["op"] not in UNARY and "value" not in node:
        raise RuleError(f"rule {rid}: {path} op {node['op']} needs a value")
    if node["op"] in ("in", "not_in") and not isinstance(node.get("value"), list):
        raise RuleError(f"rule {rid}: {path} op {node['op']} needs a list value")
    extra = keys - {"field", "op", "value"}
    if extra:
        raise RuleError(f"rule {rid}: {path} has unknown keys {sorted(extra)}")


def validate(cfg: dict) -> list[dict]:
    roles, books, ladders = set(cfg["roles"]), set(cfg["playbooks"]), set(cfg["escalation"])
    prios = set(cfg["priorities"])
    seen: set[str] = set()
    out = []
    for r in cfg["rules"]:
        rid = r.get("id", "<missing id>")
        if "id" not in r:
            raise RuleError(f"rule {rid}: missing id")
        if rid in seen:
            raise RuleError(f"rule {rid}: duplicate id")
        seen.add(rid)
        mode = r.get("mode", "open")
        if mode not in MODES:
            raise RuleError(f"rule {rid}: unknown mode {mode!r}")
        if r.get("level") not in LEVELS:
            raise RuleError(f"rule {rid}: level must be one of {sorted(LEVELS)}")
        if "when" not in r:
            raise RuleError(f"rule {rid}: missing when")
        _check_tree(rid, r["when"])
        if mode == "modifier":
            if not isinstance(r.get("raise_priority"), int):
                raise RuleError(f"rule {rid}: modifier needs an integer raise_priority")
        else:
            for k in ("playbook", "owner_role", "priority", "due_days", "escalation", "group"):
                if k not in r:
                    raise RuleError(f"rule {rid}: missing {k}")
            if r["playbook"] not in books:
                raise RuleError(f"rule {rid}: unknown playbook {r['playbook']!r}")
            if r["owner_role"] not in roles:
                raise RuleError(f"rule {rid}: unknown owner_role {r['owner_role']!r}")
            for nr in r.get("notify_roles", []):
                if nr not in roles:
                    raise RuleError(f"rule {rid}: unknown notify role {nr!r}")
            if r["escalation"] not in ladders:
                raise RuleError(f"rule {rid}: unknown escalation ladder {r['escalation']!r}")
            if r["priority"] not in prios:
                raise RuleError(f"rule {rid}: unknown priority {r['priority']!r}")
        out.append({**r, "mode": mode})
    return out


def rules(cfg: dict | None = None) -> list[dict]:
    return validate(cfg or actions_cfg())


def mask(df: pd.DataFrame, node: dict, missing: set | None = None) -> pd.Series:
    """Boolean Series: which rows satisfy the condition tree. A field the records do not have makes its
    leaf False everywhere (recorded in `missing`), e.g. access fields before the access layer is built."""
    if "all" in node:
        m = pd.Series(True, index=df.index)
        for c in node["all"]:
            m &= mask(df, c, missing)
        return m
    if "any" in node:
        m = pd.Series(False, index=df.index)
        for c in node["any"]:
            m |= mask(df, c, missing)
        return m
    f, op, v = node["field"], node["op"], node.get("value")
    if f not in df.columns:
        if missing is not None:
            missing.add(f)
        return pd.Series(False, index=df.index)
    s = df[f]
    if op == "eq":
        return (s == v).fillna(False)
    if op == "ne":
        return (s != v) & s.notna()
    if op in ("lt", "le", "gt", "ge"):
        x = pd.to_numeric(s, errors="coerce")
        r = {"lt": x < v, "le": x <= v, "gt": x > v, "ge": x >= v}[op]
        return r.fillna(False)
    if op == "in":
        return s.isin(v)
    if op == "not_in":
        return ~s.isin(v) & s.notna()
    if op == "is_true":
        return s.fillna(False).astype(bool)
    if op == "is_false":
        return (s == False).fillna(False)  # noqa: E712  (explicit False only; missing is not False)
    raise RuleError(f"unknown op {op}")


def evaluate(node: dict, record: dict) -> bool:
    """Single-record convenience wrapper (used by tests and the API)."""
    return bool(mask(pd.DataFrame([record]), node).iloc[0])


def assign(df: pd.DataFrame, level: str, rule_list: list[dict] | None = None) -> tuple[pd.DataFrame, set]:
    """For each record, which open/suggest rules fire (first match within each group).
    Returns one row per (record, fired rule): the record's index as `rec`, plus rule_id."""
    rule_list = [r for r in (rule_list or rules()) if r["level"] == level and r["mode"] != "modifier"]
    missing: set = set()
    taken: dict[str, pd.Series] = {}
    parts = []
    for r in rule_list:
        g = r["group"]
        m = mask(df, r["when"], missing)
        free = ~taken.get(g, pd.Series(False, index=df.index))
        hit = m & free
        taken[g] = taken.get(g, pd.Series(False, index=df.index)) | hit
        if hit.any():
            parts.append(pd.DataFrame({"rec": df.index[hit], "rule_id": r["id"]}))
    out = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["rec", "rule_id"])
    return out, missing


def modifiers(df: pd.DataFrame, level: str, rule_list: list[dict] | None = None) -> list[tuple[dict, pd.Series]]:
    return [(r, mask(df, r["when"])) for r in (rule_list or rules()) if r["level"] == level and r["mode"] == "modifier"]


def raise_priority(p: str, steps: int, order: list[str]) -> str:
    i = order.index(p)
    return order[max(0, i - steps)]
