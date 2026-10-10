# Design decisions and departures from the proposal

Each entry records where the build differs from the Final Build Proposal (5 Oct 2026), and why.
Every one is a config value or a single rule, so it can be reverted.

| # | Proposal | Build | Why | Where |
|---|---|---|---|---|
| D1 | Service pressure at robust z >= 3.5 is High and can put a facility in Resource Action on its own (§7.3, Appendix B) | Pressure alone is capped at **Watch** unless another credible domain is at Watch or worse | §7.3 says pressure is a proxy and must never read as a stockout prediction. An uncorroborated "ACT NOW" on a demand spike contradicts that. | `service_pressure.requires_corroboration` |
| D2 | MoS below the 2-month minimum is High (§7.4) | Below the **emergency order point (1 month)** is High; below the 2-month minimum is Watch | NHLMIS counts stock at review time, when it is at its lowest. In a healthy min-max system stock sits near the minimum then, so "below minimum = High" flagged about half of all facilities. The EOP value must be confirmed against [10] in Phase 0. | `commodity.eop_months` |
| D3 | Any stockout days in the period is Critical (§7.4) | Stockout days **with stock still below the minimum** is Critical; a stockout since resupplied above the minimum is Watch | A facility that ran out but now holds 3+ months does not need emergency resupply. | `engines/risk.py` commodity rule |
| D4 | Penta1 to Penta3 dropout "rising sharply" (§7.5) | Dropout on a 3-month rolling sum vs the previous 12 months, +15 points, Penta1 >= 20 | Monthly PHC counts are too small to compare directly; single-month dropout is mostly noise. | `vaccine.dropout_rise_points` |
| D5 | Penta3 > Penta1 coherence (§7.2) | Checked on trailing 12-month totals | Monthly Penta3 legitimately exceeds Penta1 because of the dosing lag; WHO DQR applies this check to annual totals. | `COH_PENTA3_GT_PENTA1` |
| D6 | Outlier check (§7.2) | Two levels: statistical outlier (z >= 3.5, minor) and implausible value (>= 4x expected, severe -> Low confidence) | A 5-10x spike is almost always a keying error. It should send the facility to verification before anyone acts on it. | `dqr.extreme_value_ratio` |
| D7 | Analysis date not specified | Analysis for month M runs **30 days after M ends**; reports submitted later are invisible for that month | Point-in-time correctness: the engines see only what a manager could have seen on that date. | `calendar.analysis_lag_days` |
| D8 | Not specified | GRID3 facilities with coordinates outside Bauchi (28) are kept but not mapped | They still report to DHIS2; dropping them would remove them from monitoring. | `coord_status` |

## TODO: hard-coded constants outside `config/settings.yaml`

Logged, not moved. Moving them would touch engine code, which the UI work did not. Each should become a
settings entry with a basis tag (POLICY, WHO-DQR, STAT or DESIGN) in a later pass.

| Constant | Where | Meaning |
|---|---|---|
| `61` | `sentinel/engines/decision.py:133` | Days of NHLMIS age (one 2-month cycle plus a day) after which a stale commodity report counts as overdue, for ranking. Should derive from `reporting.nhlmis_cycle_months`. |
| `MIN_FACILITIES_FOR_INDEX = 30` | `sentinel/engines/baseline.py:17` | Minimum facilities in a calendar month before it gets a seasonal index value. |
| `>= 10` | `sentinel/engines/dqr.py:114` | Minimum value for the repeated-value rule, so tiny counts are not flagged. |
| `count_r >= 3`, `count_p >= 4`, `median_p >= 10` | `sentinel/engines/dqr.py:126` | Minimum months and volume for the OPD level-shift rule. |
| `dropout(p12, 6, 30)`, `dropout(p3, 2, 20)` | `sentinel/engines/risk.py:133-134` | Minimum months and minimum Penta1 doses for the baseline (6 months, 30 doses) and current (2 months, 20 doses) dropout. |
| `days_out / 30` | `sentinel/engines/risk.py:82` | Days per month when scoring stockout days in the commodity signal. |

## UI notes

- **Warm-up months.** Until history exists no facility can be classed Monitor, so the first months of `mart_lga_month` are almost
  entirely Data Verification (Oct and Nov 2023: about 96%). `/state/summary` flags these leading months (`warmup`) and the
  "Queue sizes over time" chart starts after them. The flag is derived from the data (leading months with no Monitor facility),
  not hard-coded.
- **Two coordinate counts.** `/meta/coords` returns `outside_state` (outside every Bauchi LGA polygon, D8) and `outside_lga`
  (`coord_status = 'invalid'`, more than 5 km outside the facility's own LGA). The state map note uses the first; the facilities
  directory flag uses the second. They are both 28 in the current data but are different definitions.
