"""Live layer: the monthly assessment plus fresh field evidence, without touching the baseline.

    live = baseline (mart_queue / mart_facility_month, latest month)
           + field_verification records newer than the baseline analysis date and no older than
             verification.max_age_days on the simulated clock

Overlay rules (decisions D22-D23):
  1. Stock confirmed adequate: commodity domain set from verified quantity / AMC; confidence may rise to at
     most Moderate, and only when every severe quality reason is liftable (an overdue NHLMIS report).
  2. Shortage confirmed: commodity domain High/Critical from the verified quantity; tag ACT NOW
     (field-verified) because the verification IS the "verify" step.
  3. Fridge reported non-functional: vaccine domain at least High.
  4. Reports submitted: recorded only; confidence recovers only when the real report is ingested.
With no fresh verifications the live row equals the baseline exactly.
"""
from __future__ import annotations

from datetime import date, timedelta

from ..config import actions_cfg, settings

SEV = {"NORMAL": 0, "WATCH": 1, "HIGH": 2, "CRITICAL": 3}
SEV_NAME = {v: k for k, v in SEV.items()}
CONF_RANK = {"LOW": 0, "MODERATE": 1, "HIGH": 2}


def fresh(verifs: list[dict], today: date, baseline_as_of: date) -> list[dict]:
    """Verifications that count: after the baseline analysis date and within max_age_days of today."""
    max_age = actions_cfg()["verification"]["max_age_days"]
    lo = today - timedelta(days=max_age)
    return [v for v in verifs if v["verified_at"] > baseline_as_of and lo <= v["verified_at"] <= today]


def commodity_severity(qty: float | None, amc: float | None) -> int | None:
    """Same boundaries as the commodity engine: stockout Critical, < EOP High, < minimum Watch."""
    if qty is None:
        return None
    c = settings()["commodity"]
    if qty <= 0:
        return SEV["CRITICAL"]
    if not amc or amc <= 0:
        return SEV["WATCH"]          # stock present but no consumption basis: cannot call it adequate
    mos = qty / amc
    if mos < c["eop_months"]:
        return SEV["HIGH"]
    if mos < c["min_months"]:
        return SEV["WATCH"]
    return SEV["NORMAL"]


def live_status(base: dict, severe_rules: set[str], amc: dict[str, float], verifs: list[dict],
                today: date) -> dict:
    """base: the facility's baseline row (mart_facility_month fields). severe_rules: its severe quality
    rule ids. amc: AMC per reply commodity ('ACT', 'RDT'). verifs: its field verifications (any age)."""
    cfg = actions_cfg()["verification"]
    as_of = base["as_of"] if isinstance(base["as_of"], date) else date.fromisoformat(str(base["as_of"])[:10])
    use = sorted(fresh(verifs, today, as_of), key=lambda v: v["verified_at"])
    out = {
        "facility_id": base["facility_id"], "baseline_queue": base["queue"], "baseline_tag": base["tag"],
        "baseline_risk": base["operational_risk"], "baseline_confidence": base["data_confidence"],
        "live_queue": base["queue"], "live_tag": base["tag"], "live_risk": base["operational_risk"],
        "live_confidence": base["data_confidence"], "field_verified": False, "verified_at": None,
        "verification_source": None, "live_reasons": [], "changed": False, "live_field_driven": False,
        # An overdue NHLMIS report stays visible as stale context even when field-verified.
        "nhlmis_stale": bool(base.get("nhlmis_stale")),
    }
    if not use:
        return out

    latest: dict[str, dict] = {}
    for v in use:                                   # newest value per item wins
        if v.get("commodity_code"):
            latest[v["commodity_code"]] = v
        if v.get("fridge_functional") is not None:
            latest["FRIDGE"] = v
    reasons = []
    last = use[-1]
    out.update(field_verified=True, verified_at=last["verified_at"], verification_source=last["source"])

    # Commodity domain from verified quantities.
    csev = [commodity_severity(latest[k]["quantity"], amc.get(k)) for k in ("ACT", "RDT") if k in latest]
    csev = [s for s in csev if s is not None]
    com_field = max(csev) if csev else None
    if com_field is not None:
        parts = [f"{k} {latest[k]['quantity']:.0f}" for k in ("ACT", "RDT") if k in latest]
        when = max(latest[k]["verified_at"] for k in ("ACT", "RDT") if k in latest)
        reasons.append(f"Field count {', '.join(parts)} ({when:%d %b}, {last['source'].replace('_', ' ')})")

    # Vaccine domain from fridge / Penta replies.
    vac_base = SEV.get(base.get("sev_vaccine_cold_chain") or "NORMAL", 0) if base.get("credible_vaccine_cold_chain") else None
    vac_field = None
    pen = latest.get("PENTA")
    fr = latest.get("FRIDGE")
    if fr is not None and fr["fridge_functional"] is False:
        vac_field = SEV["HIGH"]
        if pen is not None and pen["quantity"] <= cfg["penta_stockout_doses"]:
            vac_field = SEV["CRITICAL"]
        reasons.append(f"Refrigerator reported not working ({fr['verified_at']:%d %b})")
    elif pen is not None:
        vac_field = SEV["HIGH"] if pen["quantity"] <= cfg["penta_stockout_doses"] else SEV["NORMAL"]
        reasons.append(f"Field count Penta {pen['quantity']:.0f} doses")
    elif fr is not None and fr["fridge_functional"] is True and vac_base is not None and vac_base >= SEV["HIGH"]             and base.get("vaccine_stockout") is not None:
        # Fridge reported working: with a stockout still reported the domain is High (not Critical);
        # without one, the fridge failure no longer drives it.
        if base["vaccine_stockout"]:
            vac_field = SEV["HIGH"]
        else:
            vac_field = SEV["WATCH"] if base.get("vaccine_watch") else SEV["NORMAL"]
        reasons.append(f"Refrigerator reported working ({fr['verified_at']:%d %b})")

    com_base = SEV.get(base.get("sev_malaria_commodity") or "NORMAL", 0) if base.get("credible_malaria_commodity") else None
    pres = SEV.get(base.get("sev_service_pressure") or "NORMAL", 0) if base.get("credible_service_pressure") else None
    com = com_field if com_field is not None else com_base
    vac = max(x for x in (vac_field, vac_base if vac_field is None else None) if x is not None) \
        if (vac_field is not None or vac_base is not None) else None
    others = [x for x in (com, vac) if x is not None]
    if pres is not None and pres >= SEV["HIGH"] and settings()["service_pressure"]["requires_corroboration"] \
            and not any(x >= SEV["WATCH"] for x in others):
        pres = SEV["WATCH"]
    doms = {"malaria_commodity": com, "vaccine_cold_chain": vac, "service_pressure": pres}
    risk_n = max([x for x in doms.values() if x is not None] or [0])
    driver = max((k for k, x in doms.items() if x is not None), key=lambda k: doms[k], default=None)
    field_driven = (driver == "malaria_commodity" and com_field is not None and com_field == risk_n) or \
                   (driver == "vaccine_cold_chain" and vac_field is not None and vac_field == risk_n)

    # Confidence: a field count lifts only liftable severe reasons, and never above max_confidence.
    conf = base["data_confidence"]
    if com_field is not None and conf == "LOW" and severe_rules and severe_rules <= set(cfg["liftable_rules"]):
        conf = cfg["max_confidence"]
        reasons.append(f"Confidence {conf.lower()}: field-verified {last['verified_at']:%d %b}; "
                       "NHLMIS report still overdue (kept as stale context)")
    elif conf == "LOW" and com_field is not None:
        reasons.append("Confidence stays low: missing or incoherent reports are not cleared by a field count")
    if CONF_RANK[conf] > CONF_RANK[base["data_confidence"]] and CONF_RANK[conf] > CONF_RANK[cfg["max_confidence"]]:
        conf = cfg["max_confidence"]   # defensive: a verification never produces High

    high, low = risk_n >= SEV["HIGH"], conf == "LOW"
    if high and field_driven:
        queue, tag = "RESOURCE_ACTION", "ACT NOW"
        reasons.append("Shortage field-verified: act now")
    elif high and low:
        queue, tag = "RESOURCE_ACTION", "VERIFY THEN ACT"
    elif high:
        queue, tag = "RESOURCE_ACTION", "ACT NOW"
    elif low:
        queue, tag = "DATA_VERIFICATION", "DO NOT ASSUME SAFE"
    else:
        queue, tag = "MONITOR", "MONITOR"
    out.update(live_queue=queue, live_tag=tag, live_risk=SEV_NAME[risk_n], live_confidence=conf,
               live_reasons=reasons, live_field_driven=field_driven)
    out["changed"] = (queue, tag, SEV_NAME[risk_n], conf) != (base["queue"], base["tag"], base["operational_risk"],
                                                            base["data_confidence"])
    return out
