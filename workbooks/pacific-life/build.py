#!/usr/bin/env python3
"""Pacific Life -- Brand Scorecard workbook generator (new Aug-2026 schema).
Usage: python3 build.py <SIGMA_BASE_URL> <TOKEN> <CONNECTION_ID> <FOLDER_ID> <LOGO_DATAURI_FILE>
"""
import json, sys, urllib.request, urllib.error

BASE, TOKEN, CONN, FOLDER, LOGO_FILE = sys.argv[1:6]
with open(LOGO_FILE) as f:
    LOGO = f.read().strip()
H = {"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json", "Accept": "application/json"}

# ---------- palette ----------
NAVY = "#0B2E4F"; BLUE = "#1C5C8C"; TEAL = "#2E8B8B"; GOLD = "#C9A24B"
GREEN = "#2FA36B"; RED = "#D64545"; TEXT = "#12212F"; SLATE = "#5B6B79"
BORDER = "#E1E6EC"; CARD = "#F5F7FA"
STY_CARD = {"backgroundColor": "#FFFFFF", "borderColor": BORDER, "borderWidth": 1, "borderRadius": "round"}
STY_TINT = {"backgroundColor": CARD, "borderColor": BORDER, "borderWidth": 1, "borderRadius": "round"}

EVENT_TYPES = ["PGA Tour Sponsorship", "Golf Pro-Am", "Concert Series", "Industry Conference", "Community Event"]

def c(id_, **kw):
    d = {"id": id_}
    d.update({k: v for k, v in kw.items() if v is not None})
    return d

# ==================================================================
# DATA LAYER (hidden page)
# ==================================================================
tbl_events = {
    "id": "tbl-events", "kind": "input-table", "name": "Events",
    "source": {"kind": "empty", "connectionId": CONN}, "inputMode": "view",
    "columns": [
        c("ev-name", type="text", name="Event Name"),
        c("ev-type", type="text", name="Event Type", values=EVENT_TYPES, pills="color-by-option"),
        c("ev-date", type="text", name="Event Date"),
        c("ev-owner", type="text", name="Requested By"),
        c("ev-budget", type="number", name="Requested Budget"),
        c("ev-just", type="text", name="Summary and Justification"),
        {"id": "CREATED_AT"},
    ],
    "order": ["ev-name", "ev-type", "ev-date", "ev-owner", "ev-budget", "ev-just", "CREATED_AT"],
}
tbl_targets = {
    "id": "tbl-targets", "kind": "input-table", "name": "Targets",
    "source": {"kind": "empty", "connectionId": CONN}, "inputMode": "view",
    "columns": [
        c("tg-event", type="text", name="Event Name"),
        c("tg-impr", type="number", name="Target Impressions"),
        c("tg-eng", type="number", name="Target Engagements"),
        c("tg-leads", type="number", name="Target Leads and Meetings"),
        c("tg-emv", type="number", name="Target Earned Media Value"),
        c("tg-lift", type="number", name="Target Brand Lift %"),
        c("tg-budget", type="number", name="Approved Budget"),
        {"id": "CREATED_AT"},
    ],
    "order": ["tg-event", "tg-impr", "tg-eng", "tg-leads", "tg-emv", "tg-lift", "tg-budget", "CREATED_AT"],
}
tbl_approvals = {
    "id": "tbl-approvals", "kind": "input-table", "name": "Approvals",
    "source": {"kind": "empty", "connectionId": CONN}, "inputMode": "view",
    "columns": [
        c("ap-event", type="text", name="Event Name"),
        c("ap-decision", type="text", name="Decision", values=["Approved", "Denied"], pills="color-by-option"),
        c("ap-reviewer", type="text", name="Reviewer"),
        c("ap-comments", type="text", name="Comments"),
        {"id": "CREATED_AT"},
    ],
    "order": ["ap-event", "ap-decision", "ap-reviewer", "ap-comments", "CREATED_AT"],
}
tbl_actuals = {
    "id": "tbl-actuals", "kind": "input-table", "name": "Actuals",
    "source": {"kind": "empty", "connectionId": CONN}, "inputMode": "view",
    "columns": [
        c("ac-event", type="text", name="Event Name"),
        c("ac-impr", type="number", name="Actual Impressions"),
        c("ac-eng", type="number", name="Actual Engagements"),
        c("ac-leads", type="number", name="Actual Leads and Meetings"),
        c("ac-emv", type="number", name="Actual Earned Media Value"),
        c("ac-lift", type="number", name="Actual Brand Lift %"),
        c("ac-spend", type="number", name="Actual Spend"),
        {"id": "CREATED_AT"},
    ],
    "order": ["ac-event", "ac-impr", "ac-eng", "ac-leads", "ac-emv", "ac-lift", "ac-spend", "CREATED_AT"],
}

# ------------------------------------------------------------------
# SEED DATA -- there is no code-representable way to insert rows into an
# input table on this org (insert-rows/update-rows/delete-rows and the CSV
# input-table source are all rejected at POST; an "initialValues" column
# field is silently dropped). So the demo dataset is baked in as read-only
# SQL "VALUES" tables -- the same mechanism already used for spend-bar's
# chart data -- and the wide Scorecard table below reads the SEED tables
# for its row grain, then Coalesces in a live value from the matching real
# input table when one exists. That means: the four sample events always
# show data, and typing a real target/decision/actual for one of THOSE same
# event names in the live Targets/Approvals/Actuals tables overrides the
# seed value immediately. (A brand-new event name typed into the live
# Events table won't get its own scorecard row -- there's no UNION-style
# source kind to merge it into this grain -- but its Target/Approval/Actual
# entries are still captured in the raw tables on each page.)
def _sqlval(rows):
    def lit(v):
        if v is None: return "NULL"
        if isinstance(v, str): return "'" + v.replace("'", "''") + "'"
        return str(v)
    n = len(rows[0])
    first = "SELECT " + ",".join(f"{lit(v)} AS C{i+1}" for i, v in enumerate(rows[0]))
    rest = [" UNION ALL SELECT " + ",".join(lit(v) for v in row) for row in rows[1:]]
    return first + "".join(rest)

SEED_EVENTS_ROWS = [
    ("AT&T Pebble Beach Pro-Am", "PGA Tour Sponsorship", "2026-02-05", "Sarah Chen", 450000,
     "Marquee PGA Tour pairing event; strong overlap with our target affluent demographic."),
    ("Pacific Life Open Golf Classic", "Golf Pro-Am", "2026-06-12", "James Whitfield", 275000,
     "Regional client-appreciation pro-am; strengthens advisor relationships in key markets."),
    ("Newport Beach Jazz & Wine Festival", "Concert Series", "2026-09-20", "Maria Lopez", 120000,
     "Community brand visibility in our Newport Beach HQ market."),
    ("Financial Advisors Forum West", "Industry Conference", "2026-11-03", "David Kim", 90000,
     "Advisor recruitment and thought-leadership positioning."),
]
SEED_TARGETS_ROWS = [
    ("AT&T Pebble Beach Pro-Am", 8000000, 45000, 150, 1200000, 4, 430000),
    ("Pacific Life Open Golf Classic", 1500000, 12000, 60, 300000, 2.5, 260000),
    ("Financial Advisors Forum West", 600000, 5000, 40, 150000, 1.5, 85000),
]
SEED_APPROVALS_ROWS = [
    ("AT&T Pebble Beach Pro-Am", "Approved", "Karen Ito", "Strong ROI history with this event; approve at requested budget."),
    ("Pacific Life Open Golf Classic", "Approved", "Karen Ito", "Approved with a slight budget trim."),
    ("Newport Beach Jazz & Wine Festival", "Denied", "Karen Ito", "Low strategic fit this cycle; revisit next year."),
]
SEED_ACTUALS_ROWS = [
    ("AT&T Pebble Beach Pro-Am", 8400000, 51000, 162, 1350000, 4.6, 421000),
]

seed_events = {"id": "events-seed", "kind": "table", "name": "Events Seed", "visibleAsSource": True,
    "source": {"connectionId": CONN, "kind": "sql", "statement": _sqlval(SEED_EVENTS_ROWS)},
    "columns": [
        c("se-name", formula="[Custom SQL/C1]", name="Event Name"), c("se-type", formula="[Custom SQL/C2]", name="Event Type"),
        c("se-date", formula="[Custom SQL/C3]", name="Event Date"), c("se-owner", formula="[Custom SQL/C4]", name="Requested By"),
        c("se-budget", formula="[Custom SQL/C5]", name="Requested Budget"), c("se-just", formula="[Custom SQL/C6]", name="Summary and Justification"),
    ], "order": ["se-name", "se-type", "se-date", "se-owner", "se-budget", "se-just"]}
seed_targets = {"id": "targets-seed", "kind": "table", "name": "Targets Seed", "visibleAsSource": True,
    "source": {"connectionId": CONN, "kind": "sql", "statement": _sqlval(SEED_TARGETS_ROWS)},
    "columns": [
        c("st-name", formula="[Custom SQL/C1]", name="Event Name"), c("st-impr", formula="[Custom SQL/C2]", name="Target Impressions"),
        c("st-eng", formula="[Custom SQL/C3]", name="Target Engagements"), c("st-leads", formula="[Custom SQL/C4]", name="Target Leads and Meetings"),
        c("st-emv", formula="[Custom SQL/C5]", name="Target Earned Media Value"), c("st-lift", formula="[Custom SQL/C6]", name="Target Brand Lift %"),
        c("st-budget", formula="[Custom SQL/C7]", name="Approved Budget"),
    ], "order": ["st-name", "st-impr", "st-eng", "st-leads", "st-emv", "st-lift", "st-budget"]}
seed_approvals = {"id": "approvals-seed", "kind": "table", "name": "Approvals Seed", "visibleAsSource": True,
    "source": {"connectionId": CONN, "kind": "sql", "statement": _sqlval(SEED_APPROVALS_ROWS)},
    "columns": [
        c("sa-name", formula="[Custom SQL/C1]", name="Event Name"), c("sa-decision", formula="[Custom SQL/C2]", name="Decision"),
        c("sa-reviewer", formula="[Custom SQL/C3]", name="Reviewer"), c("sa-comments", formula="[Custom SQL/C4]", name="Comments"),
    ], "order": ["sa-name", "sa-decision", "sa-reviewer", "sa-comments"]}
seed_actuals = {"id": "actuals-seed", "kind": "table", "name": "Actuals Seed", "visibleAsSource": True,
    "source": {"connectionId": CONN, "kind": "sql", "statement": _sqlval(SEED_ACTUALS_ROWS)},
    "columns": [
        c("sc2-name", formula="[Custom SQL/C1]", name="Event Name"), c("sc2-impr", formula="[Custom SQL/C2]", name="Actual Impressions"),
        c("sc2-eng", formula="[Custom SQL/C3]", name="Actual Engagements"), c("sc2-leads", formula="[Custom SQL/C4]", name="Actual Leads and Meetings"),
        c("sc2-emv", formula="[Custom SQL/C5]", name="Actual Earned Media Value"), c("sc2-lift", formula="[Custom SQL/C6]", name="Actual Brand Lift %"),
        c("sc2-spend", formula="[Custom SQL/C7]", name="Actual Spend"),
    ], "order": ["sc2-name", "sc2-impr", "sc2-eng", "sc2-leads", "sc2-emv", "sc2-lift", "sc2-spend"]}

SEED_ELEMENTS = [seed_events, seed_targets, seed_approvals, seed_actuals]

# Wide scorecard: one row per (seed) event. Base dimensions come straight
# from the seed; every Targets/Approvals/Actuals field prefers a live entry
# in the real input table (matched by event name) and falls back to seed.
def _override(real_table, real_col, seed_table, seed_col):
    # Lookup(<foreign value>, <THIS element's own key, bare>, <foreign key, prefixed>)
    real = f'Lookup([{real_table}/{real_col}],[Event Name],[{real_table}/Event Name])'
    seed = f'Lookup([{seed_table}/{seed_col}],[Event Name],[{seed_table}/Event Name])'
    return f'Coalesce({real},{seed})'

SC_DEFS = [
    ("sc-name", "Event Name", "[Events Seed/Event Name]"),
    ("sc-type", "Event Type", "[Events Seed/Event Type]"),
    ("sc-date", "Event Date", "[Events Seed/Event Date]"),
    ("sc-owner", "Requested By", "[Events Seed/Requested By]"),
    ("sc-reqbudget", "Requested Budget", "[Events Seed/Requested Budget]"),
    ("sc-just", "Justification", "[Events Seed/Summary and Justification]"),
    ("sc-decision", "Decision", _override("Approvals", "Decision", "Approvals Seed", "Decision")),
    ("sc-reviewer", "Reviewer", _override("Approvals", "Reviewer", "Approvals Seed", "Reviewer")),
    ("sc-comments", "Review Comments", _override("Approvals", "Comments", "Approvals Seed", "Comments")),
    ("sc-status", "Status", 'Coalesce([Decision],"Pending Brand Council Review")'),
    ("sc-tgimpr", "Target Impressions", _override("Targets", "Target Impressions", "Targets Seed", "Target Impressions")),
    ("sc-tgeng", "Target Engagements", _override("Targets", "Target Engagements", "Targets Seed", "Target Engagements")),
    ("sc-tgleads", "Target Leads and Meetings", _override("Targets", "Target Leads and Meetings", "Targets Seed", "Target Leads and Meetings")),
    ("sc-tgemv", "Target Earned Media Value", _override("Targets", "Target Earned Media Value", "Targets Seed", "Target Earned Media Value")),
    ("sc-tglift", "Target Brand Lift %", _override("Targets", "Target Brand Lift %", "Targets Seed", "Target Brand Lift %")),
    ("sc-apprbudget", "Approved Budget", _override("Targets", "Approved Budget", "Targets Seed", "Approved Budget")),
    ("sc-acimpr", "Actual Impressions", _override("Actuals", "Actual Impressions", "Actuals Seed", "Actual Impressions")),
    ("sc-aceng", "Actual Engagements", _override("Actuals", "Actual Engagements", "Actuals Seed", "Actual Engagements")),
    ("sc-acleads", "Actual Leads and Meetings", _override("Actuals", "Actual Leads and Meetings", "Actuals Seed", "Actual Leads and Meetings")),
    ("sc-acemv", "Actual Earned Media Value", _override("Actuals", "Actual Earned Media Value", "Actuals Seed", "Actual Earned Media Value")),
    ("sc-aclift", "Actual Brand Lift %", _override("Actuals", "Actual Brand Lift %", "Actuals Seed", "Actual Brand Lift %")),
    ("sc-acspend", "Actual Spend", _override("Actuals", "Actual Spend", "Actuals Seed", "Actual Spend")),
    ("sc-hastargets", "Has Targets", 'IsNotNull([Target Impressions])'),
    ("sc-hasactuals", "Has Actuals", 'IsNotNull([Actual Impressions])'),
]

def make_wide_table(elid, name):
    return {
        "id": elid, "kind": "table", "name": name, "visibleAsSource": True,
        "source": {"elementId": "events-seed", "kind": "table"},
        "columns": [c(cid, formula=f, name=n) for cid, n, f in SC_DEFS],
        "order": [cid for cid, _, _ in SC_DEFS],
    }

scorecard = make_wide_table("scorecard", "Scorecard")
scorecard_view = make_wide_table("scorecard-view", "Scorecard View")

DATA_ELEMENTS = [tbl_events, tbl_targets, tbl_approvals, tbl_actuals, scorecard, scorecard_view]

# ==================================================================
# LAYOUT HELPERS
# ==================================================================
def header(page_sfx, title, subtitle):
    hdr = {"id": f"c-hdr{page_sfx}", "kind": "container", "style": dict(STY_CARD)}
    logo = {"id": f"logo{page_sfx}", "kind": "image", "source": {"kind": "url", "url": LOGO}, "style": {"fit": "contain"}}
    ttl = {"id": f"ttl{page_sfx}", "kind": "text", "body": f"## {title}", "verticalAlign": "middle", "style": {"color": NAVY}}
    sub = {"id": f"sub{page_sfx}", "kind": "text", "body": subtitle, "verticalAlign": "middle", "style": {"color": SLATE}}
    elems = [hdr, logo, ttl, sub]
    lay = (f'<Container elementId="c-hdr{page_sfx}" type="grid" gridColumn="1 / 25" gridRow="1 / 6" '
           f'gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="repeat(5,1fr)">'
           f'<Element elementId="logo{page_sfx}" gridColumn="1 / 5" gridRow="1 / 6"/>'
           f'<Element elementId="ttl{page_sfx}" gridColumn="5 / 20" gridRow="1 / 4"/>'
           f'<Element elementId="sub{page_sfx}" gridColumn="5 / 20" gridRow="4 / 6"/>'
           f'</Container>')
    return elems, lay

def kpi_plain(elid, title, formula, source_id="scorecard"):
    el = {"id": elid, "kind": "kpi-chart", "source": {"elementId": source_id, "kind": "table"},
          "columns": [c(f"{elid}v", formula=formula, name=title)],
          "value": {"columnId": f"{elid}v", "fontSize": 30, "color": NAVY},
          "name": {"text": title, "fontSize": 13, "color": SLATE}, "style": dict(STY_CARD)}
    return el

def kpi_delta(elid, title, value_formula, comp_formula, source_id="scorecard"):
    el = {"id": elid, "kind": "kpi-chart", "source": {"elementId": source_id, "kind": "table"},
          "columns": [c(f"{elid}v", formula=value_formula, name=title),
                      c(f"{elid}c", formula=comp_formula, name="Target")],
          "value": {"columnId": f"{elid}v", "fontSize": 26, "color": NAVY},
          "comparisonColumn": {"columnId": f"{elid}c"},
          "comparison": {"display": "delta", "colorGood": GREEN, "colorBad": RED, "fontSize": 12},
          "name": {"text": title, "fontSize": 12, "color": SLATE}, "style": dict(STY_CARD)}
    return el

def kpi_row_layout(ids, row, ncols_each, start_row_span="7 / 15"):
    n = len(ids)
    width = 24 // n
    parts = []
    for i, eid in enumerate(ids):
        a, b = 1 + i * width, 1 + (i + 1) * width
        parts.append(f'<Element elementId="{eid}" gridColumn="{a} / {b}" gridRow="{start_row_span}"/>')
    return "".join(parts)

def field_control(cid, controlId, label, area=False):
    return {"kind": "control", "id": cid, "controlId": controlId, "name": label,
            "controlType": "text-area" if area else "text",
            "mode": "equals", "case": "insensitive",
            "includeNulls": "when-no-value-is-selected", "showOperators": False}

def btn(elid, text, effects, appearance="filled"):
    return {"id": elid, "kind": "button", "text": text, "appearance": appearance,
            "actions": [{"id": f"a-{elid}", "trigger": "on-click", "effects": effects}]}

def val_ctrl(control): return {"type": "control", "control": control}
def val_num(control): return {"type": "formula", "formula": f"Number([{control}])"}
def val_const_text(v): return {"type": "constant", "value": {"type": "text", "value": v}}

# ==================================================================
# NOTE ON WRITE-BACK: this org's live workbook-spec API accepts button
# effects open-overlay / close-overlay / navigate / set-control-value /
# clear-control, but rejects insert-rows / update-rows / delete-rows /
# open-url / refresh-element outright (verified empirically against
# api.sigmacomputing.com -- same "Invalid kind" signature as a made-up
# effect name, i.e. not enabled on this org, not a shape bug). So every
# input table below is placed directly on its page as an EDITABLE grid
# -- users add/edit rows with Sigma's native input-table row controls
# -- rather than via a button-driven modal.
# ==================================================================

# ==================================================================
# PAGE 1 -- Events (list + add via the input table)
# ==================================================================
h1e, h1l = header("1", "Pacific Life -- Brand Scorecard", "Marketing event & sponsorship tracking")
p1_kpis = [
    kpi_plain("k1a", "Total Events", "Count([Scorecard/Event Name])"),
    kpi_plain("k1b", "Pending Brand Council Review", 'CountIf([Scorecard/Status]="Pending Brand Council Review")'),
    kpi_plain("k1c", "Approved Events", 'CountIf([Scorecard/Status]="Approved")'),
    kpi_plain("k1d", "Total Requested Budget", "Sum([Scorecard/Requested Budget])"),
]
p1_note = {"id": "p1-note", "kind": "text", "verticalAlign": "middle", "style": {"color": SLATE},
           "body": "**+ Add Event:** click the **+** at the bottom of the table below to submit a new event / sponsorship request (name, type, date, requester, budget, justification). Finance and Brand Council pick it up from there."}
events_tbl = {
    "id": "events-list", "kind": "table", "name": "Events List", "source": {"elementId": "scorecard", "kind": "table"},
    "columns": [
        c("el-name", formula="[Scorecard/Event Name]", name="Event Name"),
        c("el-type", formula="[Scorecard/Event Type]", name="Event Type"),
        c("el-date", formula="[Scorecard/Event Date]", name="Event Date"),
        c("el-owner", formula="[Scorecard/Requested By]", name="Requested By"),
        c("el-budget", formula="[Scorecard/Requested Budget]", name="Requested Budget"),
        c("el-status", formula="[Scorecard/Status]", name="Status"),
    ],
    "order": ["el-name", "el-type", "el-date", "el-owner", "el-budget", "el-status"],
    "conditionalFormats": [
        {"type": "single", "columnIds": ["el-status"], "condition": "=", "value": "Approved", "style": {"backgroundColor": "#DCF3E6"}},
        {"type": "single", "columnIds": ["el-status"], "condition": "=", "value": "Denied", "style": {"backgroundColor": "#FBE1E1"}},
        {"type": "single", "columnIds": ["el-status"], "condition": "=", "value": "Pending Brand Council Review", "style": {"backgroundColor": "#FCF2DA"}},
    ],
    "style": dict(STY_CARD),
}

def page1():
    elems = h1e + p1_kpis + [events_tbl, p1_note, tbl_events]
    lay = (f'<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="pgEvents">'
           f'{h1l}'
           f'{kpi_row_layout(["k1a","k1b","k1c","k1d"], None, None, "7 / 15")}'
           f'<Element elementId="events-list" gridColumn="1 / 25" gridRow="16 / 32"/>'
           f'<Element elementId="p1-note" gridColumn="1 / 25" gridRow="33 / 35"/>'
           f'<Element elementId="tbl-events" gridColumn="1 / 25" gridRow="35 / 48"/>'
           f'</Page>')
    return elems, lay

# ==================================================================
# PAGE 2 -- Finance: enter targets
# ==================================================================
h2e, h2l = header("2", "Finance -- Enter Targets & Approved Budget", "Set performance targets before Brand Council review")
k2 = kpi_plain("k2a", "Awaiting Targets", 'CountIf([Scorecard/Has Targets]=False)')
p2_note = {"id": "p2-note", "kind": "text", "verticalAlign": "middle", "style": {"color": SLATE},
           "body": "**Alert:** the events below have no targets yet. Add a row in the table underneath -- type the **Event Name** exactly as it appears above, then the target metrics and the Finance-approved budget."}
awaiting_tbl = {
    "id": "awaiting-targets", "kind": "table", "name": "Awaiting Targets", "source": {"elementId": "scorecard", "kind": "table"},
    "columns": [c("at-name", formula="[Scorecard/Event Name]", name="Event Name"), c("at-type", formula="[Scorecard/Event Type]", name="Event Type"),
                c("at-req", formula="[Scorecard/Requested Budget]", name="Requested Budget"), c("at-just", formula="[Scorecard/Justification]", name="Justification")],
    "order": ["at-name", "at-type", "at-req", "at-just"], "style": dict(STY_CARD),
}
targets_tbl = {
    "id": "targets-table", "kind": "table", "name": "Targets Submitted", "source": {"elementId": "scorecard", "kind": "table"},
    "columns": [c("tt-name", formula="[Scorecard/Event Name]", name="Event Name"), c("tt-type", formula="[Scorecard/Event Type]", name="Event Type"),
                c("tt-req", formula="[Scorecard/Requested Budget]", name="Requested Budget"), c("tt-impr", formula="[Scorecard/Target Impressions]", name="Target Impressions"),
                c("tt-eng", formula="[Scorecard/Target Engagements]", name="Target Engagements"), c("tt-leads", formula="[Scorecard/Target Leads and Meetings]", name="Target Leads and Meetings"),
                c("tt-emv", formula="[Scorecard/Target Earned Media Value]", name="Target Earned Media Value"), c("tt-lift", formula="[Scorecard/Target Brand Lift %]", name="Target Brand Lift %"),
                c("tt-budget", formula="[Scorecard/Approved Budget]", name="Approved Budget")],
    "order": ["tt-name", "tt-type", "tt-req", "tt-impr", "tt-eng", "tt-leads", "tt-emv", "tt-lift", "tt-budget"],
    "style": dict(STY_CARD),
}

def page2():
    elems = h2e + [k2, awaiting_tbl, p2_note, tbl_targets, targets_tbl]
    lay = (f'<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="pgFinance">'
           f'{h2l}'
           f'<Element elementId="k2a" gridColumn="1 / 7" gridRow="7 / 14"/>'
           f'<Element elementId="awaiting-targets" gridColumn="1 / 25" gridRow="15 / 27"/>'
           f'<Element elementId="p2-note" gridColumn="1 / 25" gridRow="28 / 30"/>'
           f'<Element elementId="tbl-targets" gridColumn="1 / 25" gridRow="30 / 40"/>'
           f'<Element elementId="targets-table" gridColumn="1 / 25" gridRow="41 / 55"/>'
           f'</Page>')
    return elems, lay

# ==================================================================
# PAGE 3 -- Brand Council approvals
# ==================================================================
h3e, h3l = header("3", "Brand Council -- Approve or Deny", "Review targets & budget, then record a decision")
k3 = kpi_plain("k3a", "Awaiting Decision", 'CountIf([Scorecard/Has Targets]=True And IsNull([Scorecard/Decision]))')
p3_note = {"id": "p3-note", "kind": "text", "verticalAlign": "middle", "style": {"color": SLATE},
           "body": "Add a row below -- type the **Event Name** exactly as it appears above, then set **Decision** (Approved/Denied), **Reviewer**, and **Comments**."}
pending_tbl = {
    "id": "pending-approval", "kind": "table", "name": "Awaiting Decision", "source": {"elementId": "scorecard", "kind": "table"},
    "columns": [c("pa-name", formula="[Scorecard/Event Name]", name="Event Name"), c("pa-type", formula="[Scorecard/Event Type]", name="Event Type"),
                c("pa-just", formula="[Scorecard/Justification]", name="Justification"), c("pa-req", formula="[Scorecard/Requested Budget]", name="Requested Budget"),
                c("pa-budget", formula="[Scorecard/Approved Budget]", name="Finance-Approved Budget"), c("pa-status", formula="[Scorecard/Status]", name="Status")],
    "order": ["pa-name", "pa-type", "pa-just", "pa-req", "pa-budget", "pa-status"],
    "style": dict(STY_CARD),
}
decisions_tbl = {
    "id": "decisions-log", "kind": "table", "name": "Decisions Log", "source": {"elementId": "scorecard", "kind": "table"},
    "columns": [c("dl-name", formula="[Scorecard/Event Name]", name="Event Name"), c("dl-decision", formula="[Scorecard/Decision]", name="Decision"),
                c("dl-reviewer", formula="[Scorecard/Reviewer]", name="Reviewer"), c("dl-comments", formula="[Scorecard/Review Comments]", name="Comments")],
    "order": ["dl-name", "dl-decision", "dl-reviewer", "dl-comments"],
    "conditionalFormats": [
        {"type": "single", "columnIds": ["dl-decision"], "condition": "=", "value": "Approved", "style": {"backgroundColor": "#DCF3E6"}},
        {"type": "single", "columnIds": ["dl-decision"], "condition": "=", "value": "Denied", "style": {"backgroundColor": "#FBE1E1"}},
    ],
    "style": dict(STY_CARD),
}

def page3():
    elems = h3e + [k3, pending_tbl, p3_note, tbl_approvals, decisions_tbl]
    lay = (f'<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="pgApprovals">'
           f'{h3l}'
           f'<Element elementId="k3a" gridColumn="1 / 7" gridRow="7 / 14"/>'
           f'<Element elementId="pending-approval" gridColumn="1 / 25" gridRow="15 / 27"/>'
           f'<Element elementId="p3-note" gridColumn="1 / 25" gridRow="28 / 30"/>'
           f'<Element elementId="tbl-approvals" gridColumn="1 / 25" gridRow="30 / 38"/>'
           f'<Element elementId="decisions-log" gridColumn="1 / 25" gridRow="39 / 51"/>'
           f'</Page>')
    return elems, lay

# ==================================================================
# PAGE 4 -- Individual Event Scorecard
# ==================================================================
h4e, h4l = header("4", "Event Scorecard", "Targets vs. actuals for a single event")
ctrl_sc_event = {"kind": "control", "id": "ctrl-sc-event", "controlId": "ScEvent", "name": "Select Event", "controlType": "list",
                  "selectionMode": "single", "mode": "include", "values": [],
                  "filters": [{"source": {"kind": "table", "elementId": "scorecard-view"}, "columnId": "sc-name"}],
                  "source": {"kind": "source", "source": {"kind": "table", "elementId": "scorecard-view"}, "columnId": "sc-name"}}
sc_kpis = [
    kpi_delta("k4a", "Actual Spend vs Approved Budget", "[Scorecard View/Actual Spend]", "[Scorecard View/Approved Budget]", "scorecard-view"),
    kpi_delta("k4b", "Impressions", "[Scorecard View/Actual Impressions]", "[Scorecard View/Target Impressions]", "scorecard-view"),
    kpi_delta("k4c", "Engagements", "[Scorecard View/Actual Engagements]", "[Scorecard View/Target Engagements]", "scorecard-view"),
    kpi_delta("k4d", "Leads / Meetings", "[Scorecard View/Actual Leads and Meetings]", "[Scorecard View/Target Leads and Meetings]", "scorecard-view"),
    kpi_delta("k4e", "Earned Media Value", "[Scorecard View/Actual Earned Media Value]", "[Scorecard View/Target Earned Media Value]", "scorecard-view"),
    kpi_delta("k4f", "Brand Lift %", "[Scorecard View/Actual Brand Lift %]", "[Scorecard View/Target Brand Lift %]", "scorecard-view"),
]
detail_tbl = {
    "id": "sc-detail", "kind": "table", "name": "Event Detail", "source": {"elementId": "scorecard-view", "kind": "table"},
    "columns": [c("sd-type", formula="[Scorecard View/Event Type]", name="Event Type"), c("sd-date", formula="[Scorecard View/Event Date]", name="Event Date"),
                c("sd-owner", formula="[Scorecard View/Requested By]", name="Requested By"), c("sd-status", formula="[Scorecard View/Status]", name="Status"),
                c("sd-just", formula="[Scorecard View/Justification]", name="Justification"), c("sd-reviewer", formula="[Scorecard View/Reviewer]", name="Reviewer"),
                c("sd-comments", formula="[Scorecard View/Review Comments]", name="Review Comments")],
    "order": ["sd-type", "sd-date", "sd-owner", "sd-status", "sd-just", "sd-reviewer", "sd-comments"],
    "style": dict(STY_CARD),
}
p4_note = {"id": "p4-note", "kind": "text", "verticalAlign": "middle", "style": {"color": SLATE},
           "body": "**Enter Actuals** (after the event runs): add a row below -- type the **Event Name** exactly as it appears in the picker above, then the actual results and spend."}

def page4():
    elems = h4e + [ctrl_sc_event] + sc_kpis + [detail_tbl, p4_note, tbl_actuals]
    lay = (f'<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="pgScorecard">'
           f'{h4l}'
           f'<Element elementId="ctrl-sc-event" gridColumn="1 / 9" gridRow="7 / 10"/>'
           f'{kpi_row_layout(["k4a","k4b","k4c","k4d","k4e","k4f"], None, None, "11 / 20")}'
           f'<Element elementId="sc-detail" gridColumn="1 / 25" gridRow="21 / 30"/>'
           f'<Element elementId="p4-note" gridColumn="1 / 25" gridRow="31 / 33"/>'
           f'<Element elementId="tbl-actuals" gridColumn="1 / 25" gridRow="33 / 43"/>'
           f'</Page>')
    return elems, lay

# ==================================================================
# PAGE 5 -- Annual Scorecard (aggregate)
# ==================================================================
h5e, h5l = header("5", "Annual Brand Scorecard", "Aggregate performance across all events this year")
p5_kpis = [
    kpi_plain("k5a", "Total Events", "Count([Scorecard/Event Name])"),
    kpi_plain("k5b", "Total Requested Budget", "Sum([Scorecard/Requested Budget])"),
    kpi_plain("k5c", "Total Approved Budget", "Sum([Scorecard/Approved Budget])"),
    kpi_plain("k5d", "Total Actual Spend", "Sum([Scorecard/Actual Spend])"),
    kpi_plain("k5e", "Total Earned Media Value", "Sum([Scorecard/Actual Earned Media Value])"),
    kpi_plain("k5f", "Blended Brand Lift %", "AvgIf([Scorecard/Actual Brand Lift %],IsNotNull([Scorecard/Actual Brand Lift %]))"),
]
spend_bar = {
    "id": "spend-bar", "kind": "bar-chart", "name": "Actual Spend by Event",
    "source": {"elementId": "scorecard", "kind": "table"},
    "columns": [c("sb-name", formula="[Scorecard/Event Name]", name="Event Name"), c("sb-spend", formula="[Scorecard/Actual Spend]", name="Actual Spend"),
                c("sb-status", formula="[Scorecard/Status]", name="Status")],
    "xAxis": {"columnId": "sb-name", "sort": {"by": "sb-spend", "direction": "descending"}}, "yAxis": {"columnIds": ["sb-spend"]},
    "color": {"by": "category", "column": "sb-status", "scheme": [GREEN, RED, GOLD]},
    "legend": {"visibility": "visible"}, "style": dict(STY_CARD),
}
status_donut = {
    "id": "status-donut", "kind": "donut-chart", "name": "Events by Status",
    "source": {"elementId": "scorecard", "kind": "table"},
    "columns": [c("sd2-status", formula="[Scorecard/Status]", name="Status"), c("sd2-count", formula="Count([Scorecard/Event Name])", name="Events")],
    "color": {"id": "sd2-status"}, "value": {"id": "sd2-count"},
    "style": dict(STY_CARD),
}
rollup_tbl = {
    "id": "rollup", "kind": "table", "name": "Annual Rollup", "source": {"elementId": "scorecard", "kind": "table"},
    "columns": [c("ru-name", formula="[Scorecard/Event Name]", name="Event Name"), c("ru-type", formula="[Scorecard/Event Type]", name="Event Type"),
                c("ru-status", formula="[Scorecard/Status]", name="Status"), c("ru-budget", formula="[Scorecard/Approved Budget]", name="Approved Budget"),
                c("ru-spend", formula="[Scorecard/Actual Spend]", name="Actual Spend"),
                c("ru-tgimpr", formula="[Scorecard/Target Impressions]", name="Target Impressions"), c("ru-acimpr", formula="[Scorecard/Actual Impressions]", name="Actual Impressions"),
                c("ru-tgemv", formula="[Scorecard/Target Earned Media Value]", name="Target EMV"), c("ru-acemv", formula="[Scorecard/Actual Earned Media Value]", name="Actual EMV"),
                c("ru-varimpr", formula="[Scorecard/Actual Impressions]-[Scorecard/Target Impressions]", name="Impressions Variance")],
    "order": ["ru-name", "ru-type", "ru-status", "ru-budget", "ru-spend", "ru-tgimpr", "ru-acimpr", "ru-tgemv", "ru-acemv", "ru-varimpr"],
    "style": dict(STY_CARD),
}

def page5():
    elems = h5e + p5_kpis + [spend_bar, status_donut, rollup_tbl]
    lay = (f'<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="pgAnnual">'
           f'{h5l}'
           f'{kpi_row_layout(["k5a","k5b","k5c","k5d","k5e","k5f"], None, None, "7 / 15")}'
           f'<Element elementId="spend-bar" gridColumn="1 / 17" gridRow="16 / 34"/>'
           f'<Element elementId="status-donut" gridColumn="17 / 25" gridRow="16 / 34"/>'
           f'<Element elementId="rollup" gridColumn="1 / 25" gridRow="35 / 55"/>'
           f'</Page>')
    return elems, lay

# ==================================================================
# ASSEMBLE + POST
# ==================================================================
THEME = {"colors": {"text": TEXT, "highlight": BLUE, "success": GREEN, "warning": GOLD, "danger": RED, "darkMode": "hidden"},
          "colorOverrides": {"backgroundCanvas": "#FFFFFF", "canvasBackground": "#F7F9FB"},
          "categoricalScheme": [NAVY, BLUE, TEAL, GOLD, GREEN, RED],
          "fonts": {"textFont": "Inter", "dataFont": "Inter"}, "pageWidth": "large",
          "tableStyles": {"preset": "presentation", "cellSpacing": "small"}}

# Only the derived Lookup tables live on the hidden Data page; the four raw
# input tables are placed directly on their own pages (see page1..page4).
HIDDEN_DATA_ELEMENTS = SEED_ELEMENTS + [scorecard, scorecard_view]
DATA_PAGE_LAYOUT = ('<Page type="grid" gridTemplateColumns="repeat(24,1fr)" gridTemplateRows="auto" id="pgData">'
                     + "".join(f'<Element elementId="{e["id"]}" gridColumn="1 / 25" gridRow="{1+i*4} / {5+i*4}"/>'
                               for i, e in enumerate(HIDDEN_DATA_ELEMENTS))
                     + '</Page>')

def build():
    p1e, p1l = page1(); p2e, p2l = page2(); p3e, p3l = page3(); p4e, p4l = page4(); p5e, p5l = page5()
    all_elements = HIDDEN_DATA_ELEMENTS + p1e + p2e + p3e + p4e + p5e
    layout = ('<?xml version="1.0" encoding="utf-8"?>\n' + DATA_PAGE_LAYOUT + p1l + p2l + p3l + p4l + p5l)
    doc = {
        "schemaVersion": 1, "kind": "workbook",
        "elements": all_elements,
        "pages": [
            {"id": "pgData", "name": "Data", "visibility": "hidden"},
            {"id": "pgEvents", "name": "Events"},
            {"id": "pgFinance", "name": "Finance - Targets"},
            {"id": "pgApprovals", "name": "Brand Council"},
            {"id": "pgScorecard", "name": "Event Scorecard"},
            {"id": "pgAnnual", "name": "Annual Scorecard"},
        ],
        "settings": {"theme": {"overrides": THEME}},
        "layout": layout,
    }
    return {"name": "Pacific Life -- Brand Scorecard", "folderId": FOLDER, "document": doc}

def post(spec):
    data = json.dumps(spec).encode()
    req = urllib.request.Request(BASE + "/v2/workbooks/spec", data=data, headers=H, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=120)
        body = resp.read().decode()
        return True, body
    except urllib.error.HTTPError as e:
        return False, e.read().decode()

if __name__ == "__main__":
    spec = build()
    with open("spec.json", "w") as f:
        json.dump(spec, f, indent=2)
    print(f"wrote spec.json ({len(json.dumps(spec))} bytes)", file=sys.stderr)
    ok, body = post(spec)
    print("POST", "OK" if ok else "FAILED", file=sys.stderr)
    print(body[:4000])
    if not ok:
        sys.exit(1)
