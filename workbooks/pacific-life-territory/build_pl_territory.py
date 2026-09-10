#!/usr/bin/env python3
"""Pacific Life Territory Planning app — generator.

Builds a Sigma workbook (new 2026-08 document{} schema) implementing:
- Reps (static reference table)
- Accounts (synthetic ~26k-row population, custom SQL + Ntile window fns)
- Carves (input table — named scenarios)
- Overrides (append-only input table — one-off manual reallocations)
- Latest Override (derived: newest override per carve+account key)
- 4 "Territory" views (Overview/Detail/CompareA/CompareB), each an
  un-grouped accounts+effective-rep table driven by its own carve-picker
  control, so charts/KPIs can do their own xAxis/yAxis aggregation without
  the grouped-table fan-out trap.
- A Territory Carving Agent with 5 tools (name/desc/dimension/create/reallocate)

Run:
    python3 build_pl_territory.py > spec.json
    python3 ../../scripts/validate-spec.py spec.json   # legacy-schema checks only
    ../../scripts/api/publish-workbook.sh post spec.json
"""
import json

FOLDER = "004d8497-18ea-4cf6-a8c5-deca403c22d9"
CONN = "8b007632-070b-4442-ac69-6abd1a690bd3"  # DEMO_ACTUARY (Snowflake)

N_REPS = 13
ACCOUNTS_PER_REP = 2000
TOTAL_ACCOUNTS = N_REPS * ACCOUNTS_PER_REP  # 26,000

INK = "#141414"
BLUE = "#1B5FBF"
GRAY = "#5A6472"
LABEL_GRAY = "#8A8F98"
GOOD = "#2E9B6B"
BAD = "#9A1B2F"

CARD = {"backgroundColor": "#FFFFFF", "borderColor": "#E5E7EB", "borderWidth": 1, "borderRadius": "round"}
TINT = {"backgroundColor": "#EEF3FC", "borderColor": "#CFE0F5", "borderWidth": 1, "borderRadius": "round"}
CUR = {"kind": "number", "formatString": "$.3~s", "currencySymbol": "$", "decimalSymbol": ".",
       "digitGroupingSymbol": ",", "digitGroupingSize": [3]}
NUM = {"kind": "number", "formatString": ",.3~s"}

REGION_SCHEME = ["#1B5FBF", "#5A6472", "#2E9B6B", "#C9A94B", "#B0407A"]
INDUSTRY_SCHEME = ["#1B5FBF", "#5A6472", "#2E9B6B", "#C9A94B", "#B0407A", "#9A1B2F",
                    "#4B7BAF", "#7A8471", "#C97A3C"]

# ---------------------------------------------------------------------------
# Reps — 13 Pacific Life wholesalers, home region + target capacity.
# ---------------------------------------------------------------------------
REPS = [
    (1, "Sarah Chen", "West", 2000),
    (2, "Marcus Alvarez", "West", 2000),
    (3, "Grace Kim", "West", 2000),
    (4, "Devon Whitfield", "Southwest", 2000),
    (5, "Priya Natarajan", "Southwest", 2000),
    (6, "Liam O'Connor", "Midwest", 2000),
    (7, "Angela Brooks", "Midwest", 2000),
    (8, "Tyrell Jackson", "Midwest", 2000),
    (9, "Nicole Ferraro", "Southeast", 2000),
    (10, "Ben Kessler", "Southeast", 2000),
    (11, "Monica Reyes", "Southeast", 2000),
    (12, "Adam Silverstein", "Northeast", 2000),
    (13, "Diane Okafor", "Northeast", 2000),
]
assert len(REPS) == N_REPS
def _sqlstr(s):
    return s.replace("'", "''")


_rep_values = ",".join(f"({rid},'{_sqlstr(name)}','{region}',{cap})" for rid, name, region, cap in REPS)
REPS_SQL = (
    "SELECT column1 AS REP_ID, column2 AS REP_NAME, column3 AS HOME_REGION, column4 AS TARGET_CAPACITY "
    f"FROM (VALUES {_rep_values})"
)

reps = {
    "id": "reps", "kind": "table", "name": "Reps", "visibleAsSource": True,
    "source": {"kind": "sql", "connectionId": CONN, "statement": REPS_SQL},
    "columns": [
        {"id": "r-id", "name": "Rep Id", "formula": "[Custom SQL/REP_ID]"},
        {"id": "r-name", "name": "Rep Name", "formula": "[Custom SQL/REP_NAME]"},
        {"id": "r-region", "name": "Home Region", "formula": "[Custom SQL/HOME_REGION]"},
        {"id": "r-capacity", "name": "Target Capacity", "formula": "[Custom SQL/TARGET_CAPACITY]", "format": NUM},
    ],
    "order": ["r-id", "r-name", "r-region", "r-capacity"],
    "style": dict(CARD),
}

# ---------------------------------------------------------------------------
# Accounts — synthetic ~26,000-row book of business.
# ---------------------------------------------------------------------------
FIRST_NAMES = ["James", "Mary", "Robert", "Patricia", "John", "Linda", "Michael", "Barbara", "William",
               "Elizabeth", "David", "Susan", "Richard", "Jessica", "Joseph", "Sarah", "Thomas", "Karen",
               "Charles", "Nancy", "Daniel", "Lisa", "Matthew", "Betty", "Anthony"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez",
              "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor",
              "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson", "White", "Harris"]
STATES = ["NY", "MA", "NJ", "PA", "CT", "FL", "GA", "NC", "VA", "TN", "IL", "OH", "MI", "WI", "MN",
          "TX", "AZ", "OK", "NM", "CO", "CA", "WA", "OR", "NV", "UT"]
REGIONS = ["Northeast", "Southeast", "Midwest", "Southwest", "West"]
INDUSTRIES = ["Healthcare", "Technology", "Manufacturing", "Retail Trade", "Financial Services",
              "Education", "Construction", "Government", "Professional Services"]


def arr(vals):
    return "ARRAY_CONSTRUCT(" + ",".join(f"'{v}'" for v in vals) + ")"


ACCOUNTS_SQL = f"""WITH g AS (SELECT SEQ4() AS I FROM TABLE(GENERATOR(ROWCOUNT=>{TOTAL_ACCOUNTS}))),
base AS (
  SELECT
    I,
    MOD(I*7, 25) AS STATE_IDX,
    MOD(I*13, 9) AS INDUSTRY_IDX,
    MOD(I, 100) AS SEG_ROLL
  FROM g
)
SELECT
  'ACCT-'||LPAD(I::string,6,'0') AS ACCOUNT_ID,
  GET({arr(FIRST_NAMES)}, MOD(I*3,25))::string || ' ' || GET({arr(LAST_NAMES)}, MOD(I*17,25))::string AS ACCOUNT_NAME,
  GET({arr(STATES)}, STATE_IDX)::string AS STATE,
  GET({arr(REGIONS)}, FLOOR(STATE_IDX/5))::string AS REGION,
  GET({arr(INDUSTRIES)}, INDUSTRY_IDX)::string AS INDUSTRY,
  CASE WHEN SEG_ROLL < 15 THEN 'High Net Worth' WHEN SEG_ROLL < 55 THEN 'Mass Affluent' ELSE 'Retail' END AS SEGMENT,
  CASE WHEN SEG_ROLL < 15 THEN 50000 + MOD(I*8191, 200000)
       WHEN SEG_ROLL < 55 THEN 8000 + MOD(I*4423, 32000)
       ELSE 1500 + MOD(I*97, 6500) END AS ACCOUNT_VALUE,
  FLOOR(STATE_IDX/5)*100000 + I AS GEO_SORT_KEY,
  INDUSTRY_IDX*100000 + I AS INDUSTRY_SORT_KEY,
  (CASE WHEN SEG_ROLL < 15 THEN 0 WHEN SEG_ROLL < 55 THEN 1 ELSE 2 END)*100000 + I AS SEGMENT_SORT_KEY
FROM base"""

accounts = {
    "id": "accounts", "kind": "table", "name": "Accounts", "visibleAsSource": True,
    "source": {"kind": "sql", "connectionId": CONN, "statement": ACCOUNTS_SQL},
    "columns": [
        {"id": "a-id", "name": "Account Id", "formula": "[Custom SQL/ACCOUNT_ID]"},
        {"id": "a-name", "name": "Account Name", "formula": "[Custom SQL/ACCOUNT_NAME]"},
        {"id": "a-state", "name": "State", "formula": "[Custom SQL/STATE]"},
        {"id": "a-region", "name": "Region", "formula": "[Custom SQL/REGION]"},
        {"id": "a-industry", "name": "Industry", "formula": "[Custom SQL/INDUSTRY]"},
        {"id": "a-segment", "name": "Segment", "formula": "[Custom SQL/SEGMENT]"},
        {"id": "a-value", "name": "Account Value", "formula": "[Custom SQL/ACCOUNT_VALUE]", "format": CUR},
        {"id": "a-geokey", "name": "Geo Sort Key", "formula": "[Custom SQL/GEO_SORT_KEY]"},
        {"id": "a-indkey", "name": "Industry Sort Key", "formula": "[Custom SQL/INDUSTRY_SORT_KEY]"},
        {"id": "a-segkey", "name": "Segment Sort Key", "formula": "[Custom SQL/SEGMENT_SORT_KEY]"},
        {"id": "a-ntilegeo", "name": "Ntile Geo", "formula": f"Ntile({N_REPS},[Geo Sort Key])"},
        {"id": "a-ntileind", "name": "Ntile Industry", "formula": f"Ntile({N_REPS},[Industry Sort Key])"},
        {"id": "a-ntileseg", "name": "Ntile Segment", "formula": f"Ntile({N_REPS},[Segment Sort Key])"},
    ],
    "order": ["a-id", "a-name", "a-state", "a-region", "a-industry", "a-segment", "a-value",
              "a-geokey", "a-indkey", "a-segkey", "a-ntilegeo", "a-ntileind", "a-ntileseg"],
    "style": dict(CARD),
}

# ---------------------------------------------------------------------------
# Carves — named allocation scenarios (input table).
# ---------------------------------------------------------------------------
carves = {
    "id": "carves", "kind": "input-table", "name": "Carves",
    "source": {"kind": "empty", "connectionId": CONN}, "inputMode": "explore",
    "columns": [
        {"id": "c-name", "type": "text", "name": "Name"},
        {"id": "c-dim", "type": "text", "name": "Balance Dimension",
         "values": ["Geography", "Industry", "Segment"], "pills": "color-by-option"},
        {"id": "c-desc", "type": "text", "name": "Description"},
        {"id": "CREATED_AT"},
        {"id": "CREATED_BY"},
    ],
    "order": ["c-name", "c-dim", "c-desc", "CREATED_AT", "CREATED_BY"],
    "style": dict(CARD),
}

# ---------------------------------------------------------------------------
# Overrides — append-only log of one-off manual reallocations.
# ---------------------------------------------------------------------------
overrides = {
    "id": "overrides", "kind": "input-table", "name": "Overrides",
    "source": {"kind": "empty", "connectionId": CONN}, "inputMode": "explore",
    "columns": [
        {"id": "o-carve", "type": "text", "name": "Carve Name"},
        {"id": "o-account", "type": "text", "name": "Account Id"},
        {"id": "o-newrep", "type": "number", "name": "New Rep Id"},
        {"id": "CREATED_AT"},
        {"id": "CREATED_BY"},
    ],
    "order": ["o-carve", "o-account", "o-newrep", "CREATED_AT", "CREATED_BY"],
    "style": dict(CARD),
}

# Latest Override — newest override per (carve|account) key. groupBy the Key;
# MaxIf-latest pattern per sigma-input-table-app's governed-modal section.
latest_override = {
    "id": "latest-override", "kind": "table", "name": "Latest Override", "visibleAsSource": True,
    "source": {"kind": "table", "elementId": "overrides"},
    "columns": [
        {"id": "lo-key", "name": "Key", "formula": '[Overrides/Carve Name] & "|" & [Overrides/Account Id]'},
        {"id": "lo-created", "name": "Created At", "formula": "[Overrides/Created At]"},
        {"id": "lo-newrep-raw", "name": "New Rep Id Raw", "formula": "[Overrides/New Rep Id]"},
        {"id": "lo-newrep", "name": "New Rep Id",
         "formula": "MaxIf([New Rep Id Raw],[Created At]=Max([Created At]))"},
    ],
    "order": ["lo-key", "lo-created", "lo-newrep-raw", "lo-newrep"],
    "groupings": [{"id": "g-lo", "groupBy": ["lo-key"], "calculations": ["lo-newrep"]}],
    "visibleAsSource": False,
}

# ---------------------------------------------------------------------------
# 4 carve-pickers (no `filters` — value providers only, per cohort-builder
# skill's analysis-picker gotcha) + the reallocation/create controls.
# ---------------------------------------------------------------------------
def carve_picker(control_id, elid, label):
    return {"kind": "control", "controlId": control_id, "id": elid, "name": label,
            "controlType": "list", "mode": "include", "selectionMode": "single", "values": [],
            "source": {"kind": "source", "source": {"kind": "table", "elementId": "carves"}, "columnId": "c-name"}}


ctrl_carvepick = carve_picker("CarvePick", "ctrl-carvepick", "Select Carve")
ctrl_detailpick = carve_picker("DetailCarvePick", "ctrl-detailpick", "Select Carve to View / Edit")
ctrl_comparea = carve_picker("CompareCarveA", "ctrl-comparea", "Carve A")
ctrl_compareb = carve_picker("CompareCarveB", "ctrl-compareb", "Carve B")

ctrl_new_name = {"kind": "control", "controlId": "NewCarveName", "id": "ctrl-new-name", "name": "New Carve Name",
                  "controlType": "text", "mode": "equals", "case": "insensitive",
                  "includeNulls": "when-no-value-is-selected", "showOperators": False}
ctrl_new_desc = {"kind": "control", "controlId": "NewCarveDesc", "id": "ctrl-new-desc", "name": "Description",
                  "controlType": "text-area", "mode": "equals", "case": "insensitive",
                  "includeNulls": "when-no-value-is-selected", "showOperators": False}
ctrl_new_dim = {"kind": "control", "controlId": "NewCarveDim", "id": "ctrl-new-dim", "name": "Balance Dimension",
                 "controlType": "segmented", "value": "Geography",
                 "source": {"kind": "manual", "valueType": "text",
                            "values": ["Geography", "Industry", "Segment"],
                            "labels": ["Geography", "Industry", "Segment"]}}

ctrl_reassign_acct = {"kind": "control", "controlId": "ReassignAccountId", "id": "ctrl-reassign-acct",
                       "name": "Account Id to Reassign", "controlType": "text", "mode": "equals",
                       "case": "insensitive", "includeNulls": "when-no-value-is-selected", "showOperators": False}
ctrl_reassign_rep = {"kind": "control", "controlId": "ReassignNewRep", "id": "ctrl-reassign-rep", "name": "New Rep",
                      "controlType": "list", "mode": "include", "selectionMode": "single", "values": [],
                      "source": {"kind": "source", "source": {"kind": "table", "elementId": "reps"}, "columnId": "r-name"}}

# ---------------------------------------------------------------------------
# 4 "Territory" views: raw (ungrouped) Accounts + effective Rep, one per
# carve-picker control, so downstream charts/KPIs can aggregate themselves
# without the grouped-table fan-out trap.
# ---------------------------------------------------------------------------
def territory_view(elid, name, carve_ctrl):
    dim = f'Lookup([Carves/Balance Dimension],[{carve_ctrl}],[Carves/Name])'
    computed = ('Switch([Carve Dimension],'
                '"Geography",[Ntile Geo],"Industry",[Ntile Industry],"Segment",[Ntile Segment])')
    key = f'[{carve_ctrl}] & "|" & [Account Id]'
    effective = f'Coalesce(Lookup([Latest Override/New Rep Id],{key},[Latest Override/Key]),[Computed Rep Id])'
    return {
        "id": elid, "kind": "table", "name": name, "visibleAsSource": True,
        "source": {"kind": "table", "elementId": "accounts"},
        "columns": [
            {"id": "ae-id", "name": "Account Id", "formula": "[Accounts/Account Id]"},
            {"id": "ae-name", "name": "Account Name", "formula": "[Accounts/Account Name]"},
            {"id": "ae-state", "name": "State", "formula": "[Accounts/State]"},
            {"id": "ae-region", "name": "Region", "formula": "[Accounts/Region]"},
            {"id": "ae-industry", "name": "Industry", "formula": "[Accounts/Industry]"},
            {"id": "ae-segment", "name": "Segment", "formula": "[Accounts/Segment]"},
            {"id": "ae-value", "name": "Account Value", "formula": "[Accounts/Account Value]", "format": CUR},
            {"id": "ae-ntilegeo", "name": "Ntile Geo", "formula": "[Accounts/Ntile Geo]"},
            {"id": "ae-ntileind", "name": "Ntile Industry", "formula": "[Accounts/Ntile Industry]"},
            {"id": "ae-ntileseg", "name": "Ntile Segment", "formula": "[Accounts/Ntile Segment]"},
            {"id": "ae-dim", "name": "Carve Dimension", "formula": dim},
            {"id": "ae-computedrep", "name": "Computed Rep Id", "formula": computed},
            {"id": "ae-effrep", "name": "Effective Rep Id", "formula": effective},
            {"id": "ae-repname", "name": "Rep Name",
             "formula": "Lookup([Reps/Rep Name],[Effective Rep Id],[Reps/Rep Id])"},
            {"id": "ae-repcount", "name": "Rep Account Count",
             "formula": "Rollup(CountDistinct([Account Id]),[Rep Name],[Rep Name])"},
        ],
        "order": ["ae-id", "ae-name", "ae-state", "ae-region", "ae-industry", "ae-segment", "ae-value",
                  "ae-ntilegeo", "ae-ntileind", "ae-ntileseg", "ae-dim", "ae-computedrep", "ae-effrep",
                  "ae-repname", "ae-repcount"],
        "visibleAsSource": False,
    }


tv_overview = territory_view("tv-overview", "Territory — Overview", "CarvePick")
tv_detail = territory_view("tv-detail", "Territory — Detail", "DetailCarvePick")
tv_a = territory_view("tv-a", "Territory — Compare A", "CompareCarveA")
tv_b = territory_view("tv-b", "Territory — Compare B", "CompareCarveB")

UTIL_ELEMENTS = [reps, accounts, carves, overrides, latest_override, tv_overview, tv_detail, tv_a, tv_b]


# ---------------------------------------------------------------------------
# Rep-level summary tables — LEAF display only (nothing sources these further,
# so the grouped-table fan-out trap does not apply). One per territory view.
# ---------------------------------------------------------------------------
def rep_summary(elid, name, tv_name, tv_elid):
    return {
        "id": elid, "kind": "table", "name": name,
        "source": {"kind": "table", "elementId": tv_elid},
        "columns": [
            {"id": elid + "-rep", "name": "Rep Name", "formula": f"[{tv_name}/Rep Name]"},
            {"id": elid + "-cnt", "name": "Accounts", "formula": f"CountDistinct([{tv_name}/Account Id])", "format": NUM},
            {"id": elid + "-val", "name": "Total Value", "formula": f"Sum([{tv_name}/Account Value])", "format": CUR},
        ],
        "order": [elid + "-rep", elid + "-cnt", elid + "-val"],
        "groupings": [{"id": "g-" + elid, "groupBy": [elid + "-rep"], "calculations": [elid + "-cnt", elid + "-val"],
                       "sort": [{"columnId": elid + "-cnt", "direction": "descending"}]}],
        "name_field_note": None,
        "style": dict(CARD),
    }


rs_overview = rep_summary("rs-ov", "Rep Summary — Overview", "Territory — Overview", "tv-overview")
rs_builder = rep_summary("rs-bld", "Rep Summary — New Carve", "Territory — Overview", "tv-overview")
rs_detail = rep_summary("rs-det", "Rep Summary — Detail", "Territory — Detail", "tv-detail")
rs_a = rep_summary("rs-a", "Rep Summary — Compare A", "Territory — Compare A", "tv-a")
rs_b = rep_summary("rs-b", "Rep Summary — Compare B", "Territory — Compare B", "tv-b")
for _t in (rs_overview, rs_builder, rs_detail, rs_a, rs_b):
    _t.pop("name_field_note", None)

# ---------------------------------------------------------------------------
# KPI helper (flat white bordered card — the "clean light + comparison" look)
# ---------------------------------------------------------------------------
def flat_stat(elid, source_id, formula, label, fmt, color=INK, size=26):
    return {"id": elid, "kind": "kpi-chart", "source": {"elementId": source_id, "kind": "table"},
            "columns": [{"id": elid + "v", "formula": formula, "name": label, "format": fmt}],
            "value": {"columnId": elid + "v", "color": color, "fontSize": size, "fontWeight": "bold"},
            "name": {"text": label, "color": LABEL_GRAY, "fontSize": 11, "fontWeight": "bold"},
            "layout": {"anchor": "start"},
            "style": dict(CARD)}


# ---- Overview KPIs ----
k_total_accounts = flat_stat("k-accts", "accounts", "CountDistinct([Accounts/Account Id])",
                              "TOTAL ACCOUNTS", NUM, color=BLUE, size=28)
k_total_reps = flat_stat("k-reps", "reps", "CountDistinct([Reps/Rep Id])",
                          "TOTAL REPS", NUM, color=BLUE, size=28)
k_avg_per_rep = flat_stat("k-avg", "tv-overview",
                           "CountDistinct([Territory — Overview/Account Id])/CountDistinct([Territory — Overview/Rep Name])",
                           "AVG ACCOUNTS / REP", NUM, color=BLUE, size=28)
k_num_carves = flat_stat("k-carves", "carves", "CountDistinct([Carves/Name])",
                          "CARVES CREATED", NUM, color=BLUE, size=28)

k_most_loaded = flat_stat("k-most", "tv-overview", "Max([Territory — Overview/Rep Account Count])",
                           "MOST-LOADED REP (ACCOUNTS)", NUM, color=BAD, size=26)
k_least_loaded = flat_stat("k-least", "tv-overview", "Min([Territory — Overview/Rep Account Count])",
                            "LEAST-LOADED REP (ACCOUNTS)", NUM, color=GOOD, size=26)

# ---- Overview charts: driven by the RAW tv-overview table (chart does its
# own xAxis/yAxis aggregation — no `groupings` on the source, no fan-out) ----
region_bar = {"id": "region-bar", "kind": "bar-chart", "source": {"elementId": "tv-overview", "kind": "table"},
              "columns": [
                  {"id": "rb-rep", "name": "Rep Name", "formula": "[Territory — Overview/Rep Name]"},
                  {"id": "rb-region", "name": "Region", "formula": "[Territory — Overview/Region]"},
                  {"id": "rb-cnt", "name": "Accounts", "formula": "CountDistinct([Territory — Overview/Account Id])", "format": NUM},
              ],
              "xAxis": {"columnId": "rb-rep"}, "yAxis": {"columnIds": ["rb-cnt"]},
              "color": {"by": "category", "column": "rb-region", "scheme": REGION_SCHEME},
              "stacking": "stacked",
              "name": {"text": "Accounts per Rep — colored by Region (selected carve)", "fontWeight": "bold", "fontSize": 14, "color": INK},
              "style": dict(CARD)}

industry_bar = {"id": "industry-bar", "kind": "bar-chart", "source": {"elementId": "tv-overview", "kind": "table"},
                 "columns": [
                     {"id": "ib-rep", "name": "Rep Name", "formula": "[Territory — Overview/Rep Name]"},
                     {"id": "ib-industry", "name": "Industry", "formula": "[Territory — Overview/Industry]"},
                     {"id": "ib-cnt", "name": "Accounts", "formula": "CountDistinct([Territory — Overview/Account Id])", "format": NUM},
                 ],
                 "xAxis": {"columnId": "ib-rep"}, "yAxis": {"columnIds": ["ib-cnt"]},
                 "color": {"by": "category", "column": "ib-industry", "scheme": INDUSTRY_SCHEME},
                 "stacking": "stacked",
                 "name": {"text": "Accounts per Rep — colored by Industry (selected carve)", "fontWeight": "bold", "fontSize": 14, "color": INK},
                 "style": dict(CARD)}

segment_donut = {"id": "segment-donut", "kind": "donut-chart", "source": {"elementId": "tv-overview", "kind": "table"},
                  "columns": [
                      {"id": "sd-seg", "name": "Segment", "formula": "[Territory — Overview/Segment]"},
                      {"id": "sd-cnt", "name": "Accounts", "formula": "CountDistinct([Territory — Overview/Account Id])", "format": NUM},
                  ],
                  "color": {"columnId": "sd-seg"}, "value": {"columnId": "sd-cnt"},
                  "name": {"text": "Segment Mix — whole book", "fontWeight": "bold", "fontSize": 14, "color": INK},
                  "style": dict(CARD)}

# ---------------------------------------------------------------------------
# Buttons
# ---------------------------------------------------------------------------
CREATE_VALUES = {
    "c-name": {"type": "control", "control": "NewCarveName"},
    "c-dim": {"type": "control", "control": "NewCarveDim"},
    "c-desc": {"type": "control", "control": "NewCarveDesc"},
}
btn_create = {"id": "btn-create", "kind": "button", "text": "Create Carve", "appearance": "filled",
              "actions": [{"id": "a-create", "trigger": "on-click", "effects": [
                  {"effect": "insert-rows", "tableElementId": "carves", "values": CREATE_VALUES},
                  {"effect": "set-control-value", "control": "CarvePick", "value": {"type": "control", "control": "NewCarveName"}},
                  {"effect": "clear-control", "scope": {"type": "control", "controlId": "NewCarveName"}},
                  {"effect": "clear-control", "scope": {"type": "control", "controlId": "NewCarveDesc"}},
              ]}]}

REASSIGN_VALUES = {
    "o-carve": {"type": "control", "control": "DetailCarvePick"},
    "o-account": {"type": "control", "control": "ReassignAccountId"},
    "o-newrep": {"type": "formula", "formula": "Lookup([Reps/Rep Id],[ReassignNewRep],[Reps/Rep Name])"},
}
btn_reassign = {"id": "btn-reassign", "kind": "button", "text": "Reassign Account", "appearance": "filled",
                 "actions": [{"id": "a-reassign", "trigger": "on-click", "effects": [
                     {"effect": "insert-rows", "tableElementId": "overrides", "values": REASSIGN_VALUES},
                     {"effect": "clear-control", "scope": {"type": "control", "controlId": "ReassignAccountId"}},
                 ]}]}

# ---------------------------------------------------------------------------
# Territory Carving Agent — 5 tools: name, description, dimension, create,
# reallocate. Mirrors the cohort-builder "one tool per field" pattern.
# ---------------------------------------------------------------------------
AGENT_TOOLS = [
    {"toolId": "t-name", "kind": "action", "name": "Set new carve name",
     "description": "Set the name for the new territory carve/scenario being built.",
     "steps": [{"kind": "effect", "effect": "set-control-value", "control": "NewCarveName",
                "value": {"type": "agent-input", "inputName": "A short, memorable name for this carve"}}]},
    {"toolId": "t-desc", "kind": "action", "name": "Set new carve description",
     "description": "Set a one-sentence description of the new carve based on what the user is trying to accomplish.",
     "steps": [{"kind": "effect", "effect": "set-control-value", "control": "NewCarveDesc",
                "value": {"type": "agent-input", "inputName": "A one-sentence description of this carve"}}]},
    {"toolId": "t-dim", "kind": "action", "name": "Set the balance dimension",
     "description": ('Set which attribute the new carve should balance rep territories by. Must be exactly '
                      'one of: "Geography", "Industry", or "Segment".'),
     "steps": [{"kind": "effect", "effect": "set-control-value", "control": "NewCarveDim",
                "value": {"type": "agent-input", "inputName": 'Exactly one of "Geography", "Industry", "Segment"'}}]},
    {"toolId": "t-create", "kind": "action", "name": "Create the carve",
     "description": ("When the user asks to create/build/save the carve, insert it into the Carves log using "
                      "the name, description, and balance dimension already set, then select it for viewing."),
     "steps": [{"kind": "effect", "effect": "insert-rows", "tableElementId": "carves", "values": CREATE_VALUES},
               {"kind": "effect", "effect": "set-control-value", "control": "CarvePick",
                "value": {"type": "control", "control": "NewCarveName"}}]},
    {"toolId": "t-reallocate", "kind": "action", "name": "Reallocate an account to a different rep",
     "description": ("When the user asks to move/reassign/reallocate a specific account to a different rep on a "
                      "one-off basis, set the carve, account, and target rep, then log the override."),
     "steps": [
         {"kind": "effect", "effect": "set-control-value", "control": "DetailCarvePick",
          "value": {"type": "agent-input", "inputName": "Which carve this reallocation applies to (carve name)"}},
         {"kind": "effect", "effect": "set-control-value", "control": "ReassignAccountId",
          "value": {"type": "agent-input", "inputName": "The Account Id to move, e.g. ACCT-000123"}},
         {"kind": "effect", "effect": "set-control-value", "control": "ReassignNewRep",
          "value": {"type": "agent-input", "inputName": "The exact name of the rep to reassign the account to"}},
         {"kind": "effect", "effect": "insert-rows", "tableElementId": "overrides", "values": REASSIGN_VALUES},
     ]},
]
agent = {"id": "ag-territory", "name": "Territory Carving Assistant",
          "description": "Helps Pacific Life sales leadership build and adjust rep territory carves.",
          "instructions": (
              "You help Pacific Life sales operations build 'carves' — named scenarios that allocate the "
              "~26,000-account book of business across 13 wholesaler reps. A carve balances territories by "
              "exactly one dimension: Geography, Industry, or Segment (High Net Worth / Mass Affluent / Retail). "
              "When the user describes a new carve, use the name/description/dimension tools to set each field, "
              "then use the create tool to save it — confirm back the carve name, dimension, and that it's now "
              "selected for viewing. When the user asks to move a specific account to a different rep ('move "
              "ACCT-000123 to Sarah Chen'), use the reallocation tool with the exact carve name, account id, and "
              "rep name, then confirm back exactly which carve/account/rep you acted on. Never guess an account id "
              "or rep name the user didn't provide — ask if it's ambiguous."),
          "greeting": {"mode": "static",
                       "message": "Ask me to build a new territory carve (e.g. \"balance by industry, call it "
                                  "'Q4 Industry Rebalance'\") or to move a specific account to a different rep."},
          "dataSources": [{"kind": "table", "elementId": "accounts"}, {"kind": "table", "elementId": "reps"},
                           {"kind": "table", "elementId": "carves"}],
          "tools": AGENT_TOOLS}
chat = {"id": "chat1", "kind": "chat", "agentId": "ag-territory"}
chat_hd = {"id": "chat-hd", "kind": "text", "body": "**Ask the Territory Carving Assistant**",
            "verticalAlign": "middle", "style": {"color": INK}}
chat_c = {"id": "c-chat", "kind": "container", "style": dict(TINT)}

# ---------------------------------------------------------------------------
# Compare-page KPIs (per carve A/B)
# ---------------------------------------------------------------------------
def compare_kpis(prefix, tv_elid, tv_name):
    return [
        flat_stat(f"{prefix}-accts", tv_elid, f"CountDistinct([{tv_name}/Account Id])", "ACCOUNTS", NUM, color=BLUE, size=24),
        flat_stat(f"{prefix}-value", tv_elid, f"Sum([{tv_name}/Account Value])", "TOTAL VALUE", CUR, color=BLUE, size=24),
        flat_stat(f"{prefix}-max", tv_elid, f"Max([{tv_name}/Rep Account Count])", "MAX ACCOUNTS/REP", NUM, color=BAD, size=22),
        flat_stat(f"{prefix}-min", tv_elid, f"Min([{tv_name}/Rep Account Count])", "MIN ACCOUNTS/REP", NUM, color=GOOD, size=22),
    ]


kpis_a = compare_kpis("cmp-a", "tv-a", "Territory — Compare A")
kpis_b = compare_kpis("cmp-b", "tv-b", "Territory — Compare B")

# ---------------------------------------------------------------------------
# Detail-page account grid (row-level, all 26k accounts for the selected carve)
# ---------------------------------------------------------------------------
detail_grid = {"id": "detail-grid", "kind": "table", "name": "Territory Detail",
                "source": {"elementId": "tv-detail", "kind": "table"},
                "columns": [
                    {"id": "dg-id", "name": "Account Id", "formula": "[Territory — Detail/Account Id]"},
                    {"id": "dg-name", "name": "Account Name", "formula": "[Territory — Detail/Account Name]"},
                    {"id": "dg-region", "name": "Region", "formula": "[Territory — Detail/Region]"},
                    {"id": "dg-industry", "name": "Industry", "formula": "[Territory — Detail/Industry]"},
                    {"id": "dg-segment", "name": "Segment", "formula": "[Territory — Detail/Segment]"},
                    {"id": "dg-value", "name": "Account Value", "formula": "[Territory — Detail/Account Value]", "format": CUR},
                    {"id": "dg-rep", "name": "Effective Rep", "formula": "[Territory — Detail/Rep Name]"},
                ],
                "order": ["dg-id", "dg-name", "dg-region", "dg-industry", "dg-segment", "dg-value", "dg-rep"],
                "style": dict(CARD)}

saved_carves_table = {"id": "carves-view", "kind": "table", "name": "All Carves",
                        "source": {"elementId": "carves", "kind": "table"},
                        "columns": [
                            {"id": "cv-name", "name": "Name", "formula": "[Carves/Name]"},
                            {"id": "cv-dim", "name": "Balance Dimension", "formula": "[Carves/Balance Dimension]"},
                            {"id": "cv-desc", "name": "Description", "formula": "[Carves/Description]"},
                            {"id": "cv-created", "name": "Created At", "formula": "[Carves/Created At]"},
                            {"id": "cv-by", "name": "Created By", "formula": "[Carves/Created By]"},
                        ],
                        "order": ["cv-name", "cv-dim", "cv-desc", "cv-created", "cv-by"],
                        "style": dict(CARD)}

# ---------------------------------------------------------------------------
# Text elements
# ---------------------------------------------------------------------------
def title(elid, body):
    return {"id": elid, "kind": "text", "body": body, "verticalAlign": "middle", "style": {"color": INK}}


def subtitle(elid, body):
    return {"id": elid, "kind": "text", "body": body, "verticalAlign": "middle", "style": {"color": "#3A3A3A"}}


t_overview = title("t-overview", "# Pacific Life Territory Planning — Overview")
s_overview = subtitle("s-overview", "Pick a carve to see how it balances the ~26,000-account book across 13 wholesalers. "
                                     "Empty on first load until a carve is created on the Carve Builder page.")
t_builder = title("t-builder", "# Carve Builder")
s_builder = subtitle("s-builder", "Name a new carve, pick a balance dimension, and Create — or ask the Territory "
                                    "Carving Assistant to do it for you in natural language.")
t_detail = title("t-detail", "# Territory Detail & Reallocation")
s_detail = subtitle("s-detail", "Pick a carve to see every account's effective rep. To move one account "
                                  "one-off, type its Account Id, pick a new rep, and click Reassign.")
t_compare = title("t-compare", "# Compare Carves")
s_compare = subtitle("s-compare", "Pick two carves to compare how each balances reps by accounts and value.")

# ---------------------------------------------------------------------------
# Page element groupings
# ---------------------------------------------------------------------------
overview_elements = [t_overview, s_overview, ctrl_carvepick,
                      k_total_accounts, k_total_reps, k_avg_per_rep, k_num_carves,
                      k_most_loaded, k_least_loaded,
                      region_bar, industry_bar, segment_donut, rs_overview]

builder_elements = [t_builder, s_builder, ctrl_new_name, ctrl_new_dim, ctrl_new_desc, btn_create,
                     chat_c, chat_hd, chat, rs_builder]

detail_elements = [t_detail, s_detail, ctrl_detailpick, ctrl_reassign_acct, ctrl_reassign_rep, btn_reassign,
                    detail_grid]

compare_elements = [t_compare, s_compare, ctrl_comparea, ctrl_compareb, *kpis_a, *kpis_b, rs_a, rs_b, saved_carves_table]

ALL_ELEMENTS = UTIL_ELEMENTS + overview_elements + builder_elements + detail_elements + compare_elements

# ---------------------------------------------------------------------------
# Layout — NEW 2026-08 schema tags: <Page>/<Container>/<Element>.
# ---------------------------------------------------------------------------
layout_overview = """<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="p-overview">
  <Element elementId="t-overview" gridColumn="1 / 25" gridRow="1 / 3"/>
  <Element elementId="s-overview" gridColumn="1 / 19" gridRow="3 / 5"/>
  <Element elementId="ctrl-carvepick" gridColumn="19 / 25" gridRow="3 / 6"/>
  <Element elementId="k-accts" gridColumn="1 / 7" gridRow="6 / 12"/>
  <Element elementId="k-reps" gridColumn="7 / 13" gridRow="6 / 12"/>
  <Element elementId="k-avg" gridColumn="13 / 19" gridRow="6 / 12"/>
  <Element elementId="k-carves" gridColumn="19 / 25" gridRow="6 / 12"/>
  <Element elementId="k-most" gridColumn="1 / 13" gridRow="12 / 18"/>
  <Element elementId="k-least" gridColumn="13 / 25" gridRow="12 / 18"/>
  <Element elementId="region-bar" gridColumn="1 / 25" gridRow="18 / 34"/>
  <Element elementId="industry-bar" gridColumn="1 / 25" gridRow="34 / 50"/>
  <Element elementId="segment-donut" gridColumn="1 / 13" gridRow="50 / 66"/>
  <Element elementId="rs-ov" gridColumn="13 / 25" gridRow="50 / 66"/>
</Page>"""

layout_builder = """<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="p-builder">
  <Element elementId="t-builder" gridColumn="1 / 17" gridRow="1 / 3"/>
  <Element elementId="s-builder" gridColumn="1 / 17" gridRow="3 / 5"/>
  <Element elementId="ctrl-new-name" gridColumn="1 / 9" gridRow="5 / 8"/>
  <Element elementId="ctrl-new-dim" gridColumn="9 / 17" gridRow="5 / 8"/>
  <Element elementId="ctrl-new-desc" gridColumn="1 / 17" gridRow="8 / 11"/>
  <Element elementId="btn-create" gridColumn="1 / 9" gridRow="11 / 14"/>
  <Container elementId="c-chat" type="grid" gridColumn="17 / 25" gridRow="1 / 44"
             gridTemplateColumns="repeat(12, 1fr)" gridTemplateRows="auto">
    <Element elementId="chat-hd" gridColumn="1 / 13" gridRow="1 / 2"/>
    <Element elementId="chat1" gridColumn="1 / 13" gridRow="2 / 43"/>
  </Container>
  <Element elementId="rs-bld" gridColumn="1 / 17" gridRow="14 / 44"/>
</Page>"""

layout_detail = """<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="p-detail">
  <Element elementId="t-detail" gridColumn="1 / 25" gridRow="1 / 3"/>
  <Element elementId="s-detail" gridColumn="1 / 25" gridRow="3 / 5"/>
  <Element elementId="ctrl-detailpick" gridColumn="1 / 9" gridRow="5 / 8"/>
  <Element elementId="ctrl-reassign-acct" gridColumn="9 / 15" gridRow="5 / 8"/>
  <Element elementId="ctrl-reassign-rep" gridColumn="15 / 21" gridRow="5 / 8"/>
  <Element elementId="btn-reassign" gridColumn="21 / 25" gridRow="5 / 8"/>
  <Element elementId="detail-grid" gridColumn="1 / 25" gridRow="8 / 44"/>
</Page>"""

layout_compare = """<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="p-compare">
  <Element elementId="t-compare" gridColumn="1 / 25" gridRow="1 / 3"/>
  <Element elementId="s-compare" gridColumn="1 / 25" gridRow="3 / 5"/>
  <Element elementId="ctrl-comparea" gridColumn="1 / 13" gridRow="5 / 8"/>
  <Element elementId="ctrl-compareb" gridColumn="13 / 25" gridRow="5 / 8"/>
  <Element elementId="cmp-a-accts" gridColumn="1 / 4" gridRow="8 / 13"/>
  <Element elementId="cmp-a-value" gridColumn="4 / 7" gridRow="8 / 13"/>
  <Element elementId="cmp-a-max" gridColumn="7 / 10" gridRow="8 / 13"/>
  <Element elementId="cmp-a-min" gridColumn="10 / 13" gridRow="8 / 13"/>
  <Element elementId="cmp-b-accts" gridColumn="13 / 16" gridRow="8 / 13"/>
  <Element elementId="cmp-b-value" gridColumn="16 / 19" gridRow="8 / 13"/>
  <Element elementId="cmp-b-max" gridColumn="19 / 22" gridRow="8 / 13"/>
  <Element elementId="cmp-b-min" gridColumn="22 / 25" gridRow="8 / 13"/>
  <Element elementId="rs-a" gridColumn="1 / 13" gridRow="13 / 40"/>
  <Element elementId="rs-b" gridColumn="13 / 25" gridRow="13 / 40"/>
  <Element elementId="carves-view" gridColumn="1 / 25" gridRow="40 / 52"/>
</Page>"""

layout_util = """<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="p-util">
  <Element elementId="reps" gridColumn="1 / 7" gridRow="1 / 12"/>
  <Element elementId="accounts" gridColumn="7 / 13" gridRow="1 / 12"/>
  <Element elementId="carves" gridColumn="13 / 19" gridRow="1 / 12"/>
  <Element elementId="overrides" gridColumn="19 / 25" gridRow="1 / 12"/>
  <Element elementId="latest-override" gridColumn="1 / 7" gridRow="12 / 22"/>
  <Element elementId="tv-overview" gridColumn="7 / 13" gridRow="12 / 22"/>
  <Element elementId="tv-detail" gridColumn="13 / 19" gridRow="12 / 22"/>
  <Element elementId="tv-a" gridColumn="19 / 25" gridRow="12 / 22"/>
  <Element elementId="tv-b" gridColumn="1 / 7" gridRow="22 / 32"/>
</Page>"""

layout = ('<?xml version="1.0" encoding="utf-8"?>\n' + layout_overview + layout_builder + layout_detail
          + layout_compare + layout_util)

# ---------------------------------------------------------------------------
# Spec assembly — 2026-08 document{} envelope.
# ---------------------------------------------------------------------------
spec = {
    "name": "Pacific Life — Territory Planning",
    "folderId": FOLDER,
    "document": {
        "schemaVersion": 1,
        "kind": "workbook",
        "elements": ALL_ELEMENTS,
        "pages": [
            {"id": "p-overview", "name": "Overview", "pageWidth": "large"},
            {"id": "p-builder", "name": "Carve Builder", "pageWidth": "large"},
            {"id": "p-detail", "name": "Territory Detail & Reallocation", "pageWidth": "large"},
            {"id": "p-compare", "name": "Compare Carves", "pageWidth": "large"},
            {"id": "p-util", "name": "Utility Data", "visibility": "hidden", "pageWidth": "large"},
        ],
        "layout": layout,
        "agents": [agent],
    },
}

if __name__ == "__main__":
    import sys
    with open(sys.argv[1] if len(sys.argv) > 1 else "spec.json", "w") as f:
        json.dump(spec, f, indent=2)
    print("wrote spec with", len(ALL_ELEMENTS), "elements")
