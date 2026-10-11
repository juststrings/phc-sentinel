# PHC Sentinel: from early warning to action

Build report for the action layer (Workstream C), access (Workstream A) and hidden burden (Workstream B).
Branch `feat/action-access-burden`, phases P0–P9, 11 October 2026.

## Summary

Sentinel already told a State PHC Board **which** facilities need action or verification. It now also shows
**who acts, by when and with what result**, **where people travel furthest for care**, and **what the reporting gaps hide**.

- **Every flagged PHC is now a case.** A reset opens 8,425 cases across the 12 states. Each has a named
  (synthetic) owner, a playbook, a deadline and an escalation ladder. No queued PHC is left without a case, there are no
  duplicate open cases, and no case lacks an owner.
- **The 90-second loop works end to end.** In the browser it takes about 30 seconds:
  1. A Verify-then-act case is drafted and a person approves the SMS.
  2. The simulated reply `ACT 12 RDT 0 FRIDGE 1` changes the live status to ACT NOW (field-verified).
  3. The case moves to *resupply requested* with pre-filled quantities, and a person approves them.
  4. An unacknowledged case escalates to the LGA PHC Coordinator, then (two days later) to the State LMCU Coordinator.
- **Nothing real is sent or moved.** One provider exists, and it is simulated. A person approves every outbound message,
  and nothing moves stock automatically. All of this is tested.
- **5.3 million people** (5.8% of the 91.7 M in the 12 states) live more than a 60-minute walk from a public PHC.
  Bauchi and Niger are worst at about 15%. 1,354 PHCs are isolated (the next PHC is over 60 minutes away). Real-derived.
- **About 522,000 malaria cases a month** sit behind 3,117 missing reports (80% range 518,530–525,078), roughly
  a quarter of the estimated total. The estimates were checked against the simulation's truth:
  - Facility estimates were within 14–16% on average, and the 80% range held 78–80% of the time in every state.
- **A clean `docker compose up --build` works.** It builds all 12 states, the burden estimates, the database and the action layer.
  It found one fault, now fixed: the access step needs `libexpat` in the image (the Dockerfile installs it now).
- **The decision engine is unchanged.** The Bauchi regression is exact (Sept 2026: 188 / 72 / 581 / 613, identical hashes),
  and all four safety guarantees still hold. Everything new is an overlay or an additional table.

## What was built

### Action layer (synthetic)

| Piece | What it does |
|---|---|
| Directory | 27,218 invented people: 3 national, 72 state (6 per state), 1,295 LGA (5 per LGA), 25,848 facility (2 per PHC). Zone-appropriate first-name × surname pools, no real office-holder, `SIM-{ST}-{6 digits}` phones, `.invalid` emails |
| Rules | 12 declarative rules in `config/actions.yaml` (no `eval`). Malformed rules fail loudly with the rule ID. Within a group the first match wins. Dedupe on (unit, playbook) with a 14-day cooldown |
| Cases and playbooks | Statuses with validated transitions. Every change writes an event. Due dates come from playbook SLAs. Bulk acknowledge, assign, approve and open |
| Messaging | Templates per channel. SMS is held to 160 characters (maximum at reset 151). Every variant says DEMO. P1 notices go immediately, the rest as a daily digest. At most 8 messages per person per day. Human approval is required |
| Replies | A parser for messy SMS (typos, word order, "nil", "spoilt", number-first) tested on 32 shapes. Partial or unclear replies go to a review queue |
| Live overlay | `mart_facility_live` = assessed status + fresh field verification (14 days). Confidence lifts to Moderate at most and never past a missing report. A confirmed shortage becomes ACT NOW (field-verified). A working fridge lowers the vaccine domain |
| Resupply | Pre-filled from NHLMIS quantity-to-order when current, otherwise AMC × 4 months minus last stock. Penta doses for vaccine cases. Always approved by a person. Printable |
| Escalation | Unacknowledged after the SLA, a case moves one ladder step and notifies the next person. Once acknowledged, it escalates only when overdue and idle. It stops at the top |
| Simulation | Clock from 30 Oct 2026 (the day the Sept assessment exists). Simulated responders reply from the simulator's truth, with delays, noise, typos and silence. They acknowledge cases but never approve anything |
| Persona and scope | "Acting as" in the top bar. The API returns 403 outside a person's scope: national acts on state cases, LGA on its own LGA, facility staff reply only |
| UI | Action Centre (list / kanban, approvals, outbox, inbox, LGAs, escalations, KPIs, demo guide, clock), case page, Take-action panel and live status on the facility page, bulk queue actions on the LGA page, directory, My cases, resupply print view |

Cases at reset, by rule:

| Rule | Cases |
|---|---|
| R07 other Do-not-assume-safe | 2,380 |
| R06 stale NHLMIS | 1,853 |
| R01 Act now, commodity | 1,549 |
| R04 Verify then act | 753 |
| R08 session shortfall | 697 |
| R05 reliable reporter silent | 426 |
| R03 fridge down | 396 |
| R02 Act now, vaccine | 339 |
| R09 LGA reporting review | 32 |

By priority: P1 3,139, P2 2,238, P3 3,048. Also created at reset: 20,149 draft messages, 5,746 digest notices,
1,506 draft resupply requests and 6 state-response suggestions.

### Access (real-derived)

WorldPop 2026 constrained population, MAP 2020 walking and motorised friction surfaces, and GRID3 facilities and wards
feed a cost-distance computation on 1 km equal-area cells. Population is conserved exactly. What it adds:

- **Access tab:** ward choropleth or travel-time raster, LGA ranking by people affected, the 25 isolated PHCs with
  most people beyond 60 minutes (with their live status), the 15 worst wards, and 10 candidate areas.
- **Facility access panel**, the national map metric `pct_pop_beyond_threshold`, a zone column, a state-brief figure and
  the briefing slide "Where people travel furthest".
- **R11 isolation modifier and impact-weighted sort:** isolated PHCs come first within a priority.

| State | Beyond 60 min walk | Isolated PHCs |
|---|---|---|
| Bauchi | 15.6% | 238 |
| Niger | 15.0% | 288 |
| Kaduna | 10.3% | 209 |
| Adamawa | 8.5% | 164 |
| Oyo | 5.1% | 79 |
| Bayelsa | 4.8% | 97 |
| Delta | 3.0% | 87 |
| Ogun | 2.7% | 82 |
| FCT | 2.2% | 33 |
| Kano | 1.7% | 62 |
| Enugu | 0.4% | 13 |
| Abia | 0.1% | 2 |

### Hidden burden (modelled)

- **Hidden cases.** For a PHC whose report is missing, Sentinel takes its own seasonal baseline (prior months only) and
  scales it by this month's actual-to-expected ratio at PHCs that did report. The 80% range comes from the empirical
  error of reporting PHCs.
- **Implied stock.** For a PHC whose NHLMIS report is stale: last stock plus the typical net flow since that report.
  The label is the chance of having none: elevated risk, watch or no signal.
- **Where it shows:** the "Behind the gaps" tab, the national KPI `hidden_malaria_cases`, the briefing slide "What the gaps hide",
  and the R12 priority raise (131 cases).

Validation against the simulator's truth covers the last 12 months. Truth is used only to score the estimates, never to make them (tested).

| State | Facility error | Truth in 80% range | State-total error | State-total in range | Stock signal lift |
|---|---|---|---|---|---|
| Kano | 14% | 79% | 1.9% | 50% | 1.7× |
| Kaduna | 15% | 79% | 1.8% | 42% | 3.1× |
| Bauchi | 15% | 80% | 1.2% | 75% | 2.6× |
| Adamawa | 15% | 80% | 1.4% | 75% | 1.8× |
| FCT (Abuja) | 16% | 78% | 3.1% | 83% | 1.7× |
| Niger | 15% | 80% | 1.6% | 58% | 1.8× |
| Ogun | 16% | 79% | 1.4% | 92% | 2.9× |
| Oyo | 15% | 79% | 1.9% | 75% | 2.7× |
| Enugu | 16% | 79% | 2.1% | 67% | 1.9× |
| Abia | 15% | 79% | 1.5% | 83% | 1.4× |
| Delta | 15% | 80% | 2.1% | 83% | 2.2× |
| Bayelsa | 16% | 78% | 3.0% | 67% | 1.7× |

The same table is in the Validation lab on the Method & data page and in `data/national/burden_validation.json`.

Two first attempts failed validation and were replaced. Both failures are recorded in the decision log:

- **State totals without the nowcast factor:** the range held in only 1 of 12 months.
- **A stock model that ignored deliveries:** it flagged 95% of stale PHCs and was right 9% of the time.

## Guarantees and tests

| Guarantee | How it is checked |
|---|---|
| Decision logic unchanged; Bauchi exact | `test_bauchi_regression.py` (hash over every facility-month), plus a database test that the marts' hash is unchanged after replies |
| Four safety guarantees, and the same in the live layer | Existing engine tests, plus `test_actions_unit.py` (a field count never gives High confidence or lifts past a missing report; expired verifications have no effect) |
| Live = assessed with no verification | Database test across all 12 states |
| Human approval; simulated provider only | Config tests and a database test (no message sent without approval); a non-simulated provider raises; the stubs raise `NotImplementedError` |
| SMS ≤ 160 characters, DEMO label | Every template, with worst-case names; database check on all 20,149 drafts |
| Escalation one step per breach, stops at top; no escalation for acknowledged in-date cases | `test_actions_db.py` |
| Scope (403) | Unit-level scope tests and API tests |
| National = sum of states (queues, access, hidden burden, actions) | `test_national.py`, `test_access_api.py`, `test_burden.py`, `test_national_actions.py` |
| Demo loop | Database test of the scripted reply → live status → resupply request; Playwright run in the browser |

Test run (11 Oct 2026): **190 passed** (175 fast, 15 slow including the Bauchi regression and the action-layer database
tests) in 5 min 24 s. Browser pass against the clean Docker build:
- The demo loop took 23 s from "Act as" to approved resupply.
- 80 page views (20 pages at 390 px and 1440 px, light and dark) had zero console errors and a visible focus ring everywhere.
- Two phone-width overflows were found (briefing controls, directory filters) and fixed.

## Needs owner review

| # | Item | Choice made |
|---|---|---|
| D24 | R10 state response | Suggested, not automatic: a national persona opens it. The national level never auto-messages a state |
| D63 | Stock label behind stale NHLMIS reports | Shown as a risk ranking ("elevated risk", about 2× the base rate), never as "out of stock". R12 raises priority on it |
| A28 | R11 catchment threshold (10,000 people) | It raises no priority at reset because every case it applies to already opens at P1. It still annotates 50 cases and drives the impact sort. Consider applying it to P2/P3 rules or lowering the bar |
| D41 | Population year | WorldPop 2026 projection; Ogun comes out high (11.0 M). A census-anchored year is the alternative |
| D43 | Friction resampling | Nearest-neighbour. The share beyond 60 minutes moves 1–2 points between methods |
| D44 | State edges | PHCs outside the 12 states are not counted as alternatives, so border burden may be overstated |
| D52 | Parallel per-state commands on Windows | The existing pool cannot pickle `__main__` functions with more than 1 worker; access and burden avoid this, the shared code is unchanged |
| A40, A41 | Walking thresholds and the 60-minute headline | Common bands in the travel-time literature, not a Nigerian standard |
| Sources | MAP and GRID3 ward licences | Assumed CC BY 4.0; confirm on the publishers' pages (`docs/data_sources.md`) |

## Known limits

- **Escalation volume is high.** About 1,300–2,300 escalations a day in the first days after a reset, because no simulated
  person approves drafts. This is the intended pressure: the queue only moves when people act. A pilot would tune SLAs to capacity.
- **R11 rarely changes priority.** See the owner-review table.
- **The stock signal is weak on its own.** Most PHCs flagged "elevated risk" still had stock. The Action Centre's field
  count is what settles it.
- **Access ignores PHCs outside the demo states and across the national border.** Catchments are proximity, not use.
- **Everything operational is simulated.** That includes the people and replies. Real-world accuracy needs a state's own data.

## Regenerate every number

```bash
python -m sentinel all && python -m sentinel burden
python -m sentinel fetch-access && python -m sentinel access
python -m sentinel load-db && python -m sentinel actions load
```

`docker compose up --build` runs the same sequence. Decisions D21–D34 (action layer), D40–D52 (access) and D60–D66
(burden) are in `docs/decisions.md`; assumptions A20–A28, A40–A48 and A60–A63 are in `docs/assumptions.md`.
