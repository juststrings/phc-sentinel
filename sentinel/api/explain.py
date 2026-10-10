"""Presentation helpers over the stored facility explanation. Read-only; the engines are not involved."""
from __future__ import annotations

SEV = {"NORMAL": 0, "WATCH": 1, "HIGH": 2, "CRITICAL": 3}


def _evidence_label(ev: dict) -> str:
    return ev["text"].split(":")[0]


def corroborated_by(explanation: dict | None, top_domain: str | None, risk: str | None) -> str | None:
    """For a High or worse facility driven by service pressure, name the domain that corroborated it.

    The engine only lets pressure reach High when another credible domain is at Watch or worse, but it does not
    record which one, so it is derived here from the explanation: the worst credible other domain.
    """
    if not explanation or top_domain != "service_pressure" or SEV.get(risk or "", 0) < SEV["HIGH"]:
        return None
    cands = [d for d in explanation.get("domains", [])
             if d["domain"] != "service_pressure" and d.get("credible") and SEV.get(d["severity"], 0) >= SEV["WATCH"]]
    if not cands:
        return None
    d = max(cands, key=lambda x: SEV[x["severity"]])
    evidence = d.get("evidence") or []
    with_mos = [e for e in evidence if e.get("mos") is not None]
    if with_mos:
        e = min(with_mos, key=lambda x: x["mos"])
        text = f"{_evidence_label(e)} at {e['mos']:.1f} months"
    elif evidence:
        text = evidence[0]["text"]
    else:
        text = d["label"]
    return f"{text} ({d['severity'].capitalize()})"
