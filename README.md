# PHC Sentinel

*See risk before it becomes a shortage.* Young Data Professionals Datathon 2026, Track 01: Health.

PHC Sentinel is an early-warning tool for primary health care. It turns imperfect routine PHC data into two
separate outputs for every facility, **operational risk** and **data confidence**, and routes each facility
into a ranked queue:

|                         | High / moderate confidence | Low confidence                          |
|-------------------------|----------------------------|-----------------------------------------|
| **High / critical risk** | Resource action: ACT NOW   | Resource action: VERIFY THEN ACT        |
| **Normal / watch risk**  | Monitor                    | Data verification: DO NOT ASSUME SAFE   |

Low observed risk with low confidence is not safe.

It runs for **12 states, two per geopolitical zone**, each with its own state portal, plus a **National
Command Centre** that rolls the state results up for federal users.

| Zone | States |
|---|---|
| North West | Kano, Kaduna |
| North East | Bauchi, Adamawa |
| North Central | FCT (Abuja), Niger |
| South West | Ogun, Oyo |
| South East | Enugu, Abia |
| South South | Delta, Bayelsa |

Lagos, Anambra, Rivers and Cross River were requested but are not in GRID3 Health Facilities v3.0, so
same-zone states stand in for them ([decision D9](docs/decisions.md)). The list lives in `config/settings.yaml`.

> **Data:** facility lists (12,924 public PHCs) and LGA/state boundaries are real (GRID3 v3.0, CC BY 4.0).
> All operational reporting data are **simulated** in the structure of real DHIS2 and NHLMIS exports, and a
> banner says so on every page.

## Views

Every view has its own address and is one click from the landing page. The demo has no login; a pilot adds
real authentication with state-scoped access.

| URL | View |
|---|---|
| `/` | Role switcher: National Command Centre, or pick a state |
| `/national` | National Command Centre: headline numbers, interactive Nigeria map (colour by % act now, % data verification, reporting completeness or % stale stock reports), state cards with search / zone filter / sort, zone comparison, and a state brief opened from the map or a card. Brief, metric and filters stay in the URL, e.g. `/national?state=kano&metric=pct_stale`. |
| `/national/briefing` | Briefing mode: large-type slides for senior officials (arrow keys, printable) |
| `/state/{code}` | State overview: LGA ranking, Risk x Confidence, map, queue trend |
| `/state/{code}/lga/{id}` | LGA action and verification queues |
| `/state/{code}/facility/{id}` | Facility explanation: evidence by domain, why confidence is reduced, trends |
| `/about` | Method, coverage, data labels, access model, limitations |

## Run it

**Docker (one command):**

```bash
docker compose up --build
```

This builds the 12 facility masters, simulates each state's exports, runs the engines (3 states in parallel,
`SENTINEL_WORKERS`), builds the national marts, loads PostGIS and starts the app. Allow about 25 minutes and
~5 GB of disk for the first build. Web: http://localhost:3000 · API docs: http://localhost:8000/docs

**Local development:**

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # (bin/ on macOS/Linux)
docker compose up -d db                       # PostGIS on localhost:5433
python -m sentinel all                        # 12 states + national marts (~13 min with 3 workers)
python -m sentinel load-db                    # ~8 min
uvicorn sentinel.api.main:app --port 8000
cd web && npm install && API_URL=http://localhost:8000 npm run dev
pytest -m "not slow"                          # 68 tests (1 skipped), ~15 s
pytest -m slow                                # full Bauchi rebuild vs the frozen baseline, ~3 min
```

Web tests: `cd web && npm test` (queue-token tests).

One state only: `python -m sentinel all --state kano`. Step-1 coverage check against GRID3:
`python -m sentinel coverage`. Add a state: add an entry to `states` in `settings.yaml`, then
`python -m sentinel fetch-grid3 --state <code>`.

See [CHANGELOG.md](CHANGELOG.md) for the Stitch UI restyle and the API additions that came with it.

## How it works

```
GRID3 facilities ──┐                              (per state, data/states/{code}/)
DHIS2 exports ─────┼─> adapters (mapping file) ─> monthly spine (point-in-time)
NHLMIS exports ────┘                                  │
                       ┌──────────────┬───────────────┼───────────────┐
                 WHO-aligned DQR   commodity risk  vaccine risk   service pressure
                       │                └───────────────┼───────────────┘
                data confidence                 operational risk (worst credible domain)
                       └──────────── queues + ranking + explanation
                                          │
              state marts ──> national marts (sum of states) ──> PostGIS ──> API ──> web
```

| Path | What |
|---|---|
| `config/settings.yaml` | Every threshold with its basis; the state list, zones and per-state simulator parameters |
| `config/dhis2_mapping.yaml` | Source identifiers → internal fields. **To pilot: replace the export files and edit this file.** |
| `sentinel/facility/grid3.py` | Phase 1: GRID3 fetch, filter, de-duplicate, LGA polygon check, boundary tags |
| `sentinel/simulator/` | Phase 2: seeded truth + reporting layer + fault injection per state, written as DHIS2 / NHLMIS exports |
| `sentinel/ingest/` | Phase 3: mapping-driven adapters with validation and a rejection log |
| `sentinel/spine.py` | Phase 3: point-in-time monthly spine; NHLMIS marked stale once the next report is overdue |
| `sentinel/engines/dqr.py` | Phase 4: 14 WHO-aligned rules, each with severity and a plain-language reason |
| `sentinel/engines/baseline.py`, `risk.py` | Phase 5: seasonal robust baselines; commodity, vaccine and pressure domains |
| `sentinel/engines/decision.py` | Phase 6: confidence, worst-credible-domain risk, queues, ranking, next actions, LGA roll-up |
| `sentinel/national.py` | State, zone and national marts (counts summed; rates recomputed from counts) |
| `sentinel/db.py`, `sentinel/api/` | PostGIS load and the FastAPI read API ([docs/api.md](docs/api.md)) |
| `web/` | Next.js: landing, National Command Centre, briefing mode, state portal template, method & data |
| `docs/` | [Data contract](docs/data_contract.md), [assumptions register](docs/assumptions.md), [design decisions](docs/decisions.md), [API](docs/api.md) |

## What is real and what is simulated

The app shows a banner on every page. Behind it (all 12 states):

| Data | Status |
|---|---|
| Facility names, wards, LGA, type, ownership, coordinates, NHFR code | **Real** (GRID3 Nigeria v3.0, CC BY 4.0) |
| LGA boundaries | **Real** (GRID3) |
| DHIS2 org unit UIDs and LMIS facility codes | **Synthetic** linkage keys |
| Monthly reports: OPD, malaria cases, ANC, deliveries, Penta doses, RI sessions, vaccine stockout, refrigerator status | **Simulated** (DHIS2 structure) |
| Commodity reports: stock, consumption, stockout days, AMC (ACT adult, ACT child, malaria RDT) | **Simulated** (NHLMIS structure) |
| Report dates, lateness, silence and missing reports | **Simulated** |
| Months of stock, risk, confidence, queues, ranks, next actions, LGA roll-ups, trends | **Derived** from the simulated data, so also not real |
| Thresholds in `config/settings.yaml` | Real policy or convention where tagged POLICY, WHO-DQR or STAT; `commodity.eop_months` (1 month) still needs confirming against national policy |

Nothing in the UI describes an actual facility's stock or reporting. The Stitch design files in
`stitch_phc_sentinel_early_warning/` contain placeholder names, counts, contacts and dates; none were copied into the app.
In-charge names and phones, fridge models, an officer on duty, a data-sync panel, epi-weeks and a WHO state target are not shown
because no data source backs them.

## Facility locations

Each GRID3 point is checked against its own LGA polygon (Python at build time, PostGIS view
`v_facility_lga_check` after load). Outside the polygon but within 5 km is **Near boundary** and stays on the
map; further away is **Location unverified**: the facility stays in every queue but is not drawn
(`geography.near_boundary_km`). Across the 12 states: 12,189 inside, 504 near boundary, 231 unverified.

## Guarantees checked

Across all 465,264 facility-months, in every state:

- no facility with an overdue commodity report gets High confidence;
- every missing monthly report means Low confidence;
- every Normal/Watch risk + Low confidence facility goes to Data Verification, never Monitor;
- every High/Critical risk + Low confidence facility carries VERIFY THEN ACT;
- national and zone totals equal the sum of their states;
- Bauchi's outputs are identical to the single-state build (Sep 2026: 188 act now, 72 verify then act,
  581 do not assume safe, 613 monitor), by hash over every facility-month (`tests/test_bauchi_regression.py`).

## What we claim, and what we don't

We claim the engines detect what they were designed to detect, follow WHO DQR methods and published
inventory policy, and run on the structure of real DHIS2 and NHLMIS exports. We do **not** claim
real-world predictive accuracy, optimal thresholds, coverage of general essential medicines or staffing,
or that simulated numbers describe actual facilities in any state. Differences between states come from
labelled simulator parameters ([assumptions A13–A16](docs/assumptions.md)), not from real state performance.
