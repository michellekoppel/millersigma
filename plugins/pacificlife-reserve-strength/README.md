# Reserve Strength — Sigma plugin

Bespoke hero plugin for the Pacific Life dashboard build. A central radial
gauge showing the reserve coverage ratio (assets held against guaranteed
liabilities), flanked by two heritage stat chips — consecutive years rated
"A" or higher by A.M. Best, and total years in business. Single-file,
vanilla JS, `@sigmacomputing/plugin` SDK from CDN (no build step). Renders
synthetic data (108%, 50 years, 160 years) when opened standalone.

Not reused from any other industry in this collection — designed for a
life insurance & annuity carrier's "confidence for generations" brand
story, distinct from the balance flywheels, cost-flow ribbons and loss
triangles used elsewhere.

**Hosted:** https://cdn.jsdelivr.net/gh/michellekoppel/millersigma@pacificlife-plugin-v1/plugins/pacificlife-reserve-strength/index.html

## Use in Sigma
1. Admin → Plugins → Add plugin → paste the hosted URL.
2. In a workbook, add the plugin element; in the editor panel set: **source**
   element, **Metric name** column, **Value** column. The source table has
   one row per metric (`Reserve Coverage Ratio`, `Consecutive A-Rated Years`,
   `Years in Business`) — see `sql/reserve_strength.sql` in the company
   dashboard skill.
