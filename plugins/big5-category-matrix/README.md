# Big 5 — Category Productivity Matrix

A bespoke Sigma plugin for the **Big 5 Sporting Goods Merchandising Command Center**
(`skills/sigma-company-dashboard/examples/build_big5.py`).

A squarified **treemap** of merchandise categories:

- **tile size** = net sales
- **tile color** = gross-margin % (diverging crimson → slate → emerald)
- tooltip: net sales, gross margin %, units, AUR, and share of total

It's the view a merchant lives in — instantly separates *big-but-thin-margin*
categories from *small-but-rich* ones, i.e. assortment/space-to-sales productivity.

## Bindings (`configureEditorPanel`)

| key | type | maps to |
|---|---|---|
| `source` | element | the aggregate data element (one row per category) |
| `category` | column | category label |
| `sales` | column (number) | net sales — sizes the tile |
| `margin` | column (number) | gross-margin % — colors the tile |
| `units` | column (number, optional) | units — enables AUR in the tooltip |

Margin is aggregated **sales-weighted** client-side, so row-level or
pre-aggregated input both work. Ships a synthetic sporting-goods fallback so it
previews standalone, and redraws on a `ResizeObserver` (Sigma sizes the panel
after first paint).

## Host + register

Single self-contained `index.html`. Host it anywhere static (this repo uses the
`raw.githack.com` GitHub CDN, pinned to a commit SHA), then:

```
python3 scripts/register_plugin.py "$SIGMA_BASE_URL" "$TOKEN" \
  "Big 5 Category Productivity Matrix" \
  "https://raw.githack.com/<owner>/millersigma/<sha>/plugins/big5-category-matrix/index.html"
# -> prints a pluginId; pass it to the generator as PLUGIN_ID
```
