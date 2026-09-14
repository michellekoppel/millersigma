# Alliant Insurance Group — Loss Run Analytics

- **Workbook:** https://app.sigmacomputing.com/papercrane/workbook/4rgPyaIB3J9hiXlZa95qWo
- **workbookId:** `91e14288-28b6-4bca-9197-96f22d95ca74`
- **Folder:** My Documents (Michelle Koppel), papercrane (production, `api.sigmacomputing.com`)
- **Connection:** Snowflake (`9e79f38b-a310-405c-aad9-72f762ac6ff1`), literal `VALUES` SQL — no real warehouse tables.
- Built via direct REST calls (`POST`/`PUT /v2/workbooks/spec`) using this session's
  `SIGMA_CLIENT_ID`/`SIGMA_CLIENT_SECRET` env vars, not the Sigma MCP tools (those
  pointed at a different org, `sigma-on-sigma` on staging).

## Data model

One large synthetic claims fact table (`tbl-claims`, 336 rows: policy_year 2019-2025 ×
LOB {WC, GL, Auto, Property} × status {Open, Closed, Reopened} × development period,
truncated so it's a real triangle) + one small premium reference table (`tbl-premium`,
28 rows, policy_year × LOB — premium/policy-count don't have a status or dev-period
dimension, so they get their own row grain rather than being unioned in and
double-counted).

## Findings worth keeping (schema facts, not in the older skill docs)

The `sigma-workbook-conventions` reference docs are stale in several places for the
current (2026-08+) live API on papercrane production. Confirmed via
`GET /v2/workbooks/{id}/spec` on a real live workbook and the public OpenAPI
(`https://assets.sigmacomputing.com/openapi/public-rest-api/sigma-computing-public-rest-api.json`):

1. **KPI `value` field is `{"columnId": "..."}`, not `{"id": "..."}`.** The doc's
   example is wrong for the current schema — `Invalid kind: "kpi-chart"` is the
   (masked) error you get.
2. **Chart `xAxis`/`yAxis` use `columnId`/`columnIds`, not `{id}` objects.**
   `xAxis: {"columnId": "..."}`, `yAxis: {"columnIds": ["...", ...]}` (a plural
   array even for one series). Verified on bar-chart, line-chart.
3. **Pivot-table `rowsBy`/`columnsBy` items are `{"columnId": "..."}`**, not
   `{"id": "..."}`. `values` stays a bare array of id strings.
4. **Custom-SQL table source is `{"kind": "sql", "connectionId", "statement"}`** —
   not `warehouse-table`. Reference columns via `[Custom SQL/<RAW_COL_NAME>]`.
5. Text `body` accepts inline HTML (`<p style=...>`, `<span style=...>`) in this
   org, but the sanitizer only allows `color`, `background-color`, `font-size`,
   `font-family` inline — `letter-spacing` (and presumably anything else) gets a
   clear 400, not silently dropped.
6. **The OpenAPI's real structure**: `WorkbookElement.oneOf` → "Common elements"
   variant → `CommonElement.oneOf[0]` ("Data elements") → `.oneOf[]` has the actual
   chart-kind titles (Table, KPI, Bar Chart, ..., Pivot Table). The doc's `jq`
   one-liner for "every field a kind accepts" doesn't resolve `$ref`s or nested
   `oneOf`s — you have to walk down through those first.

## The fan-out bug (the big one — cost most of the build)

**Never further-aggregate (`Sum`, or a new `groupings`) a column from a sibling
element that already has its own `groupings`, unless your new grouping is at
*exactly* the same grain.** Sigma recompiles through the raw ancestor and
LEFT JOINs it to the sibling's grouped result — if your consumer's grain is
coarser (or absent, e.g. a whole-book KPI with no grouping at all), you get
one raw row per *ungrouped* ancestor row, each carrying the *same* group total,
and a further `Sum()` on top multiplies each group's true value by however many
raw rows happen to belong to that group. Verified live: a "Total Incurred" KPI
doing `Sum([Policy Year LOB Summary/Incurred (Current)])` against the grouped
28-row `tbl-loss-ratio` came back **14x inflated** ($698M vs. the correct
$50.5M) because `tbl-claims` (its raw ancestor) has ~12 raw dev-period/status
rows per (year, LOB) group. A ratio KPI (`Sum(incurred)/Sum(premium)`) doesn't
error out but is still *wrong* — the duplication factor differs per group
(more dev-period rows for older, more-developed years), so it doesn't cancel;
it silently overweights whichever groups happen to have more raw rows. This is
the dangerous case: no error, a plausible-looking number, wrong by ~6 points
(42.7% vs. the true 36.4%).

Two safe patterns, both verified:

- **Matching grain is safe.** A chart whose own `xAxis`/`color` grouping exactly
  reproduces the sibling's native `groupings` grain (e.g. a chart grouped by
  policy-year + LOB, reading from a table already grouped by policy-year + LOB)
  compiles as a clean 1:1 join. No fan-out.
- **`summary` + `Max()` is fan-out-proof regardless of grain.** Add the
  whole-book scalars as `summary` columns on the grouped table itself (they're
  computed inside that element's own query, not re-derived by a consumer), then
  have every downstream KPI/chart read them via `Max(...)`, never `Sum(...)`.
  `Max` of a broadcast-constant is correct no matter how many duplicate rows a
  careless recompilation produces.
- For a genuinely *different* (coarser or differently-shaped) grouping than an
  existing grouped sibling provides (e.g. "by LOB only" when the existing table
  is grouped "by year × LOB"), don't try to re-group the sibling — build a new
  element grouped directly off the *original* raw table instead
  (`tbl-lob-summary`, `tbl-year-summary` here, both sourced from `tbl-claims`).

Also: a plain (non-`groupings`) table sourced from an already-grouped sibling via
passthrough columns hits the identical trap — it's not just a KPI/chart thing.
`tbl-detail-view` sourcing from a hidden `tbl-current-detail` (grouped by
year+LOB+status) rendered the correct *values* but repeated each group once per
underlying raw row (336 rows instead of 84). Fix: give `tbl-detail-view` the
`groupings` directly, sourced straight off `tbl-claims` — don't put `groupings`
on a separate hidden intermediate and try to read it plain from a second element.

## Minor known imperfections (not worth another iteration)

- The `order` field on a `table` element (declared column display order) didn't
  round-trip / wasn't respected in CSV export — display order instead follows
  `groupings[].groupBy` columns first, then `calculations` in listed order.
  Worked around by putting the technical `Join Key` grouping column last in
  `columns[]` and accepting it appears first in the actual column order anyway
  (cosmetic only, all data is correct).
- Not visually verified in the browser (no interactive SSO session available in
  this environment) — verified via `POST /v2/workbooks/{id}/export` per element
  instead, cross-checked against hand-calculated expected totals in Python.
  Ask the user to confirm layout/styling/agent behavior look right live.
