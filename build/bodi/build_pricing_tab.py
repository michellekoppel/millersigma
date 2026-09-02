#!/usr/bin/env python3
"""Adds a 'Pricing Scenario' tab to the live BODi — Nutrition Business (2)
workbook WITHOUT touching any existing tab/content. Two new physical SQL
tables (Price Base, Price Timeline) generated from the same deterministic
population as `fact`, plus a scenario pivot -> linked input table -> book
chain (the verified cava/bundle-promo pattern) for the price-increase model.

Also applies the minimal, previously-agreed cleanup needed for ANY API save
to succeed on this workbook: re-places the orphaned Cohort Name/Description/
Save-cohort elements, drops the 6 fully-superseded filter controls (and their
now-dangling agent tools), and clears the Scenario Copilot's two dangling
dataSource references. None of this changes anything visible that the user
built — those elements were already invisible/broken before this run.

Usage: python3 build_pricing_tab.py <path-to-live-spec.json> <output-path>
"""
import json
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import build_bodi as b

IN = sys.argv[1]
OUT = sys.argv[2]

d = json.load(open(IN))
doc = d["document"]
CONN = b.CONN

# ======================================================================
# 1. Safety cleanup (same fix already applied+approved on the original workbook)
# ======================================================================
ORPHAN_CONTROLS = {"ctrl-fitprog", "ctrl-nutprog", "ctrl-chan", "ctrl-bundle", "ctrl-stage", "ctrl-adh"}
ORPHAN_TOOLS = {"t-fitprog", "t-nutprog", "t-chan", "t-bundle", "t-stage", "jKhn0PDC77"}

before = len(doc["elements"])
doc["elements"] = [e for e in doc["elements"] if e["id"] not in ORPHAN_CONTROLS]
print("removed orphaned controls:", before - len(doc["elements"]))

for ag in doc.get("agents", []):
    if ag.get("name") == "Cohort Copilot":
        ag["tools"] = [t for t in ag.get("tools", []) if t.get("toolId") not in ORPHAN_TOOLS]
        # the API rejects instructions text that mentions a tool by @tool(id) if
        # that tool isn't configured — strip only the dead references, leave the
        # surrounding authored strategy prose untouched.
        instr = ag.get("instructions", "")
        instr = instr.replace(
            'You can use the @tool("jKhn0PDC77") action to instantly apply a preset filter '
            '(70%+ adherence, Week 3-4 stage), or guide users to build custom filters using the '
            'individual filter actions like @tool("t-fitprog"), @tool("t-nutprog"), @tool("t-chan"), '
            '@tool("t-stage"), and others.',
            'Guide users to build custom filters by describing the criteria (program, stage, adherence, '
            'channel) for them to apply in the Segment Filters panel.'
        )
        for dead_tool in ORPHAN_TOOLS:
            instr = instr.replace(f'@tool("{dead_tool}")', "")
        ag["instructions"] = instr
    if ag.get("name") == "Scenario Copilot":
        live_ids = {e["id"] for e in doc["elements"]}
        ag["dataSources"] = [ds for ds in ag.get("dataSources", []) if ds.get("elementId") in live_ids]

# re-place Cohort Name / Description / Save button if they exist and aren't placed —
# appended at the END of pgdata (rows 160+, well past every existing pgdata element
# in this copy) rather than a fixed band, since this copy's pgdata layout differs
# from the original workbook's and a fixed band collided with her content there.
layout = doc["layout"]
restore_lines = []
for eid, band in [("ctrl-cname", (1, 10)), ("ctrl-cdesc", (10, 19)), ("btn-save-cohort", (19, 25))]:
    if eid in {e["id"] for e in doc["elements"]} and f'elementId="{eid}"' not in layout:
        c1, c2 = band
        restore_lines.append(f'  <Element elementId="{eid}" gridColumn="{c1} / {c2}" gridRow="160 / 162"/>')
if restore_lines:
    pgdata_open = '<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="pgdata">'
    assert layout.count(pgdata_open) == 1
    layout = layout.replace(pgdata_open, pgdata_open + "\n" + "\n".join(restore_lines))
doc["layout"] = layout

# ======================================================================
# 2. New SQL — Price Base (7 SKUs) and Price Timeline (24 historical + 6 future months)
# ======================================================================
PRICE_TXN_CTE = """
, txns AS (
  SELECT
    'Shakeology' AS product_line,
    GET(ARRAY_CONSTRUCT('Shakeology - Chocolate','Shakeology - Vanilla','Shakeology - Vegan Chocolate'), MOD(member_id, 3))::string AS sku,
    shake_revenue AS amount
  FROM fc6 WHERE shake_revenue > 0
  UNION ALL
  SELECT 'Meal Plan', (nutrition_program || ' Program Kit'), mealplan_revenue FROM fc6 WHERE mealplan_revenue > 0
  UNION ALL
  SELECT 'Bars & Supplements', 'Beachbar & Boost Bundle', bars_revenue FROM fc6 WHERE bars_revenue > 0
)"""

PRICE_SBASE_SQL = b.CTE_CHAIN + PRICE_TXN_CTE + """
SELECT
  sku,
  product_line,
  CASE WHEN product_line = 'Shakeology' THEN 129.0
       WHEN product_line = 'Meal Plan' THEN 44.0
       ELSE 39.0 END AS current_price,
  COUNT(*) / 24.0 AS avg_monthly_units,
  SUM(amount) AS total_historical_revenue
FROM txns
GROUP BY sku, product_line
"""

PRICE_TIMELINE_SQL = b.CTE_CHAIN + """
, hist AS (
  SELECT calendar_month AS month,
         SUM(shake_revenue + mealplan_revenue + bars_revenue) AS historical_revenue,
         FALSE AS is_future
  FROM fc6
  GROUP BY calendar_month
),
future_months AS (
  SELECT DATEADD('month', (ROW_NUMBER() OVER (ORDER BY SEQ4())), DATE_TRUNC('month', CURRENT_DATE())) AS month,
         NULL AS historical_revenue,
         TRUE AS is_future
  FROM TABLE(GENERATOR(ROWCOUNT => 6))
)
SELECT month, historical_revenue, is_future FROM hist
UNION ALL
SELECT month, historical_revenue, is_future FROM future_months
ORDER BY month
"""

SBASE_COLS = [("ps-sku", "SKU", "Sku"), ("ps-line", "PRODUCT_LINE", "Product Line"),
              ("ps-price", "CURRENT_PRICE", "Current Price"), ("ps-units", "AVG_MONTHLY_UNITS", "Avg Monthly Units"),
              ("ps-histrev", "TOTAL_HISTORICAL_REVENUE", "Total Historical Revenue")]
TIMELINE_COLS = [("pt-month", "MONTH", "Month"), ("pt-histrev", "HISTORICAL_REVENUE", "Historical Revenue"),
                 ("pt-future", "IS_FUTURE", "Is Future")]

price_sbase = b.sql_table("px-sbase", "Price Base", PRICE_SBASE_SQL, SBASE_COLS)
price_timeline = b.sql_table("px-timeline", "Price Timeline", PRICE_TIMELINE_SQL, TIMELINE_COLS)

# ======================================================================
# 3. Scenario chain — Price Scenarios (named runs) -> pivot -> linked input table -> book
# ======================================================================
price_scenarios = {"id": "px-scenarios", "kind": "input-table", "source": {"kind": "empty", "connectionId": CONN},
                    "inputMode": "edit", "name": "Price Scenarios",
                    "columns": [{"id": "sc-name", "type": "text", "name": "Scenario Name"},
                                {"id": "sc-status", "type": "text", "name": "Status", "values": ["Draft"], "pills": "color-by-option"}]}

price_spivot = {"id": "px-spivot", "kind": "pivot-table", "name": "Price Scenario Pivot", "visibleAsSource": True,
                "source": {"kind": "join", "joins": [{"left": {"elementId": "px-sbase", "kind": "table"},
                                                        "right": {"elementId": "px-scenarios", "kind": "table"},
                                                        "columns": [{"left": "1", "right": "1"}], "joinType": "left-outer"}],
                           "primarySource": {"elementId": "px-sbase", "kind": "table"}},
                "columns": [
                    {"id": "pv-sku", "formula": "[Price Base/Sku]", "name": "Sku"},
                    {"id": "pv-line", "formula": "[Price Base/Product Line]", "name": "Product Line"},
                    {"id": "pv-scen", "formula": 'Coalesce([Price Scenarios/Scenario Name],"Base Case")', "name": "Scenario"},
                    {"id": "pv-price", "formula": "Sum([Price Base/Current Price])", "name": "Current Price", "format": b.CUR2},
                    {"id": "pv-units", "formula": "Sum([Price Base/Avg Monthly Units])", "name": "Avg Monthly Units", "format": b.NUM}],
                "rowsBy": [{"id": "pv-sku"}, {"id": "pv-line"}], "values": ["pv-price", "pv-units"]}

price_assum = {"id": "px-assum", "kind": "input-table", "source": {"kind": "linked", "from": "px-spivot"},
               "inputMode": "edit", "name": "Price Assumptions",
               "columns": [
                   {"id": "ia-sku", "key": "pv-sku"}, {"id": "ia-line", "key": "pv-line"}, {"id": "ia-scen", "key": "pv-scen"},
                   {"id": "ia-price", "key": "pv-price"}, {"id": "ia-units", "key": "pv-units"},
                   {"id": "ia-increase", "type": "number", "name": "Price Increase %"},
                   {"id": "ia-newprice", "formula": "[Current Price]*(1+Coalesce([Price Increase %],0)/100)", "name": "New Price"},
                   {"id": "ia-baserev", "formula": "[Avg Monthly Units]*[Current Price]", "name": "Baseline Monthly Revenue"},
                   {"id": "ia-projrev", "formula": "[Avg Monthly Units]*[New Price]", "name": "Projected Monthly Revenue"},
                   {"id": "ia-delta", "formula": "[Projected Monthly Revenue]-[Baseline Monthly Revenue]", "name": "Revenue Delta"}],
               "order": ["ia-scen", "ia-sku", "ia-line", "ia-price", "ia-increase", "ia-newprice", "ia-units", "ia-baserev", "ia-projrev", "ia-delta"]}

price_book = {"id": "px-book", "kind": "table", "name": "Price Book", "visibleAsSource": True,
              "source": {"elementId": "px-assum", "kind": "table"},
              "columns": [
                  {"id": "pb-scen", "formula": "[Price Assumptions/Scenario]", "name": "Scenario"},
                  {"id": "pb-sku", "formula": "[Price Assumptions/Sku]", "name": "Sku"},
                  {"id": "pb-line", "formula": "[Price Assumptions/Product Line]", "name": "Product Line"},
                  {"id": "pb-price", "formula": "[Price Assumptions/Current Price]", "name": "Current Price", "format": b.CUR2},
                  {"id": "pb-newprice", "formula": "[Price Assumptions/New Price]", "name": "New Price", "format": b.CUR2},
                  {"id": "pb-baserev", "formula": "[Price Assumptions/Baseline Monthly Revenue]", "name": "Baseline Monthly Revenue", "format": b.CUR2},
                  {"id": "pb-projrev", "formula": "[Price Assumptions/Projected Monthly Revenue]", "name": "Projected Monthly Revenue", "format": b.CUR2}]}

# ======================================================================
# 4. Controls + buttons
# ======================================================================
ctrl_scenario = {"kind": "control", "controlId": "ActiveScenario", "id": "px-ctrl-scenario", "name": "Active scenario",
                  "controlType": "list", "selectionMode": "single", "mode": "include", "value": "Base Case",
                  "source": {"kind": "source", "source": {"kind": "table", "elementId": "px-book"}, "columnId": "pb-scen"}}
ctrl_newname = {"kind": "control", "controlId": "NewPriceScenarioName", "id": "px-ctrl-newname", "name": "Scenario name",
                 "controlType": "text", "mode": "equals", "case": "insensitive",
                 "includeNulls": "when-no-value-is-selected", "showOperators": False}

btn_open = {"id": "px-btn-open", "kind": "button", "text": "New price scenario", "appearance": "filled",
            "actions": [{"id": "px-a1", "trigger": "on-click", "effects": [{"effect": "open-overlay", "overlayId": "modalPriceScenario"}]}]}
btn_create = {"id": "px-btn-create", "kind": "button", "text": "Create scenario", "appearance": "filled",
              "actions": [{"id": "px-a2", "trigger": "on-click", "effects": [
                  {"effect": "insert-rows", "tableElementId": "px-scenarios", "values": {
                      "sc-name": {"type": "control", "control": "NewPriceScenarioName"},
                      "sc-status": {"type": "constant", "value": {"type": "text", "value": "Draft"}}}},
                  {"effect": "set-control-value", "control": "ActiveScenario", "value": {"type": "control", "control": "NewPriceScenarioName"}},
                  {"effect": "clear-control", "scope": {"type": "control", "controlId": "NewPriceScenarioName"}},
                  {"effect": "close-overlay"}]}]}
btn_cancel = {"id": "px-btn-cancel", "kind": "button", "text": "Cancel", "appearance": "outline",
              "actions": [{"id": "px-a3", "trigger": "on-click", "effects": [{"effect": "close-overlay"}]}]}

# ======================================================================
# 5. KPIs (matched to the active scenario, defaulting to Base Case if unset —
#    a code-created list control has no reliable initial value)
# ======================================================================
ACTIVE = 'Coalesce([ActiveScenario],"Base Case")'
kpi_defs = [
    ("px-kpi-base", "BASELINE MONTHLY REVENUE", f"SumIf([Price Book/Baseline Monthly Revenue],[Price Book/Scenario]={ACTIVE})", b.CUR, None),
    ("px-kpi-proj", "PROJECTED MONTHLY REVENUE", f"SumIf([Price Book/Projected Monthly Revenue],[Price Book/Scenario]={ACTIVE})", b.CUR,
     f"SumIf([Price Book/Baseline Monthly Revenue],[Price Book/Scenario]={ACTIVE})"),
    ("px-kpi-uplift", "6-MONTH REVENUE IMPACT",
     f"(SumIf([Price Book/Projected Monthly Revenue],[Price Book/Scenario]={ACTIVE})-SumIf([Price Book/Baseline Monthly Revenue],[Price Book/Scenario]={ACTIVE}))*6",
     b.CUR, None),
]
kpi_els, kpi_lay = [], []
for i, (key, title, formula, fmt, comp) in enumerate(kpi_defs):
    e, l = b.plain_kpi(key, "px-book", title, formula, fmt, comp_formula=comp, col=(1 + i * 8, 1 + (i + 1) * 8), row=(9, 17))
    kpi_els += e; kpi_lay.append(l)

# ======================================================================
# 6. The chart — historic solid line + 2 future dashed lines, one join source
# ======================================================================
chart = {"id": "px-chart", "kind": "combo-chart",
         "source": {"kind": "join", "joins": [{"left": {"elementId": "px-timeline", "kind": "table"},
                                                 "right": {"elementId": "px-book", "kind": "table"},
                                                 "columns": [{"left": "1", "right": "1"}], "joinType": "left-outer"}],
                    "primarySource": {"elementId": "px-timeline", "kind": "table"}},
         "columns": [
             {"id": "pc-month", "formula": "[Price Timeline/Month]", "name": "Month", "format": {"kind": "datetime", "formatString": "%b %Y"}},
             {"id": "pc-hist", "formula": "Max(If([Price Timeline/Is Future],Null,[Price Timeline/Historical Revenue]))", "name": "Historical Revenue", "format": b.CUR},
             {"id": "pc-base", "formula": f"Sum(If([Price Timeline/Is Future] And [Price Book/Scenario]={ACTIVE},[Price Book/Baseline Monthly Revenue],Null))", "name": "Future Revenue — Price Unchanged", "format": b.CUR},
             {"id": "pc-proj", "formula": f"Sum(If([Price Timeline/Is Future] And [Price Book/Scenario]={ACTIVE},[Price Book/Projected Monthly Revenue],Null))", "name": "Future Revenue — Scenario Price", "format": b.CUR}],
         "xAxis": {"columnId": "pc-month"},
         "yAxis": {"columnIds": [{"columnId": "pc-hist", "type": "line"}, {"columnId": "pc-base", "type": "line"}, {"columnId": "pc-proj", "type": "line"}]},
         "legend": {"visibility": "visible"},
         "name": {"text": "Revenue — historical actuals vs. future price scenario", "fontWeight": "bold", "fontSize": 14, "color": b.INK},
         "style": dict(b.CARD)}

# ======================================================================
# 7. Assembly of the new tab
# ======================================================================
hdr = b.text_el("px-hdr", "## Pricing Scenario\nModel a price change per product and see the projected impact on future revenue, based on trailing demand.", color=b.INK)
instr = b.text_el("px-instr", "Type a **Price Increase %** for any product below (e.g. 5 for +5%) — leave blank to hold today's price. Pick or create a scenario above to compare runs.", color=b.GREEN_D)

modal_title = b.text_el("px-modal-title", "### New price scenario\nName this what-if (e.g. \"Shakeology +5%\") — it clones today's prices so you can adjust from there.")
modal_els = [modal_title, ctrl_newname, btn_create, btn_cancel]
modal_layout = ('<Page type="grid" gridTemplateColumns="repeat(24,1fr)" gridTemplateRows="auto" id="modalPriceScenario">\n'
                 + b.elx("px-modal-title", (1, 25), (1, 3)) + "\n"
                 + b.elx("px-ctrl-newname", (1, 25), (3, 5)) + "\n"
                 + b.elx("px-btn-cancel", (13, 19), (5, 7)) + "\n"
                 + b.elx("px-btn-create", (19, 25), (5, 7)) + "\n</Page>")

new_tab_elements = ([price_sbase, price_timeline, price_scenarios, price_spivot, price_assum, price_book,
                      ctrl_scenario, btn_open, hdr, instr] + kpi_els + [chart] + modal_els)

new_tab_layout = "\n".join([
    b.elx("px-hdr", (1, 19), (1, 4)),
    b.elx("px-ctrl-scenario", (19, 23), (1, 3)),
    b.elx("px-btn-open", (23, 25), (1, 3)),
] + kpi_lay + [
    b.elx("px-instr", (1, 25), (18, 19)),
    b.elx("px-assum", (1, 25), (19, 32)),
    b.elx("px-chart", (1, 25), (33, 52)),
])

# ---- patch document.elements ----
doc["elements"] = doc["elements"] + new_tab_elements

# ---- patch agents: add Scenario Copilot's dataSources back, pointed at the new tables ----
for ag in doc.get("agents", []):
    if ag.get("name") == "Scenario Copilot":
        ag["dataSources"] = [{"kind": "table", "elementId": "px-book"}, {"kind": "table", "elementId": "px-assum"}]
        ag["instructions"] = ("You help analyze BODi's pricing scenarios. `Price Book` shows, per SKU and named "
                               "scenario, the current price, any modeled price increase, and baseline vs. projected "
                               "monthly revenue (projected units come from trailing historical demand, held flat). "
                               "Explain the revenue tradeoff of a price change and which scenario looks best.")

# ---- patch layout: new tab entry + new Tab block + overlay page ----
tabbed = next(e for e in doc["elements"] if e["id"] == "tc-main")
tabbed["tabs"].append({"name": "Pricing Scenario"})

layout = doc["layout"]
# insert the new <Tab> block right before the TabbedContainer's closing tag
close_tag = "</TabbedContainer>"
assert layout.count(close_tag) == 1
new_tab_block = f'    <Tab gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto">\n{new_tab_layout}\n    </Tab>\n  '
layout = layout.replace(close_tag, new_tab_block + close_tag)

# hidden data-plumbing tables on pgdata, and the new modal page, appended at the end
pgdata_close = '</Page>\n<Page type="grid" gridTemplateColumns="repeat(12, 1fr)" gridTemplateRows="auto" id="k1L663v2Vu">'
assert layout.count(pgdata_close) == 1
pgdata_insert = ('  <Element elementId="px-sbase" gridColumn="1 / 25" gridRow="124 / 130"/>\n'
                  '  <Element elementId="px-timeline" gridColumn="1 / 25" gridRow="130 / 136"/>\n'
                  '  <Element elementId="px-scenarios" gridColumn="1 / 25" gridRow="136 / 142"/>\n'
                  '  <Element elementId="px-spivot" gridColumn="1 / 25" gridRow="142 / 148"/>\n'
                  '  <Element elementId="px-book" gridColumn="1 / 25" gridRow="148 / 154"/>\n'
                  + pgdata_close)
layout = layout.replace(pgdata_close, pgdata_insert)

layout = layout.rstrip() + "\n" + modal_layout
doc["layout"] = layout

# ---- patch overlays ----
doc.setdefault("overlays", []).append({
    "id": "modalPriceScenario", "type": "modal", "name": "New price scenario",
    "modal": {"width": "small", "header": {"title": "New price scenario", "showCloseIcon": "shown"},
              "footer": {"primaryCta": {"visible": "hidden"}, "secondaryCta": {"visible": "hidden"}}}})

clean = {"name": d["name"], "folderId": d["folderId"], "document": doc}
json.dump(clean, open(OUT, "w"), indent=2)
print("wrote", OUT)
