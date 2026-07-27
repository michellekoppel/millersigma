# Sponsorship Value Quadrant — Pacific Life plugin

A bespoke Sigma plugin for the **Pacific Life Brand Sponsorship Scorecard**. Plots each
golf-event sponsorship as a bubble on a **spend (x) × ROI (y)** field, sized by
**annuities sold** and colored by **finance segment** (Scale / Sustain / Optimize /
Review-Cut). Median crosshairs split the field into four value quadrants — *Efficient
wins*, *Marquee bets*, *Low priority*, *Review / cut* — and a tinted band marks
negative-ROI (money-losing) sponsorships. This is the "be more selective, reallocate to
value" visual the finance team wants.

Single file, vanilla JS + the `@sigmacomputing/plugin` SDK. Ships a Pacific Life
synthetic fallback so it previews standalone, and attaches a `ResizeObserver` so it
redraws at Sigma's true panel size (not the stale load-time size).

## Editor-panel bindings
| variable | type | maps to (workbook `portfolio` column) |
|---|---|---|
| `source` | element | the `portfolio` table |
| `event` | column | Event |
| `spend` | column (number) | Spend |
| `roi` | column (number) | ROI |
| `annuities` | column (number) | Annuities |
| `segment` | column | Segment |

## Host it (needs a URL the *viewer's* browser can reach)
The workbook opens in the user's browser, so the plugin must be on a URL **they** can
load — a localhost server on a build box will not render for them. Deploy to any static
HTTPS host:

```bash
# Netlify (authenticated CLI)
netlify api createSite --data '{"name":"paclife-quadrant-<unique>","account_slug":"<slug>"}'
netlify deploy --prod --dir plugins/paclife-sponsorship-quadrant --site <site-id>
```

For local iteration only (renders just on your machine):
```bash
cd plugins/paclife-sponsorship-quadrant && python3 -m http.server 8080   # http://localhost:8080/
```

## Register + wire into the workbook
```bash
# 1) register in your org -> prints a pluginId
python3 scripts/register_plugin.py "$SIGMA_BASE_URL" "$TOKEN" \
  "Pacific Life Sponsorship Quadrant" "<hosted-url>"
export QUADRANT_PLUGIN_ID=<pluginId>
```

Then swap the **native scatter** in `build_pacific_life.py` for the live plugin. Replace
the `scatter` element with:

```python
QUADRANT_PLUGIN = os.environ["QUADRANT_PLUGIN_ID"]
scatter = {"id": "valuemap", "kind": "plugin", "pluginId": QUADRANT_PLUGIN,
    "config": {"source": {"kind": "element", "elementId": "portfolio"},
               "event": "p-event", "spend": "p-spend", "roi": "p-roi",
               "annuities": "p-ann", "segment": "p-seg"}}
```

(Column bindings are **bare columnId strings**; keys match the `configureEditorPanel`
variable names.) Re-run the generator to POST. Until it's hosted+registered, the
workbook uses a native `scatter-chart` that renders the same value map without any
external dependency.
