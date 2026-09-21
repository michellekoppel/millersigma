# Territory Map — Big Buys

An interactive US store map for a Big Buys sales-territory Sigma dashboard.
Every store is plotted at its lat/lon and colour-coded by its current
region. Clicking a store opens a region picker; picking a new region
recolours the store immediately and writes the reassignment back to the
workbook so an Action Sequence can persist it to the source table. Ships
with a matching Sigma AI agent that can perform the same reassignment from
a chat instruction ("move the Providence store to Mid-Atlantic").

- Single-file `index.html`, vanilla JS + `@sigmacomputing/plugin` CDN SDK.
- Uses **d3** + **topojson-client** + **us-atlas** (all from CDN) for the state background; stores are plotted as `circle` markers via `d3.geoAlbersUsa`, sized by an optional sales column.
- Region colours are assigned in a **fixed categorical order** (never cycled) from the first-seen region names in the data, so the same region always gets the same colour across a session; an 8th+ distinct region folds to a neutral grey "Other" rather than reusing a hue.
- Ships a 32-store / 6-region synthetic fallback (`synth()`) so the plugin previews correctly before it's bound to real data.

## Config (editor panel)

| Field | Type | Notes |
|---|---|---|
| `source` | element | The stores table |
| `storeId` | column | Stable row key — required for reassignment to target the right row |
| `storeName` | column | Display name |
| `lat` / `lon` | column (number) | Store coordinates |
| `region` | column | Current region assignment |
| `sales` | column (number, optional) | Sizes the dot |
| `enableReassign` | toggle | Turn off to make the map view-only (e.g. for a rep-facing page) |
| `selectedStoreId` | variable | Written with the clicked store's ID |
| `selectedNewRegion` | variable | Written with the region the user picked |
| `onReassign` | action-trigger | Fired once both variables above are set |

## Wiring the write-back

The plugin never writes to the warehouse itself — it only reports *what*
changed (`selectedStoreId`, `selectedNewRegion`) and *that* something
changed (`onReassign`), exactly like the Variable + Action Trigger pattern
in `sigma-plugin-patterns`. In the Sigma workbook:

1. Bind `source` to the stores table (or an **input table** if you want the
   region column to be directly editable/auditable).
2. Add an Action Sequence triggered by `onReassign`:
   - **Update row** in the stores input table where `Store ID` =
     `[selectedStoreId]`, setting `Region` = `[selectedNewRegion]`.
   - Optionally follow with **Refresh element(s)** for the map and any
     downstream region roll-up KPIs/tables so they redraw with the
     persisted value on next load.
3. If the underlying table isn't an input table (e.g. it's a warehouse
   table synced some other way), point the same two control variables at
   whatever write-back mechanism your org uses (a stored-procedure call
   action, a webhook action, etc.) — the plugin's contract is the same
   either way: two variables + one trigger.

The plugin also keeps a **local optimistic override** (recolours the dot
and logs the change instantly) so the map feels responsive while the
Action Sequence round-trips; the next data refresh reconciles it against
the real, persisted value.

## Companion agent — Territory Reassignment Copilot

Add a Sigma agent to the same page so reps/ops can reassign a store by
describing it instead of finding it on the map. It uses the identical
write-back contract as the plugin — same two control variables, same
action trigger — so both paths converge on one Action Sequence:

```json
{
  "name": "Territory Reassignment Copilot",
  "instructions": "You help Big Buys sales-ops reassign stores between regions (Northeast, Mid-Atlantic, Southeast, Midwest, South Central, West). Look up the store the user names in the Stores table (fuzzy-match on store name or ID), tell them its current region, confirm the target region before acting, then call reassign_store. If the store or region is ambiguous, ask which one they mean instead of guessing.",
  "dataSources": ["Stores"],
  "tools": [
    {
      "name": "reassign_store",
      "kind": "effect",
      "effect": "set-control-value",
      "control": "selectedStoreId",
      "value": { "type": "agent-input", "inputName": "storeId" }
    },
    {
      "name": "reassign_store_region",
      "kind": "effect",
      "effect": "set-control-value",
      "control": "selectedNewRegion",
      "value": { "type": "agent-input", "inputName": "newRegion" }
    },
    {
      "name": "reassign_store_commit",
      "kind": "effect",
      "effect": "set-control-value",
      "control": "onReassign",
      "value": { "type": "agent-input", "inputName": "confirm" }
    }
  ],
  "greeting": { "mode": "generated" }
}
```

Wire all three `control` values to the *same* `selectedStoreId` /
`selectedNewRegion` / `onReassign` config entries the plugin uses, so the
one Action Sequence above fires no matter whether the reassignment came
from a click on the map or an instruction to the agent.

## Run locally

```bash
python3 -m http.server 8099
```

Open `http://localhost:8099/`, or host it statically anywhere and register
that URL as the plugin's source (see the repo-wide hosting notes in
`skills/sigma-company-dashboard-v2/reference/HANDOFF.md` §9 — GitHub Pages,
not jsDelivr, for a plugin that needs `Content-Type: text/html`).
