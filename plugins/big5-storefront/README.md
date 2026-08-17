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

## Hosting note
The plugin must be served as real `text/html` from a public URL. **Avoid
`raw.githack.com`** — it rate-limits (returns `429 "something is wrong"` in the
panel). **Avoid `cdn.jsdelivr.net/gh/...`** — it serves `.html` as `text/plain`,
which won't render in the plugin iframe. Use a host that serves `text/html`:
`cdn.statically.io/gh/<owner>/<repo>@<commit-sha>/plugins/big5-storefront/index.html`
(pin to a commit SHA so it's immutable), or GitHub Pages.

## Register + embed
```
SHA=$(git rev-parse HEAD)
python3 scripts/register_plugin.py "$SIGMA_BASE_URL" "$TOKEN" \
  "Big 5 Storefront" "https://cdn.statically.io/gh/michellekoppel/millersigma@$SHA/plugins/big5-storefront/index.html"
```
Then embed `{kind:"plugin", pluginId, config:{source:{kind:"element",elementId}, name:"<colId>", ...}}`.
The plugin `url` is set once at registration — to change hosts, register a new
plugin and swap the `pluginId` in the workbook (PUT `/v2/workbooks/{id}/spec`).
