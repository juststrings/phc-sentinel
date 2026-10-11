"""Message template rendering. SMS bodies are held to messaging.sms_max_chars (160): long placeholders are
shortened (with '.') to their configured maximum and, if the body is still too long, the facility name is
shortened further. Every body carries "Sentinel (DEMO)"."""
from __future__ import annotations

import string

from ..config import actions_cfg, templates_cfg

CHANNEL_FALLBACK = {"sms": ["sms"], "whatsapp": ["whatsapp", "sms"], "email": ["email", "sms"], "in_app": ["sms"]}


class TemplateError(ValueError):
    pass


def template(tid: str) -> dict:
    t = templates_cfg()["templates"].get(tid)
    if t is None:
        raise TemplateError(f"unknown template {tid}")
    return t


def _short(v: str, n: int) -> str:
    v = str(v)
    return v if len(v) <= n else v[: max(1, n - 1)].rstrip() + "."


class _Safe(dict):
    def __missing__(self, k):
        return "{" + k + "}"


def render(tid: str, channel: str, ctx: dict) -> tuple[str, str]:
    """Returns (body, channel actually used). SMS never exceeds the limit."""
    t = template(tid)
    used = next((c for c in CHANNEL_FALLBACK.get(channel, ["sms"]) if c in t), "sms")
    limits = templates_cfg().get("placeholder_max", {})
    c = dict(ctx)
    for k, n in limits.items():
        if k in c and c[k] is not None:
            c[k] = _short(c[k], n)
    body = string.Formatter().vformat(t[used], (), _Safe(c))
    if used == "sms":
        cap = actions_cfg()["messaging"]["sms_max_chars"]
        n = limits.get("facility", 30)
        while len(body) > cap and n > 8 and "facility" in c:
            n -= 2
            c["facility"] = _short(ctx["facility"], n)
            body = string.Formatter().vformat(t[used], (), _Safe(c))
        if len(body) > cap:
            raise TemplateError(f"{tid}: SMS body {len(body)} chars > {cap}")
    return body, used


def expects(tid: str) -> list[str]:
    return list(template(tid).get("expects", []))
