# Big 5 Sporting Goods — Merchandising Dashboard

A branded Sigma workbook modeled on the Cold Provisions storefront demo, rebuilt
for **Big 5 Sporting Goods** (royal-blue `#343A94` + red accent, real white
wordmark, sporting-goods product lines).

## What it builds

Two pages, POSTed via the workbooks-as-code API (`POST /v2/workbooks/spec`):

1. **Storefront** — blue-gradient header + the real Big 5 white wordmark, a
   store-sales trend sparkline, a **Category** dropdown + **Product search** +
   **Date** filter, and the bespoke **Big 5 Storefront Grid** plugin: product
   cards with SVG sporting-goods glyphs on brand tiles (rating, Sold / Available,
   out-of-stock & low-stock bands) plus a live **notifications rail**
   (stockout / low-stock / delivery) derived from inventory status.
2. **Manager** — four comparative gradient KPI cards (Net Sales / Units Sold /
   Avg Selling Price / Gross Margin, each Current + delta-vs-Prior-Year +
   sparkline), a live **CallText AI insight**, control-driven charts
   (date grain / color-by / category), a stacked net-sales-by-category bar,
   side-by-side Category-mix and Category×Region pivots, and a
   **Merchandising Copilot** agent.

## Data

- **Manager** — `SE_DEMO_DB.BIG_BUYS.BIG_BUYS_POS` reshaped via custom SQL into
  eight Big 5 categories (Footwear, Team Sports, Fitness, Camping & Outdoors,
  Water Sports, Cycling, Fan Gear, Hunting & Fishing), real store regions, with
  Current-Period / Prior-Year tagging for the comparative KPIs. Prices scaled to
  sporting-goods realism (ASP ≈ $94).
- **Storefront** — a curated Big 5 product catalog (28 SKUs) via a `VALUES`
  table that feeds the plugin and is filtered live by the Category / Search
  controls.

## The plugin

`../plugins/big5-storefront/index.html` — a single-file `@sigmacomputing/plugin`
element. Hosted from this public repo over the githack CDN (renders as real
`text/html`, unlike jsDelivr) at an immutable commit SHA, and registered once via
`POST /v2/plugins`. It redraws on `ResizeObserver` and ships a synthetic fallback
so it previews standalone in a browser.

## Rebuild

```bash
# 1. host + register the plugin (once per org) — prints a pluginId
python3 ../scripts/register_plugin.py "$SIGMA_BASE_URL" "$TOKEN" \
  "Big 5 Storefront Grid" \
  "https://rawcdn.githack.com/michellekoppel/millersigma/<COMMIT_SHA>/plugins/big5-storefront/index.html"

# 2. build + POST the workbook
export PLUGIN_ID=<pluginId>
python3 build_big5.py "$SIGMA_BASE_URL" "$TOKEN" <CONNECTION_ID> <FOLDER_ID>
```

`CONNECTION_ID` must be a Snowflake connection that can see
`SE_DEMO_DB.BIG_BUYS.BIG_BUYS_POS`. `LOGO_PNG` (default `big5_logo_white.png`) is
the white Big 5 wordmark used in both page headers.
