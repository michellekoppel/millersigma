#!/usr/bin/env python3
"""Assemble the Alliant Insurance Group - Loss Run Analytics workbook spec
(new 2026-08 document{} envelope) and write it to spec_draft.json."""
import json

SCRATCH = "/tmp/claude-0/-home-user-millersigma/4706fb90-7ebb-51e4-87f3-b8ea4078388e/scratchpad"
CONNECTION_ID = "9e79f38b-a310-405c-aad9-72f762ac6ff1"  # Snowflake, verified in this org
FOLDER_ID = "004d8497-18ea-4cf6-a8c5-deca403c22d9"       # Michelle Koppel / My Documents

with open(f"{SCRATCH}/claims_values.sql") as f:
    CLAIMS_VALUES = f.read()
with open(f"{SCRATCH}/premium_values.sql") as f:
    PREMIUM_VALUES = f.read()
with open(f"{SCRATCH}/claim_queue_values.sql") as f:
    CLAIM_QUEUE_VALUES = f.read()

CLAIMS_RAW_COLS = [
    "ROW_TYPE", "POLICY_YEAR", "LINE_OF_BUSINESS", "CLAIM_STATUS",
    "DEV_PERIOD_MONTHS", "VALUATION_YEAR", "EARNED_PREMIUM",
    "PAID_LOSS", "CASE_RESERVE", "CLAIM_COUNT", "POLICY_COUNT",
    "IS_LATEST_VALUATION", "JOIN_KEY", "POLICY_YEAR_DATE",
]
PREMIUM_RAW_COLS = [
    "ROW_TYPE", "POLICY_YEAR", "LINE_OF_BUSINESS", "CLAIM_STATUS",
    "DEV_PERIOD_MONTHS", "VALUATION_YEAR", "EARNED_PREMIUM",
    "PAID_LOSS", "CASE_RESERVE", "CLAIM_COUNT", "POLICY_COUNT",
    "JOIN_KEY", "POLICY_YEAR_DATE",
]

CLAIMS_SQL = f"SELECT * FROM (VALUES\n    {CLAIMS_VALUES}\n) AS t({', '.join(CLAIMS_RAW_COLS)})"
PREMIUM_SQL = f"SELECT * FROM (VALUES\n    {PREMIUM_VALUES}\n) AS t({', '.join(PREMIUM_RAW_COLS)})"

CLAIM_QUEUE_RAW_COLS = [
    "CLAIM_ID", "POLICY_YEAR", "LINE_OF_BUSINESS", "CLAIM_STATUS",
    "PAID_TO_DATE", "CASE_RESERVE", "INCURRED", "DAYS_OPEN", "REPORTED_DATE",
]
CLAIM_QUEUE_SQL = f"SELECT * FROM (VALUES\n    {CLAIM_QUEUE_VALUES}\n) AS t({', '.join(CLAIM_QUEUE_RAW_COLS)})"

# ---------------------------------------------------------------------------
# Brand kit (lifted from the reference Alliant Interactive Analytics dashboard)
# ---------------------------------------------------------------------------
NAVY = "#1b3a5c"
TEAL = "#5fbfc0"
AMBER = "#e8a33d"
DARK_TEAL = "#2e8b8b"
GRAY = "#9ca3af"
CARD_BG = "#dce4ee"
WORDMARK_TEAL = "#8FD8D6"
LOGO_DATA_URI = (
    "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMDAiIGhlaWdodD0iMTAwIiB2aWV3Qm94PSIwIDAgMTAwIDEwMCI+"
    "CjxjaXJjbGUgY3g9IjM2IiBjeT0iNDAiIHI9IjMwIiBmaWxsPSIjOEZEOEQ2IiBvcGFjaXR5PSIwLjkyIi8+"
    "CjxjaXJjbGUgY3g9IjYyIiBjeT0iNTYiIHI9IjI2IiBmaWxsPSIjMkU4QjhCIiBvcGFjaXR5PSIwLjkyIi8+Cjwvc3ZnPg=="
)

elements = []
layouts = {}  # page_id -> list of XML lines (children of <Page>)


def add_layout(page_id, xml_line):
    layouts.setdefault(page_id, []).append(xml_line)


def col(id_, formula, name=None, format_=None):
    d = {"id": id_, "formula": formula}
    if name:
        d["name"] = name
    if format_:
        d["format"] = format_
    return d


CURRENCY_FMT = {"kind": "number", "formatString": "$,.0f"}
PCT_FMT = {"kind": "number", "formatString": ".1%"}
NUM_FMT = {"kind": "number", "formatString": ",.0f"}

# ---------------------------------------------------------------------------
# tbl-claims -- the ONE large dataset (336 rows: claim snapshots at every
# development period). Passthrough columns + calculated/masked columns.
# ---------------------------------------------------------------------------
tbl_claims = {
    "id": "tbl-claims", "kind": "table", "name": "Claims",
    "source": {"kind": "sql", "connectionId": CONNECTION_ID, "statement": CLAIMS_SQL},
    "columns": [
        col("cl-policy-year", "[Custom SQL/POLICY_YEAR]", "Policy Year"),
        col("cl-lob", "[Custom SQL/LINE_OF_BUSINESS]", "Line of Business"),
        col("cl-status", "[Custom SQL/CLAIM_STATUS]", "Claim Status"),
        col("cl-dev-period", "[Custom SQL/DEV_PERIOD_MONTHS]", "Development Period (Months)"),
        col("cl-valuation-year", "[Custom SQL/VALUATION_YEAR]", "Valuation Year"),
        col("cl-paid", "[Custom SQL/PAID_LOSS]", "Paid Loss", CURRENCY_FMT),
        col("cl-reserve", "[Custom SQL/CASE_RESERVE]", "Case Reserve", CURRENCY_FMT),
        col("cl-claimcount", "[Custom SQL/CLAIM_COUNT]", "Claim Count"),
        col("cl-is-latest", "[Custom SQL/IS_LATEST_VALUATION]", "Is Latest Valuation"),
        col("cl-joinkey", "[Custom SQL/JOIN_KEY]", "Join Key"),
        col("cl-year-date", "[Custom SQL/POLICY_YEAR_DATE]", "Policy Year Date"),
        # Derived
        col("cl-incurred", "[Paid Loss] + [Case Reserve]", "Incurred Loss", CURRENCY_FMT),
        col("cl-latest-paid", 'If([Is Latest Valuation] = 1, [Paid Loss], 0)', "Latest Paid", CURRENCY_FMT),
        col("cl-latest-reserve", 'If([Is Latest Valuation] = 1, [Case Reserve], 0)', "Latest Reserve", CURRENCY_FMT),
        col("cl-latest-incurred", 'If([Is Latest Valuation] = 1, [Incurred Loss], 0)', "Latest Incurred", CURRENCY_FMT),
        col("cl-latest-claimcount", 'If([Is Latest Valuation] = 1, [Claim Count], 0)', "Latest Claim Count"),
    ],
}
elements.append(tbl_claims)

# ---------------------------------------------------------------------------
# tbl-premium -- small reference table (28 rows: policy_year x LOB premium)
# ---------------------------------------------------------------------------
tbl_premium = {
    "id": "tbl-premium", "kind": "table", "name": "Premium",
    "source": {"kind": "sql", "connectionId": CONNECTION_ID, "statement": PREMIUM_SQL},
    "columns": [
        col("pr-policy-year", "[Custom SQL/POLICY_YEAR]", "Policy Year"),
        col("pr-lob", "[Custom SQL/LINE_OF_BUSINESS]", "Line of Business"),
        col("pr-premium", "[Custom SQL/EARNED_PREMIUM]", "Earned Premium", CURRENCY_FMT),
        col("pr-policycount", "[Custom SQL/POLICY_COUNT]", "Policy Count"),
        col("pr-joinkey", "[Custom SQL/JOIN_KEY]", "Join Key"),
        col("pr-year-date", "[Custom SQL/POLICY_YEAR_DATE]", "Policy Year Date"),
    ],
}
elements.append(tbl_premium)

# ---------------------------------------------------------------------------
# tbl-loss-ratio -- aggregated sibling, grain = policy_year x LOB (join_key).
# Sum() of tbl-claims' latest_* masked columns + Lookup() premium/policies.
# ---------------------------------------------------------------------------
tbl_loss_ratio = {
    "id": "tbl-loss-ratio", "kind": "table", "name": "Policy Year LOB Summary",
    "source": {"kind": "table", "elementId": "tbl-claims"},
    "columns": [
        col("lr-joinkey", "[Claims/Join Key]", "Join Key"),
        col("lr-policy-year", "Max([Claims/Policy Year])", "Policy Year"),
        col("lr-year-date", "Max([Claims/Policy Year Date])", "Policy Year Date"),
        col("lr-lob", "Max([Claims/Line of Business])", "Line of Business"),
        col("lr-incurred", "Sum([Claims/Latest Incurred])", "Incurred (Current)", CURRENCY_FMT),
        col("lr-paid", "Sum([Claims/Latest Paid])", "Paid (Current)", CURRENCY_FMT),
        col("lr-reserve", "Sum([Claims/Latest Reserve])", "Reserve (Current)", CURRENCY_FMT),
        col("lr-claimcount", "Sum([Claims/Latest Claim Count])", "Claim Count (Current)"),
        col("lr-premium", "Lookup([Premium/Earned Premium], [Join Key], [Premium/Join Key])", "Earned Premium", CURRENCY_FMT),
        col("lr-policycount", "Lookup([Premium/Policy Count], [Join Key], [Premium/Join Key])", "Policy Count"),
        col("lr-lossratio", "[Incurred (Current)] / [Earned Premium]", "Loss Ratio", PCT_FMT),
        col("lr-frequency", "[Claim Count (Current)] / [Policy Count] * 100", "Frequency (per 100 policies)"),
        col("lr-severity", "[Incurred (Current)] / [Claim Count (Current)]", "Severity (Avg Cost per Claim)", CURRENCY_FMT),
        # Whole-book scalars (summary grain -- one value broadcast to every
        # row). Downstream KPIs read these via Max(), NOT Sum(): re-summing a
        # column from an already-grouped sibling re-expands through the raw
        # ancestor and fans out (verified live -- Sum() inflated Total
        # Incurred ~14x). Max() of a broadcast constant is fan-out-proof.
        col("bk-incurred", "Sum([Incurred (Current)])", "Book Incurred", CURRENCY_FMT),
        col("bk-paid", "Sum([Paid (Current)])", "Book Paid", CURRENCY_FMT),
        col("bk-reserve", "Sum([Reserve (Current)])", "Book Reserve", CURRENCY_FMT),
        col("bk-claimcount", "Sum([Claim Count (Current)])", "Book Claim Count"),
        col("bk-premium", "Sum([Earned Premium])", "Book Premium", CURRENCY_FMT),
        col("bk-policycount", "Sum([Policy Count])", "Book Policy Count"),
        col("bk-lossratio", "[Book Incurred] / [Book Premium]", "Book Loss Ratio", PCT_FMT),
        col("bk-frequency", "[Book Claim Count] / [Book Policy Count] * 100", "Book Frequency"),
        col("bk-severity", "[Book Incurred] / [Book Claim Count]", "Book Severity", CURRENCY_FMT),
    ],
    "groupings": [{
        "id": "grp-loss-ratio",
        "groupBy": ["lr-joinkey"],
        "calculations": [
            "lr-policy-year", "lr-year-date", "lr-lob", "lr-incurred", "lr-paid",
            "lr-reserve", "lr-claimcount", "lr-premium", "lr-policycount",
            "lr-lossratio", "lr-frequency", "lr-severity",
        ],
    }],
    "summary": [
        "bk-incurred", "bk-paid", "bk-reserve", "bk-claimcount", "bk-premium",
        "bk-policycount", "bk-lossratio", "bk-frequency", "bk-severity",
    ],
}
elements.append(tbl_loss_ratio)

# ---------------------------------------------------------------------------
# tbl-lob-summary -- grouped by LOB only, one hop off tbl-claims (NOT off
# tbl-loss-ratio -- re-grouping an already-grouped sibling at a different
# grain fans out through the raw ancestor; verified live, see notes above).
# ---------------------------------------------------------------------------
tbl_lob_summary = {
    "id": "tbl-lob-summary", "kind": "table", "name": "LOB Summary",
    "source": {"kind": "table", "elementId": "tbl-claims"},
    "columns": [
        col("ls-lob", "[Claims/Line of Business]", "Line of Business"),
        col("ls-incurred", "Sum([Claims/Latest Incurred])", "Incurred (Current)", CURRENCY_FMT),
    ],
    "groupings": [{"id": "grp-lob-summary", "groupBy": ["ls-lob"], "calculations": ["ls-incurred"]}],
}
elements.append(tbl_lob_summary)

# ---------------------------------------------------------------------------
# tbl-year-premium -- premium/policy-count grouped by policy year only (one
# hop off tbl-premium). Lookup target for tbl-year-summary below.
# ---------------------------------------------------------------------------
tbl_year_premium = {
    "id": "tbl-year-premium", "kind": "table", "name": "Year Premium Summary",
    "source": {"kind": "table", "elementId": "tbl-premium"},
    "columns": [
        col("yp-year-date", "[Premium/Policy Year Date]", "Policy Year Date"),
        col("yp-premium", "Sum([Premium/Earned Premium])", "Earned Premium", CURRENCY_FMT),
        col("yp-policycount", "Sum([Premium/Policy Count])", "Policy Count"),
    ],
    "groupings": [{"id": "grp-year-premium", "groupBy": ["yp-year-date"], "calculations": ["yp-premium", "yp-policycount"]}],
}
elements.append(tbl_year_premium)

# ---------------------------------------------------------------------------
# tbl-year-summary -- claims grouped by policy year only (one hop off
# tbl-claims), Lookup-joined to tbl-year-premium (symmetric grouped-to-
# grouped join, the same safe shape tbl-loss-ratio itself uses).
# ---------------------------------------------------------------------------
tbl_year_summary = {
    "id": "tbl-year-summary", "kind": "table", "name": "Year Summary",
    "source": {"kind": "table", "elementId": "tbl-claims"},
    "columns": [
        col("ys-year-date", "[Claims/Policy Year Date]", "Policy Year Date"),
        col("ys-incurred", "Sum([Claims/Latest Incurred])", "Incurred (Current)", CURRENCY_FMT),
        col("ys-claimcount", "Sum([Claims/Latest Claim Count])", "Claim Count (Current)"),
        col("ys-premium", "Lookup([Year Premium Summary/Earned Premium], [Policy Year Date], [Year Premium Summary/Policy Year Date])", "Earned Premium", CURRENCY_FMT),
        col("ys-policycount", "Lookup([Year Premium Summary/Policy Count], [Policy Year Date], [Year Premium Summary/Policy Year Date])", "Policy Count"),
        col("ys-frequency", "[Claim Count (Current)] / [Policy Count] * 100", "Frequency (per 100 policies)"),
        col("ys-severity", "[Incurred (Current)] / [Claim Count (Current)]", "Severity (Avg Cost per Claim)", CURRENCY_FMT),
    ],
    "groupings": [{
        "id": "grp-year-summary", "groupBy": ["ys-year-date"],
        "calculations": ["ys-incurred", "ys-claimcount", "ys-premium", "ys-policycount", "ys-frequency", "ys-severity"],
    }],
}
elements.append(tbl_year_summary)

# ---------------------------------------------------------------------------
# tbl-detail-view -- current-position detail, grain = policy_year x LOB x
# status (join_key + status). Placed directly on the Claims Detail page (its
# OWN native groupings, so Sigma's UI collapses it to one row per group
# instead of leaf-joining back to the raw per-dev-period rows).
# ---------------------------------------------------------------------------
tbl_detail_view = {
    "id": "tbl-detail-view", "kind": "table", "name": "Claims Detail Table",
    "source": {"kind": "table", "elementId": "tbl-claims"},
    "columns": [
        col("cd-policy-year", "Max([Claims/Policy Year])", "Policy Year"),
        col("cd-lob", "Max([Claims/Line of Business])", "Line of Business"),
        col("cd-status", "[Claims/Claim Status]", "Claim Status"),
        col("cd-incurred", "Sum([Claims/Latest Incurred])", "Incurred", CURRENCY_FMT),
        col("cd-paid", "Sum([Claims/Latest Paid])", "Paid to Date", CURRENCY_FMT),
        col("cd-reserve", "Sum([Claims/Latest Reserve])", "Case Reserve", CURRENCY_FMT),
        col("cd-claimcount", "Sum([Claims/Latest Claim Count])", "Claim Count"),
        col("cd-severity", "[Incurred] / [Claim Count]", "Avg Severity", CURRENCY_FMT),
        col("cd-joinkey", "[Claims/Join Key]", "Join Key"),
    ],
    "groupings": [{
        "id": "grp-current-detail",
        "groupBy": ["cd-joinkey", "cd-status"],
        "calculations": [
            "cd-policy-year", "cd-lob", "cd-incurred", "cd-paid",
            "cd-reserve", "cd-claimcount", "cd-severity",
        ],
    }],
}
elements.append(tbl_detail_view)

# ---------------------------------------------------------------------------
# tbl-triangle -- row-level (all dev periods), adds the Incurred/Paid toggle
# value driven by the Mode segmented control. Feeds the pivot triangle.
# ---------------------------------------------------------------------------
tbl_triangle = {
    "id": "tbl-triangle", "kind": "table", "name": "Triangle Detail",
    "source": {"kind": "table", "elementId": "tbl-claims"},
    "columns": [
        col("tr-policy-year", "[Claims/Policy Year]", "Policy Year"),
        col("tr-dev-period", "[Claims/Development Period (Months)]", "Development Period (Months)"),
        col("tr-lob", "[Claims/Line of Business]", "Line of Business"),
        col("tr-status", "[Claims/Claim Status]", "Claim Status"),
        col("tr-incurred", "[Claims/Incurred Loss]", "Incurred Loss"),
        col("tr-paid", "[Claims/Paid Loss]", "Paid Loss"),
        col("tr-value", 'If([Mode] = "Paid", [Paid Loss], [Incurred Loss])', "Triangle Value"),
    ],
}
elements.append(tbl_triangle)

# ---------------------------------------------------------------------------
# Reserve Review Workbench -- the app/actions tab.
#
# tbl-claim-queue: individual synthetic claim records (Open/Reopened only,
# latest valuation), expanded from the same cohort totals already in
# tbl-claims (see gen_claim_queue.py) -- a realistic per-claim work queue,
# read-only. it-review-log: an EMPTY, append-only input table that a
# "Submit Review" button writes to via insert-rows -- the actual action.
# ---------------------------------------------------------------------------
tbl_claim_queue = {
    "id": "tbl-claim-queue", "kind": "table", "name": "Claim Queue",
    "source": {"kind": "sql", "connectionId": CONNECTION_ID, "statement": CLAIM_QUEUE_SQL},
    "columns": [
        col("cq-claimid", "[Custom SQL/CLAIM_ID]", "Claim ID"),
        col("cq-policy-year", "[Custom SQL/POLICY_YEAR]", "Policy Year"),
        col("cq-lob", "[Custom SQL/LINE_OF_BUSINESS]", "Line of Business"),
        col("cq-status", "[Custom SQL/CLAIM_STATUS]", "Claim Status"),
        col("cq-paid", "[Custom SQL/PAID_TO_DATE]", "Paid to Date", CURRENCY_FMT),
        col("cq-reserve", "[Custom SQL/CASE_RESERVE]", "Case Reserve", CURRENCY_FMT),
        col("cq-incurred", "[Custom SQL/INCURRED]", "Incurred", CURRENCY_FMT),
        col("cq-days-open", "[Custom SQL/DAYS_OPEN]", "Days Open"),
        col("cq-reported", "[Custom SQL/REPORTED_DATE]", "Reported Date"),
    ],
    "order": ["cq-claimid", "cq-policy-year", "cq-lob", "cq-status", "cq-reserve",
              "cq-paid", "cq-incurred", "cq-days-open", "cq-reported"],
    "sort": [{"columnId": "cq-reserve", "direction": "descending"}],
}
elements.append(tbl_claim_queue)

it_review_log = {
    "id": "it-review-log", "kind": "input-table", "name": "Reserve Review Log",
    "source": {"kind": "empty", "connectionId": CONNECTION_ID},
    "inputMode": "edit",
    "columns": [
        {"id": "rl-claimid", "type": "text", "name": "Claim ID"},
        {"id": "rl-note", "type": "text", "name": "Reviewer Note"},
        {"id": "rl-decision", "type": "text", "name": "Decision",
         "values": ["Reserve Confirmed", "Reserve Adjusted", "Escalated"],
         "pills": "color-by-option"},
        {"id": "rl-adjusted", "type": "number", "name": "Adjusted Reserve", "format": CURRENCY_FMT},
        {"id": "CREATED_AT"},
        {"id": "CREATED_BY"},
    ],
    "sort": [{"columnId": "CREATED_AT", "direction": "descending"}],
}
elements.append(it_review_log)

# ---------------------------------------------------------------------------
# Review-form controls (page-scoped; not wired to filters[] on any other
# element -- these are parameters for the Submit Review action, not filters).
# ---------------------------------------------------------------------------
ctrl_rr_claim = {
    "kind": "control", "id": "ctrl-rr-claim", "controlId": "rr-claim", "name": "Select Claim",
    "controlType": "list", "mode": "include", "selectionMode": "single", "values": [],
    "source": {"kind": "source", "source": {"kind": "table", "elementId": "tbl-claim-queue"}, "columnId": "cq-claimid"},
}
ctrl_rr_decision = {
    "kind": "control", "id": "ctrl-rr-decision", "controlId": "rr-decision", "name": "Decision",
    "controlType": "segmented", "value": "Reserve Confirmed",
    "source": {"kind": "manual", "valueType": "text",
               "values": ["Reserve Confirmed", "Reserve Adjusted", "Escalated"],
               "labels": ["Confirm Reserve", "Adjust Reserve", "Escalate"]},
}
ctrl_rr_adjusted = {
    "kind": "control", "id": "ctrl-rr-adjusted", "controlId": "rr-adjusted", "name": "Adjusted Reserve ($, if applicable)",
    "controlType": "text", "mode": "equals", "case": "insensitive", "value": "",
}
ctrl_rr_note = {
    "kind": "control", "id": "ctrl-rr-note", "controlId": "rr-note", "name": "Reviewer Note",
    "controlType": "text", "mode": "equals", "case": "insensitive", "value": "",
}
elements += [ctrl_rr_claim, ctrl_rr_decision, ctrl_rr_adjusted, ctrl_rr_note]

btn_submit_review = {
    "id": "btn-submit-review", "kind": "button", "text": "Submit Review",
    "appearance": "filled", "fillColor": NAVY,
    "actions": [{
        "id": "act-submit-review",
        "trigger": "on-click",
        "successToast": {"showMessage": "shown", "title": "Review logged",
                          "message": "The reserve review was added to the log below."},
        "effects": [
            {
                "effect": "insert-rows",
                "tableElementId": "it-review-log",
                "values": {
                    "rl-claimid": {"type": "control", "control": "rr-claim"},
                    "rl-note": {"type": "control", "control": "rr-note"},
                    "rl-decision": {"type": "control", "control": "rr-decision"},
                    "rl-adjusted": {"type": "formula", "formula": "Number([rr-adjusted])"},
                },
            },
            {"effect": "clear-control", "scope": {"type": "control", "controlId": "rr-claim"}},
            {"effect": "clear-control", "scope": {"type": "control", "controlId": "rr-note"}},
            {"effect": "clear-control", "scope": {"type": "control", "controlId": "rr-adjusted"}},
            {"effect": "refresh-element", "target": {"type": "element", "element": "it-review-log"}},
        ],
    }],
}
elements.append(btn_submit_review)

print("base + derived elements built:", len(elements))

# ---------------------------------------------------------------------------
# Global filter controls (placed once, on Command Center; cascade to every
# page because Triangle/Detail/Assistant all two-tier source off tbl-claims).
# ---------------------------------------------------------------------------
ctrl_lob = {
    "kind": "control", "id": "ctrl-lob", "controlId": "LOB", "name": "Line of Business",
    "controlType": "list", "mode": "include", "selectionMode": "multiple", "values": [],
    "source": {"kind": "source", "source": {"kind": "table", "elementId": "tbl-claims"}, "columnId": "cl-lob"},
    "filters": [
        {"source": {"kind": "table", "elementId": "tbl-claims"}, "columnId": "cl-lob"},
        {"source": {"kind": "table", "elementId": "tbl-premium"}, "columnId": "pr-lob"},
    ],
}
ctrl_policy_year = {
    "kind": "control", "id": "ctrl-policyyear", "controlId": "PolicyYear", "name": "Policy Year",
    "controlType": "list", "mode": "include", "selectionMode": "multiple", "values": [],
    "source": {"kind": "source", "source": {"kind": "table", "elementId": "tbl-claims"}, "columnId": "cl-policy-year"},
    "filters": [
        {"source": {"kind": "table", "elementId": "tbl-claims"}, "columnId": "cl-policy-year"},
        {"source": {"kind": "table", "elementId": "tbl-premium"}, "columnId": "pr-policy-year"},
    ],
}
ctrl_status = {
    "kind": "control", "id": "ctrl-status", "controlId": "Status", "name": "Claim Status",
    "controlType": "list", "mode": "include", "selectionMode": "multiple", "values": [],
    "source": {"kind": "source", "source": {"kind": "table", "elementId": "tbl-claims"}, "columnId": "cl-status"},
    "filters": [
        {"source": {"kind": "table", "elementId": "tbl-claims"}, "columnId": "cl-status"},
    ],
}
ctrl_mode = {
    "kind": "control", "id": "ctrl-mode", "controlId": "Mode", "name": "Triangle View",
    "controlType": "segmented", "value": "Incurred",
    "source": {"kind": "manual", "valueType": "text", "values": ["Incurred", "Paid"], "labels": ["Incurred", "Paid"]},
}
elements += [ctrl_lob, ctrl_policy_year, ctrl_status, ctrl_mode]

# ---------------------------------------------------------------------------
# Masthead: logo, title, wordmark, subtitle
# ---------------------------------------------------------------------------
def masthead(page_key, title_body, subtitle_body):
    return [
        {"id": f"img-logo-{page_key}", "kind": "image",
         "source": {"kind": "url", "url": LOGO_DATA_URI}},
        {"id": f"txt-title-{page_key}", "kind": "text",
         "body": f'### <span style="color: #FFFFFF">**{title_body}**</span>'},
        {"id": f"txt-brand-{page_key}", "kind": "text",
         "body": f'<p style="text-align: right"><span style="font-size: 16px; color: {WORDMARK_TEAL}">ALLIANT</span></p>'},
        {"id": f"txt-sub-{page_key}", "kind": "text",
         "body": f'<p class="p-small"><span style="color: #FFFFFF">{subtitle_body}</span></p>'},
    ]

print("controls + masthead helper ready")

# ---------------------------------------------------------------------------
# Navigation (every visible page needs its own instance, same options list)
# ---------------------------------------------------------------------------
NAV_OPTIONS = [
    {"label": "Command Center", "destination": {"type": "page", "pageId": "page-command"}},
    {"label": "Loss Triangle", "destination": {"type": "page", "pageId": "page-triangle"}},
    {"label": "Claims Detail", "destination": {"type": "page", "pageId": "page-detail"}},
    {"label": "Loss Run Assistant", "destination": {"type": "page", "pageId": "page-assistant"}},
    {"label": "Reserve Review", "destination": {"type": "page", "pageId": "page-reserve"}},
]


def nav_element(page_key):
    return {
        "id": f"nav-{page_key}", "kind": "navigation", "mode": "manual", "showIcons": False,
        "style": {"backgroundColor": "transparent"},
        "optionStyle": {"textColor": "#FFFFFF", "selectedColor": WORDMARK_TEAL,
                         "style": "pill", "orientation": "horizontal"},
        "options": NAV_OPTIONS,
    }


# ---------------------------------------------------------------------------
# KPI helper
# ---------------------------------------------------------------------------
def kpi(id_, name, source_id, value_formula, date_col_ref=None, value_format=None, extra_cols=None):
    columns = []
    if date_col_ref:
        columns.append(col(f"{id_}-date", date_col_ref, "Date"))
    if extra_cols:
        columns += extra_cols
    columns.append(col(f"{id_}-value", value_formula, name, value_format))
    return {
        "id": id_, "kind": "kpi-chart", "name": name,
        "source": {"kind": "table", "elementId": source_id},
        "columns": columns,
        "value": {"columnId": f"{id_}-value"},
    }


# Whole-book KPIs read the `summary` scalars via Max() -- fan-out-proof
# (see the comment on tbl-loss-ratio's `summary` block). No date dimension:
# these are current-snapshot totals, not a period series, so a sparkline
# would just be a flat, non-informative line.
kpi_incurred = kpi("kpi-incurred", "Total Incurred", "tbl-loss-ratio",
                    "Max([Policy Year LOB Summary/Book Incurred])", value_format=CURRENCY_FMT)
kpi_paid = kpi("kpi-paid", "Paid to Date", "tbl-loss-ratio",
               "Max([Policy Year LOB Summary/Book Paid])", value_format=CURRENCY_FMT)
kpi_reserve = kpi("kpi-reserve", "Case Reserve Outstanding", "tbl-loss-ratio",
                   "Max([Policy Year LOB Summary/Book Reserve])", value_format=CURRENCY_FMT)
kpi_lossratio = kpi("kpi-lossratio", "Loss Ratio", "tbl-loss-ratio",
                     "Max([Policy Year LOB Summary/Book Loss Ratio])", value_format=PCT_FMT)
kpi_frequency = kpi("kpi-frequency", "Claim Frequency (per 100 policies)", "tbl-loss-ratio",
                     "Max([Policy Year LOB Summary/Book Frequency])")
kpi_severity = kpi("kpi-severity", "Avg Severity per Claim", "tbl-loss-ratio",
                    "Max([Policy Year LOB Summary/Book Severity])", value_format=CURRENCY_FMT)
elements += [kpi_incurred, kpi_paid, kpi_reserve, kpi_lossratio, kpi_frequency, kpi_severity]

# small assistant-page KPIs (reuse same summary scalars, distinct ids)
kpi_a_incurred = kpi("kpi-a-incurred", "Total Incurred", "tbl-loss-ratio",
                      "Max([Policy Year LOB Summary/Book Incurred])", value_format=CURRENCY_FMT)
kpi_a_lossratio = kpi("kpi-a-lossratio", "Loss Ratio", "tbl-loss-ratio",
                       "Max([Policy Year LOB Summary/Book Loss Ratio])", value_format=PCT_FMT)
kpi_a_claimcount = kpi("kpi-a-claimcount", "Claim Count", "tbl-loss-ratio",
                        "Max([Policy Year LOB Summary/Book Claim Count])")
elements += [kpi_a_incurred, kpi_a_lossratio, kpi_a_claimcount]

# Reserve Review page KPIs
kpi_rr_pending = kpi("kpi-rr-pending", "Claims Pending Review", "tbl-claim-queue",
                      "Count([Claim Queue/Claim ID])")
kpi_rr_reserve = kpi("kpi-rr-reserve", "Reserve Under Review", "tbl-claim-queue",
                      "Sum([Claim Queue/Case Reserve])", value_format=CURRENCY_FMT)
kpi_rr_reviewed = kpi("kpi-rr-reviewed", "Reviews Logged", "it-review-log",
                       "Count([Reserve Review Log/Claim ID])")
elements += [kpi_rr_pending, kpi_rr_reserve, kpi_rr_reviewed]

print("KPIs built")

# ---------------------------------------------------------------------------
# Charts (Command Center)
# ---------------------------------------------------------------------------
chart_loss_ratio_trend = {
    "id": "chart-lossratio-trend", "kind": "line-chart", "name": "Loss Ratio by Policy Year",
    "source": {"kind": "table", "elementId": "tbl-loss-ratio"},
    "columns": [
        col("lrt-year", "[Policy Year LOB Summary/Policy Year Date]", "Policy Year"),
        col("lrt-lob", "[Policy Year LOB Summary/Line of Business]", "Line of Business"),
        col("lrt-ratio", "Max([Policy Year LOB Summary/Loss Ratio])", "Loss Ratio", PCT_FMT),
    ],
    "xAxis": {"columnId": "lrt-year"},
    "yAxis": {"columnIds": ["lrt-ratio"]},
    "color": {"by": "category", "column": "lrt-lob"},
}

chart_frequency_trend = {
    "id": "chart-frequency-trend", "kind": "bar-chart", "name": "Claim Frequency Trend (per 100 policies)",
    "source": {"kind": "table", "elementId": "tbl-year-summary"},
    "columns": [
        col("fq-year", "[Year Summary/Policy Year Date]", "Policy Year"),
        col("fq-freq", "Max([Year Summary/Frequency (per 100 policies)])", "Frequency (per 100 policies)"),
    ],
    "xAxis": {"columnId": "fq-year"},
    "yAxis": {"columnIds": ["fq-freq"]},
}

chart_severity_trend = {
    "id": "chart-severity-trend", "kind": "line-chart", "name": "Avg Severity per Claim Trend",
    "source": {"kind": "table", "elementId": "tbl-year-summary"},
    "columns": [
        col("sv-year", "[Year Summary/Policy Year Date]", "Policy Year"),
        col("sv-sev", "Max([Year Summary/Severity (Avg Cost per Claim)])", "Avg Severity", CURRENCY_FMT),
    ],
    "xAxis": {"columnId": "sv-year"},
    "yAxis": {"columnIds": ["sv-sev"]},
}

chart_incurred_by_lob = {
    "id": "chart-incurred-by-lob", "kind": "bar-chart", "name": "Incurred Loss by Line of Business",
    "source": {"kind": "table", "elementId": "tbl-lob-summary"},
    "columns": [
        col("ibl-lob", "[LOB Summary/Line of Business]", "Line of Business"),
        col("ibl-incurred", "Max([LOB Summary/Incurred (Current)])", "Incurred Loss", CURRENCY_FMT),
    ],
    "xAxis": {"columnId": "ibl-lob", "sort": {"by": "ibl-incurred", "direction": "descending"}},
    "yAxis": {"columnIds": ["ibl-incurred"]},
}
elements += [chart_loss_ratio_trend, chart_frequency_trend, chart_severity_trend, chart_incurred_by_lob]

# ---------------------------------------------------------------------------
# Loss Triangle: pivot table
# ---------------------------------------------------------------------------
pivot_triangle = {
    "id": "pivot-triangle", "kind": "pivot-table", "name": "Loss Development Triangle",
    "source": {"kind": "table", "elementId": "tbl-triangle"},
    "columns": [
        col("pvt-year", "[Triangle Detail/Policy Year]", "Policy Year"),
        col("pvt-dev", "[Triangle Detail/Development Period (Months)]", "Development Period (Months)"),
        col("pvt-value", "Sum([Triangle Detail/Triangle Value])", "Loss ($)"),
    ],
    "rowsBy": [{"columnId": "pvt-year"}],
    "columnsBy": [{"columnId": "pvt-dev"}],
    "values": ["pvt-value"],
}
elements.append(pivot_triangle)


print("charts + pivot + detail table built")

# ---------------------------------------------------------------------------
# Chat agent: Loss Run Assistant
# ---------------------------------------------------------------------------
agent_lossrun = {
    "id": "ag-lossrun",
    "name": "Loss Run Assistant",
    "description": "Helps an analyst slice Alliant's loss run by line of business, policy year, and claim status, and narrates the resulting incurred, loss ratio, and frequency/severity.",
    "instructions": (
        "You are a loss-run analysis assistant for Alliant Insurance Group's book of business "
        "(Workers Comp, General Liability, Commercial Auto, Property; policy years 2019-2025). "
        "Help an analyst slice the loss run by line of business, policy year, and claim status "
        "(Open, Closed, Reopened) based on natural language. Never assume a constraint the user "
        "didn't specify -- leave it unset (all values) by default. After each change, summarize the "
        "resulting Total Incurred, Loss Ratio, Claim Frequency, and Avg Severity for that slice, and "
        "compare briefly to the unfiltered book of business so the analyst can see how the slice differs. "
        "Note that recent policy years (2024-2025) are immature -- their loss ratios will look "
        "artificially low because losses haven't fully developed yet -- call this out when relevant."
    ),
    "greeting": {
        "mode": "static",
        "message": "Ask me about Alliant's loss run -- for example, \"show me open Workers Comp claims from 2022 to 2024\" -- and I'll set the filters and summarize the results.",
    },
    "dataSources": [
        {"kind": "table", "elementId": "tbl-loss-ratio"},
        {"kind": "table", "elementId": "tbl-claims"},
    ],
    "tools": [
        {
            "toolId": "t-lob", "kind": "action", "name": "Set line of business filter",
            "description": "Filter to one or more lines of business (Workers Comp, General Liability, Commercial Auto, Property).",
            "steps": [{"kind": "effect", "effect": "set-control-value", "control": "LOB",
                       "selectionMode": "add",
                       "value": {"type": "agent-input", "inputName": "Line(s) of business mentioned"}}],
        },
        {
            "toolId": "t-year", "kind": "action", "name": "Set policy year filter",
            "description": "Filter to one or more policy years between 2019 and 2025.",
            "steps": [{"kind": "effect", "effect": "set-control-value", "control": "PolicyYear",
                       "selectionMode": "add",
                       "value": {"type": "agent-input", "inputName": "Policy year(s) mentioned"}}],
        },
        {
            "toolId": "t-status", "kind": "action", "name": "Set claim status filter",
            "description": "Filter to one or more claim statuses (Open, Closed, Reopened).",
            "steps": [{"kind": "effect", "effect": "set-control-value", "control": "Status",
                       "selectionMode": "add",
                       "value": {"type": "agent-input", "inputName": "Claim status(es) mentioned"}}],
        },
        {
            "toolId": "t-clear", "kind": "action", "name": "Clear all filters",
            "description": "Reset line of business, policy year, and claim status back to the full book of business.",
            "steps": [
                {"kind": "effect", "effect": "clear-control", "scope": {"type": "control", "controlId": "LOB"}},
                {"kind": "effect", "effect": "clear-control", "scope": {"type": "control", "controlId": "PolicyYear"}},
                {"kind": "effect", "effect": "clear-control", "scope": {"type": "control", "controlId": "Status"}},
            ],
        },
    ],
}
agents = [agent_lossrun]

chat_assistant = {"id": "chat-assistant", "kind": "chat", "agentId": "ag-lossrun"}
elements.append(chat_assistant)

print("agent + chat element built. total elements:", len(elements))

# ---------------------------------------------------------------------------
# Masthead text/image elements + header containers per visible page
# ---------------------------------------------------------------------------
elements += masthead("command", "Alliant Insurance Group — Loss Run Analytics",
                      "Multi-year loss triangle, incurred and paid trends, and loss ratio by line of business")
elements += masthead("triangle", "Loss Development Triangle",
                      "Cumulative incurred / paid loss by policy year and development period")
elements += masthead("detail", "Claims Detail",
                      "Current-position claim detail by policy year, line of business, and status")
elements += masthead("assistant", "Loss Run Assistant",
                      "Ask the assistant to slice the book of business in natural language")
elements += masthead("reserve", "Reserve Review Workbench",
                      "Review open and reopened claims, confirm or adjust the reserve, and log the decision")

header_containers = [
    {"id": f"ctr-header-{k}", "kind": "container", "style": {"backgroundColor": NAVY, "borderRadius": "square"}}
    for k in ["command", "triangle", "detail", "assistant", "reserve"]
]
elements += header_containers

# Filter bar (Command Center only -- the shared global filters)
ctr_filters_command = {"id": "ctr-filters-command", "kind": "container", "style": {"backgroundColor": CARD_BG}}
elements.append(ctr_filters_command)

# KPI row + chart-body containers (Command Center)
ctr_kpis = {"id": "ctr-kpis-command", "kind": "container"}
elements.append(ctr_kpis)

# Triangle page: mode toggle strip
ctr_mode_bar = {"id": "ctr-mode-triangle", "kind": "container", "style": {"backgroundColor": CARD_BG}}
elements.append(ctr_mode_bar)

# Assistant page: KPI strip beside chat
ctr_kpis_assistant = {"id": "ctr-kpis-assistant", "kind": "container"}
elements.append(ctr_kpis_assistant)

# Reserve Review page: KPI strip + review-form panel
ctr_kpis_reserve = {"id": "ctr-kpis-reserve", "kind": "container"}
elements.append(ctr_kpis_reserve)
ctr_form_reserve = {
    "id": "ctr-form-reserve", "kind": "container",
    "style": {"backgroundColor": CARD_BG, "borderRadius": "round"},
}
elements.append(ctr_form_reserve)

elements += [
    {"id": "txt-queue-title-reserve", "kind": "text", "body": "### Claims Pending Review"},
    {"id": "txt-form-title-reserve", "kind": "text", "body": "### Log a Review"},
    {"id": "txt-log-title-reserve", "kind": "text", "body": "### Recent Review Activity"},
]

print("containers built. total elements:", len(elements))

# ---------------------------------------------------------------------------
# Layout XML
# ---------------------------------------------------------------------------
def E(eid, col_, row_):
    return f'<Element elementId="{eid}" gridColumn="{col_}" gridRow="{row_}"/>'


def C_open(eid, col_, row_, cols=24):
    return f'<Container elementId="{eid}" type="grid" gridColumn="{col_}" gridRow="{row_}" gridTemplateColumns="repeat({cols}, 1fr)" gridTemplateRows="auto">'


C_close = "</Container>"


def page_open(pid):
    return f'<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="{pid}">'


PAGE_CLOSE = "</Page>"


def header_block(key, nav_id):
    return "\n".join([
        C_open(f"ctr-header-{key}", "1 / 25", "1 / 4"),
        E(f"txt-title-{key}", "1 / 11", "1 / 3"),
        E(nav_id, "11 / 20", "1 / 3"),
        E(f"txt-brand-{key}", "20 / 24", "1 / 3"),
        E(f"img-logo-{key}", "24 / 25", "1 / 3"),
        E(f"txt-sub-{key}", "1 / 15", "3 / 4"),
        C_close,
    ])


# ---- page-command ----
page_command_xml = "\n".join([
    page_open("page-command"),
    header_block("command", "nav-command"),
    C_open("ctr-filters-command", "1 / 25", "4 / 6"),
    E("ctrl-lob", "1 / 9", "1 / 3"),
    E("ctrl-policyyear", "9 / 17", "1 / 3"),
    E("ctrl-status", "17 / 25", "1 / 3"),
    C_close,
    C_open("ctr-kpis-command", "1 / 25", "6 / 16"),
    E("kpi-incurred", "1 / 5", "1 / 11"),
    E("kpi-paid", "5 / 9", "1 / 11"),
    E("kpi-reserve", "9 / 13", "1 / 11"),
    E("kpi-lossratio", "13 / 17", "1 / 11"),
    E("kpi-frequency", "17 / 21", "1 / 11"),
    E("kpi-severity", "21 / 25", "1 / 11"),
    C_close,
    E("chart-lossratio-trend", "1 / 13", "16 / 32"),
    E("chart-frequency-trend", "13 / 25", "16 / 24"),
    E("chart-severity-trend", "13 / 25", "24 / 32"),
    E("chart-incurred-by-lob", "1 / 25", "32 / 46"),
    PAGE_CLOSE,
])

# ---- page-triangle ----
page_triangle_xml = "\n".join([
    page_open("page-triangle"),
    header_block("triangle", "nav-triangle"),
    C_open("ctr-mode-triangle", "1 / 25", "4 / 6"),
    E("ctrl-mode", "1 / 6", "1 / 3"),
    C_close,
    E("pivot-triangle", "1 / 25", "6 / 45"),
    PAGE_CLOSE,
])

# ---- page-detail ----
page_detail_xml = "\n".join([
    page_open("page-detail"),
    header_block("detail", "nav-detail"),
    E("tbl-detail-view", "1 / 25", "4 / 50"),
    PAGE_CLOSE,
])

# ---- page-assistant ----
page_assistant_xml = "\n".join([
    page_open("page-assistant"),
    header_block("assistant", "nav-assistant"),
    C_open("ctr-kpis-assistant", "1 / 9", "4 / 34"),
    E("kpi-a-incurred", "1 / 25", "1 / 11"),
    E("kpi-a-lossratio", "1 / 25", "11 / 21"),
    E("kpi-a-claimcount", "1 / 25", "21 / 31"),
    C_close,
    E("chat-assistant", "9 / 25", "4 / 40"),
    PAGE_CLOSE,
])

# ---- page-reserve ----
page_reserve_xml = "\n".join([
    page_open("page-reserve"),
    header_block("reserve", "nav-reserve"),
    C_open("ctr-kpis-reserve", "1 / 25", "4 / 14"),
    E("kpi-rr-pending", "1 / 9", "1 / 11"),
    E("kpi-rr-reserve", "9 / 17", "1 / 11"),
    E("kpi-rr-reviewed", "17 / 25", "1 / 11"),
    C_close,
    E("txt-queue-title-reserve", "1 / 25", "14 / 16"),
    E("tbl-claim-queue", "1 / 25", "16 / 40"),
    E("txt-form-title-reserve", "1 / 25", "40 / 42"),
    C_open("ctr-form-reserve", "1 / 25", "42 / 48"),
    E("ctrl-rr-claim", "1 / 7", "1 / 3"),
    E("ctrl-rr-decision", "7 / 13", "1 / 3"),
    E("ctrl-rr-adjusted", "13 / 18", "1 / 3"),
    E("ctrl-rr-note", "18 / 23", "1 / 3"),
    E("btn-submit-review", "23 / 25", "1 / 3"),
    C_close,
    E("txt-log-title-reserve", "1 / 25", "48 / 50"),
    E("it-review-log", "1 / 25", "50 / 74"),
    PAGE_CLOSE,
])

# ---- page-data (hidden) ----
DATA_ELEMENT_IDS = ["tbl-claims", "tbl-premium", "tbl-loss-ratio", "tbl-lob-summary",
                     "tbl-year-premium", "tbl-year-summary", "tbl-triangle"]
page_data_xml = "\n".join(
    [page_open("page-data")]
    + [E(eid, "1 / 3", f"{i+1} / {i+2}") for i, eid in enumerate(DATA_ELEMENT_IDS)]
    + [PAGE_CLOSE]
)

LAYOUT = '<?xml version="1.0" encoding="utf-8"?>\n' + "\n".join([
    page_data_xml, page_command_xml, page_triangle_xml, page_detail_xml, page_assistant_xml,
    page_reserve_xml,
])

pages = [
    {"id": "page-data", "name": "Base Data (hidden)", "visibility": "hidden"},
    {"id": "page-command", "name": "Command Center"},
    {"id": "page-triangle", "name": "Loss Triangle"},
    {"id": "page-detail", "name": "Claims Detail"},
    {"id": "page-assistant", "name": "Loss Run Assistant"},
    {"id": "page-reserve", "name": "Reserve Review"},
]

# navigation elements (one per visible page)
elements += [nav_element(k) for k in ["command", "triangle", "detail", "assistant", "reserve"]]

document = {
    "schemaVersion": 1,
    "kind": "workbook",
    "elements": elements,
    "pages": pages,
    "agents": agents,
    "overlays": [],
    "settings": {
        "theme": {
            "overrides": {
                "categoricalScheme": [NAVY, TEAL, AMBER, DARK_TEAL, GRAY],
                "pageWidth": "large",
                "space": {"unit": "small"},
                "colorOverrides": [],
            }
        }
    },
    "layout": LAYOUT,
}

spec = {
    "name": "Alliant Insurance Group — Loss Run Analytics",
    "folderId": FOLDER_ID,
    "document": document,
}

with open(f"{SCRATCH}/spec_draft.json", "w") as f:
    json.dump(spec, f, indent=2)

print("Wrote spec_draft.json —", len(elements), "elements,", len(pages), "pages")
print("Layout length:", len(LAYOUT), "chars")







