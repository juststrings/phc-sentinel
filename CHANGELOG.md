# Changelog

## UI restyle to the Stitch design (branch `ui/stitch-restyle`)

The web app was restyled to match the Stitch design. Engines, thresholds, queue rules and the database schema are unchanged.
All numbers still come from the FastAPI API; nothing from the Stitch files' placeholder data was copied.

### Merged with `main`: 12 states and the National Command Centre

`origin/main` gained 12-state coverage (two states per geopolitical zone), state-scoped API routes and a National Command Centre.
This branch merges it (main itself is untouched) and carries the restyle across:

- **Routes:** the restyled pages now live under `/state/{code}/...` (overview, LGA queues, facilities, facility detail); `/about` is Method;
  `/` (role switcher), `/national` and `/national/briefing` are main's pages. Old `/lga/{id}` and `/facility/{id}` still redirect.
- **Shell:** the sidebar has a **View** switcher (National Command Centre or any state, grouped by zone) and state-aware links.
  The top-bar search finds facilities in every state. The theme toggle is in the top bar.
- **National, landing and briefing pages** keep main's components. Their old stylesheet is scoped to a `.legacy` wrapper
  (`web/app/legacy.css`, `postcss.config.mjs`) and mapped onto the design tokens, so they follow light/dark and cannot affect the new pages.
  Restyling them to the Stitch look is a follow-up. The national map follows the theme toggle.
- **API:** the restyle's endpoints are state-scoped: `/state/{code}/insights`, `/state/{code}/coords`, `/state/{code}/facilities`,
  plus `/search` (all states). `/meta/rules` and `/meta/thresholds` stay global; the thresholds table now also shows the state-status
  and geography thresholds. A facility with no row for the month returns 404.
- **Coordinates:** main's two tags are used: *Near boundary* (kept on the map) and *Location unverified* (kept in every queue, not drawn).
  The state overview reports both the unverified count and how many are outside the state.
- **Method page** gains the 12-state coverage table and the access section (demo has no login; a pilot adds state-scoped access).
- **Tests:** 68 pass in `pytest -m "not slow"` (1 skipped) and 4 in `npm test`.

> Windows note: `python -m sentinel all` fails on Windows (its process pool cannot unpickle `_state_all` under spawn, in code pushed to main).
> The same per-state steps were run in separate processes instead, then `python -m sentinel national` and `load-db`.

### Web app (`web/`)
- **Design system:** Tailwind with CSS-variable tokens (`web/app/globals.css`, `web/lib/tokens.ts`). Queue colours are named tokens:
  act-now (deep red), verify-then-act (amber), do-not-assume-safe (indigo with a diagonal hatch), monitor (teal).
  One shared `Chip` for queue, risk (Critical, High, Watch, Normal) and confidence (High, Moderate, Low).
- **Light and dark themes:** light by default, with a toggle in the top bar. The choice is saved; with no choice it follows the system.
- **Shell:** left sidebar (State Overview, LGA Queues, Facilities, Method), top bar with state label, month selector and facility search.
  The simulated-data banner is on every page.
- **State Overview:** 2x2 queue matrix with month-over-month deltas, a "This week" panel generated from data, LGA choropleth,
  full 20-LGA table (with Silent and Stale LMIS), queue sizes over time, what drives resource action.
- **LGA Queues:** LGA selector, four queue tabs, ranked work list (engine ranking), filters (area, confidence, overdue), CSV export of the filtered view.
  Pressure-driven High facilities show the corroborating domain in the "Why" text.
- **Facilities (new):** searchable, filterable, sortable, paginated directory of all PHCs, with a flag for coordinates outside the facility's LGA.
- **Facility detail:** risk and confidence tiles, summary, next action, malaria months-of-stock bars (policy lines from settings),
  vaccines and cold chain, service demand (last 18 months), reasons for confidence, 12-month strips with legends.
  A facility with no data for the month shows a clear "No data for this month" page.
- **Method:** thresholds and basis tags read from `config/settings.yaml`; the 14 data quality rules with severities read from the engine.
- **Queue sizes chart** starts after the warm-up months (first two months are almost all verification because no history exists yet).
- **Tests:** vitest checks that every queue tag maps to one of the four tokens and that do-not-assume-safe stays distinct.

### API (`sentinel/api/`, read-only additions)
`/facilities` (search, filters, sort, paging), `/state/insights`, `/meta/rules`, `/meta/thresholds`, `/meta/coords`, `/meta/state`.
`/state/summary` trend gains the act-now / verify-then-act split and a `warmup` flag. `/lga/{id}/queue` rows gain last-report fields and
`corroborated_by`. `/geo/lgas` gains Act now counts. `/facility/{id}` returns 404 when there is no row for the month.

### Docs and tests
- README: what is real versus simulated, updated test count (46 pytest, 5 of which need PostGIS; plus the web tests).
- `docs/decisions.md`: hard-coded constants outside `settings.yaml` are logged as TODO (not moved); notes on warm-up months and the two coordinate counts.

### Deliberately not built
Stitch's hand-drawn SVG map (real GRID3 boundaries used), facility in-charge name and phone, fridge model, "Officer on duty",
"Data stream sync", epi-week labels, "WHO state target", secondary hub distance, Compare toggle, notification bell, profile,
the disease tabs and dispatch buttons from `DESIGN.md`, a Penta dropout gauge (the engine only exposes it as text), and urban/rural
(not in the data; Stitch's "Area" is the risk domain).

### Run and verify
```bash
docker compose up --build            # or the local steps in the main README
python -m pytest -m "not slow"       # 68 tests
cd web && npm test && npm run build  # stop `next dev` before building
```
