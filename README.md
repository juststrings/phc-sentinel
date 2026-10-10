# PHC Sentinel

*See risk before it becomes a shortage.* Young Data Professionals Datathon 2026, Track 01: Health.

PHC Sentinel is a state-level early-warning tool for primary health care. It turns imperfect routine PHC data
into two separate outputs for every facility, **operational risk** and **data confidence**, and routes each
facility into a ranked queue:

|                         | High / moderate confidence | Low confidence                          |
|-------------------------|----------------------------|-----------------------------------------|
| **High / critical risk** | Resource action: ACT NOW   | Resource action: VERIFY THEN ACT        |
| **Normal / watch risk**  | Monitor                    | Data verification: DO NOT ASSUME SAFE   |

Low observed risk with low confidence is not safe.

> **Data:** the Bauchi facility list (1,454 public PHCs) and LGA boundaries are real (GRID3 v3.0, CC BY 4.0).
> All operational reporting data are **simulated** in the structure of real DHIS2 and NHLMIS exports.

## Run it

**Docker (one command):**

```bash
docker compose up --build
```

This builds the facility master, simulates the exports, runs the engines, loads PostGIS and starts the app.
Web: http://localhost:3000 · API docs: http://localhost:8000/docs

**Local development:**

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # (bin/ on macOS/Linux)
docker compose up -d db                       # PostGIS on localhost:5433
python -m sentinel all                        # facilities -> simulate -> pipeline (~4 min)
python -m sentinel load-db
uvicorn sentinel.api.main:app --port 8000
cd web && npm install && API_URL=http://localhost:8000 npm run dev
pytest                                        # 46 tests (5 need the PostGIS db and skip without it)
cd web && npm test                            # queue-token tests
```

## How it works

```
GRID3 facilities ──┐
DHIS2 exports ─────┼─> adapters (mapping file) ─> monthly spine (point-in-time)
NHLMIS exports ────┘                                  │
                       ┌──────────────┬───────────────┼───────────────┐
                 WHO-aligned DQR   commodity risk  vaccine risk   service pressure
                       │                └───────────────┼───────────────┘
                data confidence                 operational risk (worst credible domain)
                       └──────────── queues + ranking + explanation ──> PostGIS ─> API ─> web
```

| Path | What |
|---|---|
| `config/settings.yaml` | Every threshold, with its basis (policy, WHO DQR, statistics, design) |
| `config/dhis2_mapping.yaml` | Source identifiers → internal fields. **To pilot: replace the export files and edit this file.** |
| `sentinel/facility/grid3.py` | Phase 1: GRID3 fetch, filter, de-duplicate, LGA polygon check |
| `sentinel/simulator/` | Phase 2: seeded truth + reporting layer + fault injection, written as DHIS2 / NHLMIS exports |
| `sentinel/ingest/` | Phase 3: mapping-driven adapters with validation and a rejection log |
| `sentinel/spine.py` | Phase 3: point-in-time monthly spine; NHLMIS marked stale once the next report is overdue |
| `sentinel/engines/dqr.py` | Phase 4: 14 WHO-aligned rules, each with severity and a plain-language reason |
| `sentinel/engines/baseline.py`, `risk.py` | Phase 5: seasonal robust baselines; commodity, vaccine and pressure domains |
| `sentinel/engines/decision.py` | Phase 6: confidence, worst-credible-domain risk, queues, ranking, next actions, LGA roll-up |
| `sentinel/db.py`, `sentinel/api/` | PostGIS load and the FastAPI read API (§8.2 contract) |
| `web/` | Next.js + Tailwind: state overview, LGA queues, facilities directory, facility explanation, method. Colours are tokens in `web/app/globals.css` and `web/lib/tokens.ts` |
| `docs/` | Data contract, assumptions register, design decisions (departures from the proposal) |

## What is real and what is simulated

The app shows a banner on every page. Behind it:

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

Nothing in the UI describes an actual Bauchi facility's stock or reporting. The Stitch design files in
`stitch_phc_sentinel_early_warning/` contain placeholder names, counts, contacts and dates; none were copied into the app.
In-charge names and phones, fridge models, an officer on duty, a data-sync panel, epi-weeks and a WHO state target are not shown
because no data source backs them.

## Guarantees checked on every run

Across all 52,344 facility-months:

- no facility with an overdue commodity report gets High confidence;
- every missing monthly report means Low confidence;
- every Normal/Watch risk + Low confidence facility goes to Data Verification, never Monitor;
- every High/Critical risk + Low confidence facility carries VERIFY THEN ACT.

## What we claim, and what we don't

We claim the engines detect what they were designed to detect, follow WHO DQR methods and published
inventory policy, and run on the structure of real DHIS2 and NHLMIS exports. We do **not** claim
real-world predictive accuracy, optimal thresholds, coverage of general essential medicines or staffing,
or that simulated numbers describe actual Bauchi facilities.
