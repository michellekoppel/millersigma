# Policy Persistency Curve — Pacific Life plugin

A bespoke Sigma plugin for the Pacific Life *In-Force Command Center* workbook:
a cohort **survival curve** showing the **percent of policies still in force by
policy year** across product lines (Term / Whole / Universal Life and Variable /
Fixed / Indexed Annuities). It's the iconic operational view for a life insurer —
lapse/persistency behavior, not a KPI reskin.

- Single file (`index.html`), vanilla JS + `@sigmacomputing/plugin` SDK.
- Multi-line SVG chart, hover tooltips, per-line legend, best/weakest callout.
- **ResizeObserver** redraw so it fills the panel Sigma sizes *after* first paint.
- **Synthetic fallback** so it previews standalone (open the file directly).

## Editor-panel bindings

| Variable | Type | Bind to |
|---|---|---|
| `source` | element | the data element |
| `series` | column | Product line |
| `year`   | column (number) | Policy year (0, 1, 2, …) |
| `value`  | column (number) | % in force (accepts 0–1 or 0–100) |

## Hosting / registration

Registered per-org via `POST /v2/plugins` (see `scripts/register_plugin.py`).
The workbook is wired to a public copy served from the repo through githack:

```
https://rawcdn.githack.com/michellekoppel/millersigma/<commit-sha>/plugins/paclife-persistency/index.html
```

For local iteration instead, serve it and register that URL:

```
cd plugins && python3 -m http.server 8080
python3 ../scripts/register_plugin.py "$SIGMA_BASE_URL" "$TOKEN" \
  "Policy Persistency Curve" "http://localhost:8080/paclife-persistency/"
```

(localhost only renders in a browser that can reach that server; use the githack
URL for anything shared.)
