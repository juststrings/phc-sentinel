# Assumptions register (proposal Appendix C, extended)

| ID | Assumption | Basis | Handling |
|---|---|---|---|
| A1 | Service reporting is monthly; programme commodities bimonthly | Published system descriptions [10][16] | Built into the spine (`spine.py`) |
| A2 | Facility minimum stock 2 months, maximum 4 | Published Nigerian min-max policy [10] | `commodity.min_months`, `max_months` |
| A2b | Emergency order point 1 month | Min-max practice; **confirm against [10] in Phase 0** | `commodity.eop_months` |
| A3 | Strain modestly increases the chance of silence | Capacity-related non-reporting evidence [17] | Simulator parameter `strain_silence_multiplier` (1.5), labelled |
| A4 | Demand above the seasonal baseline signals pressure | Consumption follows service volume | Worded as pressure; capped at Watch alone (D1) |
| A5 | Robust z, session and dropout thresholds | Statistical convention, design judgement | All in `settings.yaml`; sensitivity tests in Phase 8 |
| A6 | Operational history is synthetic | No public facility-level longitudinal data | Banner on every page, `meta_data_labels` table |
| A7 | States can export from DHIS2 | States and LGAs use DHIS2 monthly [16] | Adapter reads data value set + registration exports |
| A8 | Analysis runs 30 days after month end; DHIS2 deadline 15 days; NHLMIS deadline 15 days after period end | Design judgement | `calendar`, `reporting` in settings |
| A9 | One LGA delivery carries all malaria commodities | LMCU distribution practice | Simulator: delivery success shared across products |
| A10 | The LMCU pre-positions malaria commodities ahead of the rainy season | NMEP seasonal planning | Simulator: orders follow max(recent use, seasonal forecast) |
| A11 | Simulated reporting rates fall within published Bauchi ranges | [14]: ~65% timeliness, ~71% completeness in a weak LGA | `realism_report.json`: completeness 0.80, timeliness 0.67 |
| A12 | DHIS2 org unit UIDs and LMIS facility codes link to GRID3 IDs | In a pilot this comes from the state's org unit list / NHFR codes | Synthetic deterministic keys in `dim_facility` |
| A13 | Monthly reporting, on-time, NHLMIS reporting and LGA delivery probabilities differ by state | **Design assumption.** No published facility-level 2026 figures exist per state; ranges are spread so the national view shows contrast, and stay within the published Bauchi range used for A11 ([14]: ~65% timeliness, ~71% completeness in a weak LGA). They are not claims about any state. | `states[].sim.*_range`; realism report per state |
| A14 | Malaria seasonality has three profiles: `sudan_sahel` (short, sharp Aug–Oct peak), `guinea_savanna` (the original Bauchi profile), `forest_south` (longer, flatter Apr–Oct season) | **Design assumption**, direction from the north–south gradient in rainy-season length; magnitudes are not survey values | `simulator.seasonality`, `states[].sim.season` |
| A15 | Relative malaria burden: higher in the North West / North Central demo states, lower in the South and FCT | **Design assumption**; direction informed by the zonal gradient reported in the Nigeria Malaria Indicator Survey 2021. Multipliers (0.70–1.10) are not the survey's prevalence values. | `states[].sim.malaria_burden` |
| A16 | Median monthly OPD attendance per PHC differs by state (260–450) | **Design assumption** | `states[].sim.base_opd_median` |
| A17 | Facilities more than 5 km outside their own LGA polygon cannot be placed reliably on a map | **Design assumption** (boundary simplification and GRID3 geocoding precision) | `geography.near_boundary_km`; D11 |
| A18 | A state is "High action load" at >= 17% of PHCs in ACT NOW and has an "Evidence gap" at >= 36% in Data Verification | **Design assumption**, set near the middle of the simulated state range; a pilot would set them with state M&E teams | `national.status`; D15 |
| A19 | Ogun, Abia, Delta and Bayelsa stand in for Lagos, Anambra, Rivers and Cross River | GRID3 Health Facilities v3.0 coverage (Step-1 check, 10 Oct 2026) | D9 |

## Per-state simulator parameters (A13–A16)

All values are labelled simulator inputs in `config/settings.yaml`. Bauchi uses the defaults
(`simulator.state_defaults`), which are the original single-state calibration. The last column is the
simulated result over 36 months (final DHIS2 completeness / timeliness / NHLMIS reporting rate), from each
state's `realism_report.json`; every state passes the realism checks (no impossible stock flows,
completeness 0.65–0.97, timeliness 0.55–0.92).

| State | Zone | Monthly report | On time | NHLMIS report | LGA delivery | OPD median | Malaria burden | Season | Simulated completeness / timeliness / NHLMIS |
|---|---|---|---|---|---|---|---|---|---|
| Kano | North West | 0.70–0.93 | 0.72–0.92 | 0.70–0.95 | 0.84–0.97 | 420 | 1.10 | sudan_sahel | 0.80 / 0.66 / 0.81 |
| Kaduna | North West | 0.78–0.96 | 0.75–0.95 | 0.74–0.96 | 0.84–0.97 | 380 | 1.00 | guinea_savanna | 0.84 / 0.72 / 0.82 |
| Bauchi | North East | 0.74–0.95 | 0.75–0.95 | 0.70–0.95 | 0.84–0.97 | 350 | 1.00 | guinea_savanna | 0.80 / 0.68 / 0.79 |
| Adamawa | North East | 0.66–0.90 | 0.68–0.90 | 0.70–0.95 | 0.80–0.95 | 300 | 1.05 | guinea_savanna | 0.74 / 0.59 / 0.79 |
| FCT (Abuja) | North Central | 0.84–0.97 | 0.82–0.96 | 0.80–0.97 | 0.88–0.98 | 450 | 0.70 | guinea_savanna | 0.87 / 0.79 / 0.87 |
| Niger | North Central | 0.70–0.92 | 0.75–0.95 | 0.66–0.92 | 0.82–0.96 | 300 | 1.10 | guinea_savanna | 0.77 / 0.66 / 0.80 |
| Ogun | South West | 0.80–0.96 | 0.78–0.95 | 0.70–0.95 | 0.84–0.97 | 320 | 0.75 | forest_south | 0.86 / 0.75 / 0.78 |
| Oyo | South West | 0.76–0.95 | 0.75–0.95 | 0.70–0.95 | 0.84–0.97 | 330 | 0.80 | forest_south | 0.83 / 0.70 / 0.80 |
| Enugu | South East | 0.80–0.96 | 0.75–0.95 | 0.76–0.96 | 0.84–0.97 | 300 | 0.80 | forest_south | 0.83 / 0.71 / 0.84 |
| Abia | South East | 0.72–0.93 | 0.70–0.92 | 0.70–0.95 | 0.84–0.97 | 280 | 0.80 | forest_south | 0.81 / 0.69 / 0.80 |
| Delta | South South | 0.74–0.94 | 0.75–0.95 | 0.70–0.95 | 0.82–0.96 | 300 | 0.85 | forest_south | 0.82 / 0.71 / 0.79 |
| Bayelsa | South South | 0.64–0.90 | 0.66–0.90 | 0.62–0.90 | 0.78–0.94 | 260 | 0.90 | forest_south | 0.73 / 0.57 / 0.77 |
