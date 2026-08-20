#!/usr/bin/env python3
"""Adds ONE new page — "Population Builder", a member cohort builder with a
real AI agent bound to it — to the LIVE Alliant workbook
(69b0edbc-751a-4ea5-840b-d2ceefef824d), additively. Does not touch the
existing 5 pages (page-exec, page-enroll, page-trend, page-util, page-data)
except to append 4 new data-plumbing tables to the bottom of the hidden
page-data layout.

Built per skills/sigma-cohort-builder-app/SKILL.md (the verified tabbed-
container / agent-tool-per-filter / wide-snapshot-save / grouped-table-sort
shapes), with styling/measure conventions lifted directly from this
workbook's own live spec (GET'd fresh below) rather than guessed — navy
#1b3a5c header/text, card style {white, round, #e2e2e2 border}, the
[GroupName/AgeBand/Plan/Gender] domains already used on the other 4 pages,
confirmed via a live GET of tbl-group/tbl-age/tbl-plan/tbl-gender-split
(GEICO/FIS Global/Contoso Logistics; <35/36-49/50-64/65+; Plan 1/2/3).

Population: a 2,000-row deterministic synthetic member roster (SQL in
sql/alliant_cohort_population.sql, HASH-seeded, no RANDOM) — segmented by
Coverage Tier, Age Band, Gender, Relationship, Plan, Enrollment Tenure, and
Group Name, with a PMPM cost value measure.

Usage:
    python3 build_cohort_page.py           # dry run -> writes cohort_spec_new.json
                                            #   + runs static QA, does not touch the live wb
    python3 build_cohort_page.py --push    # re-checks staleness, then PUTs
"""
import copy
import json
import re
import sys

import sigmaapi as S

WORKBOOK_ID = "69b0edbc-751a-4ea5-840b-d2ceefef824d"

SRC = S.get_workbook(WORKBOOK_ID)
DOC = SRC["document"]
ELEMENTS = {e["id"]: e for e in DOC["elements"]}

# ---------------------------------------------------------------------------
# Palette + conventions, lifted verbatim from this workbook's live elements
# (ctr-header-exec, kpi-enr-cur-exec, bar-tier-enroll, ctrl-group-exec,
# settings.theme.overrides.categoricalScheme) rather than guessed.
# ---------------------------------------------------------------------------
NAVY = "#1b3a5c"
TEAL_BRIGHT = "#5fbfc0"
TEAL_DEEP = "#2e8b8b"
GOLD = "#e8a33d"
GRAY = "#9ca3af"
LOGO_TEAL = "#8FD8D6"

CARD_STYLE = {"backgroundColor": "#ffffff", "borderRadius": "round",
              "borderColor": "#e2e2e2", "borderWidth": 1}
CTRL_STYLE = {"backgroundColor": "#faf7f2", "borderRadius": "round"}
HEADER_STYLE = {"backgroundColor": NAVY, "borderRadius": "square"}
CONTEXT_STYLE = {"backgroundColor": "#161616", "borderRadius": "square"}
CHAT_TINT_STYLE = {"backgroundColor": "#eef6f6", "borderColor": "#cfe8e8",
                    "borderWidth": 1, "borderRadius": "round"}

FMT_DOLLAR = {"kind": "number", "formatString": "$,.0f", "currencySymbol": "$"}
FMT_NUM0 = {"kind": "number", "formatString": ",.0f"}
FMT_PCT1 = {"kind": "number", "formatString": ".1%"}

CONN_ID = ELEMENTS["tbl-group"]["source"]["connectionId"]  # confirmed 8b007632-...
assert CONN_ID == "8b007632-070b-4442-ac69-6abd1a690bd3"

# Reuse the same abstract two-circle SVG mark already live on every other
# page's header (img-logo2-*) so the new page reads as the same product.
LOGO_URL = ELEMENTS["img-logo2-exec"]["source"]["url"]

POP_SQL = open(
    "/home/user/millersigma/skills/sigma-company-dashboard-v2/sql/alliant_cohort_population.sql"
).read()

AGE_BANDS = ["<35", "36-49", "50-64", "65+"]

new_elements = []


def add(e):
    new_elements.append(e)
    return e["id"]


def el(element_id, col, row):
    return '<Element elementId="%s" gridColumn="%s" gridRow="%s"/>' % (element_id, col, row)


def container(element_id, col, row, children, cols=24, extra=None, kind_tag="Container"):
    body = {"id": element_id, "kind": "container"}
    if extra:
        body.update(extra)
    add(body)
    inner = "\n".join(children)
    return ('<%s elementId="%s" type="grid" gridColumn="%s" gridRow="%s" '
            'gridTemplateColumns="repeat(%d, 1fr)" gridTemplateRows="auto">\n%s\n</%s>'
            % (kind_tag, element_id, col, row, cols, inner, kind_tag))


# ---------------------------------------------------------------------------
# Static layout QA (row-overflow / overlap), copied verbatim from
# build_alliant_pages.py's check_layout — same discipline, new page.
# ---------------------------------------------------------------------------

def check_layout(xml_fragment, label):
    import xml.etree.ElementTree as ET
    wrapped = "<root>" + xml_fragment + "</root>"
    root = ET.fromstring(wrapped)

    def span(node):
        def parse(attr):
            a, b = node.get(attr).split("/")
            return int(a.strip()), int(b.strip())
        c0, c1 = parse("gridColumn")
        r0, r1 = parse("gridRow")
        return c0, c1, r0, r1

    issues = []

    def walk(node, parent_row_span=None):
        children = [c for c in node if c.tag in ("Container", "Element", "TabbedContainer", "Tab")]
        max_end_row = 0
        rects = []
        for c in children:
            if c.tag == "Tab":
                walk(c, None)
                continue
            if c.get("gridColumn") is None:
                continue
            c0, c1, r0, r1 = span(c)
            max_end_row = max(max_end_row, r1)
            rects.append((c0, c1, r0, r1, c.get("elementId")))
            if c.tag in ("Container", "TabbedContainer"):
                walk(c, None)
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                a, b = rects[i], rects[j]
                col_overlap = a[0] < b[1] and b[0] < a[1]
                row_overlap = a[2] < b[3] and b[2] < a[3]
                if col_overlap and row_overlap:
                    issues.append("%s: OVERLAP %s and %s" % (label, a[4], b[4]))
        if parent_row_span is not None and max_end_row:
            if max_end_row - 1 > parent_row_span:
                issues.append("%s: container span=%d but children reach row %d (need >= %d)"
                              % (label, parent_row_span, max_end_row, max_end_row - 1))

    for page in root.findall("Page"):
        for c in page:
            if c.tag not in ("Container", "TabbedContainer", "Element"):
                continue
            if c.get("gridRow") and c.tag in ("Container", "TabbedContainer"):
                r0, r1 = [int(x.strip()) for x in c.get("gridRow").split("/")]
                walk(c, r1 - r0)
            elif c.tag == "TabbedContainer":
                walk(c, None)
    return issues


# ===========================================================================
# 1. Data-plumbing tables — parked on the hidden page-data page
# ===========================================================================

POP_NAME = "Cohort Population"
add({
    "id": "tbl-cohort-pop", "kind": "table", "name": POP_NAME, "visibleAsSource": True,
    "source": {"connectionId": CONN_ID, "kind": "sql", "statement": POP_SQL},
    "columns": [
        {"id": "p-id", "formula": "[Custom SQL/MEMBER_ID]", "name": "Member ID"},
        {"id": "p-group", "formula": "[Custom SQL/GROUP_NAME]", "name": "Group Name"},
        {"id": "p-tier", "formula": "[Custom SQL/COVERAGE_TIER]", "name": "Coverage Tier"},
        {"id": "p-age", "formula": "[Custom SQL/AGE_BAND]", "name": "Age Band"},
        {"id": "p-gender", "formula": "[Custom SQL/GENDER]", "name": "Gender"},
        {"id": "p-rel", "formula": "[Custom SQL/RELATIONSHIP]", "name": "Relationship"},
        {"id": "p-plan", "formula": "[Custom SQL/PLAN_NAME]", "name": "Plan"},
        {"id": "p-tenure", "formula": "[Custom SQL/TENURE_BAND]", "name": "Enrollment Tenure"},
        {"id": "p-pmpm", "formula": "[Custom SQL/PMPM_COST]", "name": "PMPM Cost", "format": FMT_DOLLAR},
    ],
    "order": ["p-id", "p-group", "p-tier", "p-age", "p-gender", "p-rel", "p-plan", "p-tenure", "p-pmpm"],
})

# Independent, UNFILTERED baseline copy — a separate element id, never
# targeted by any filter control — so KPI cards can show "book of business"
# alongside the live cohort. Only the 2 columns any baseline KPI needs.
add({
    "id": "tbl-cohort-baseline", "kind": "table", "name": "Cohort Population Baseline",
    "visibleAsSource": True,
    "source": {"connectionId": CONN_ID, "kind": "sql", "statement": POP_SQL},
    "columns": [
        {"id": "pb-id", "formula": "[Custom SQL/MEMBER_ID]", "name": "Member ID"},
        {"id": "pb-pmpm", "formula": "[Custom SQL/PMPM_COST]", "name": "PMPM Cost", "format": FMT_DOLLAR},
    ],
    "order": ["pb-id", "pb-pmpm"],
})

AGE_LABEL_VALUES = ",".join("('%s',%d)" % (b, i) for i, b in enumerate(AGE_BANDS))
add({
    "id": "tbl-cohort-age-labels", "kind": "table", "name": "Age Band Labels", "visibleAsSource": True,
    "source": {"connectionId": CONN_ID, "kind": "sql",
               "statement": "SELECT * FROM (VALUES\n    %s\n) AS t(LABEL, IDX)" % AGE_LABEL_VALUES},
    "columns": [
        {"id": "al-label", "formula": "[Custom SQL/LABEL]", "name": "Label"},
        {"id": "al-idx", "formula": "[Custom SQL/IDX]", "name": "Idx"},
    ],
    "order": ["al-label", "al-idx"],
})

# Cross-join (saved cohorts x age-band labels) + Switch unpivot — the
# "analyze a saved cohort" mechanic (skill non-negotiable #2).
add({
    "id": "tbl-cohort-age-cross", "kind": "table", "name": "Selected Cohort — Age Breakdown",
    "visibleAsSource": True,
    "source": {"kind": "join", "joins": [{
        "left": {"elementId": "input-cohort-saved", "kind": "table"},
        "right": {"elementId": "tbl-cohort-age-labels", "kind": "table"},
        "columns": [{"left": "1", "right": "1"}], "joinType": "left-outer",
    }], "primarySource": {"elementId": "input-cohort-saved", "kind": "table"}},
    "columns": [
        {"id": "cac-cohort", "formula": "[Saved Cohorts/Cohort Name]", "name": "Cohort Name"},
        {"id": "cac-label", "formula": "[Age Band Labels/Label]", "name": "Age Band"},
        {"id": "cac-count", "formula": ("Switch([Age Band Labels/Label]," +
            ",".join('"%s",[Saved Cohorts/Age %s Count]' % (b, b) for b in AGE_BANDS) + ")"),
         "name": "Members", "format": FMT_NUM0},
        {"id": "cac-label2", "formula": "[Age Band Labels/Label]", "name": "Age Band "},
    ],
    "order": ["cac-cohort", "cac-label", "cac-count", "cac-label2"],
})

DATA_PAGE_APPEND = "\n".join([
    el("tbl-cohort-pop", "1 / 13", "145 / 153"),
    el("tbl-cohort-baseline", "13 / 25", "145 / 153"),
    el("tbl-cohort-age-labels", "1 / 13", "153 / 161"),
    el("tbl-cohort-age-cross", "13 / 25", "153 / 161"),
])

# ===========================================================================
# 2. Header + context row (matches every other page's ctr-header-* pattern)
# ===========================================================================

add({"id": "txt-title-cohort", "kind": "text", "verticalAlign": "middle",
     "body": ("# <span style=\"color: #FFFFFF\">POPULATION BUILDER</span>\n\n"
              "<span style=\"color: #C9D6E3\">Segment Alliant's book of business into a named, "
              "saveable member cohort — ask the assistant or set filters directly</span>")})
add({"id": "txt-brand-cohort", "kind": "text", "verticalAlign": "middle",
     "body": "<p style=\"text-align: right\"><span style=\"font-size: 12px; color: %s\">ALLIANT</span></p>" % LOGO_TEAL})
add({"id": "img-logo2-cohort", "kind": "image", "source": {"kind": "url", "url": LOGO_URL}})

header_xml = container("ctr-header-cohort", "1 / 25", "1 / 6", [
    el("txt-title-cohort", "1 / 15", "1 / 6"),
    el("txt-brand-cohort", "15 / 22", "1 / 6"),
    el("img-logo2-cohort", "22 / 25", "1 / 6"),
], extra={"style": HEADER_STYLE})

add({"id": "txt-ctx-cohort", "kind": "text", "verticalAlign": "middle",
     "body": ("<span style=\"color: #FFFFFF\">**2,000 synthetic members** across "
              "**GEICO, FIS Global, and Contoso Logistics** &middot; "
              "filter by coverage tier, age band, gender, relationship, plan, "
              "tenure, and group, then save the cohort to compare it against others</span>")})
context_xml = container("ctr-context-cohort", "1 / 25", "6 / 9", [
    el("txt-ctx-cohort", "1 / 25", "1 / 3"),
], extra={"style": CONTEXT_STYLE})

# ===========================================================================
# 3. Filter + name/description controls (Tab 1)
# ===========================================================================

def list_ctrl(elid, control_id, name, col, selection_mode="multiple"):
    return add({
        "kind": "control", "id": elid, "controlId": control_id, "name": name,
        "controlType": "list", "mode": "include", "selectionMode": selection_mode,
        "values": [], "style": dict(CTRL_STYLE),
        "filters": [{"source": {"kind": "table", "elementId": "tbl-cohort-pop"}, "columnId": col}],
        "source": {"kind": "source", "source": {"kind": "table", "elementId": "tbl-cohort-pop"}, "columnId": col},
    })

ctrl_tier = list_ctrl("ctrl-cohort-tier", "CoverageTier", "Coverage Tier", "p-tier")
ctrl_age = list_ctrl("ctrl-cohort-age", "AgeBand", "Age Band", "p-age")
ctrl_gender = list_ctrl("ctrl-cohort-gender", "Gender", "Gender", "p-gender")
ctrl_rel = list_ctrl("ctrl-cohort-rel", "Relationship", "Relationship", "p-rel")
ctrl_plan = list_ctrl("ctrl-cohort-plan", "Plan", "Plan", "p-plan")
ctrl_tenure = list_ctrl("ctrl-cohort-tenure", "Tenure", "Enrollment Tenure", "p-tenure")
ctrl_group = list_ctrl("ctrl-cohort-group", "GroupName", "Group Name", "p-group")

add({"kind": "control", "id": "ctrl-cohort-name", "controlId": "CohortName", "name": "Cohort Name",
     "controlType": "text", "mode": "equals", "case": "insensitive",
     "includeNulls": "when-no-value-is-selected", "showOperators": False, "style": dict(CTRL_STYLE)})
add({"kind": "control", "id": "ctrl-cohort-desc", "controlId": "CohortDesc", "name": "Cohort Description",
     "controlType": "text-area", "mode": "equals", "case": "insensitive",
     "includeNulls": "when-no-value-is-selected", "showOperators": False, "style": dict(CTRL_STYLE)})

# ===========================================================================
# 4. Cohort detail table (Tab 1) — reactively filtered by every control above
# ===========================================================================

add({
    "id": "tbl-cohort-detail", "kind": "table", "source": {"elementId": "tbl-cohort-pop", "kind": "table"},
    "name": {"text": "Cohort Detail", "color": NAVY, "fontWeight": "bold", "fontSize": 14},
    "columns": [
        {"id": "cd-id", "formula": "[%s/Member ID]" % POP_NAME, "name": "Member ID"},
        {"id": "cd-group", "formula": "[%s/Group Name]" % POP_NAME, "name": "Group Name"},
        {"id": "cd-tier", "formula": "[%s/Coverage Tier]" % POP_NAME, "name": "Coverage Tier"},
        {"id": "cd-age", "formula": "[%s/Age Band]" % POP_NAME, "name": "Age Band"},
        {"id": "cd-gender", "formula": "[%s/Gender]" % POP_NAME, "name": "Gender"},
        {"id": "cd-rel", "formula": "[%s/Relationship]" % POP_NAME, "name": "Relationship"},
        {"id": "cd-plan", "formula": "[%s/Plan]" % POP_NAME, "name": "Plan"},
        {"id": "cd-tenure", "formula": "[%s/Enrollment Tenure]" % POP_NAME, "name": "Enrollment Tenure"},
        {"id": "cd-pmpm", "formula": "[%s/PMPM Cost]" % POP_NAME, "name": "PMPM Cost", "format": FMT_DOLLAR},
    ],
    "order": ["cd-id", "cd-group", "cd-tier", "cd-age", "cd-gender", "cd-rel", "cd-plan", "cd-tenure", "cd-pmpm"],
    "style": dict(CARD_STYLE),
})

# ===========================================================================
# 5. Saved cohorts — real insert-rows input table (append-only, wide snapshot)
# ===========================================================================

SAVED_NAME = "Saved Cohorts"
saved_cols = (
    [{"id": "s-name", "type": "text", "name": "Cohort Name"},
     {"id": "s-desc", "type": "text", "name": "Description"},
     {"id": "s-size", "type": "number", "name": "Size at Save Time"},
     {"id": "s-totcost", "type": "number", "name": "Total PMPM Cost"},
     {"id": "s-avgpmpm", "type": "number", "name": "Avg PMPM Cost"},
     {"id": "s-femalerate", "type": "number", "name": "Female Rate"}] +
    [{"id": "s-age%d" % i, "type": "number", "name": "Age %s Count" % b} for i, b in enumerate(AGE_BANDS)]
)
add({
    "id": "input-cohort-saved", "kind": "input-table", "name": SAVED_NAME,
    "source": {"kind": "empty", "connectionId": CONN_ID}, "inputMode": "view",
    "style": dict(CARD_STYLE), "columns": saved_cols,
})

SAVE_VALUES = {
    "s-name": {"type": "control", "control": "CohortName"},
    "s-desc": {"type": "control", "control": "CohortDesc"},
    "s-size": {"type": "formula", "formula": "CountDistinct([%s/Member ID])" % POP_NAME},
    "s-totcost": {"type": "formula", "formula": "Sum([%s/PMPM Cost])" % POP_NAME},
    "s-avgpmpm": {"type": "formula",
                  "formula": "Sum([%s/PMPM Cost])/CountDistinct([%s/Member ID])" % (POP_NAME, POP_NAME)},
    "s-femalerate": {"type": "formula",
                      "formula": ('CountDistinct(If([%s/Gender]="Female",[%s/Member ID],Null))'
                                  '/CountDistinct([%s/Member ID])') % (POP_NAME, POP_NAME, POP_NAME)},
}
for i, b in enumerate(AGE_BANDS):
    SAVE_VALUES["s-age%d" % i] = {
        "type": "formula",
        "formula": 'CountDistinct(If([%s/Age Band]="%s",[%s/Member ID],Null))' % (POP_NAME, b, POP_NAME),
    }

add({"id": "btn-cohort-save", "kind": "button", "text": "Save Cohort", "appearance": "filled",
     "actions": [{"id": "a-cohort-save", "trigger": "on-click", "effects": [
         {"effect": "insert-rows", "table": "input-cohort-saved", "values": SAVE_VALUES},
         {"effect": "set-control-value", "control": "CohortPick",
          "value": {"type": "control", "control": "CohortName"}},
     ]}]})
add({"id": "btn-cohort-reset", "kind": "button", "text": "Reset Filters", "appearance": "outline",
     "actions": [{"id": "a-cohort-reset", "trigger": "on-click", "effects": [
         {"effect": "clear-control", "scope": {"type": "page", "page": "page-cohort"},
          "usePublishedValue": True},
     ]}]})
add({"id": "txt-cohort-savenote", "kind": "text", "verticalAlign": "middle",
     "body": "<span style=\"color: %s\">Save inserts a real row into the Saved Cohorts log — "
             "never a UI-only Action Sequence.</span>" % GRAY})

# ===========================================================================
# 6. Agent — one tool per filter dimension + name/description + save
# ===========================================================================

def filter_tool(tool_id, name, desc, control, input_desc, selection_mode="add"):
    step = {"kind": "effect", "effect": "set-control-value", "control": control,
            "value": {"type": "agent-input", "inputName": input_desc}}
    if selection_mode:
        step["selectionMode"] = selection_mode
    return {"toolId": tool_id, "kind": "action", "name": name, "description": desc, "steps": [step]}

AGENT_TOOLS = [
    filter_tool("t-coh-tier", "Set coverage tier filter",
                "Filter the cohort to one or more coverage tiers (EE Only, +Spouse, +Child(ren), Family).",
                "CoverageTier", "Coverage tier(s) mentioned, e.g. 'Family' or 'EE Only'"),
    filter_tool("t-coh-age", "Set age band filter",
                "Filter the cohort to one or more age bands (<35, 36-49, 50-64, 65+).",
                "AgeBand", "Age band(s) mentioned, e.g. '50-64' or '65+'"),
    filter_tool("t-coh-gender", "Set gender filter",
                "Filter the cohort to one or more genders.",
                "Gender", "Gender(s) mentioned, e.g. 'Female'"),
    filter_tool("t-coh-rel", "Set relationship filter",
                "Filter the cohort to one or more relationship types (Employee, Spouse, Dependent).",
                "Relationship", "Relationship(s) mentioned, e.g. 'Employee'"),
    filter_tool("t-coh-plan", "Set plan filter",
                "Filter the cohort to one or more medical plans (Plan 1, Plan 2, Plan 3).",
                "Plan", "Plan(s) mentioned, e.g. 'Plan 2'"),
    filter_tool("t-coh-tenure", "Set enrollment tenure filter",
                "Filter the cohort to one or more tenure bands (New Enrollee, Established, Long-Tenured, Legacy Member).",
                "Tenure", "Tenure band(s) mentioned, e.g. 'New Enrollee'"),
    filter_tool("t-coh-group", "Set group name filter",
                "Filter the cohort to one or more employer groups (GEICO, FIS Global, Contoso Logistics).",
                "GroupName", "Group name(s) mentioned, e.g. 'GEICO'"),
    {"toolId": "t-coh-name", "kind": "action", "name": "Set cohort name & description",
     "description": "Set the cohort's name and description based on what the user is building.",
     "steps": [
         {"kind": "effect", "effect": "set-control-value", "control": "CohortName",
          "value": {"type": "agent-input", "inputName": "A short name for this cohort, based on the user's request"}},
         {"kind": "effect", "effect": "set-control-value", "control": "CohortDesc",
          "value": {"type": "agent-input", "inputName": "A one-sentence description of this cohort"}},
     ]},
    {"toolId": "t-coh-save", "kind": "action", "name": "Save the cohort",
     "description": ("When the user asks to save/persist/record the current cohort, insert it into the "
                      "Saved Cohorts log with its live size, PMPM cost, and demographic snapshot so it "
                      "can be compared against other saved cohorts."),
     "steps": [
         {"kind": "effect", "effect": "insert-rows", "table": "input-cohort-saved", "values": SAVE_VALUES},
         {"kind": "effect", "effect": "set-control-value", "control": "CohortPick",
          "value": {"type": "control", "control": "CohortName"}},
     ]},
]

AGENT = {
    "id": "ag-cohort-builder", "name": "Population Builder Assistant",
    "description": "Helps segment Alliant's member population into named, saveable cohorts.",
    "instructions": (
        "You are a benefits/population-segmentation assistant for Alliant's book of business "
        "(GEICO, FIS Global, and Contoso Logistics). Help an analyst build a member cohort by "
        "setting filters — coverage tier, age band, gender, relationship, plan, enrollment "
        "tenure, and group name — based on natural language. Never assume a constraint the user "
        "didn't specify; leave it unset. After each change, confirm the resulting cohort size and "
        "average PMPM cost, and compare it to the baseline (the full book of business) so the "
        "user can see how selective the cohort is. Proactively propose and set a short cohort "
        "name and description as soon as the first filter is applied or changed — keep them in "
        "sync with the current filters throughout the conversation; don't wait for the user to "
        "ask for a name. When the user asks to save, use the save tool."
    ),
    "greeting": {"mode": "static", "message": (
        "Describe the member population you want to segment — for example, "
        "\"female employees over 50 on Plan 2\" — and I'll set the filters and build the cohort."
    )},
    "dataSources": [{"kind": "table", "elementId": "tbl-cohort-pop"},
                     {"kind": "table", "elementId": "tbl-cohort-baseline"}],
    "tools": AGENT_TOOLS,
}

add({"id": "chat-cohort", "kind": "chat", "agentId": "ag-cohort-builder"})
chat_container_xml = container("ctr-cohort-chat", "18 / 25", "1 / 49", [
    el("txt-cohort-chathd", "1 / 13", "1 / 2"),
    el("chat-cohort", "1 / 13", "2 / 47"),
], cols=12, extra={"style": dict(CHAT_TINT_STYLE)})
add({"id": "txt-cohort-chathd", "kind": "text", "verticalAlign": "middle",
     "body": "**Ask the Population Builder Assistant**"})

# ===========================================================================
# 7. Tab 1 assembly — "Cohort Builder"
# ===========================================================================

tab1_children = [
    el("ctrl-cohort-name", "1 / 10", "1 / 4"),
    el("ctrl-cohort-desc", "10 / 18", "1 / 4"),
    el("ctrl-cohort-tier", "1 / 7", "4 / 7"),
    el("ctrl-cohort-age", "7 / 13", "4 / 7"),
    el("ctrl-cohort-gender", "13 / 18", "4 / 7"),
    el("ctrl-cohort-rel", "1 / 7", "7 / 10"),
    el("ctrl-cohort-plan", "7 / 13", "7 / 10"),
    el("ctrl-cohort-tenure", "13 / 18", "7 / 10"),
    el("ctrl-cohort-group", "1 / 7", "10 / 13"),
    el("tbl-cohort-detail", "1 / 18", "13 / 46"),
    el("btn-cohort-save", "1 / 6", "46 / 49"),
    el("btn-cohort-reset", "6 / 10", "46 / 49"),
    el("txt-cohort-savenote", "10 / 18", "46 / 49"),
]
# The agent chat panel is a bare Container (structurally necessary — header
# text above the chat surface), NOT wrapping a styled leaf card, so it is
# safe under the tabbed-container render-order gotcha (SKILL.md).
tab1_xml = "<Tab gridTemplateColumns=\"repeat(24, 1fr)\" gridTemplateRows=\"auto\">\n" + \
    "\n".join(tab1_children) + "\n" + chat_container_xml + "\n</Tab>"

# ===========================================================================
# 8. Tab 2 assembly — "Visualize"
# ===========================================================================

def kpi(id_, title, formula, source_elem, fmt, value_color=NAVY, title_color=NAVY):
    return add({
        "id": id_, "kind": "kpi-chart", "source": {"elementId": source_elem, "kind": "table"},
        "columns": [{"id": id_ + "-v", "formula": formula, "name": title, "format": fmt}],
        "value": {"columnId": id_ + "-v", "color": value_color, "fontSize": 24},
        "name": {"text": title, "color": title_color, "fontWeight": "bold", "fontSize": 12},
        "description": {"visibility": "hidden"},
        "style": dict(CARD_STYLE), "layout": {"anchor": "middle"},
    })

kpi("kpi-cohsize-c", "Cohort Size (Live)", "CountDistinct([%s/Member ID])" % POP_NAME,
    "tbl-cohort-pop", FMT_NUM0)
kpi("kpi-cohsize-b", "Book of Business (Baseline)", "CountDistinct([Cohort Population Baseline/Member ID])",
    "tbl-cohort-baseline", FMT_NUM0, value_color=GRAY, title_color=GRAY)
kpi("kpi-cohavg-c", "Avg PMPM Cost (Live)",
    "Sum([%s/PMPM Cost])/CountDistinct([%s/Member ID])" % (POP_NAME, POP_NAME),
    "tbl-cohort-pop", FMT_DOLLAR)
kpi("kpi-cohavg-b", "Avg PMPM Cost (Baseline)",
    "Sum([Cohort Population Baseline/PMPM Cost])/CountDistinct([Cohort Population Baseline/Member ID])",
    "tbl-cohort-baseline", FMT_DOLLAR, value_color=GRAY, title_color=GRAY)
kpi("kpi-cohtot-c", "Total PMPM Cost (Live)", "Sum([%s/PMPM Cost])" % POP_NAME,
    "tbl-cohort-pop", FMT_DOLLAR)
kpi("kpi-cohtot-b", "Total PMPM Cost (Baseline)", "Sum([Cohort Population Baseline/PMPM Cost])",
    "tbl-cohort-baseline", FMT_DOLLAR, value_color=GRAY, title_color=GRAY)

# PMPM cost distribution — bucketed histogram (bar-chart), single series,
# color:{by:"single"} confirmed live on this org (bar-tier-enroll).
add({
    "id": "bar-cohort-pmpmdist", "kind": "bar-chart", "source": {"elementId": "tbl-cohort-pop", "kind": "table"},
    "columns": [
        {"id": "pd-bucket", "formula": "Floor([%s/PMPM Cost]/150)*150" % POP_NAME,
         "name": "PMPM Bucket", "format": FMT_DOLLAR},
        {"id": "pd-cnt", "formula": "CountDistinct([%s/Member ID])" % POP_NAME, "name": "Members", "format": FMT_NUM0},
    ],
    "xAxis": {"columnId": "pd-bucket"}, "yAxis": {"columnIds": ["pd-cnt"]},
    "stacking": "none", "color": {"by": "single", "value": TEAL_DEEP},
    "legend": {"visibility": "hidden"},
    "name": {"text": "PMPM Cost Distribution — Current Cohort", "color": NAVY, "fontWeight": "bold", "fontSize": 13},
    "style": dict(CARD_STYLE),
})

# Demographic distribution — Age Band, matching the domain used elsewhere.
add({
    "id": "bar-cohort-agedist", "kind": "bar-chart", "source": {"elementId": "tbl-cohort-pop", "kind": "table"},
    "columns": [
        {"id": "ad-age", "formula": "[%s/Age Band]" % POP_NAME, "name": "Age Band"},
        {"id": "ad-cnt", "formula": "CountDistinct([%s/Member ID])" % POP_NAME, "name": "Members", "format": FMT_NUM0},
    ],
    "xAxis": {"columnId": "ad-age", "sort": {"by": "ad-cnt", "direction": "descending"}},
    "yAxis": {"columnIds": ["ad-cnt"]},
    "stacking": "none", "color": {"by": "single", "value": NAVY},
    "legend": {"visibility": "hidden"},
    "name": {"text": "Age Band Distribution — Current Cohort", "color": NAVY, "fontWeight": "bold", "fontSize": 13},
    "style": dict(CARD_STYLE),
})

# Top-N table — grouped + sorted (skill non-negotiable #5); plain-table
# sort/limit is silently dropped.
add({
    "id": "tbl-cohort-topn", "kind": "table", "source": {"elementId": "tbl-cohort-pop", "kind": "table"},
    "name": {"text": "Top Members by PMPM Cost — Current Cohort", "color": NAVY, "fontWeight": "bold", "fontSize": 13},
    "columns": [
        {"id": "tn-id", "formula": "[%s/Member ID]" % POP_NAME, "name": "Member ID"},
        {"id": "tn-group", "formula": "[%s/Group Name]" % POP_NAME, "name": "Group Name"},
        {"id": "tn-tier", "formula": "[%s/Coverage Tier]" % POP_NAME, "name": "Coverage Tier"},
        {"id": "tn-plan", "formula": "[%s/Plan]" % POP_NAME, "name": "Plan"},
        {"id": "tn-pmpm", "formula": "Sum([%s/PMPM Cost])" % POP_NAME, "name": "PMPM Cost", "format": FMT_DOLLAR},
    ],
    "order": ["tn-id", "tn-group", "tn-tier", "tn-plan", "tn-pmpm"],
    "groupings": [{"id": "g-cohort-topn", "groupBy": ["tn-id", "tn-group", "tn-tier", "tn-plan"],
                   "calculations": ["tn-pmpm"],
                   "sort": [{"columnId": "tn-pmpm", "direction": "descending"}]}],
    "style": dict(CARD_STYLE),
})

# --- Saved-cohort analysis: picker (NO filters — gotcha #3) + KPIs + Switch bar ---
add({
    "kind": "control", "id": "ctrl-cohort-pick", "controlId": "CohortPick",
    "name": "Select a saved cohort to analyze", "controlType": "list",
    "mode": "include", "selectionMode": "single", "values": [], "style": dict(CTRL_STYLE),
    "source": {"kind": "source", "source": {"kind": "table", "elementId": "input-cohort-saved"},
               "columnId": "s-name"},
})
add({"id": "txt-cohort-pickhint", "kind": "text", "verticalAlign": "middle",
     "body": "<span style=\"color: %s\">_Save a cohort on the Builder tab and it'll auto-select "
             "here — a freshly-deployed workbook shows blank until the first Save._</span>" % GRAY})

_SEL = '[Saved Cohorts/Cohort Name]=[CohortPick]'
add({
    "id": "kpi-coh-ak-size", "kind": "kpi-chart", "source": {"elementId": "input-cohort-saved", "kind": "table"},
    "columns": [{"id": "ak-size-v", "formula": "SumIf([Saved Cohorts/Size at Save Time],%s)" % _SEL,
                 "name": "SIZE", "format": FMT_NUM0}],
    "value": {"columnId": "ak-size-v", "color": NAVY, "fontSize": 24},
    "name": {"text": "SIZE", "color": NAVY, "fontWeight": "bold", "fontSize": 12},
    "description": {"visibility": "hidden"}, "style": dict(CARD_STYLE), "layout": {"anchor": "middle"},
})
add({
    "id": "kpi-coh-ak-tot", "kind": "kpi-chart", "source": {"elementId": "input-cohort-saved", "kind": "table"},
    "columns": [{"id": "ak-tot-v", "formula": "SumIf([Saved Cohorts/Total PMPM Cost],%s)" % _SEL,
                 "name": "TOTAL PMPM COST", "format": FMT_DOLLAR}],
    "value": {"columnId": "ak-tot-v", "color": TEAL_DEEP, "fontSize": 24},
    "name": {"text": "TOTAL PMPM COST", "color": NAVY, "fontWeight": "bold", "fontSize": 12},
    "description": {"visibility": "hidden"}, "style": dict(CARD_STYLE), "layout": {"anchor": "middle"},
})
# MaxIf, not AvgIf (not a real Sigma function, per SKILL.md) — exactly one
# row matches a given cohort name, so Max of that one value is correct.
add({
    "id": "kpi-coh-ak-avg", "kind": "kpi-chart", "source": {"elementId": "input-cohort-saved", "kind": "table"},
    "columns": [{"id": "ak-avg-v", "formula": "MaxIf([Saved Cohorts/Avg PMPM Cost],%s)" % _SEL,
                 "name": "AVG PMPM COST", "format": FMT_DOLLAR}],
    "value": {"columnId": "ak-avg-v", "color": GOLD, "fontSize": 24},
    "name": {"text": "AVG PMPM COST", "color": NAVY, "fontWeight": "bold", "fontSize": 12},
    "description": {"visibility": "hidden"}, "style": dict(CARD_STYLE), "layout": {"anchor": "middle"},
})
add({
    "id": "kpi-coh-ak-female", "kind": "kpi-chart", "source": {"elementId": "input-cohort-saved", "kind": "table"},
    "columns": [{"id": "ak-female-v", "formula": "MaxIf([Saved Cohorts/Female Rate],%s)" % _SEL,
                 "name": "FEMALE RATE", "format": FMT_PCT1}],
    "value": {"columnId": "ak-female-v", "color": TEAL_BRIGHT, "fontSize": 24},
    "name": {"text": "FEMALE RATE", "color": NAVY, "fontWeight": "bold", "fontSize": 12},
    "description": {"visibility": "hidden"}, "style": dict(CARD_STYLE), "layout": {"anchor": "middle"},
})

add({
    "id": "bar-cohort-age-analysis", "kind": "bar-chart",
    "source": {"elementId": "tbl-cohort-age-cross", "kind": "table"},
    "columns": [
        {"id": "aa-label", "formula": "[Selected Cohort — Age Breakdown/Age Band]", "name": "Age Band"},
        {"id": "aa-count", "formula": ("SumIf([Selected Cohort — Age Breakdown/Members],"
                                        "[Selected Cohort — Age Breakdown/Cohort Name]=[CohortPick])"),
         "name": "Members", "format": FMT_NUM0},
    ],
    "xAxis": {"columnId": "aa-label"}, "yAxis": {"columnIds": ["aa-count"]},
    "stacking": "none", "color": {"by": "single", "value": NAVY}, "legend": {"visibility": "hidden"},
    "name": {"text": "Age Breakdown — Selected Saved Cohort", "color": NAVY, "fontWeight": "bold", "fontSize": 13},
    "style": dict(CARD_STYLE),
})

# Formatted read view of every saved cohort + a comparison bar chart —
# unfiltered (no control involved), the "compare many saved cohorts" half.
add({
    "id": "tbl-cohort-saved-view", "kind": "table", "source": {"elementId": "input-cohort-saved", "kind": "table"},
    "name": {"text": "Saved Cohorts", "color": NAVY, "fontWeight": "bold", "fontSize": 13},
    "columns": [
        {"id": "sv-name", "formula": "[Saved Cohorts/Cohort Name]", "name": "Cohort Name"},
        {"id": "sv-desc", "formula": "[Saved Cohorts/Description]", "name": "Description"},
        {"id": "sv-size", "formula": "[Saved Cohorts/Size at Save Time]", "name": "Size", "format": FMT_NUM0},
        {"id": "sv-tot", "formula": "[Saved Cohorts/Total PMPM Cost]", "name": "Total PMPM Cost", "format": FMT_DOLLAR},
        {"id": "sv-avg", "formula": "[Saved Cohorts/Avg PMPM Cost]", "name": "Avg PMPM Cost", "format": FMT_DOLLAR},
        {"id": "sv-female", "formula": "[Saved Cohorts/Female Rate]", "name": "Female Rate", "format": FMT_PCT1},
    ],
    "order": ["sv-name", "sv-desc", "sv-size", "sv-tot", "sv-avg", "sv-female"],
    "style": dict(CARD_STYLE),
})
add({
    "id": "bar-cohort-saved-compare", "kind": "bar-chart",
    "source": {"elementId": "input-cohort-saved", "kind": "table"},
    "columns": [
        {"id": "sb-name", "formula": "[Saved Cohorts/Cohort Name]", "name": "Cohort Name"},
        {"id": "sb-tot", "formula": "Sum([Saved Cohorts/Total PMPM Cost])", "name": "Total PMPM Cost", "format": FMT_DOLLAR},
    ],
    "xAxis": {"columnId": "sb-name", "sort": {"by": "sb-tot", "direction": "descending"}},
    "yAxis": {"columnIds": ["sb-tot"]},
    "stacking": "none", "color": {"by": "single", "value": TEAL_DEEP}, "legend": {"visibility": "hidden"},
    "name": {"text": "Saved Cohorts Compared — Total PMPM Cost", "color": NAVY, "fontWeight": "bold", "fontSize": 13},
    "style": dict(CARD_STYLE),
})

tab2_children = [
    el("kpi-cohsize-c", "1 / 5", "1 / 7"), el("kpi-cohsize-b", "5 / 9", "1 / 7"),
    el("kpi-cohavg-c", "9 / 13", "1 / 7"), el("kpi-cohavg-b", "13 / 17", "1 / 7"),
    el("kpi-cohtot-c", "17 / 21", "1 / 7"), el("kpi-cohtot-b", "21 / 25", "1 / 7"),
    el("bar-cohort-pmpmdist", "1 / 25", "8 / 22"),
    el("bar-cohort-agedist", "1 / 25", "23 / 37"),
    el("tbl-cohort-topn", "1 / 25", "38 / 50"),
    el("txt-cohort-pickhint", "1 / 25", "51 / 53"),
    el("ctrl-cohort-pick", "1 / 13", "53 / 57"),
    el("kpi-coh-ak-size", "1 / 7", "58 / 65"), el("kpi-coh-ak-tot", "7 / 13", "58 / 65"),
    el("kpi-coh-ak-avg", "13 / 19", "58 / 65"), el("kpi-coh-ak-female", "19 / 25", "58 / 65"),
    el("bar-cohort-age-analysis", "1 / 25", "66 / 82"),
    el("tbl-cohort-saved-view", "1 / 25", "83 / 96"),
    el("bar-cohort-saved-compare", "1 / 25", "97 / 112"),
    el("input-cohort-saved", "1 / 25", "113 / 125"),
]
tab2_xml = "<Tab gridTemplateColumns=\"repeat(24, 1fr)\" gridTemplateRows=\"auto\">\n" + \
    "\n".join(tab2_children) + "\n</Tab>"

# ===========================================================================
# 9. Tabbed container + full page assembly
# ===========================================================================

add({"id": "tc-cohort", "kind": "tabbed-container",
     "tabs": [{"name": "Cohort Builder"}, {"name": "Visualize"}],
     "tabBar": {"alignment": "start"}})

tc_xml = ('<TabbedContainer elementId="tc-cohort" type="tabbed-container" gridColumn="1 / 25" gridRow="9 / 135">\n'
          + tab1_xml + "\n" + tab2_xml + "\n</TabbedContainer>")

page_cohort_xml = ('<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="page-cohort">\n'
                    + header_xml + "\n" + context_xml + "\n" + tc_xml + "\n</Page>")

print("page-cohort layout issues:", check_layout(page_cohort_xml, "page-cohort"))

# ===========================================================================
# 10. Splice into the full document — additive only
# ===========================================================================

old_layout = DOC["layout"]
m = re.search(r'<Page[^>]*id="page-data"[^>]*>.*?</Page>', old_layout, re.S)
old_data_block = m.group(0)
new_data_block = old_data_block.replace("</Page>", DATA_PAGE_APPEND + "\n</Page>")
assert new_data_block != old_data_block

final_layout = (old_layout.replace(old_data_block, new_data_block).rstrip()
                + "\n" + page_cohort_xml + "\n")

final_pages = list(DOC["pages"])
data_idx = next(i for i, p in enumerate(final_pages) if p["id"] == "page-data")
final_pages.insert(data_idx, {"id": "page-cohort", "name": "Population Builder"})

final_elements = DOC["elements"] + new_elements
final_agents = (DOC.get("agents") or []) + [AGENT]

final_doc = {
    "schemaVersion": DOC["schemaVersion"], "kind": DOC["kind"],
    "elements": final_elements, "pages": final_pages,
    "settings": DOC["settings"], "agents": final_agents, "layout": final_layout,
}
if DOC.get("overlays"):
    final_doc["overlays"] = DOC["overlays"]
final_spec = {"name": SRC["name"], "folderId": SRC["folderId"], "document": final_doc}

json.dump(final_spec, open("cohort_spec_new.json", "w"))
print("FINAL: %d elements (%d new), %d pages, %d agents" %
      (len(final_elements), len(new_elements), len(final_pages), len(final_agents)))

# ---------------------------------------------------------------------------
# Static QA — duplicate ids, placement, dangling refs (same discipline as
# build_alliant_pages.py)
# ---------------------------------------------------------------------------
ids = [e["id"] for e in final_elements]
dupes = [x for x in set(ids) if ids.count(x) > 1]
print("duplicate element ids:", dupes)
cids = [e.get("controlId") for e in final_elements if e.get("kind") == "control"]
cdupes = [x for x in set(cids) if cids.count(x) > 1]
print("duplicate controlIds:", cdupes)

placed = set(re.findall(r'elementId="([^"]+)"', final_layout))
all_ids = set(ids)
unplaced = all_ids - placed
print("unplaced elements:", unplaced)
placed_not_declared = placed - all_ids
print("layout refs to non-existent elements:", placed_not_declared)

full_issues = check_layout(final_layout.replace('<?xml version="1.0" encoding="utf-8"?>', ""), "FULL")
print("full-layout static issues:", full_issues)


def walk_refs(obj, found):
    if isinstance(obj, dict):
        if "elementId" in obj and isinstance(obj["elementId"], str):
            found.add(("elementId", obj["elementId"]))
        if "pageId" in obj and isinstance(obj["pageId"], str):
            found.add(("pageId", obj["pageId"]))
        if obj.get("type") == "page" and isinstance(obj.get("page"), str):
            found.add(("pageId", obj["page"]))
        for v in obj.values():
            walk_refs(v, found)
    elif isinstance(obj, list):
        for v in obj:
            walk_refs(v, found)


final_page_ids = {p["id"] for p in final_pages}
refs = set()
walk_refs(final_elements, refs)
walk_refs(final_agents, refs)
dangling_elem = [v for k, v in refs if k == "elementId" and v not in all_ids]
dangling_page = [v for k, v in refs if k == "pageId" and v not in final_page_ids]
print("dangling elementId refs:", dangling_elem)
print("dangling pageId refs:", dangling_page)

final_control_ids = {e["controlId"] for e in final_elements if e.get("kind") == "control"}
refs2 = set()


def walk_control_refs(obj, found):
    if isinstance(obj, dict):
        if "control" in obj and isinstance(obj["control"], str):
            found.add(obj["control"])
        if obj.get("scope", {}).get("type") == "control" and isinstance(obj["scope"].get("control"), str):
            found.add(obj["scope"]["control"])
        for v in obj.values():
            walk_control_refs(v, found)
    elif isinstance(obj, list):
        for v in obj:
            walk_control_refs(v, found)


walk_control_refs(final_elements, refs2)
walk_control_refs(final_agents, refs2)
dangling_controls = [c for c in refs2 if c not in final_control_ids]
print("dangling control refs:", dangling_controls)

any_issues = (dupes or cdupes or unplaced or placed_not_declared or full_issues
              or dangling_elem or dangling_page or dangling_controls)
if any_issues:
    print("\nSTATIC CHECKS FAILED — not pushing. Fix the above before --push.")
    sys.exit(1)

if "--push" in sys.argv:
    meta = S.get_workbook_meta(WORKBOOK_ID)
    if meta["latestVersion"] != SRC["documentVersion"]:
        print("Live workbook changed since this script's GET (latestVersion %s != %s) — "
              "refusing to push blind. Re-run the script to pick up the new baseline."
              % (meta["latestVersion"], SRC["documentVersion"]))
        sys.exit(1)
    S.update_workbook(WORKBOOK_ID, final_spec)
    new_meta = S.get_workbook_meta(WORKBOOK_ID)
    print("PUSHED. New latestVersion:", new_meta["latestVersion"])
else:
    print("\n(dry run — pass --push to actually update the live workbook)")
