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
| D8 | Not specified | GRID3 facilities with coordinates outside Bauchi (28) are kept but not mapped | They still report to DHIS2; dropping them would remove them from monitoring. | `coord_status` (superseded by D11) |

## 12-state extension and National Command Centre (10 Oct 2026)

| # | Request / proposal | Build | Why | Where |
|---|---|---|---|---|
| D9 | 12 states, 2 per zone: Kano, Kaduna, Bauchi, Adamawa, FCT, Niger, **Lagos**, Oyo, Enugu, **Anambra**, **Rivers**, **Cross River** | **Lagos → Ogun**, **Anambra → Abia**, **Rivers → Delta**, **Cross River → Bayelsa** | Step-1 check: GRID3 Health Facilities v3.0 covers 24 states; Lagos, Anambra, Rivers and Cross River are not in it (the LGA boundary layer covers all 37). Same-zone substitutes from v3.0 keep one consistent facility source. Ogun borders Lagos; Abia is the only other South East state in v3.0; Delta and Bayelsa are the only South South states in v3.0. **Alternative not taken:** GRID3 v2.0 (`GRID3_NGA_health_facilities_v2_0`) does cover the four states (public primary: Lagos 572, Anambra 818, Rivers 421, Cross River 1,176) but has an older, different schema (no `functional`, no GRID3 flag counts) and would mix two releases. Switching is a config change plus a v2 field mapping. | `states` in settings.yaml |
| D10 | One state | The state list, zones, GRID3 names and per-state parameters live in `settings.yaml`; every pipeline step takes a state code and reads/writes `data/states/{code}/` | No state-specific code anywhere. Adding a state is a settings entry plus `fetch-grid3`. | `config.py` (`states()`, `StatePaths`) |
| D11 | Single "outside state" flag | Two tags: **Near boundary** (outside its own LGA polygon, within `geography.near_boundary_km` = 5 km; mapped) and **Location unverified** (further; kept in every queue, not mapped). Distance is to the facility's own LGA polygon, the stricter of "state or LGA". `in_state` is kept as a separate column. | A point a few hundred metres outside a simplified boundary is a precision issue, not an error; one 20 km away cannot be trusted on a map but the facility still reports. | `grid3.coord_status`, `geography` |
| D12 | LGA alias table in code | Per-state `lga_aliases` in settings (Bauchi `damban→dambam`, Kano `garummallam→garunmalam`) | Lists live in config; aliases can differ by state. | `states[].lga_aliases` |
| D13 | Synthetic LMIS facility codes `BA-LMIS-xxxxxx` | `{GRID3 state code}-LMIS-` + 6 hex characters, lengthened for a whole state only on a collision | Bayelsa had a 6-character hash collision. Bauchi codes are unchanged. | `grid3._lmis_codes` |
| D14 | One seed | Seed = `simulator.seed + seed_offset` per state (Bauchi offset 0), and per-state parameters (`report_range`, `timely_range`, `lmis_range`, `supply_range`, `base_opd_median`, `malaria_burden`, `season`) drawn in the original order | Bauchi with default parameters reproduces the original simulation exactly (regression test); other states are independent and individually reproducible. | `simulator.state_defaults`, `states[].sim` |
| D15 | Status label per state (requested: "status label in text") | Four labels mirroring Risk x Confidence at state level: **Act and verify**, **High action load** (ACT NOW share >= 17%), **Evidence gap** (Data Verification share >= 36%), **Watch** (neither). Thresholds set near the middle of the simulated state range. | A first setting (10% / 33%) put 9 of 12 states in one label and told a reader nothing. "Watch" rather than "Stable": a state below both thresholds still has PHCs to act on. Always shown as icon + text. | `national.status` |
| D16 | National view | State aggregates only, precomputed at build time (`mart_state_month`, `mart_zone_month`, `mart_national_month`); counts are summed and every rate is recomputed from summed counts | National totals then equal the sum of states by construction (tested), and a small state cannot pull a national rate toward its own. `/national/states` is ~5 KB gzipped. | `sentinel/national.py` |
| D17 | Map colour | Single-hue sequential blue, 5 equal-interval classes over the 12 states; darker (light theme) / brighter (dark theme) always means "needs more attention", so reporting completeness runs high → low. States not in the demo are neutral grey and labelled "Not in demo" (legend and tooltip). | One reading rule for every metric; no red/green; status colours stay reserved for queue state. | `NationalMap.tsx` |
| D18 | Routes | `/` role switcher, `/national`, `/national/briefing`, `/state/{code}`, `/state/{code}/lga/{id}`, `/state/{code}/facility/{id}`. Old `/lga/{id}` and `/facility/{id}` redirect; old single-state API paths remain as deprecated aliases for the default state. | Every view is one click from the landing page and shareable; nothing that linked to the Bauchi build breaks. Brief, metric and filters are kept in the URL (`/national?state=kano&metric=pct_stale`). | `web/app`, `api/main.py` |
| D19 | Access | No login in the demo. A pilot adds real authentication with state-scoped access, enforced in the API as well as the interface (About page). | Judges must reach any view logged out. | About page |
| D20 | Database | `shm_size: 512mb` on the PostGIS container and `ANALYZE` instead of `VACUUM ANALYZE` after load | At 12 states (3.4 GB) the default 64 MB `/dev/shm` is too small for maintenance work. | `docker-compose.yml`, `db.py` |

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
  entirely Data Verification (Oct and Nov 2023: about 96%). `/state/{code}/summary` flags these leading months (`warmup`) and the
  "Queue sizes over time" chart starts after them. The flag is derived from the data (leading months with no Monitor facility),
  not hard-coded.
- **Two coordinate counts.** `/state/{code}/coords` returns `outside_state` (outside every polygon of the state, the original D8
  idea) and `unverified` (`coord_status = 'location_unverified'`, more than `geography.near_boundary_km` outside the facility's own
  LGA, D11), plus `near_boundary`. The state map note uses the first; the facilities directory flag uses the second. They are
  different definitions and are not substituted for each other.

## View-as scope (the row-level filter)

| # | Question | Decision | Why | Where |
|---|---|---|---|---|
| V1 | How are national, state and LGA separated without a login? | Like Power BI's "View as": the web app sends `X-View-As: national | state:<code> | lga:<code>:<lga_id>` with every API call and the API enforces it. The choice is made in the browser, so this is demo-grade separation; a pilot replaces `viewas.parse()` with a verified identity and keeps the rules. | A demo needs to switch viewpoint in one click; real accounts add nothing to what is being shown. | `sentinel/viewas.py`, middleware in `sentinel/api/main.py` |
| V2 | What stops a forgotten filter leaking numbers? | Two layers: a path check for every request (deny by default for state and LGA views) and row clamps inside every handler that lists or fetches rows by id (facility directory, search, cases, messages, replies, people). A request with no header gets 401; `/health`, `/meta/*` and the clock stay open. | Aderoju's API checked scope only on writes; any read endpoint served any state. | `authorize()`, `clamp()`, `check_case()`, `check_person()` |
| V3 | What does each view see? | National: everything. State board: its state and its LGAs. LGA team: its LGA and its clinics; state-wide figures (summary, top, map, insights, resupply) return 403. | Matches the portal rules; the owner chose full access for national. | `authorize()` |
| V4 | Who can you act as? | The person you act as (cases, approvals, replies) must sit inside the chosen view: a state board cannot act as a national officer or another state's director. | Stops a state view from approving another state's messages. | `check_persona()` via `actions/scope.persona()` |
| V5 | How is it tested? | `tests/test_view_as.py` calls the real API as each kind of viewer and asserts routes are refused and no row from another state or LGA appears in lists, search, cases, messages, replies or people. | | `tests/test_view_as.py` |
