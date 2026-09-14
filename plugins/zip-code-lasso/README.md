# Zip Code Lasso — Sigma plugin

Draw a free-hand lasso (or box) around zip codes on a map and write the
selected zip codes back to a Sigma control variable, so any other element in
the workbook can filter on them. Adapted from
[tyleraspencer/lasso_map](https://github.com/tyleraspencer/lasso_map) (which
lassos raw lat/long points) — this version only needs a **Zip Code** column;
coordinates come from a bundled US zip-centroid lookup, no lat/long columns
required in your data.

Single-file vanilla JS on the `@sigmacomputing/plugin` SDK + Plotly.js
(`scattermapbox`, which is how the native lasso/box-select tool is
implemented). Ships with a synthetic 10-zip demo so it previews standalone.

## Files
- `index.html` — the plugin
- `zip-centroids.js` — bundled zip → [lat, lon] centroid lookup (~33.8k US
  ZIP Code Tabulation Areas), sets `window.ZIP_CENTROIDS`. Sourced from the
  US Census Bureau's public-domain 2023 ZCTA Gazetteer file
  (`2023_Gaz_zcta_national.txt`). Coordinates are rounded to 4 decimal
  places (~11m precision) — plenty for point placement at zip-code scale.
  Zip+4 suffixes and short numeric zips missing a leading zero (e.g. Sigma
  returning `1001` for `01001`) are normalized before lookup.

## Editor-panel config
- **source** — the data element (one row per zip code, or per record with a zip column)
- **Zip Code** — the zip code column (text or number; ZIP+4 and missing leading zeros are handled)
- **Legend / group (optional)** — an optional column to color/group points into separate map traces (e.g. region, segment)
- **Selected Zip Codes (writeback)** — a text control variable; the plugin writes the lassoed zip codes to it as a comma-separated string (e.g. `"10001,10002,94103"`), and clears it (`""`) when the selection is cleared
- **Show legend** — toggle the map legend when a Legend/group column is set
- **Map style** — one of `light`, `dark`, `streets`, `outdoors`, `satellite`, `satellite-streets` (defaults to `light`)
- **Mapbox Access Token** — required; get one free at [mapbox.com](https://www.mapbox.com/)

## Using the selection
Bind a Sigma element's filter to the `Selected Zip Codes` variable, e.g. a
formula filter like `IsIn([Zip Code], Split([Selected Zip Codes CSV], ","))`
on the table/chart you want the lasso to drive. Leaving the variable empty
(the default, and what happens after a deselect) should mean "no filter" in
that formula.

## Register + embed
1. Host this folder (e.g. `http://localhost:8080/zip-code-lasso/` for dev, or any static host — GitHub Pages, Netlify, Vercel, S3 — for production). `zip-centroids.js` must be served alongside `index.html` at the same relative path.
2. Register: `POST /v2/plugins {name,description,url,type:"element"}` → returns `pluginId`.
3. Embed in a workbook spec: `{kind:"plugin", pluginId, config:{source:{kind:"element",elementId}, zipCode:"<colId>", legend:"<colId>", filterZipCodes:{kind:"variable", variableId}, MapboxAccessToken:"<token>"}}` (bindings are bare columnId/variableId values that match the editor-panel names).

## Notes
- Rows whose zip code isn't a recognized 5-digit US ZCTA (bad data, non-US
  zips, etc.) are skipped and counted in a small on-map warning badge rather
  than breaking the render.
- The map is re-centered/zoomed to fit whatever zip codes are currently in
  the source data every time that data changes — same behavior as the
  original lat/long lasso plugin.
