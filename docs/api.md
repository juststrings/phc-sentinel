# API reference

Read-only FastAPI over the PostgreSQL marts. Interactive docs: http://localhost:8000/docs.
Every response describes simulated operational data; `/meta/data-labels` returns the banner text.

`month` is always optional (`YYYY-MM`, defaults to the latest analysis month, 2026-09). `{code}` is a state
code from `config/settings.yaml`: `kano`, `kaduna`, `bauchi`, `adamawa`, `fct`, `niger`, `ogun`, `oyo`,
`enugu`, `abia`, `delta`, `bayelsa`. Unknown codes, LGAs or facilities return 404; invalid parameters 422.

## National Command Centre (state aggregates only)

These read only the precomputed `mart_state_month`, `mart_zone_month` and `mart_national_month`. No
facility rows are returned at national level. Responses are cached in memory and sent with
`Cache-Control: public, max-age=300`, gzipped.

| Endpoint | Returns | Size (gzip) |
|---|---|---|
| `GET /national/summary?month=` | `kpis` (national totals: states, facilities, act_now, verify_then_act, verification, monitor, reports_received, reporting_completeness, on_time_rate, stale_commodity, pct_*, status), `zones` (six rows, same fields), `trend` (all months), `metrics` (map metric labels) | ~2 KB |
| `GET /national/states?month=&metric=` | One row per covered state with the same fields as `kpis`, plus `main_domain`, `status`, `action_<domain>` counts, `lgas`, `location_unverified`, `trend` (last `national.trend_months` = 6 months), `top_lgas` (top `national.top_lgas_in_brief` = 3 LGAs), `value` and `metric_rank` for the chosen metric. `metric` is one of `pct_act_now` (default), `pct_verification`, `reporting_completeness`, `pct_stale`. | ~5 KB |
| `GET /national/geo` | All 36 states + FCT as GeoJSON; `state_code` is null and `covered` false for states not in the demo. `Cache-Control: max-age=86400`. | ~20 KB |

National totals equal the sum of the state rows for every count; rates are recomputed from the summed
counts (`tests/test_national.py`, `tests/test_api.py`).

## State portal (one template for every state)

| Endpoint | Returns |
|---|---|
| `GET /state/{code}/summary?month=` | `state`, `kpis` (the state's `mart_state_month` row), Risk x Confidence `matrix`, `risk` and `confidence` distributions, `action_by_domain`, `lgas` (ranked LGA roll-up), `trend` |
| `GET /state/{code}/top?month=&limit=` | Top of the state-wide action and verification queues |
| `GET /state/{code}/geo/lgas?month=` | LGA polygons with queue counts |
| `GET /state/{code}/geo/facilities?month=&lga_id=` | Facility points with queue tag. **Location unverified** facilities are left off (they remain in every queue). |
| `GET /state/{code}/lga/{lga_id}/queue?month=` | LGA summary and its action / verification / monitor queues |
| `GET /state/{code}/facility/{facility_id}?month=` | Facility master record (incl. `coord_status`, `dist_to_lga_m`), status, explanation, trends |
| `GET /state/{code}/quality/{facility_id}?month=` | Failed DQR checks and NHLMIS freshness |

A facility or LGA requested under the wrong state returns 404.

## Meta

| Endpoint | Returns |
|---|---|
| `GET /health` | Status, latest month, number of states |
| `GET /meta/months` | Analysis months |
| `GET /meta/states` | Covered states (code, name, zone) in display order, zones, default state |
| `GET /meta/data-labels` | Banner text; real / synthetic / derived label per table |
| `GET /meta/settings` | `settings.yaml` and `dhis2_mapping.yaml` |

## Deprecated single-state aliases

Kept so links to the Bauchi build keep working. `GET /state/summary`, `/state/top`, `/geo/lgas` and
`/geo/facilities` answer for `default_state` (Bauchi); `GET /lga/{lga_id}/queue`, `/facility/{id}` and
`/quality/{id}` resolve the state from the id. The web app redirects the old `/lga/{id}` and
`/facility/{id}` pages to their state-scoped addresses.
