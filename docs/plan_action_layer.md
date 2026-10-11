# Plan: action layer, access and hidden burden

Branch `feat/action-access-burden`, from `main` at 36846cf (12-state expansion already committed by the owner).

## Principles carried over

- The monthly decision pipeline is untouched. Every new table is an overlay keyed by `facility_id` /
  `lga_id` / `state_code`; nothing mutates `mart_facility_month` or `mart_queue`. The Bauchi regression
  (188 / 72 / 581 / 613 and three fingerprints) is re-run at every phase gate.
- Everything synthetic is labelled: people, contacts, messages, replies, responder behaviour.
- No real messages: one `SimulatedProvider`; other providers are stubs that raise; a test fails if the
  demo config names anything but `simulated`. A person approves every outbound message.
- Config over code: rules, playbooks, roles, SLAs, ladders, templates and thresholds in
  `config/actions.yaml`, `config/message_templates.yaml`, `config/name_pools.yaml`; access settings in
  `settings.yaml` under `access:`.

## Architecture

```
batch (python -m sentinel ...)                     operational (API writes)
  marts (unchanged) ──┐                              case_file, case_event, message,
  dim_person/dim_role ┼─> actions reset/seed-demo ─> inbound_response, field_verification,
  access marts  ──────┤      (rule engine opens       resupply_request, sim_clock
  burden marts  ──────┘       cases for 2026-09)            │
                                                            v
                                         mart_facility_live = mart_queue (latest month)
                                         + fresh field_verification overlay (rebuilt on change)
```

- **Operational state lives in PostgreSQL** because the UI mutates it. A single Python service layer
  (`sentinel/actions/service.py`) owns every state change and writes a `case_event` for each; the API and
  the simulated clock both call it, so a simulated reply and a person's click go through the same code.
- **Rule engine** (`sentinel/actions/rules.py`): declarative conditions `{field, op, value}`, ops
  `eq ne lt le gt ge in not_in is_true is_false`, combinators `all` / `any`. No `eval`. Malformed rules
  fail at load with the rule id.
- **Case state machine** (`sentinel/actions/cases.py`): statuses and allowed transitions read from
  `actions.yaml`; `escalated` is a level, not a status.
- **Live layer** (`sentinel/actions/live.py`): pure function of baseline row + fresh verifications; reuses
  the same thresholds as the commodity and vaccine engines. With zero verifications it returns the
  baseline exactly (tested on Bauchi).
- **Simulated responders** (`sentinel/actions/simulate.py`): the only action-layer module allowed to read
  the simulated truth (as the simulator does); replies report truth with noise, delays from each person's
  `responsiveness`.
- **Persona scope** (`sentinel/actions/scope.py`): one module decides what an acting persona may do; the
  API returns 403 otherwise. A pilot swaps it for real authentication.

## Choices made up front (logged as decisions)

- Simulation clock starts on **2026-10-30**, the date the September 2026 assessment is produced
  (analysis runs 30 days after month end), not 1 October: cases cannot open before the data that triggers
  them exists. (D21)
- Cases open from the latest analysis month only. Older months are history.
- R10 (state response) is a **suggestion**: eligible states are flagged on the national brief and a
  national persona opens the case with "Request state response". The national level never auto-messages a
  state. NEEDS OWNER REVIEW.
- A field verification can lift confidence at most to Moderate, and only when every severe reason is about
  commodity stock evidence. A missing monthly report keeps Low confidence (the existing guarantee holds in
  the live layer). A field-verified shortage is tagged ACT NOW (field-verified) even under Low confidence,
  because the verification is the "verify" step.

## Phases and gates

| Phase | Work | Gate |
|---|---|---|
| P0 | Branch, read, this plan, draft configs | 67 tests pass |
| P1 | Directory (roles, ~27k synthetic people), tables, `/people`, Directory page | every role filled; contacts non-real |
| P2 | Rule engine, cases for 2026-09, playbooks, dedupe, events, Action Centre list, case detail | cases per rules; no duplicate open cases; Bauchi regression |
| P3 | Templates, drafts, approval tray, SimulatedProvider, outbox, digest, rate limits | approval required; SMS <= 160; provider guard |
| P4 | Reply parser, responses, field verifications, live layer, baseline-vs-live UI | parser tests; live guarantees; zero-verification equality |
| P5 | Clock, responders, escalation, resupply, seed-demo/reset, persona + scope | demo loop identical on every reset; escalation reaches state; 403 |
| P6 | Access (built in parallel in a separate worktree), integrated into marts/API/UI, R11 | sources documented; population reconciles; default order unchanged |
| P7 | Hidden burden: estimates with intervals, validation vs truth, tab, modifier | coverage and error reported |
| P8 | National integration: actions strip, request response, metrics, 3 briefing slides | payloads small; national = sum of states |
| P9 | Validation Lab additions, docs, clean Docker build, Playwright pass | all tests; one command regenerates numbers |

Decision log continues from D21 (action layer D21–D39; access D40+), assumptions from A20 (access A40+).
