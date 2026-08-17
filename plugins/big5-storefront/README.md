# Big 5 Sporting Goods — Merchandising Storefront (Sigma plugin)

A single-file Sigma plugin that reproduces the "Storefront" merchandising view
(product-card grid + live notifications rail + Storefront/Manager toggle),
rebranded for **Big 5 Sporting Goods**.

- **Product grid** — responsive cards: category tag, name, price, star rating,
  favorite toggle, promo chips (Sale / New / Top Rated / Low), and a
  SOLD / AVAILABLE stat row (Manager view) or Price / In-stock (Storefront view).
- **Notifications rail** — color-coded Stockout / Low Stock / High Return / Price
  Drop / Restock alerts with an **Urgent Only** filter and per-alert Details.
- **Top bar** — category filter, foot-traffic sparkline, product search,
  Storefront/Manager segmented toggle.

## Editor-panel bindings (`configureEditorPanel`)
| variable | meaning |
|---|---|
| `source` | products element |
| `name`, `category`, `sold`, `available`, `rating`, `price` | card fields |
| `image` | optional product image URL (falls back to a category tile) |

Ships a synthetic Big 5 catalog so it previews standalone (no data binding
required). Redraws on resize via `ResizeObserver`.

## Register + embed
```
python3 scripts/register_plugin.py "$SIGMA_BASE_URL" "$TOKEN" \
  "Big 5 Storefront" "https://raw.githack.com/michellekoppel/millersigma/claude/big5-merchandising-dashboard-7klo2m/plugins/big5-storefront/index.html"
```
Then embed `{kind:"plugin", pluginId, config:{source:{kind:"element",elementId}, name:"<colId>", ...}}`.
