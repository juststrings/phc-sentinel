"""Operational truth: what actually happens at each facility, before anyone reports it.

Everything here is SIMULATED. Reporting behaviour is generated separately in
reporting.py, so a stressed facility can report well or badly and a stable one
can go silent (proposal §10.1).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..config import settings

# Malaria seasonality comes from settings (simulator.seasonality), one profile per state.
RI_SEASON = np.array([1.00, 1.00, 1.05, 1.05, 1.00, 0.95, 0.90, 0.85, 0.90, 1.00, 1.05, 1.10])

COMMODITIES = ["ACT_AL_ADULT", "ACT_AL_CHILD", "RDT_MAL"]
ACT_ADULT_SHARE = 0.55


@dataclass
class Truth:
    months: list[pd.Period]
    facilities: pd.DataFrame          # facility attributes (synthetic, seeded)
    monthly: pd.DataFrame             # facility x month: services, RI, vaccine, strain
    stock: pd.DataFrame               # facility x month x commodity: stock flow
    events: list[dict]                # scenarios planted in the truth


def facility_attributes(dim: pd.DataFrame, rng: np.random.Generator, sim: dict) -> pd.DataFrame:
    """`sim` holds the state's labelled simulator parameters (settings.yaml,
    simulator.state_defaults + the state's overrides). The draw order is fixed, so a
    state with default parameters reproduces the original Bauchi simulation exactly."""
    n = len(dim)
    lgas = dim["lga"].unique()
    # LGA-level heterogeneity in reporting and supply. Defaults are anchored on published
    # Bauchi RI reporting (~65% timeliness, ~71% completeness in a weak LGA) [14].
    lga_report = dict(zip(lgas, rng.uniform(*sim["report_range"], len(lgas))))
    lga_timely = dict(zip(lgas, rng.uniform(*sim["timely_range"], len(lgas))))
    lga_supply = dict(zip(lgas, rng.uniform(*sim["supply_range"], len(lgas))))
    lga_lmis = dict(zip(lgas, rng.uniform(*sim["lmis_range"], len(lgas))))

    a = pd.DataFrame({"facility_id": dim["facility_id"].values, "lga": dim["lga"].values})
    a["base_opd"] = np.clip(rng.lognormal(np.log(sim["base_opd_median"]), 0.6, n), 40, 3000)
    # ~25% of OPD at season index 1, scaled by the state's relative malaria burden.
    a["malaria_share"] = np.clip(rng.beta(5, 15, n) * sim["malaria_burden"], 0, 0.9)
    a["positivity"] = rng.uniform(0.40, 0.70, n)
    a["anc_rate"] = rng.uniform(0.04, 0.08, n)
    a["delivery_rate"] = rng.uniform(0.02, 0.05, n)
    a["penta_rate"] = rng.uniform(0.035, 0.065, n)
    a["dropout"] = rng.uniform(0.05, 0.20, n)
    a["sessions_planned"] = rng.choice([4, 4, 6, 8], n)
    a["fridge_fail_p"] = rng.choice([0.01, 0.02, 0.05], n, p=[0.6, 0.3, 0.1])
    a["p_report"] = np.clip(a["lga"].map(lga_report) + rng.normal(0, 0.07, n), 0.35, 0.99)
    a["p_on_time"] = np.clip(a["lga"].map(lga_timely) + rng.normal(0, 0.08, n), 0.30, 0.99)
    a["p_field_missing"] = rng.choice([0.01, 0.03, 0.10], n, p=[0.6, 0.3, 0.1])
    a["p_lmis_report"] = np.clip(a["lga"].map(lga_lmis) + rng.normal(0, 0.06, n), 0.40, 0.99)
    a["supply_reliability"] = np.clip(a["lga"].map(lga_supply) + rng.normal(0, 0.04, n), 0.5, 0.99)
    a["trend"] = rng.normal(0.03, 0.03, n)                     # annual demand drift
    return a


def simulate_truth(dim: pd.DataFrame, rng: np.random.Generator, sim: dict) -> Truth:
    s = settings()
    cal = s["calendar"]
    months = list(pd.period_range(cal["first_period"], cal["last_period"], freq="M"))
    T, F = len(months), len(dim)
    attrs = facility_attributes(dim, rng, sim)
    malaria_season = np.array(s["simulator"]["seasonality"][sim["season"]], dtype=float)
    scen = s["simulator"]

    # ---- Planted scenarios ---------------------------------------------------
    events: list[dict] = []
    demand_mult = np.ones((T, F))
    supply_block = np.zeros((T, F), dtype=bool)
    silence_from = np.full(F, T)          # month index from which the facility stops reporting
    lmis_stop_from = np.full(F, T)        # month index from which NHLMIS reporting stops

    idx = rng.permutation(F)
    n_det = max(3, int(F * scen["scenario_share_deteriorating"]))
    reliable = idx[attrs["p_report"].values[idx] >= 0.88]
    n_sil = max(2, int(F * scen["scenario_share_silent_before"]))
    sil_ids = reliable[:n_sil]
    det_ids = np.setdiff1d(idx, sil_ids)[:n_det]
    calm_ids = np.setdiff1d(idx, np.concatenate([sil_ids, det_ids]))[: max(3, F // 100)]

    for kind, ids in (("deteriorating", det_ids), ("silent_before_stockout", sil_ids)):
        for f in ids:
            t_out = int(rng.integers(18, T))              # planted stockout month index
            start = t_out - 4
            ramp = np.linspace(1.25, 1.9, t_out - start + 1)
            demand_mult[start:t_out + 1, f] *= ramp
            supply_block[start:t_out + 1, f] = True
            ev = {"event_type": kind, "facility_id": attrs.at[f, "facility_id"],
                  "start_period": months[start], "target_period": months[t_out]}
            if kind == "silent_before_stockout":
                silence_from[f] = t_out - 2
                lmis_stop_from[f] = t_out - 2
            events.append(ev)

    for f in calm_ids:
        stop = int(rng.integers(14, T - 4))
        lmis_stop_from[f] = stop
        events.append({"event_type": "calm_stale_commodity", "facility_id": attrs.at[f, "facility_id"],
                       "start_period": months[stop], "target_period": None})

    # Genuine demand surges (outbreaks): real pressure, not data error.
    surge = rng.random((T, F)) < 0.004
    surge[:8] = False
    for t, f in zip(*np.nonzero(surge)):
        mult = rng.uniform(1.8, 2.6)
        demand_mult[t:t + 2, f] *= mult
        events.append({"event_type": "demand_surge", "facility_id": attrs.at[f, "facility_id"],
                       "start_period": months[t], "target_period": months[min(t + 1, T - 1)]})

    # ---- Monthly services and RI --------------------------------------------
    cal_idx = np.array([m.month - 1 for m in months])
    years = np.arange(T) / 12.0
    noise = rng.lognormal(0, 0.12, (T, F))
    level = attrs["base_opd"].values[None, :] * (1 + attrs["trend"].values[None, :] * years[:, None]) * noise
    mal_season = malaria_season[cal_idx][:, None]
    opd_season = 0.8 + 0.2 * mal_season
    malaria_mu = level * attrs["malaria_share"].values * mal_season * demand_mult
    confirmed = rng.poisson(malaria_mu)
    opd = rng.poisson(level * opd_season) + confirmed
    anc1 = rng.poisson(level * attrs["anc_rate"].values)
    deliveries = rng.poisson(level * attrs["delivery_rate"].values)

    fridge_ok = np.ones((T, F), dtype=bool)
    vacc_stockout = np.zeros((T, F), dtype=bool)
    sessions_conducted = np.zeros((T, F), dtype=int)
    penta1 = np.zeros((T, F), dtype=int)
    penta3 = np.zeros((T, F), dtype=int)
    vacc_balance = np.zeros((T, F), dtype=int)
    planned = np.tile(attrs["sessions_planned"].values, (T, 1))
    ok = np.ones(F, dtype=bool)
    p1_prev = np.round(level[0] * attrs["penta_rate"].values).astype(int)
    for t in range(T):
        fail = rng.random(F) < attrs["fridge_fail_p"].values
        repair = rng.random(F) < 0.35
        ok = np.where(ok, ~fail, repair)
        fridge_ok[t] = ok
        p_so = np.where(ok, 0.035, 0.45) * (1 + (supply_block[t] * 0.5))
        vacc_stockout[t] = rng.random(F) < p_so
        p_conduct = np.where(vacc_stockout[t], 0.55, 0.92)
        sessions_conducted[t] = rng.binomial(planned[t], p_conduct)
        ri_mu = level[t] * attrs["penta_rate"].values * RI_SEASON[cal_idx[t]] * (sessions_conducted[t] / planned[t])
        penta1[t] = rng.poisson(ri_mu)
        penta3[t] = rng.binomial(np.maximum(p1_prev, 0), 1 - attrs["dropout"].values)
        p1_prev = penta1[t]
        need = penta1[t] + penta3[t]
        vacc_balance[t] = np.where(vacc_stockout[t], rng.integers(0, 3, F), np.round(need * rng.uniform(0.8, 2.5, F)))

    # ---- Malaria commodity stock flow (monthly truth) -------------------------
    demand = {
        "ACT_AL_ADULT": confirmed * ACT_ADULT_SHARE,
        "ACT_AL_CHILD": confirmed * (1 - ACT_ADULT_SHARE),
        "RDT_MAL": confirmed / attrs["positivity"].values[None, :],
    }
    # Noise-free planning demand: the LMCU pre-positions stock ahead of the
    # rainy season, so orders follow the seasonal forecast, not only past use.
    plan_confirmed = attrs["base_opd"].values[None, :] * (1 + attrs["trend"].values[None, :] * years[:, None])         * attrs["malaria_share"].values * mal_season
    plan = {"ACT_AL_ADULT": plan_confirmed * ACT_ADULT_SHARE, "ACT_AL_CHILD": plan_confirmed * (1 - ACT_ADULT_SHARE),
            "RDT_MAL": plan_confirmed / attrs["positivity"].values[None, :]}
    # One LGA delivery carries all malaria commodities: success is shared across products.
    delivery_ok = rng.random((T, F)) < attrs["supply_reliability"].values[None, :]
    stock_rows = []
    max_m = s["commodity"]["max_months"]
    for c in COMMODITIES:
        dem = np.round(demand[c] * rng.uniform(0.9, 1.1, (T, F))).astype(int)
        expected = np.maximum(dem.mean(axis=0), 1)
        stock = np.round(expected * rng.uniform(2.0, 4.0, F)).astype(int)
        pending = np.zeros(F, dtype=int)
        for t in range(T):
            # Planted deterioration: run stock down toward a stockout.
            first_block = supply_block[t] & ~(supply_block[t - 1] if t else np.zeros(F, dtype=bool))
            stock = np.where(first_block, np.minimum(stock, np.round(expected * 2.8)).astype(int), stock)
            receipts = np.where(supply_block[t], 0, pending)
            pending = np.zeros(F, dtype=int)
            opening = stock
            available = opening + receipts
            dispensed = np.minimum(dem[t], available)
            days = months[t].days_in_month
            short = np.where(dem[t] > 0, 1 - available / np.maximum(dem[t], 1), 0)
            days_out = np.where(dem[t] > available, np.clip(np.round(days * short), 1, days), 0)
            losses = np.where(rng.random(F) < 0.05, np.round((available - dispensed) * 0.02), 0).astype(int)
            closing = available - dispensed - losses
            stock_rows.append(pd.DataFrame({
                "t": t, "fi": np.arange(F), "commodity_code": c, "opening": opening, "received": receipts,
                "demand": dem[t], "dispensed": dispensed, "losses": losses, "closing": closing,
                "days_out": days_out.astype(int), "days_in_month": days,
            }))
            stock = closing
            # Bimonthly resupply (min-max): order at the end of each even month, delivered next month.
            if months[t].month % 2 == 0:
                recent = dem[max(0, t - 5):t + 1].mean(axis=0)
                forecast = plan[c][t + 1:t + 3].mean(axis=0) if t + 1 < T else recent
                order = np.maximum(np.round(max_m * np.maximum(recent, forecast) - stock), 0)
                delivered = delivery_ok[t]
                fill = np.where(rng.random(F) < 0.8, rng.uniform(0.9, 1.0, F), rng.uniform(0.5, 0.8, F))
                pending = np.where(delivered, np.round(order * fill), 0).astype(int)
    stock_df = pd.concat(stock_rows, ignore_index=True)

    strain = (stock_df.groupby(["t", "fi"])["days_out"].max().unstack().reindex(range(T)).values > 0) | ~fridge_ok \
        | (demand_mult > 1.5)

    monthly = pd.DataFrame({
        "t": np.repeat(np.arange(T), F), "fi": np.tile(np.arange(F), T),
        "opd": opd.ravel(), "confirmed_malaria": confirmed.ravel(), "anc1": anc1.ravel(),
        "deliveries": deliveries.ravel(), "penta1": penta1.ravel(), "penta3": penta3.ravel(),
        "sessions_planned": planned.ravel(), "sessions_conducted": sessions_conducted.ravel(),
        "vaccine_stockout_flag": vacc_stockout.ravel(), "vaccine_stock_balance": vacc_balance.ravel(),
        "refrigerator_functional": fridge_ok.ravel(), "strain": strain.ravel(),
        "silenced": (np.arange(T)[:, None] >= silence_from[None, :]).ravel(),
        "lmis_stopped": (np.arange(T)[:, None] >= lmis_stop_from[None, :]).ravel(),
    })
    monthly["period"] = [months[t] for t in monthly["t"]]
    monthly["facility_id"] = attrs["facility_id"].values[monthly["fi"]]
    stock_df["period"] = [months[t] for t in stock_df["t"]]
    stock_df["facility_id"] = attrs["facility_id"].values[stock_df["fi"]]

    # Resolve the actual planted stockout month from the truth.
    first_out = (stock_df[stock_df["commodity_code"].str.startswith("ACT") & (stock_df["days_out"] > 0)]
                 .groupby(["facility_id", "t"]).size().reset_index())
    for ev in events:
        if ev["event_type"] in ("deteriorating", "silent_before_stockout"):
            start_t = months.index(ev["start_period"])
            hits = first_out[(first_out["facility_id"] == ev["facility_id"]) & (first_out["t"] >= start_t)]["t"]
            ev["stockout_period"] = months[int(hits.min())] if len(hits) else None

    return Truth(months=months, facilities=attrs, monthly=monthly, stock=stock_df, events=events)
