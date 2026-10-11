"""Structured SMS reply parser. Forgiving by design: case-insensitive, any order, extra spaces and
punctuation, glued tokens (ACT12), one-letter typos (AKT, RTD, FRIGDE), words for zero (nil, none) and for
fridge status (ok / working / spoilt / not working).

    ACT 12 RDT 0 FRIDGE 1      -> {"ACT": 12, "RDT": 0, "FRIDGE": 1}
    PENTA 40 FRIDGE 0          -> {"PENTA": 40, "FRIDGE": 0}
    REPORT SENT                -> {"REPORT_SENT": True}
    RECEIVED ACT 200           -> {"RECEIVED": {"ACT": 200}}
    HELP                       -> {"HELP": True}

parse_status: ok (all recognised; every expected field present), partial (something recognised but an
expected field is missing or words were not understood), unparseable (nothing recognised). Unparseable
replies become a "needs human review" task for the case owner.
"""
from __future__ import annotations

import re

KEYWORDS = ["ACT", "RDT", "FRIDGE", "PENTA", "REPORT", "RECEIVED", "HELP"]
ALIASES = {
    "ACTS": "ACT", "AL": "ACT", "ACTAL": "ACT", "COARTEM": "ACT",
    "RDTS": "RDT", "MRDT": "RDT", "TEST": "RDT", "TESTS": "RDT", "KITS": "RDT",
    "FRIG": "FRIDGE", "FRIDGES": "FRIDGE", "REFRIGERATOR": "FRIDGE", "FREEZER": "FRIDGE", "FRIDG": "FRIDGE",
    "PENTAVALENT": "PENTA", "PENTA3": "PENTA", "VACCINE": "PENTA", "VACCINES": "PENTA",
    "REPORTS": "REPORT", "RPT": "REPORT", "RECIEVED": "RECEIVED", "RECEIVE": "RECEIVED", "RCVD": "RECEIVED",
    "GOT": "RECEIVED",
}
FILLER = {"PLS", "PLEASE", "THANKS", "THANK", "YOU", "SIR", "MA", "MADAM", "DEAR", "OK", "STOCK", "IS", "ARE",
          "WE", "HAVE", "THE", "AND", "OF", "IN", "AT", "NOW", "TODAY", "REF", "MY", "OUR", "PACKS", "PACK",
          "DOSES", "DOSE", "UNITS", "PCS", "BALANCE", "LEFT", "REMAINING", "HELLO", "HI", "GOOD", "MORNING",
          "AFTERNOON", "EVENING", "REGARDS", "OIC", "FROM", "SENTINEL", "DEMO", "COUNT", "QTY", "QUANTITY"}
ZERO = {"NIL", "NONE", "ZERO", "NO", "O", "NULL", "FINISHED", "OUT", "EMPTY"}
FRIDGE_OK = {"1", "OK", "OKAY", "YES", "Y", "WORKING", "WORKS", "FINE", "GOOD", "FUNCTIONAL", "ON", "FIXED", "REPAIRED"}
FRIDGE_BAD = {"0", "NO", "N", "BAD", "SPOILT", "SPOILED", "BROKEN", "FAULTY", "DOWN", "OFF", "DEAD", "NOTWORKING"}
SENT_WORDS = {"SENT", "SUBMITTED", "DONE", "SEND", "SUBMIT", "UPLOADED", "ENTERED"}
REF_RE = re.compile(r"\bC\s*-?\s*(\d{3,7})\b", re.IGNORECASE)


def _edit1(a: str, b: str) -> bool:
    """True when a and b differ by at most one edit (insert, delete, substitute or adjacent swap)."""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        diff = [i for i in range(la) if a[i] != b[i]]
        if len(diff) == 1:
            return True
        return len(diff) == 2 and diff[1] == diff[0] + 1 and a[diff[0]] == b[diff[1]] and a[diff[1]] == b[diff[0]]
    if la > lb:
        a, b = b, a
    for i in range(len(b)):
        if a == b[:i] + b[i + 1:]:
            return True
    return False


def keyword(tok: str) -> str | None:
    if tok in KEYWORDS:
        return tok
    if tok in ALIASES:
        return ALIASES[tok]
    if len(tok) >= 3 and not tok.isdigit():
        for k in KEYWORDS:
            if len(k) >= 3 and _edit1(tok, k) and not (k == "ACT" and tok in ("AT", "CAT")):
                return k
    return None


def _num(tok: str | None) -> float | None:
    if tok is None:
        return None
    if tok.isdigit():
        return float(tok)
    if tok in ZERO:
        return 0.0
    return None


def normalise(text: str) -> tuple[list[str], str | None]:
    t = text.upper()
    ref = None
    m = REF_RE.search(t)
    if m:
        ref = f"C-{m.group(1)}"
        t = REF_RE.sub(" ", t)
    t = t.replace("NOT WORKING", "NOTWORKING").replace("NOT WORK", "NOTWORKING")
    t = re.sub(r"[,;:=/\\\-\.\(\)\[\]#*_+!?'\"]", " ", t)
    t = re.sub(r"(?<=[A-Z])(?=\d)|(?<=\d)(?=[A-Z])", " ", t)     # ACT12 -> ACT 12, 12ACT -> 12 ACT
    return t.split(), ref


def parse(text: str, expects: list[str] | None = None) -> dict:
    toks, ref = normalise(text or "")
    out: dict = {}
    unknown: list[str] = []
    i, n = 0, len(toks)
    # "12 ACT 30 RDT": when the message opens with a number then a quantity word, numbers precede words.
    qty_words = ("ACT", "RDT", "PENTA")
    num_first = n >= 2 and _num(toks[0]) is not None and toks[0].isdigit() and keyword(toks[1]) in qty_words
    while i < n:
        tok = toks[i]
        k = keyword(tok)
        nxt = toks[i + 1] if i + 1 < n else None
        if k in qty_words and num_first:
            if i > 0 and toks[i - 1].isdigit():
                out[k] = float(toks[i - 1])
            else:
                out.setdefault("_missing_qty", []).append(k)
            i += 1
            continue
        if k in qty_words:
            v = _num(nxt)
            if v is None and i > 0 and toks[i - 1].isdigit():
                v = float(toks[i - 1])              # "12 ACT" (number before the word)
            if v is not None:
                out[k] = v
                i += 2 if _num(nxt) is not None else 1
                continue
            out.setdefault("_missing_qty", []).append(k)
            i += 1
            continue
        if k == "FRIDGE":
            if nxt in FRIDGE_OK:
                out["FRIDGE"] = 1; i += 2; continue
            if nxt in FRIDGE_BAD:
                out["FRIDGE"] = 0; i += 2; continue
            if nxt == "NOT" and i + 2 < n and toks[i + 2] in FRIDGE_OK:
                out["FRIDGE"] = 0; i += 3; continue
            out.setdefault("_missing_qty", []).append("FRIDGE")
            i += 1
            continue
        if k == "REPORT":
            if nxt in SENT_WORDS:
                out["REPORT_SENT"] = True; i += 2; continue
            if i > 0 and toks[i - 1] in SENT_WORDS:
                out["REPORT_SENT"] = True; i += 1; continue
            out["REPORT_SENT"] = True
            out.setdefault("_vague", []).append("REPORT")
            i += 1
            continue
        if k == "RECEIVED":
            rec: dict = out.get("RECEIVED", {})
            j = i + 1
            while j < n:
                a, b = toks[j], toks[j + 1] if j + 1 < n else None
                ka, kb = keyword(a), keyword(b) if b else None
                if ka in ("ACT", "RDT", "PENTA") and _num(b) is not None:
                    rec[ka] = _num(b); j += 2
                elif a.isdigit() and kb in ("ACT", "RDT", "PENTA"):
                    rec[kb] = float(a); j += 2
                else:
                    break
            if not rec and j < n and toks[j].isdigit():
                rec["ACT"] = float(toks[j]); j += 1     # "RECEIVED 200": assume the commodity asked about
                out.setdefault("_vague", []).append("RECEIVED")
            out["RECEIVED"] = rec or {"_unspecified": True}
            i = j
            continue
        if k == "HELP":
            out["HELP"] = True; i += 1; continue
        if tok in FILLER or tok.isdigit() and i + 1 < n and keyword(toks[i + 1]) in ("ACT", "RDT", "PENTA"):
            i += 1
            continue
        if tok in SENT_WORDS and nxt and keyword(nxt) == "REPORT":
            i += 1
            continue
        unknown.append(tok)
        i += 1

    missing_qty = out.pop("_missing_qty", [])
    vague = out.pop("_vague", [])
    recognised = [k for k in ("ACT", "RDT", "FRIDGE", "PENTA", "REPORT_SENT", "RECEIVED", "HELP") if k in out]
    exp = [e.upper() for e in (expects or [])]
    exp_map = {"REPORT": "REPORT_SENT"}
    missing_expected = [e for e in exp if exp_map.get(e, e) not in out] if exp and "HELP" not in out and "RECEIVED" not in out else []
    if not recognised:
        status = "unparseable"
    elif unknown or missing_qty or vague or missing_expected:
        status = "partial"
    else:
        status = "ok"
    return {"fields": out, "status": status, "unknown": unknown, "missing_quantity": missing_qty,
            "missing_expected": missing_expected, "vague": vague, "ref": ref}
