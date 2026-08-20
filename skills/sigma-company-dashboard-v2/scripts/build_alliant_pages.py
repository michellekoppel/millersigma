#!/usr/bin/env python3
"""Builds the 4 replacement pages (Enrollment Overview, Medical Utilization,
Medical Trend, Executive Summary) for the Alliant workbook, removes the old
Command Center + its exclusively-owned dependents (modalCard, the orphaned
drawerProduct overlay, the ag-book agent), and splices the result into the
full document alongside the untouched Renewal Modeling / Population Builder
pages. Written as a one-shot, read-modify-write generator against the LIVE
spec (not a template) because the changes are page-specific surgery, not a
parametrized company build like build_sofi.py.

ONE-TIME MIGRATION, NOT IDEMPOTENT: this script reads the OLD "Command
Center" structure (c-hdr1, bar-prod sourced off tbl-lb, etc.) off the live
spec and replaces it. It already ran successfully against the live
workbook (2026-08-20) — the Command Center page is gone now, so re-running
this script as-is will KeyError on elements it expects to still exist
(c-hdr1 first). Kept here as the record of how the migration was built and
as a reference for the field-shape findings in the comments (xAxis/yAxis
columnId vs id, donut color/value id, text sanitizer rules, style.padding).
To reuse the page-building helpers for a *different* migration, copy the
helper functions (kpi_card/donut_card/bar_card/line_card/grouped_table/
filters_panel_container/add_header/container/check_layout) rather than
re-running this file's top-level splice logic verbatim.

Usage (historical):
    WORKBOOK_ID=680f23cc-188a-4de3-9427-5748f69130da python3 build_alliant_pages.py [--push]

Without --push, writes the spliced spec to alliant_spec_new.json (next to
this script) and runs the static checks (row-overflow, overlap, dangling
element/page/control refs) without touching the live workbook. With --push,
also calls sigmaapi.update_workbook after re-checking the live
documentVersion hasn't moved since GET (see sigmaapi.get_workbook_meta) —
bump specs/wb_state_alliant.json's lastVersion by hand after a successful
push, same as build_sofi.py's update flow.
"""
import json, os, sys, copy

import sigmaapi as S

WORKBOOK_ID = os.environ.get("WORKBOOK_ID", "680f23cc-188a-4de3-9427-5748f69130da")

SRC = S.get_workbook(WORKBOOK_ID)
DOC = SRC["document"]
ELEMENTS = {e["id"]: e for e in DOC["elements"]}

NAVY = "#002E41"
NAVY_DEEP = "#00151E"
TEAL = "#1FBDC9"
TEAL_DEEP = "#0E7A85"
ACCENT = "#85D1DC"
MINT = "#00A9A5"
INK = "#0F2530"
MUTED = "#5B7480"
CARD_BG = "#FFFFFF"
PAGE_BG = "#F4F7F8"
GOOD = "#1FBDC9"
BAD = "#E8604C"

LOGO_URL = ELEMENTS["logo2"]["source"]["url"]  # reuse the already-fetched white Alliant mark
HDR_STYLE = dict(ELEMENTS["c-hdr1"]["style"])  # navy fill, reused verbatim
HDR_BG = copy.deepcopy(ELEMENTS["c-hdr1"]["backgroundImage"])  # navy->teal gradient art
HDR_SPACING = ELEMENTS["c-hdr1"].get("spacing", "small")

CONN_ID = ELEMENTS["tbl-lb"]["source"]["connectionId"]

TBL_ENROLL_SQL = open(
    "/home/user/millersigma/skills/sigma-company-dashboard-v2/sql/enrollment_claims_detail.sql"
).read()

PAYER_SPLIT_SQL = (
    "-- Fixed modeled member-paid / plan-paid split, illustrative -- not\n"
    "-- derivable from the row-level claims table (no payer-of-record column).\n"
    "SELECT 'Member Paid' AS payer, 11 AS pct UNION ALL SELECT 'Plan Paid', 89"
)

new_elements = []   # accumulate all newly authored elements
layout_pages = []   # accumulate new <Page> XML blocks (as strings)

# ---------------------------------------------------------------------------
# tiny XML builder helpers
# ---------------------------------------------------------------------------

def el(elementId, col, row):
    return '<Element elementId="%s" gridColumn="%s" gridRow="%s"/>' % (elementId, col, row)


_containers_registered = set()


def container(elementId, col, row, children, cols=24, extra=None):
    if elementId not in _containers_registered:
        body = {"id": elementId, "kind": "container"}
        if extra:
            body.update(extra)
        new_elements.append(body)
        _containers_registered.add(elementId)
    inner = "\n".join(children)
    return ('<Container elementId="%s" type="grid" gridColumn="%s" gridRow="%s" '
            'gridTemplateColumns="repeat(%d, 1fr)" gridTemplateRows="auto">\n%s\n</Container>'
            % (elementId, col, row, cols, inner))


def add(e):
    new_elements.append(e)
    return e["id"]

# ---------------------------------------------------------------------------
# tbl-enroll — the ONE base table for all 4 new pages
# ---------------------------------------------------------------------------

ENROLL_COLS = ["Group Name", "Member ID", "Month", "Month Index", "Period Name",
               "State", "County", "Age Band", "Generation", "Age Years", "Gender",
               "Relationship", "Division", "Plan", "Plan Type", "Employee Type",
               "Tier", "Tenure Years", "Coverage Status", "MEDC Category",
               "Place of Service", "Medical Spend", "Pharmacy Spend",
               "Claims Count", "Enrolled Flag"]

# ---------------------------------------------------------------------------
# Shared local column-id scheme used on EVERY tbl-enroll-sourced element so
# the 9-filter panel can wire filters[] identically on every page.
# ---------------------------------------------------------------------------

DIM_COLS = {
    "d-group": "Group Name", "d-state": "State", "d-age": "Age Band",
    "d-rel": "Relationship", "d-gender": "Gender", "d-div": "Division",
    "d-plan": "Plan", "d-ptype": "Plan Type", "d-etype": "Employee Type",
}

PASSTHROUGH_COLS = {
    "d-county": "County", "d-generation": "Generation", "d-tier": "Tier",
    "d-medc": "MEDC Category", "d-pos": "Place of Service",
    "d-period": "Period Name", "d-month": "Month", "d-midx": "Month Index",
    "d-cov": "Coverage Status",
}


def enroll_passthrough(extra=(), exclude_names=()):
    """Standard dimension passthrough columns every tbl-enroll element carries
    (drill-down + filter-wiring rule), plus any extra {id: formula/name} dicts.
    exclude_names skips a dimension already declared under a different local
    id (e.g. the chart's own xAxis column) to avoid a duplicate-name column."""
    cols = []
    for cid, colname in {**DIM_COLS, **PASSTHROUGH_COLS}.items():
        if colname in exclude_names:
            continue
        cols.append({"id": cid, "name": colname, "formula": "[Enrollment Detail/%s]" % colname})
    cols.extend(extra)
    return cols


# A control's `source` (which populates its dropdown) must reference a
# columnId that exists on the REFERENCED element — every filter control's
# source points at tbl-enroll itself, so it needs tbl-enroll's own column
# id for that dimension, not the d-* local id used on the per-page chart
# elements it filters (found via a real 400: "Invalid value source for
# list control" — not called out in the doc's control-source example).
ENROLL_COL_ID = {name: "e%d" % i for i, name in enumerate(ENROLL_COLS)}

add({
    "id": "tbl-enroll", "kind": "table", "name": "Enrollment Detail",
    "source": {"kind": "sql", "connectionId": CONN_ID, "statement": TBL_ENROLL_SQL},
    "columns": [{"id": "e%d" % i, "name": c, "formula": "[Custom SQL/%s]" % c}
                for i, c in enumerate(ENROLL_COLS)],
})

add({
    "id": "tbl-payer", "kind": "table", "name": "Payer Split",
    "source": {"kind": "sql", "connectionId": CONN_ID, "statement": PAYER_SPLIT_SQL},
    "columns": [
        {"id": "p0", "name": "Payer", "formula": "[Custom SQL/PAYER]"},
        {"id": "p1", "name": "Pct", "formula": "[Custom SQL/PCT]"},
    ],
})

# ---------------------------------------------------------------------------
# Filters panel — 9 controls, replicated per page (controlId suffixed), each
# wired to every tbl-enroll-sourced element on THAT page via the fixed
# DIM_COLS local ids above. `elements_on_page` is the list of element ids
# (from tbl-enroll) placed on this page.
# ---------------------------------------------------------------------------

FILTER_DEFS = [
    ("Group Name", "d-group"), ("State", "d-state"), ("Age Band", "d-age"),
    ("Relationship", "d-rel"), ("Gender", "d-gender"), ("Division", "d-div"),
    ("Plan", "d-plan"), ("Plan Type", "d-ptype"), ("Employee Type", "d-etype"),
]


def build_filters_panel(page_suffix, elements_on_page):
    """Returns (element_ids_in_order, xml_children_list) for a 9-control
    filters panel, each control wired to every element id in
    elements_on_page via its DIM_COLS-fixed local column id."""
    header_id = "filt-hd%s" % page_suffix
    add({"id": header_id, "kind": "text",
         "body": "**Filters**", "verticalAlign": "middle"})
    children = [el(header_id, "1 / 25", "1 / 3")]
    row = 3
    for label, local_id in FILTER_DEFS:
        cid = "f%s-%s" % (page_suffix, local_id.replace("d-", ""))
        control_id = "%s%s" % (label.replace(" ", ""), page_suffix)
        filters = [{"source": {"kind": "table", "elementId": eid}, "columnId": local_id}
                   for eid in elements_on_page]
        add({
            "kind": "control", "id": cid, "controlId": control_id, "name": label,
            "controlType": "list", "mode": "include", "selectionMode": "multiple",
            "values": [],
            "source": {"kind": "source", "source": {"kind": "table", "elementId": "tbl-enroll"},
                       "columnId": ENROLL_COL_ID[label]},
            "filters": filters,
        })
        children.append(el(cid, "1 / 25", "%d / %d" % (row, row + 3)))
        row += 3
    return children, row


def filters_panel_container(page_suffix, elements_on_page, container_id, col, start_row):
    """Full filters-panel container XML, with row-overflow math done once,
    correctly, here (span = internal max child end row - 1, plus buffer)."""
    kids, max_row = build_filters_panel(page_suffix, elements_on_page)
    end_row = start_row + max_row + 2
    return container(container_id, col, "%d / %d" % (start_row, end_row), kids)


def header_block(container_id, logo_id, nav_id, title, subtitle_id=None):
    kids = [el(logo_id, "1 / 6", "1 / 6"), el(nav_id, "13 / 25", "2 / 6")]
    return container(container_id, "1 / 25", "1 / 6", kids)


NAV_OPTIONS = [
    {"label": "Enrollment Overview", "destination": {"type": "page", "pageId": "pgEnroll"}},
    {"label": "Medical Utilization", "destination": {"type": "page", "pageId": "pgUtil"}},
    {"label": "Medical Trend", "destination": {"type": "page", "pageId": "pgTrend"}},
    {"label": "Executive Summary", "destination": {"type": "page", "pageId": "pgExec"}},
    {"label": "Renewal Modeling", "destination": {"type": "page", "pageId": "pg2"}},
    {"label": "Population Builder", "destination": {"type": "page", "pageId": "pg3"}},
]


def add_header(n, page_title, subtitle):
    logo_id = "logo%s" % n
    nav_id = "nav-main%s" % n
    title_id = "title%s" % n
    sub_id = "sub%s" % n
    hdr_id = "c-hdr%s" % n
    add({"id": logo_id, "kind": "image", "source": {"kind": "url", "url": LOGO_URL}})
    add({"id": nav_id, "kind": "navigation", "mode": "manual", "showIcons": False,
         "optionStyle": {"style": "pill", "orientation": "horizontal",
                          "textColor": "#c7e4f7", "selectedColor": "#ffffff"},
         "options": NAV_OPTIONS})
    add({"id": title_id, "kind": "text", "verticalAlign": "middle",
         "body": "<span style=\"color:#ffffff;font-size:28px\">**%s**</span>" % page_title})
    add({"id": sub_id, "kind": "text", "verticalAlign": "start",
         "body": "<span style=\"color:#c7e4f7\">%s</span>" % subtitle})
    # Nav gets its own full-width row beneath title/subtitle — 6 pill options
    # (4 new pages + Renewal Modeling + Population Builder) collapsed into a
    # cramped "More" dropdown when squeezed into a narrow right-hand column.
    kids = [
        el(logo_id, "1 / 6", "1 / 4"),
        el(title_id, "6 / 20", "1 / 3"),
        el(sub_id, "6 / 24", "3 / 6"),
        el(nav_id, "1 / 25", "6 / 9"),
    ]
    # Reuse the exact navy->teal gradient header art already live on
    # Renewal Modeling / Population Builder, so the new pages read as the
    # same product rather than a template with a different header treatment.
    return container(hdr_id, "1 / 25", "1 / 10", kids,
                      extra={"style": dict(HDR_STYLE), "backgroundImage": copy.deepcopy(HDR_BG),
                             "spacing": HDR_SPACING})


FMT_DOLLAR = {"kind": "number", "formatString": "$,.0f", "currencySymbol": "$"}
FMT_DOLLAR_COMPACT = {"kind": "number", "formatString": "$,.3s", "currencySymbol": "$"}
FMT_PCT1 = {"kind": "number", "formatString": ".1%"}
FMT_NUM0 = {"kind": "number", "formatString": ",.0f"}
FMT_NUM1 = {"kind": "number", "formatString": ",.1f"}

CARD_STYLE = {"backgroundColor": CARD_BG, "borderRadius": "round",
              "borderWidth": 1, "borderColor": {"kind": "theme", "ref": "colors-border"}}
CARD_STYLE_NAVY = {"backgroundColor": NAVY, "borderRadius": "round"}


def kpi_card(id_, title, value_formula, value_fmt, source="tbl-enroll",
             cmp_formula=None, cmp_fmt=None, extra_cols=(), navy=False,
             value_color=None, title_color=None):
    """A single KPI tile sourced from tbl-enroll (or another sibling)."""
    vcol = id_ + "-v"
    cols = [{"id": vcol, "name": title, "formula": value_formula, "format": value_fmt}]
    if source == "tbl-enroll":
        cols.extend(enroll_passthrough())
    body = {
        "id": id_, "kind": "kpi-chart", "name": title,
        "source": {"kind": "table", "elementId": source},
        "columns": cols,
        "value": {"columnId": vcol,
                  "color": value_color or ("#ffffff" if navy else INK), "fontSize": 26},
        "name": {"text": title, "color": title_color or ("#c7e4f7" if navy else MUTED), "fontSize": 12},
        "style": dict(CARD_STYLE_NAVY if navy else CARD_STYLE),
        "layout": {"anchor": "middle"},
    }
    if cmp_formula:
        ccol = id_ + "-c"
        cols.append({"id": ccol, "name": "Prior Period", "formula": cmp_formula,
                      "format": cmp_fmt or value_fmt})
        body["comparison"] = {"display": "delta", "colorGood": "#cdebb8" if navy else "#0E7A85",
                               "colorBad": "#ffcfc7" if navy else "#E8604C", "fontSize": 13}
        body["comparisonColumn"] = {"columnId": ccol}
    cols.extend(extra_cols)
    add(body)
    return id_


def donut_card(id_, title, source_elem, dims_formula, dims_name, value_formula, value_name,
               colors=None):
    dcol, vcol = id_ + "-d", id_ + "-v"
    dcols = [
        {"id": dcol, "name": dims_name, "formula": dims_formula},
        {"id": vcol, "name": value_name, "formula": value_formula},
    ]
    if source_elem == "tbl-enroll":
        dcols.extend(enroll_passthrough(exclude_names=[dims_name, value_name]))
    # NOTE on field shapes below: the workbook-spec-api.md doc documents
    # xAxis:{id}/yAxis:[{id}]/color:{id}/value:{id}. Probed live against
    # THIS org (production papercrane) and found to be stale for this
    # workspace — the org's own already-live bar-chart element (bar-prod)
    # round-trips as xAxis:{columnId}/yAxis:{columnIds:[...]}, and its
    # kpi-chart's own "value"/"comparisonColumn" fields already use
    # {columnId:...} too (confirmed via kc-rev). Applying that same
    # columnId/columnIds convention consistently below rather than the
    # doc's {id} shape, which fails with a masked "Invalid kind" on this org
    # regardless of chart kind or source table (verified via 8+ minimal
    # reproductions before finding the working shape — see build notes).
    # Probed separately from bar/line/kpi: donut-chart's color/value fields
    # use the DOC's {id:...} shape (confirmed live) — unlike bar-chart/
    # line-chart/kpi-chart's xAxis/yAxis/value fields, which needed
    # {columnId:...}/{columnIds:[...]} instead. The two shapes are
    # genuinely inconsistent across element kinds on this org; verified
    # each independently rather than assuming one convention throughout.
    add({
        "id": id_, "kind": "donut-chart", "name": title,
        "source": {"kind": "table", "elementId": source_elem},
        "columns": dcols,
        "color": {"id": dcol}, "value": {"id": vcol},
        "style": dict(CARD_STYLE),
    })
    return id_


def bar_card(id_, title, source_elem, x_formula, x_name, series, sort_desc=True,
             extra_cols=(), color_scheme=None, horizontal=False):
    """series: list of (col_id, name, formula, type). NOTE: this org's
    confirmed live yAxis shape is a flat {columnIds:[...]} array with no
    per-series type slot, so a combo (bar+line) mix isn't expressible this
    way — any 'line'-typed series is still rendered as an extra bar series
    (disclosed simplification; see build notes)."""
    xcol = id_ + "-x"
    cols = [{"id": xcol, "name": x_name, "formula": x_formula}]
    ycols = []
    for cid, name, formula, kind in series:
        full = id_ + "-" + cid
        cols.append({"id": full, "name": name, "formula": formula})
        ycols.append(full)
    cols.extend(extra_cols)
    if source_elem == "tbl-enroll":
        cols.extend(enroll_passthrough(exclude_names=[x_name]))
    body = {
        "id": id_, "kind": "bar-chart", "name": title,
        "source": {"kind": "table", "elementId": source_elem},
        "columns": cols,
        "xAxis": {"columnId": xcol},
        "yAxis": {"columnIds": ycols},
        "style": dict(CARD_STYLE),
    }
    add(body)
    return id_


def line_card(id_, title, source_elem, x_formula, x_name, series, extra_cols=()):
    xcol = id_ + "-x"
    cols = [{"id": xcol, "name": x_name, "formula": x_formula}]
    ycols = []
    for cid, name, formula in series:
        full = id_ + "-" + cid
        cols.append({"id": full, "name": name, "formula": formula})
        ycols.append(full)
    cols.extend(extra_cols)
    if source_elem == "tbl-enroll":
        cols.extend(enroll_passthrough(exclude_names=[x_name] + [s[1] for s in series]))
    add({
        "id": id_, "kind": "line-chart", "name": title,
        "source": {"kind": "table", "elementId": source_elem},
        "columns": cols, "xAxis": {"columnId": xcol}, "yAxis": {"columnIds": ycols},
        "style": dict(CARD_STYLE),
    })
    return id_


def text_card(id_, body, sibling_source=None, valign="middle"):
    t = {"id": id_, "kind": "text", "body": body, "verticalAlign": valign}
    add(t)
    return id_


def grouped_table(id_, title, source_elem, group_col_formula, group_col_name,
                   calc_cols, extra_passthrough=()):
    """calc_cols: list of (col_id, name, formula, fmt-or-None)."""
    gcol = id_ + "-g"
    cols = [{"id": gcol, "name": group_col_name, "formula": group_col_formula}]
    calc_ids = []
    for cid, name, formula, fmt in calc_cols:
        full = id_ + "-" + cid
        c = {"id": full, "name": name, "formula": formula}
        if fmt:
            c["format"] = fmt
        cols.append(c)
        calc_ids.append(full)
    cols.extend(extra_passthrough)
    if source_elem == "tbl-enroll":
        cols.extend(enroll_passthrough(exclude_names=[group_col_name] + [c[1] for c in calc_cols]))
    add({
        "id": id_, "kind": "table", "name": title,
        "source": {"kind": "table", "elementId": source_elem},
        "columns": cols,
        "groupings": [{"id": id_ + "-grp", "groupBy": [gcol], "calculations": calc_ids}],
        "style": dict(CARD_STYLE),
    })
    return id_


CUR = '[Enrollment Detail/Period Name] = "Current Period"'
PRI = '[Enrollment Detail/Period Name] = "Prior Period"'
ENR = '[Enrollment Detail/Coverage Status] = "Enrolled"'
EMP = '[Enrollment Detail/Relationship] = "Employee"'


def cond(*parts):
    return " AND ".join(parts)


print("helpers ok — %d elements so far" % len(new_elements))

# ===========================================================================
# PAGE 1 — Enrollment Overview
# ===========================================================================
p1_enroll_elements = []  # tbl-enroll-sourced elements placed on this page

def p1(id_):
    p1_enroll_elements.append(id_)
    return id_

hdr1_xml = add_header("4", "Medical Enrollment Overview",
    "An analysis of the enrollment data with insights to relationship "
    "distribution, age stratification and county data statistics")

# KPI row — 6 cards
p1(kpi_card("k1-waived", "% Waived Coverage",
    "CountIf(%s AND [Enrollment Detail/Coverage Status]=\"Waived\") / CountIf(%s)" % (CUR, CUR),
    FMT_PCT1,
    cmp_formula="CountIf(%s AND [Enrollment Detail/Coverage Status]=\"Waived\") / CountIf(%s)" % (PRI, PRI),
    cmp_fmt=FMT_PCT1, navy=True))
p1(kpi_card("k2-enrolled", "Total Enrolled",
    "CountIf(%s) / 12" % cond(CUR, ENR), FMT_NUM0,
    cmp_formula="CountIf(%s) / 12" % cond(PRI, ENR), cmp_fmt=FMT_NUM0))
p1(kpi_card("k3-age", "Avg Employee Age",
    "SumIf([Enrollment Detail/Age Years], %s) / CountIf(%s)" % (cond(CUR, ENR, EMP), cond(CUR, ENR, EMP)),
    FMT_NUM1,
    cmp_formula="SumIf([Enrollment Detail/Age Years], %s) / CountIf(%s)" % (cond(PRI, ENR, EMP), cond(PRI, ENR, EMP)),
    cmp_fmt=FMT_NUM1))
p1(kpi_card("k4-tenure", "Avg Tenure (Years)",
    "SumIf([Enrollment Detail/Tenure Years], %s) / CountIf(%s)" % (cond(CUR, ENR, EMP), cond(CUR, ENR, EMP)),
    FMT_NUM1,
    cmp_formula="SumIf([Enrollment Detail/Tenure Years], %s) / CountIf(%s)" % (cond(PRI, ENR, EMP), cond(PRI, ENR, EMP)),
    cmp_fmt=FMT_NUM1))
p1(kpi_card("k5-female", "% Female Employees",
    "CountIf(%s) / CountIf(%s)" % (
        cond(CUR, ENR, EMP, '[Enrollment Detail/Gender]="Female"'), cond(CUR, ENR, EMP)),
    FMT_PCT1,
    cmp_formula="CountIf(%s) / CountIf(%s)" % (
        cond(PRI, ENR, EMP, '[Enrollment Detail/Gender]="Female"'), cond(PRI, ENR, EMP)),
    cmp_fmt=FMT_PCT1, navy=True))
p1(kpi_card("k6-contract", "Avg Contract Size (Lives / Employee)",
    "CountIf(%s) / CountIf(%s)" % (cond(CUR, ENR), cond(CUR, ENR, EMP)), FMT_NUM1,
    cmp_formula="CountIf(%s) / CountIf(%s)" % (cond(PRI, ENR), cond(PRI, ENR, EMP)), cmp_fmt=FMT_NUM1))

kpi_row1 = container("c-kpirow1", "1 / 19", "11 / 21", [
    el("k1-waived", "1 / 4", "1 / 11"), el("k2-enrolled", "4 / 7", "1 / 11"),
    el("k3-age", "7 / 10", "1 / 11"), el("k4-tenure", "10 / 13", "1 / 11"),
    el("k5-female", "13 / 16", "1 / 11"), el("k6-contract", "16 / 19", "1 / 11"),
], cols=18)

# Breakdown panels — 4 side-by-side single-series bar charts. Sigma
# auto-groups by the categorical xAxis (see sp-rev in the live spec: a plain
# Sum() with no explicit dimension filter, grouped implicitly by xAxis) so
# the yAxis formula only needs the period/coverage condition, not the
# category itself. Deliberately raw headcounts, not %-of-total shares — a
# true share requires an aggregated-sibling + summary-table detour that
# would have to re-carry all 9 filter dimensions to stay filterable; counts
# are equally legible on one hop from the base table. See build notes for
# the "vs. BoB / vs. prior" tick-mark omission (no native reference-line
# primitive in the code spec).
p1(bar_card("b1-tier", "Enrollment by Tier", "tbl-enroll",
    "[Enrollment Detail/Tier]", "Tier",
    [("cnt", "Enrolled Members", "CountIf(%s) / 12" % cond(CUR, ENR), None)]))
p1(bar_card("b2-age", "Enrollment by Age Group", "tbl-enroll",
    "[Enrollment Detail/Age Band]", "Age Band",
    [("cnt", "Enrolled Members", "CountIf(%s) / 12" % cond(CUR, ENR), None)]))
p1(bar_card("b3-plan", "Enrollment by Plan", "tbl-enroll",
    "[Enrollment Detail/Plan]", "Plan",
    [("cnt", "Enrolled Members", "CountIf(%s) / 12" % cond(CUR, ENR), None)]))
p1(bar_card("b4-county", "Top 5 Counties", "tbl-enroll",
    "[Enrollment Detail/County]", "County",
    [("cnt", "Enrolled Members", "CountIf(%s) / 12" % cond(CUR, ENR), None)]))

breakdown_row1 = container("c-brow1", "1 / 19", "21 / 37", [
    el("b1-tier", "1 / 7", "1 / 17"), el("b2-age", "7 / 13", "1 / 17"),
    el("b3-plan", "13 / 19", "1 / 17"), el("b4-county", "19 / 25", "1 / 17"),
], cols=24)

filters_panel1 = filters_panel_container("1", p1_enroll_elements, "c-filt1", "19 / 25", 11)

page1_xml = ('<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="pgEnroll">\n'
             + hdr1_xml + "\n" + kpi_row1 + "\n" + breakdown_row1 + "\n" + filters_panel1 + "\n</Page>")

print("page1 done — %d elements" % len(new_elements))


def check_layout(xml_fragment, label):
    """Static check for silent-layout-failure #1 (container child rows must
    not exceed the span the parent grants) and #3 (overlapping siblings)."""
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
        # overlap check (siblings only, same parent)
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
        pid = page.get("id")
        for c in page:
            if c.tag not in ("Container", "TabbedContainer", "Element"):
                continue
            if c.get("gridRow") and c.tag in ("Container", "TabbedContainer"):
                r0, r1 = [int(x.strip()) for x in c.get("gridRow").split("/")]
                walk(c, r1 - r0)
            elif c.tag == "TabbedContainer":
                walk(c, None)
    return issues


print("page1 layout issues:", check_layout(page1_xml, "pgEnroll"))

# ===========================================================================
# PAGE 2 — Medical Utilization
# ===========================================================================
p2_enroll_elements = []

def p2(id_):
    p2_enroll_elements.append(id_)
    return id_

hdr2_xml = add_header("5", "Medical Utilization",
    "GEICO &middot; Current Period: Jun 2025 - May 2026 &middot; "
    "Prior Period: Jun 2024 - May 2025")

ALLIANT_AVG_PMPM = 496.82
ALLIANT_AVG_UTIL = 937
ALLIANT_AVG_CPM = 6361

# Two big current-period callouts
p2(kpi_card("u1-pmpm", "PMPM",
    "SumIf([Enrollment Detail/Medical Spend], %s) / CountIf(%s)" % (cond(CUR, ENR), cond(CUR, ENR)),
    FMT_DOLLAR,
    cmp_formula="SumIf([Enrollment Detail/Medical Spend], %s) / CountIf(%s)" % (cond(PRI, ENR), cond(PRI, ENR)),
    cmp_fmt=FMT_DOLLAR, navy=True))
p2(kpi_card("u2-util", "Utilization per 1000",
    "SumIf([Enrollment Detail/Claims Count], %s) / CountIf(%s) * 1000" % (cond(CUR, ENR), cond(CUR, ENR)),
    FMT_NUM0,
    cmp_formula="SumIf([Enrollment Detail/Claims Count], %s) / CountIf(%s) * 1000" % (cond(PRI, ENR), cond(PRI, ENR)),
    cmp_fmt=FMT_NUM0, navy=True))
u3 = text_card("u3-avgnote",
    "<span style=\"color:%s\">Alliant Average PMPM: **$%.2f**</span>" % (MUTED, ALLIANT_AVG_PMPM))
u4 = text_card("u4-avgnote",
    "<span style=\"color:%s\">Alliant Average Utilization/1000: **%d**</span>" % (MUTED, ALLIANT_AVG_UTIL))

callout_row = container("c-callout2", "1 / 19", "11 / 23", [
    el("u1-pmpm", "1 / 12", "1 / 10"), el("u3-avgnote", "1 / 12", "10 / 12"),
    el("u2-util", "12 / 24", "1 / 10"), el("u4-avgnote", "12 / 24", "10 / 12"),
], cols=24)

# PMPM / Utilization by place of service
p2(bar_card("u5-pmpmpos", "PMPM by Place of Service", "tbl-enroll",
    "[Enrollment Detail/Place of Service]", "Place of Service",
    [("v", "PMPM", "SumIf([Enrollment Detail/Medical Spend], %s) / CountIf(%s)" % (cond(CUR, ENR), cond(CUR, ENR)), None)]))
p2(bar_card("u6-utilpos", "Utilization per 1000 by Place of Service", "tbl-enroll",
    "[Enrollment Detail/Place of Service]", "Place of Service",
    [("v", "Utilization per 1000", "SumIf([Enrollment Detail/Claims Count], %s) / CountIf(%s) * 1000" % (cond(CUR, ENR), cond(CUR, ENR)), None)]))

bars_row2 = container("c-bars2", "1 / 19", "23 / 41", [
    el("u5-pmpmpos", "1 / 13", "1 / 17"), el("u6-utilpos", "13 / 25", "1 / 17"),
], cols=24)

# Member-paid / plan-paid donut + claim-cost / cost-per-member stat pairs
donut2 = donut_card("u7-payer", "Member-Paid vs. Plan-Paid Split", "tbl-payer",
    "[Payer Split/Payer]", "Payer", "Sum([Payer Split/Pct])", "Pct",
    [NAVY, TEAL])
# Real KPI cards (not text-interpolated aggregates) for the two stat pairs —
# a SumIf/CountIf ratio inside a text {{}} binding is unverified; a kpi-chart
# with the same formula is the confirmed-working shape (see kc-rev live).
p2(kpi_card("u8-claimcost", "Avg Claim Cost (Current)",
    "SumIf([Enrollment Detail/Medical Spend], %s) / CountIf(%s)" % (cond(CUR, ENR), cond(CUR, ENR)),
    FMT_DOLLAR,
    cmp_formula="SumIf([Enrollment Detail/Medical Spend], %s) / CountIf(%s)" % (cond(PRI, ENR), cond(PRI, ENR)),
    cmp_fmt=FMT_DOLLAR))
u8note = text_card("u8-note", "<span style=\"color:%s\">Alliant Average: **$431**</span>" % MUTED)
p2(kpi_card("u9-costmember", "Cost per Member (Annualized, Current)",
    "SumIf([Enrollment Detail/Medical Spend], %s) / CountIf(%s) * 12" % (cond(CUR, ENR), cond(CUR, ENR)),
    FMT_DOLLAR,
    cmp_formula="SumIf([Enrollment Detail/Medical Spend], %s) / CountIf(%s) * 12" % (cond(PRI, ENR), cond(PRI, ENR)),
    cmp_fmt=FMT_DOLLAR))
u9note = text_card("u9-note", "<span style=\"color:%s\">Alliant Average: **$6,361**</span>" % MUTED)

trio_row2 = container("c-trio2", "1 / 19", "41 / 53", [
    el("u7-payer", "1 / 9", "1 / 13"),
    el("u8-claimcost", "9 / 17", "1 / 9"), el("u8-note", "9 / 17", "9 / 11"),
    el("u9-costmember", "17 / 25", "1 / 9"), el("u9-note", "17 / 25", "9 / 11"),
], cols=24)

# PMPM by age band, Current vs Prior. NOTE: dropped the mockup's third
# "Enrollment %" line series — this org's confirmed live bar-chart yAxis
# shape (yAxis:{columnIds:[...]}) has no per-series line/bar type override,
# so a 0-1 ratio series would either render as a third invisible sliver on
# a dollar-scale bar (mixing incompatible units on one axis) or need an
# unverified secondary-axis mechanism. Two clean PMPM series communicates
# the same current-vs-prior story without the unit-mixing problem.
p2(bar_card("u10-agepmpm", "PMPM by Age Band — Current vs. Prior", "tbl-enroll",
    "[Enrollment Detail/Age Band]", "Age Band", [
        ("cur", "Current PMPM", "SumIf([Enrollment Detail/Medical Spend], %s) / CountIf(%s)" % (cond(CUR, ENR), cond(CUR, ENR)), None),
        ("pri", "Prior PMPM", "SumIf([Enrollment Detail/Medical Spend], %s) / CountIf(%s)" % (cond(PRI, ENR), cond(PRI, ENR)), None),
    ], sort_desc=False))

combo_row2 = container("c-combo2", "1 / 19", "53 / 71", [el("u10-agepmpm", "1 / 25", "1 / 18")], cols=24)

# Medical Summary grouped table by Generation — native pivot-style grouping
# with expand/collapse, per the "use native row-grouping" instruction.
p2(grouped_table("u11-summary", "Medical Summary by Generation", "tbl-enroll",
    "[Enrollment Detail/Generation]", "Generation", [
        ("spend", "Spend", "SumIf([Enrollment Detail/Medical Spend], %s)" % cond(CUR, ENR), FMT_DOLLAR_COMPACT),
        ("pspend", "Prior Spend", "SumIf([Enrollment Detail/Medical Spend], %s)" % cond(PRI, ENR), FMT_DOLLAR_COMPACT),
        ("enr", "Enrollment", "CountIf(%s) / 12" % cond(CUR, ENR), FMT_NUM0),
        ("penr", "Prior Enrollment", "CountIf(%s) / 12" % cond(PRI, ENR), FMT_NUM0),
        ("claims", "Claims", "SumIf([Enrollment Detail/Claims Count], %s)" % cond(CUR, ENR), FMT_NUM0),
        ("pclaims", "Prior Claims", "SumIf([Enrollment Detail/Claims Count], %s)" % cond(PRI, ENR), FMT_NUM0),
    ]))

summary_row2 = container("c-summary2", "1 / 19", "71 / 87", [el("u11-summary", "1 / 25", "1 / 16")], cols=24)

filters_panel2 = filters_panel_container("2", p2_enroll_elements, "c-filt2", "19 / 25", 11)

page2_xml = ('<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="pgUtil">\n'
             + hdr2_xml + "\n" + callout_row + "\n" + bars_row2 + "\n" + trio_row2 + "\n"
             + combo_row2 + "\n" + summary_row2 + "\n" + filters_panel2 + "\n</Page>")

print("page2 done — %d elements" % len(new_elements))
print("page2 layout issues:", check_layout(page2_xml, "pgUtil"))

# ===========================================================================
# PAGE 3 — Medical Trend
# ===========================================================================
p3_enroll_elements = []

def p3(id_):
    p3_enroll_elements.append(id_)
    return id_

hdr3_xml = add_header("6", "Medical Trend",
    "Not excluding high cost claimants &middot; GEICO &middot; "
    "Current Period: Jun 2025 - May 2026 &middot; Prior Period: Jun 2024 - May 2025")

# Medical Spend Summary by MEDC Category — $ Change / % Change reference
# earlier calc columns in the SAME grouping BY NAME (bare [Name] — the
# same-element namespace rule), not by id.
p3(grouped_table("t1-medc", "Medical Spend Summary by MEDC Category", "tbl-enroll",
    "[Enrollment Detail/MEDC Category]", "MEDC Category", [
        ("spend", "Medical Spend", "SumIf([Enrollment Detail/Medical Spend], %s)" % cond(CUR, ENR), FMT_DOLLAR_COMPACT),
        ("pspend", "Prior Medical Spend", "SumIf([Enrollment Detail/Medical Spend], %s)" % cond(PRI, ENR), FMT_DOLLAR_COMPACT),
        ("chg", "$ Change", "[Medical Spend] - [Prior Medical Spend]", FMT_DOLLAR_COMPACT),
        ("pchg", "% Change", "([Medical Spend] - [Prior Medical Spend]) / [Prior Medical Spend]", FMT_PCT1),
    ]))
medc_row3 = container("c-medc3", "1 / 19", "11 / 27", [el("t1-medc", "1 / 25", "1 / 16")], cols=24)

# Medical Spend line chart — Current vs Prior, by month-of-year
p3(line_card("t2-spendline", "Medical Spend — Current vs. Prior", "tbl-enroll",
    "Month([Enrollment Detail/Month])", "Month of Year", [
        ("cur", "Medical Spend (Current)", "SumIf([Enrollment Detail/Medical Spend], %s)" % cond(CUR, ENR)),
        ("pri", "Medical Spend (Prior)", "SumIf([Enrollment Detail/Medical Spend], %s)" % cond(PRI, ENR)),
    ]))
line_row3 = container("c-line3", "1 / 19", "27 / 43", [el("t2-spendline", "1 / 25", "1 / 16")], cols=24)

# 3 Alliant-Average stat blocks — literal book-of-business benchmarks (out of
# scope of this one client table, same modeling choice as the product cards'
# existing goal_pct benchmarks) compared against this table's real current
# value. NOTE: deliberately NOT using kpi-chart's comparisonColumn here —
# found live that Sigma always captions that comparison "vs Prior Period"
# regardless of what the compared value actually is, which would mislabel a
# vs-Alliant-Average benchmark. A plain KPI + a separate static caption
# (same fix already used for the page 2 claim-cost/cost-per-member cards)
# avoids the mismatch.
p3(kpi_card("t3-pmpm", "Medical PMPM",
    "SumIf([Enrollment Detail/Medical Spend], %s) / CountIf(%s)" % (cond(CUR, ENR), cond(CUR, ENR)),
    FMT_DOLLAR))
t3note = text_card("t3-note", "<span style=\"color:%s\">Alliant Average: **$496.82**</span>" % MUTED)
p3(kpi_card("t4-util", "Medical Utilization per 1000",
    "SumIf([Enrollment Detail/Claims Count], %s) / CountIf(%s) * 1000" % (cond(CUR, ENR), cond(CUR, ENR)),
    FMT_NUM0))
t4note = text_card("t4-note", "<span style=\"color:%s\">Alliant Average: **937**</span>" % MUTED)
p3(kpi_card("t5-cpm", "Medical Cost per Member",
    "SumIf([Enrollment Detail/Medical Spend], %s) / CountIf(%s) * 12" % (cond(CUR, ENR), cond(CUR, ENR)),
    FMT_DOLLAR))
t5note = text_card("t5-note", "<span style=\"color:%s\">Alliant Average: **$6,361**</span>" % MUTED)
stat_row3 = container("c-stat3", "1 / 19", "43 / 56", [
    el("t3-pmpm", "1 / 9", "1 / 9"), el("t3-note", "1 / 9", "9 / 11"),
    el("t4-util", "9 / 17", "1 / 9"), el("t4-note", "9 / 17", "9 / 11"),
    el("t5-cpm", "17 / 25", "1 / 9"), el("t5-note", "17 / 25", "9 / 11"),
], cols=24)

# Medical Summary by Place of Service — wide column set, $ + % change on
# both PMPM Spend and Utilization/1000, plus Cost per Member.
p3(grouped_table("t6-pos", "Medical Summary by Place of Service", "tbl-enroll",
    "[Enrollment Detail/Place of Service]", "Place of Service", [
        ("pmpm", "PMPM Spend", "SumIf([Enrollment Detail/Medical Spend], %s) / CountIf(%s)" % (cond(CUR, ENR), cond(CUR, ENR)), FMT_DOLLAR),
        ("ppmpm", "Prior PMPM Spend", "SumIf([Enrollment Detail/Medical Spend], %s) / CountIf(%s)" % (cond(PRI, ENR), cond(PRI, ENR)), FMT_DOLLAR),
        ("pmpmchg", "PMPM $ Change", "[PMPM Spend] - [Prior PMPM Spend]", FMT_DOLLAR),
        ("pmpmpchg", "PMPM % Change", "([PMPM Spend] - [Prior PMPM Spend]) / [Prior PMPM Spend]", FMT_PCT1),
        ("util", "Utilization per 1000", "SumIf([Enrollment Detail/Claims Count], %s) / CountIf(%s) * 1000" % (cond(CUR, ENR), cond(CUR, ENR)), FMT_NUM0),
        ("putil", "Prior Utilization per 1000", "SumIf([Enrollment Detail/Claims Count], %s) / CountIf(%s) * 1000" % (cond(PRI, ENR), cond(PRI, ENR)), FMT_NUM0),
        ("utilchg", "Utilization Change", "[Utilization per 1000] - [Prior Utilization per 1000]", FMT_NUM0),
        ("utilpchg", "Utilization % Change", "([Utilization per 1000] - [Prior Utilization per 1000]) / [Prior Utilization per 1000]", FMT_PCT1),
        ("cpm", "Cost per Member", "SumIf([Enrollment Detail/Medical Spend], %s) / CountIf(%s) * 12" % (cond(CUR, ENR), cond(CUR, ENR)), FMT_DOLLAR),
        ("pcpm", "Prior Cost per Member", "SumIf([Enrollment Detail/Medical Spend], %s) / CountIf(%s) * 12" % (cond(PRI, ENR), cond(PRI, ENR)), FMT_DOLLAR),
        ("cpmchg", "Cost per Member $ Change", "[Cost per Member] - [Prior Cost per Member]", FMT_DOLLAR),
        ("cpmpchg", "Cost per Member % Change", "([Cost per Member] - [Prior Cost per Member]) / [Prior Cost per Member]", FMT_PCT1),
    ]))
pos_row3 = container("c-pos3", "1 / 19", "56 / 74", [el("t6-pos", "1 / 25", "1 / 18")], cols=24)

filters_panel3 = filters_panel_container("3", p3_enroll_elements, "c-filt3", "19 / 25", 11)

page3_xml = ('<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="pgTrend">\n'
             + hdr3_xml + "\n" + medc_row3 + "\n" + line_row3 + "\n" + stat_row3 + "\n"
             + pos_row3 + "\n" + filters_panel3 + "\n</Page>")

print("page3 done — %d elements" % len(new_elements))
print("page3 layout issues:", check_layout(page3_xml, "pgTrend"))

# ===========================================================================
# PAGE 4 — Executive Summary
# ===========================================================================
p4_enroll_elements = []

def p4(id_):
    p4_enroll_elements.append(id_)
    return id_

hdr4_xml = add_header("7", "Executive Summary",
    "Key findings and overview for the enrollment, medical and pharmacy plans "
    "&middot; GEICO &middot; Current Period: Jun 2025 - May 2026 &middot; "
    "Prior Period: Jun 2024 - May 2025")

TOTAL_SPEND = "(SumIf([Enrollment Detail/Medical Spend], %s) + SumIf([Enrollment Detail/Pharmacy Spend], %s))"

def exec_column(n, label, kpi_fmt, cur_total_formula, pri_total_formula, line_series, alliant_avg=None):
    lc = p4(line_card("x%d-line" % n, label, "tbl-enroll",
        "Month([Enrollment Detail/Month])", "Month of Year", line_series))
    kc = p4(kpi_card("x%d-kpi" % n, "%s (Current vs. Prior)" % label, cur_total_formula, kpi_fmt,
        cmp_formula=pri_total_formula, cmp_fmt=kpi_fmt))
    extra_id = None
    if alliant_avg is not None:
        # Plain KPI + a separate static caption, NOT comparisonColumn — see
        # the page 3 note on why: Sigma always captions that comparison
        # "vs Prior Period" regardless of what's actually being compared,
        # which would mislabel a vs-Alliant-Average benchmark.
        pmpm_formula, pmpm_fmt, avg_const = alliant_avg
        avg_id = p4(kpi_card("x%d-avg" % n, "%s PMPM" % label, pmpm_formula, pmpm_fmt))
        note_id = text_card("x%d-avgnote" % n,
            "<span style=\"color:%s\">Alliant Average: **%s**</span>" % (
                MUTED, ("$%.2f" % avg_const) if pmpm_fmt is FMT_DOLLAR else str(avg_const)))
        extra_id = (avg_id, note_id)
    return lc, kc, extra_id

l1, k1, _ = exec_column(1, "Enrollment", FMT_NUM0,
    "CountIf(%s) / 12" % cond(CUR, ENR), "CountIf(%s) / 12" % cond(PRI, ENR),
    [("cur", "Enrollment (Current)", "CountIf(%s) / 12" % cond(CUR, ENR)),
     ("pri", "Enrollment (Prior)", "CountIf(%s) / 12" % cond(PRI, ENR))])
l2, k2, a2 = exec_column(2, "Medical", FMT_DOLLAR_COMPACT,
    "SumIf([Enrollment Detail/Medical Spend], %s)" % cond(CUR, ENR),
    "SumIf([Enrollment Detail/Medical Spend], %s)" % cond(PRI, ENR),
    [("cur", "Medical Spend (Current)", "SumIf([Enrollment Detail/Medical Spend], %s)" % cond(CUR, ENR)),
     ("pri", "Medical Spend (Prior)", "SumIf([Enrollment Detail/Medical Spend], %s)" % cond(PRI, ENR))],
    alliant_avg=("SumIf([Enrollment Detail/Medical Spend], %s) / CountIf(%s)" % (cond(CUR, ENR), cond(CUR, ENR)),
                 FMT_DOLLAR, 496.82))
l3, k3, a3 = exec_column(3, "Pharmacy", FMT_DOLLAR_COMPACT,
    "SumIf([Enrollment Detail/Pharmacy Spend], %s)" % cond(CUR, ENR),
    "SumIf([Enrollment Detail/Pharmacy Spend], %s)" % cond(PRI, ENR),
    [("cur", "Pharmacy Spend (Current)", "SumIf([Enrollment Detail/Pharmacy Spend], %s)" % cond(CUR, ENR)),
     ("pri", "Pharmacy Spend (Prior)", "SumIf([Enrollment Detail/Pharmacy Spend], %s)" % cond(PRI, ENR))],
    alliant_avg=("SumIf([Enrollment Detail/Pharmacy Spend], %s) / CountIf(%s)" % (cond(CUR, ENR), cond(CUR, ENR)),
                 FMT_DOLLAR, 188))
l4, k4, a4 = exec_column(4, "Total", FMT_DOLLAR_COMPACT,
    TOTAL_SPEND % (cond(CUR, ENR), cond(CUR, ENR)), TOTAL_SPEND % (cond(PRI, ENR), cond(PRI, ENR)),
    [("cur", "Total Spend (Current)", TOTAL_SPEND % (cond(CUR, ENR), cond(CUR, ENR))),
     ("pri", "Total Spend (Prior)", TOTAL_SPEND % (cond(PRI, ENR), cond(PRI, ENR)))],
    alliant_avg=((TOTAL_SPEND + " / CountIf(%s)") % (cond(CUR, ENR), cond(CUR, ENR), cond(CUR, ENR)),
                 FMT_DOLLAR, 685))

def exec_col_container(cid, col_range, line_id, kpi_id, avg_ids):
    kids = [el(line_id, "1 / 25", "1 / 15"), el(kpi_id, "1 / 25", "15 / 25")]
    if avg_ids:
        avg_id, note_id = avg_ids
        kids.append(el(avg_id, "1 / 25", "25 / 34"))
        kids.append(el(note_id, "1 / 25", "34 / 36"))
    return container(cid, col_range, "11 / 47", kids, cols=24)

# build as 4 nested sub-containers spanning the 18-col main width
cols4 = "\n".join([
    exec_col_container("c-col1", "1 / 6", l1, k1, None),
    exec_col_container("c-col2", "6 / 11", l2, k2, a2),
    exec_col_container("c-col3", "11 / 16", l3, k3, a3),
    exec_col_container("c-col4", "16 / 19", l4, k4, a4),
])

# Comparison Options — segmented controls (visual completeness; each period's
# figures above are already computed for both Current and Prior directly
# from the data rather than toggled, since a segmented control's value can't
# retroactively re-scope an already-rendered KPI's own formula without a
# dedicated wiring pass — flagged as a disclosed simplification).
add({"kind": "control", "id": "x-seg-period", "controlId": "ComparisonPeriod",
     "name": "Comparison Period", "controlType": "segmented", "value": "current",
     "source": {"kind": "manual", "valueType": "text", "values": ["current", "prior"],
                "labels": ["Current Period", "Prior Period"]}})
add({"kind": "control", "id": "x-seg-basis", "controlId": "MetricBasis",
     "name": "Metric Basis", "controlType": "segmented", "value": "pmpm",
     "source": {"kind": "manual", "valueType": "text", "values": ["pepm", "pepy", "pmpm", "pmpy"],
                "labels": ["PEPM", "PEPY", "PMPM", "PMPY"]}})
text_card("opts4-label", "**Comparison Options**")
opts_row4 = container("c-opts4", "1 / 19", "47 / 52", [
    el("opts4-label", "1 / 7", "1 / 4"),
    el("x-seg-period", "7 / 16", "1 / 4"), el("x-seg-basis", "16 / 25", "1 / 4"),
], cols=24)

filters_panel4 = filters_panel_container("4", p4_enroll_elements, "c-filt4", "19 / 25", 11)

page4_xml = ('<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="pgExec">\n'
             + hdr4_xml + "\n" + cols4 + "\n" + opts_row4 + "\n" + filters_panel4 + "\n</Page>")

print("page4 done — %d elements" % len(new_elements))
print("page4 layout issues:", check_layout(page4_xml, "pgExec"))

# ===========================================================================
# SPLICE — drop old Command Center + its exclusive dependents, insert new pages
# ===========================================================================

PG1_OWNED = set('''logo1 nav-main1 c-hdr1 c-rev kc-rev kp-rev sp-rev c-cp kc-cp kp-cp sp-cp c-bal kc-bal kp-bal sp-bal c-mem kc-mem kp-mem sp-mem c-strip plg-ticker ico-ai txt-ai c-filters ctrl-date ctrl-product ctrl-grain ctrl-colorby tc-persona map-geo bar-prod tbl-rank c-secw ico-wheel wheel-heading plg-wheel c-prodwrap ico-prod pc-heading pcard-p1 pc-name-p1 pc-ring-p1 pc-tag-p1 pc-bal-p1 pc-sub-p1 pc-open-p1 pcard-p2 pc-name-p2 pc-ring-p2 pc-tag-p2 pc-bal-p2 pc-sub-p2 pc-open-p2 pcard-p3 pc-name-p3 pc-ring-p3 pc-tag-p3 pc-bal-p3 pc-sub-p3 pc-open-p3 pcard-p4 pc-name-p4 pc-ring-p4 pc-tag-p4 pc-bal-p4 pc-sub-p4 pc-open-p4 pcard-p5 pc-name-p5 pc-ring-p5 pc-tag-p5 pc-bal-p5 pc-sub-p5 pc-open-p5 pcard-p6 pc-name-p6 pc-ring-p6 pc-tag-p6 pc-bal-p6 pc-sub-p6 pc-open-p6 c-secn ico-notif notif-heading ncard-n1 nico-n1 nsev-n1 ntitle-n1 nbody-n1 nkpi-n1 nmeta-n1 ncard-n2 nico-n2 nsev-n2 ntitle-n2 nbody-n2 nkpi-n2 nmeta-n2 ncard-n3 nico-n3 nsev-n3 ntitle-n3 nbody-n3 nkpi-n3 nmeta-n3 ncard-n4 nico-n4 nsev-n4 ntitle-n4 nbody-n4 nkpi-n4 nmeta-n4 ncard-n5 nico-n5 nsev-n5 ntitle-n5 nbody-n5 nkpi-n5 nmeta-n5 c-rail1 rail-hd1 chat1'''.split())
MODALCARD_OWNED = set('mc-band mc-logo mc-title mck-bal mck-mem mck-rate mck-qoq mc-trend mc-sku mc-model mc-close'.split())
# drawerProduct is a pre-existing dead/unreachable overlay (nothing in the
# live spec ever opened it) whose one real element, dw-tbl, sets the control
# "ProductFilter" on-select. That control was ctrl-product, a pg1-owned
# element — dropping pg1 without also dropping this orphan produces a hard
# `references unknown control` rejection at update time (found via the real
# PUT, not a static check: the dangling-control-reference validator only
# fires server-side). Since nothing reaches this overlay anyway, drop it too
# rather than leave a landmine.
DRAWERPRODUCT_OWNED = {"dw-tbl", "dw-note"}
DROP_ELEMENT_IDS = PG1_OWNED | MODALCARD_OWNED | DRAWERPRODUCT_OWNED

old_elements = [e for e in DOC["elements"] if e["id"] not in DROP_ELEMENT_IDS]

# Point nav-main2 / nav-main3 (existing pages) at the new page set instead of
# the dropped pg1 "Command Center" — HANDOFF §5b flavor #2 (a navigate/nav
# target left pointing at a dropped page id).
for e in old_elements:
    if e["id"] in ("nav-main2", "nav-main3"):
        e["options"] = copy.deepcopy(NAV_OPTIONS)

final_elements = old_elements + new_elements

# Drop ag-book (Command Center's dedicated copilot — its only chat surface,
# chat1, is dropped with the page; its dataSources tbl-lb/tbl-rh stay in use
# elsewhere so nothing else is orphaned by removing it).
final_agents = [a for a in DOC["agents"] if a["id"] != "ag-book"]

# overlays: drop modalCard (only opened by the now-dropped product-card
# buttons); keep modalScenario + drawerProduct (both already reference only
# surviving elements — drawerProduct is a separate, pre-existing dead/
# unreachable artifact not created by this change, see build notes).
final_overlays = [o for o in DOC["overlays"] if o["id"] not in ("modalCard", "drawerProduct")]

final_pages = [
    {"id": "pgEnroll", "name": "Enrollment Overview"},
    {"id": "pgUtil", "name": "Medical Utilization"},
    {"id": "pgTrend", "name": "Medical Trend"},
    {"id": "pgExec", "name": "Executive Summary"},
    {"id": "pg2", "name": "Renewal Modeling"},
    {"id": "pg3", "name": "Population Builder"},
    {"id": "pgData", "name": "Data", "visibility": "hidden"},
]

old_layout = DOC["layout"]
# strip the XML declaration and the pg1 + modalCard <Page> blocks, keep the rest verbatim
import re
def extract_page(xml, page_id):
    m = re.search(r'<Page[^>]*id="%s"[^>]*>.*?</Page>' % page_id, xml, re.S)
    return m.group(0)

pg2_block = extract_page(old_layout, "pg2")
pg3_block = extract_page(old_layout, "pg3")
pgdata_block = extract_page(old_layout, "pgData")
# place the two new source tables on the hidden pgData page, below the
# existing ones (every SQL source table must be placed somewhere — HANDOFF §2)
pgdata_block = pgdata_block.replace(
    "</Page>",
    '  %s\n  %s\n</Page>' % (el("tbl-enroll", "1 / 13", "76 / 90"), el("tbl-payer", "13 / 19", "76 / 90")))
modalscenario_block = extract_page(old_layout, "modalScenario")

final_layout = ('<?xml version="1.0" encoding="utf-8"?>\n'
    + page1_xml + "\n" + page2_xml + "\n" + page3_xml + "\n" + page4_xml + "\n"
    + pg2_block + "\n" + pg3_block + "\n" + pgdata_block + "\n"
    + modalscenario_block + "\n")

final_doc = {
    "schemaVersion": DOC["schemaVersion"], "kind": DOC["kind"],
    "elements": final_elements, "pages": final_pages,
    "settings": DOC["settings"], "overlays": final_overlays,
    "agents": final_agents, "layout": final_layout,
}
final_spec = {"name": SRC["name"], "folderId": SRC["folderId"], "document": final_doc}

json.dump(final_spec, open("alliant_spec_new.json", "w"))
print("FINAL: %d elements, %d pages, %d agents, %d overlays" %
      (len(final_elements), len(final_pages), len(final_agents), len(final_overlays)))

# duplicate id / controlId checks
ids = [e["id"] for e in final_elements]
dupes = [x for x in set(ids) if ids.count(x) > 1]
print("duplicate element ids:", dupes)
cids = [e.get("controlId") for e in final_elements if e.get("kind") == "control"]
cdupes = [x for x in set(cids) if cids.count(x) > 1]
print("duplicate controlIds:", cdupes)

# every element must be placed in the layout
placed = set(re.findall(r'elementId="([^"]+)"', final_layout))
all_ids = set(ids)
unplaced = all_ids - placed
print("unplaced elements:", unplaced)
placed_not_declared = placed - all_ids
print("layout refs to non-existent elements:", placed_not_declared)

full_issues = check_layout(final_layout.replace('<?xml version="1.0" encoding="utf-8"?>', ""), "FULL")
print("full-layout static issues:", full_issues)

final_page_ids = {p["id"] for p in final_pages}
final_elem_ids = set(ids)


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


refs = set()
walk_refs(final_elements, refs)
walk_refs(final_agents, refs)
walk_refs(final_overlays, refs)
dangling_elem = [v for k, v in refs if k == "elementId" and v not in final_elem_ids]
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
walk_control_refs(final_overlays, refs2)
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
    print("PUSHED. New latestVersion:", new_meta["latestVersion"],
          "— update specs/wb_state_alliant.json's lastVersion to match.")
else:
    print("\n(dry run — pass --push to actually update the live workbook)")
