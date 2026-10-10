# Data contract

Every input field answers "where does this come from?" (Phase 0 gate). Class: **real**, **synthetic mirror**
(simulated in the documented structure of a real system), **derived** (computed by Sentinel), **phase two** (not used).

## Coverage

Twelve states, two per geopolitical zone, listed in `config/settings.yaml` (`states`): Kano, Kaduna (North
West); Bauchi, Adamawa (North East); FCT, Niger (North Central); Ogun, Oyo (South West); Enugu, Abia
(South East); Delta, Bayelsa (South South). Ogun, Abia, Delta and Bayelsa replace Lagos, Anambra, Rivers and
Cross River, which are not in GRID3 Health Facilities v3.0 (decision D9). Each state has the same inputs,
in `data/raw/grid3/` (real, committed) and `data/states/{code}/` (generated).

| State | Public PHCs | LGAs | Near boundary | Location unverified |
|---|---|---|---|---|
| Kano | 1,527 | 44 | 5 | 1 |
| Kaduna | 1,363 | 23 | 10 | 17 |
| Bauchi | 1,454 | 20 | 5 | 28 |
| Adamawa | 1,249 | 21 | 7 | 1 |
| FCT (Abuja) | 409 | 6 | 7 | 5 |
| Niger | 2,104 | 25 | 80 | 92 |
| Ogun | 881 | 20 | 40 | 2 |
| Oyo | 1,150 | 33 | 141 | 33 |
| Enugu | 894 | 17 | 62 | 10 |
| Abia | 1,018 | 17 | 94 | 11 |
| Delta | 559 | 25 | 41 | 20 |
| Bayelsa | 316 | 8 | 12 | 11 |
| **Total** | **12,924** | **259** | **504** | **231** |

36 analysis months x 12,924 PHCs = 465,264 facility-months.

## Inputs (what a state would supply)

Paths are per state: `{code}` is the state code (`bauchi`, `kano`, ...).

| File | Format | Class | Fields | Mapped by |
|---|---|---|---|---|
| `data/raw/grid3/{code}_health_facilities_v3.geojson` | GRID3 v3.0 layer | real | unique_id, facility_name, lga_standard, ward_standard, latitude, longitude, facility_level, facility_ownership, ... | `facility/grid3.py` |
| `data/raw/grid3/{code}_lga_boundaries.geojson` | GRID3 LGA boundaries | real | lganame, lgacode, geometry | `facility/grid3.py` |
| `data/raw/grid3/nga_state_boundaries.geojson` | GRID3 state boundaries (all 37), simplified ~1 km | real | statename, statecode, geometry | national map |
| `data/states/{code}/exports/dhis2_datavalues.csv.gz` | DHIS2 `/api/dataValueSets.csv` | synthetic mirror | dataelement, period, orgunit, categoryoptioncombo, attributeoptioncombo, value, storedby, created, lastupdated | `config/dhis2_mapping.yaml` → `dhis2.data_elements` |
| `data/states/{code}/exports/dhis2_complete_registrations.csv` | DHIS2 `/api/completeDataSetRegistrations` | synthetic mirror | dataset, period, orgunit, date, completed | `dhis2.dataset` |
| `data/states/{code}/exports/dhis2_orgunits.csv` | DHIS2 org unit metadata | synthetic mirror | id, name, code, level, parent | reference only |
| `data/states/{code}/exports/nhlmis_facility_reports.csv` | NHLMIS bimonthly facility report | synthetic mirror | facility_code, reporting_period_start/end, product_code, beginning_balance, quantity_received, quantity_dispensed, losses_adjustments, physical_count, days_out_of_stock, adjusted_consumption, amc, quantity_required, date_submitted | `nhlmis.columns` |

## DHIS2 data elements

| Internal field | Data element (mapping file) | Domain use |
|---|---|---|
| opd | OPD attendance - total | Service pressure, coherence |
| confirmed_malaria | Malaria - confirmed (RDT or microscopy) | Service pressure, rising demand |
| anc1 | ANC 1st visit | Outliers, coherence |
| deliveries | Deliveries - total | Outliers, coherence |
| penta1, penta3 | Penta 1 / Penta 3 doses given (0-11m) | Dropout, coherence |
| sessions_planned, sessions_conducted | RI sessions planned / conducted | Vaccine Watch |
| vaccine_stockout_flag | Vaccine stockout during month (any antigen) | Vaccine High/Critical |
| vaccine_stock_balance | Penta vaccine stock balance end of month | Context |
| refrigerator_functional | Vaccine refrigerator functional | Vaccine High/Critical |

## Facility master columns added for multi-state

| Column | Values | Use |
|---|---|---|
| `state_code` | settings code | Every table carries it in the database |
| `coord_status` | `ok` (inside own LGA polygon), `near_boundary` (outside, within `geography.near_boundary_km` = 5 km; mapped), `location_unverified` (further; in every queue, not mapped) | Map filter, facility page note |
| `in_state` | bool | Point falls inside any LGA polygon of the state |
| `lmis_facility_code` | `{GRID3 state code}-LMIS-{hash}` | Synthetic NHLMIS linkage key |

## Derived tables

Per-state tables are built in `data/states/{code}/marts/` and loaded into one table each with a `state_code` column.

| Table | Grain | Contents |
|---|---|---|
| `fact_quality_flags` | facility x month x rule | rule_id, family, severity, explanation, source_date |
| `fact_domain_results` | facility x month x domain | severity, credible, signal, evidence (JSON) |
| `mart_facility_month` | facility x month | report status, source ages, confidence + reasons, operational risk, queue, tag, ranks |
| `mart_queue` | facility x month | queue, tag, rank (state, LGA), evidence summary, next action, explanation (JSON) |
| `mart_lga_month` | LGA x month | queue counts, quadrants, silent, stale, completeness, LGA rank |
| `mart_commodity_month` | facility x month x commodity | latest visible NHLMIS record, age, stale flag |
| `mart_service_baseline` | facility x month x indicator | value, seasonal expected, MAD, robust z |
| `mart_state_month` | state x month | facilities, queue and quadrant counts, reports received, on time, stale commodity, silent, low confidence, critical, action by domain, location unverified; shares and rates recomputed from counts; main risk domain; status (`act_and_verify`, `action_load`, `evidence_gap`, `watch`) |
| `mart_zone_month` | zone x month | sum of its states' counts; rates recomputed |
| `mart_national_month` | month | sum of all states' counts; rates recomputed |
| `dim_state_geo` | state (all 37) | simplified geometry; `state_code` null when not in the demo |

## Ground truth (never read by the engines)

`data/states/{code}/eval/`: `answer_key_faults.csv`, `answer_key_scenarios.csv` (both with a `state_code`
column), `reporting_truth.csv`, `nhlmis_reporting_truth.csv`, `truth_monthly.parquet`, `truth_stock.parquet`,
`realism_report.json` (with the state's simulator parameters). `data/national/answer_key_faults.csv` and
`answer_key_scenarios.csv` combine all states.

## Phase two (not used)

General essential medicines, staffing, supplier lead time, order fill rate.
