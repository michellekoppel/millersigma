"""Build the Pacific Life Brand Investment Scorecard report — a pixel-perfect
PDF companion to the live "Pacific Life -- Brand Scorecard" workbook
(workbookId af183ebc-df0c-473d-b167-f3069a639818, My Documents, papercrane
org). This is a bespoke one-off, not a `company.py` entry: the workbook is a
real sponsorship/brand-investment governance app (events -> targets ->
approvals -> actuals -> annual rollup), not one of the synthetic
bank/airline-statement companies `build_statement.py`'s STATEMENTS config is
built for, so this script writes its own report spec instead of forcing that
template.

All data below (event names, budgets, targets, actuals, reviewer comments) is
copied verbatim from the live workbook's own seed SQL and Lookup/Coalesce
formulas (fetched via GET /v2/workbooks/{id}/spec on 2026-09-03) — this is a
frozen snapshot of that data, matching the "statement" idiom: a report locks
in numbers at a point in time rather than staying live.

Usage:
    python3 build_paclife_report.py create           # creates the report
    python3 build_paclife_report.py update <reportId> # re-pushes after an edit
    python3 build_paclife_report.py dump              # print the layout XML
"""

import base64
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
ASSETS = HERE.parent.parent / "assets"

# --------------------------------------------------------------------- auth

BASE = os.environ["SIGMA_BASE_URL"]
CLIENT_ID = os.environ["SIGMA_CLIENT_ID"]
CLIENT_SECRET = os.environ["SIGMA_CLIENT_SECRET"]
TOKEN_CACHE = pathlib.Path("/tmp/.sigma_token_paclife")
TOKEN_TTL = 55 * 60


class SigmaError(RuntimeError):
    def __init__(self, status, body, url):
        self.status, self.body, self.url = status, body, url
        super().__init__("HTTP %s on %s\n%s" % (status, url, body))


def _fetch_token():
    cred = base64.b64encode(("%s:%s" % (CLIENT_ID, CLIENT_SECRET)).encode()).decode()
    req = urllib.request.Request(
        BASE + "/v2/auth/token",
        data=urllib.parse.urlencode({"grant_type": "client_credentials"}).encode(),
        headers={"Authorization": "Basic " + cred,
                 "Content-Type": "application/x-www-form-urlencoded"},
        method="POST")
    with urllib.request.urlopen(req, timeout=40) as resp:
        tok = json.load(resp)["access_token"]
    TOKEN_CACHE.write_text(tok)
    os.chmod(TOKEN_CACHE, 0o600)
    return tok


def token():
    if TOKEN_CACHE.exists() and time.time() - TOKEN_CACHE.stat().st_mtime < TOKEN_TTL:
        cached = TOKEN_CACHE.read_text().strip()
        if cached:
            return cached
    return _fetch_token()


def call(method, path, body=None, retry_auth=True):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Authorization": "Bearer " + token(), "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw = resp.read().decode()
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        if exc.code == 401 and retry_auth:
            _fetch_token()
            return call(method, path, body, retry_auth=False)
        raise SigmaError(exc.code, raw, url) from None
    return json.loads(raw) if raw else None


# ------------------------------------------------------------------- brand

NAVY = "#0b2e4f"
TEXT_DARK = "#12212f"
TEXT_MUTED = "#5b6b79"
ACCENT = "#1c5c8c"
GOOD = "#2fa36b"
WARN = "#c9a24b"
BAD = "#d64545"
BORDER = "#e1e6ec"
CATEGORICAL = ["#0b2e4f", "#1c5c8c", "#2e8b8b", "#c9a24b", "#2fa36b", "#d64545"]

LOGO_DATAURI = (ASSETS / "paclife_logo_navy.datauri.txt").read_text().strip()

CONN = "bee6615c-7d11-435c-8819-e32207b27fe4"     # verified live on this org (the source workbook)
FOLDER_ID = "004d8497-18ea-4cf6-a8c5-deca403c22d9"  # My Documents (Michelle Koppel) -- same folder as the source workbook
SOURCE_WORKBOOK_URL = ("https://app.sigmacomputing.com/papercrane/workbook/"
                        "Pacific-Life-Brand-Scorecard-5koJHZpdLkqvzqpMPRFVoY")

PAGE_W, PAGE_H = 816, 1056        # US Letter portrait @ 96dpi
MARGIN = 30
HEADER_H, FOOTER_H = 96, 56
CW = PAGE_W - 2 * MARGIN          # 756 usable width

MONEY0 = {"kind": "number", "formatString": "$,.0f", "currencySymbol": "$",
          "digitGroupingSymbol": ",", "digitGroupingSize": [3], "displayNullAs": "—"}
MONEYK = {"kind": "number", "formatString": "$.3~s", "displayNullAs": "—"}
NUM0 = {"kind": "number", "formatString": ",.0f", "digitGroupingSymbol": ",",
        "digitGroupingSize": [3], "displayNullAs": "—"}
PCT1 = {"kind": "number", "formatString": ",.1f", "suffix": "%", "displayNullAs": "—"}

elements = []
rows = {"p1": [], "p2": [], "pdata": [], "global-header": [], "global-footer": []}


def add(el, where, x, y, w, h):
    elements.append(el)
    rows[where].append((el["id"], x, y, w, h))
    return el["id"]


def txt(eid, body, color=TEXT_DARK, align=None, valign=None, bg="transparent"):
    el = {"id": eid, "kind": "text", "body": body,
          "style": {"color": color, "backgroundColor": bg, "padding": "none"}}
    if align:
        el["align"] = align
    if valign:
        el["verticalAlign"] = valign
    return el


def kpi(eid, source, formula, name, color=NAVY, size=26, fmt=None,
        comparison_formula=None, comparison_name="Target", filter_event=None):
    cols = [{"id": eid + "v", "formula": formula, "name": name,
             **({"format": fmt} if fmt else {})}]
    spec = {"id": eid, "kind": "kpi-chart",
            "source": {"elementId": source, "kind": "table"},
            "columns": cols,
            "value": {"columnId": eid + "v", "color": color, "fontSize": size},
            "name": {"text": name, "color": TEXT_MUTED, "fontSize": 12},
            "style": {"backgroundColor": "#ffffff", "borderRadius": "round",
                      "borderColor": BORDER, "borderWidth": 1}}
    if comparison_formula:
        cols.append({"id": eid + "c", "formula": comparison_formula,
                     "name": comparison_name, **({"format": fmt} if fmt else {})})
        spec["comparison"] = {"display": "delta", "colorGood": GOOD, "colorBad": BAD,
                               "fontSize": 11}
        spec["comparisonColumn"] = {"columnId": eid + "c"}
    if filter_event:
        # A filter can only reference a column already in THIS element's own
        # `columns` list -- add a hidden one to filter on.
        cols.append({"id": eid + "n", "formula": "[%s/Event Name]" % SC, "name": "Event Name"})
        spec["filters"] = [{"id": eid + "-f", "columnId": eid + "n", "kind": "list",
                             "mode": "include", "values": [filter_event]}]
    return spec


# ---------------------------------------------------------------- data source
# Verbatim from the live workbook's events-seed / targets-seed / approvals-seed
# / actuals-seed elements (GET /v2/workbooks/af183ebc-.../spec, 2026-09-03).

add({"id": "events-seed", "kind": "table", "name": "Events Seed",
     "source": {"connectionId": CONN, "kind": "sql", "statement":
                "SELECT 'AT&T Pebble Beach Pro-Am' AS C1,'PGA Tour Sponsorship' AS C2,"
                "'2026-02-05' AS C3,'Sarah Chen' AS C4,450000 AS C5,"
                "'Marquee PGA Tour pairing event; strong overlap with our target affluent demographic.' AS C6 "
                "UNION ALL SELECT 'Pacific Life Open Golf Classic','Golf Pro-Am','2026-06-12',"
                "'James Whitfield',275000,"
                "'Regional client-appreciation pro-am; strengthens advisor relationships in key markets.' "
                "UNION ALL SELECT 'Newport Beach Jazz & Wine Festival','Concert Series','2026-09-20',"
                "'Maria Lopez',120000,"
                "'Community brand visibility in our Newport Beach HQ market.' "
                "UNION ALL SELECT 'Financial Advisors Forum West','Industry Conference','2026-11-03',"
                "'David Kim',90000,"
                "'Advisor recruitment and thought-leadership positioning.'"},
     "columns": [
         {"id": "se-name", "formula": "[Custom SQL/C1]", "name": "Event Name"},
         {"id": "se-type", "formula": "[Custom SQL/C2]", "name": "Event Type"},
         {"id": "se-date", "formula": "[Custom SQL/C3]", "name": "Event Date"},
         {"id": "se-owner", "formula": "[Custom SQL/C4]", "name": "Requested By"},
         {"id": "se-budget", "formula": "[Custom SQL/C5]", "name": "Requested Budget"},
         {"id": "se-just", "formula": "[Custom SQL/C6]", "name": "Summary and Justification"}]},
    "pdata", MARGIN, 0, CW, 200)

add({"id": "targets-seed", "kind": "table", "name": "Targets Seed",
     "source": {"connectionId": CONN, "kind": "sql", "statement":
                "SELECT 'AT&T Pebble Beach Pro-Am' AS C1,8000000 AS C2,45000 AS C3,150 AS C4,"
                "1200000 AS C5,4 AS C6,430000 AS C7 "
                "UNION ALL SELECT 'Pacific Life Open Golf Classic',1500000,12000,60,300000,2.5,260000 "
                "UNION ALL SELECT 'Financial Advisors Forum West',600000,5000,40,150000,1.5,85000"},
     "columns": [
         {"id": "st-name", "formula": "[Custom SQL/C1]", "name": "Event Name"},
         {"id": "st-impr", "formula": "[Custom SQL/C2]", "name": "Target Impressions"},
         {"id": "st-eng", "formula": "[Custom SQL/C3]", "name": "Target Engagements"},
         {"id": "st-leads", "formula": "[Custom SQL/C4]", "name": "Target Leads and Meetings"},
         {"id": "st-emv", "formula": "[Custom SQL/C5]", "name": "Target Earned Media Value"},
         {"id": "st-lift", "formula": "[Custom SQL/C6]", "name": "Target Brand Lift %"},
         {"id": "st-budget", "formula": "[Custom SQL/C7]", "name": "Approved Budget"}]},
    "pdata", MARGIN, 210, CW, 160)

add({"id": "approvals-seed", "kind": "table", "name": "Approvals Seed",
     "source": {"connectionId": CONN, "kind": "sql", "statement":
                "SELECT 'AT&T Pebble Beach Pro-Am' AS C1,'Approved' AS C2,'Karen Ito' AS C3,"
                "'Strong ROI history with this event; approve at requested budget.' AS C4 "
                "UNION ALL SELECT 'Pacific Life Open Golf Classic','Approved','Karen Ito',"
                "'Approved with a slight budget trim.' "
                "UNION ALL SELECT 'Newport Beach Jazz & Wine Festival','Denied','Karen Ito',"
                "'Low strategic fit this cycle; revisit next year.'"},
     "columns": [
         {"id": "sa-name", "formula": "[Custom SQL/C1]", "name": "Event Name"},
         {"id": "sa-decision", "formula": "[Custom SQL/C2]", "name": "Decision"},
         {"id": "sa-reviewer", "formula": "[Custom SQL/C3]", "name": "Reviewer"},
         {"id": "sa-comments", "formula": "[Custom SQL/C4]", "name": "Comments"}]},
    "pdata", MARGIN, 380, CW, 140)

add({"id": "actuals-seed", "kind": "table", "name": "Actuals Seed",
     "source": {"connectionId": CONN, "kind": "sql", "statement":
                "SELECT 'AT&T Pebble Beach Pro-Am' AS C1,8400000 AS C2,51000 AS C3,162 AS C4,"
                "1350000 AS C5,4.6 AS C6,421000 AS C7"},
     "columns": [
         {"id": "sc2-name", "formula": "[Custom SQL/C1]", "name": "Event Name"},
         {"id": "sc2-impr", "formula": "[Custom SQL/C2]", "name": "Actual Impressions"},
         {"id": "sc2-eng", "formula": "[Custom SQL/C3]", "name": "Actual Engagements"},
         {"id": "sc2-leads", "formula": "[Custom SQL/C4]", "name": "Actual Leads and Meetings"},
         {"id": "sc2-emv", "formula": "[Custom SQL/C5]", "name": "Actual Earned Media Value"},
         {"id": "sc2-lift", "formula": "[Custom SQL/C6]", "name": "Actual Brand Lift %"},
         {"id": "sc2-spend", "formula": "[Custom SQL/C7]", "name": "Actual Spend"}]},
    "pdata", MARGIN, 530, CW, 100)

# "Scorecard" -- the same join-by-Lookup the live workbook's own `scorecard`
# element does, minus the Coalesce-with-live-input-table half (a report is a
# frozen snapshot; there is no "Awaiting Targets/Decision/Actuals" input table
# here, only each seed).
add({"id": "scorecard", "kind": "table", "name": "Scorecard",
     "source": {"elementId": "events-seed", "kind": "table"},
     "columns": [
         {"id": "sc-name", "formula": "[Events Seed/Event Name]", "name": "Event Name"},
         {"id": "sc-type", "formula": "[Events Seed/Event Type]", "name": "Event Type"},
         {"id": "sc-date", "formula": "[Events Seed/Event Date]", "name": "Event Date"},
         {"id": "sc-owner", "formula": "[Events Seed/Requested By]", "name": "Requested By"},
         {"id": "sc-reqbudget", "formula": "[Events Seed/Requested Budget]", "name": "Requested Budget"},
         {"id": "sc-just", "formula": "[Events Seed/Summary and Justification]", "name": "Justification"},
         {"id": "sc-decision",
          "formula": "Lookup([Approvals Seed/Decision], [Event Name], [Approvals Seed/Event Name])",
          "name": "Decision"},
         {"id": "sc-reviewer",
          "formula": "Coalesce(Lookup([Approvals Seed/Reviewer], [Event Name], "
                     "[Approvals Seed/Event Name]), \"Pending\")",
          "name": "Reviewer"},
         {"id": "sc-comments",
          "formula": "Coalesce(Lookup([Approvals Seed/Comments], [Event Name], "
                     "[Approvals Seed/Event Name]), \"Awaiting Brand Council review\")",
          "name": "Review Comments"},
         {"id": "sc-status", "formula": "Coalesce([Decision], \"Pending Brand Council Review\")",
          "name": "Status"},
         {"id": "sc-tgimpr",
          "formula": "Lookup([Targets Seed/Target Impressions], [Event Name], [Targets Seed/Event Name])",
          "name": "Target Impressions"},
         {"id": "sc-tgeng",
          "formula": "Lookup([Targets Seed/Target Engagements], [Event Name], [Targets Seed/Event Name])",
          "name": "Target Engagements"},
         {"id": "sc-tgleads",
          "formula": "Lookup([Targets Seed/Target Leads and Meetings], [Event Name], [Targets Seed/Event Name])",
          "name": "Target Leads and Meetings"},
         {"id": "sc-tgemv",
          "formula": "Lookup([Targets Seed/Target Earned Media Value], [Event Name], [Targets Seed/Event Name])",
          "name": "Target Earned Media Value"},
         {"id": "sc-tglift",
          "formula": "Lookup([Targets Seed/Target Brand Lift %], [Event Name], [Targets Seed/Event Name])",
          "name": "Target Brand Lift %"},
         {"id": "sc-apprbudget",
          "formula": "Lookup([Targets Seed/Approved Budget], [Event Name], [Targets Seed/Event Name])",
          "name": "Approved Budget"},
         {"id": "sc-acimpr",
          "formula": "Lookup([Actuals Seed/Actual Impressions], [Event Name], [Actuals Seed/Event Name])",
          "name": "Actual Impressions"},
         {"id": "sc-aceng",
          "formula": "Lookup([Actuals Seed/Actual Engagements], [Event Name], [Actuals Seed/Event Name])",
          "name": "Actual Engagements"},
         {"id": "sc-acleads",
          "formula": "Lookup([Actuals Seed/Actual Leads and Meetings], [Event Name], [Actuals Seed/Event Name])",
          "name": "Actual Leads and Meetings"},
         {"id": "sc-acemv",
          "formula": "Lookup([Actuals Seed/Actual Earned Media Value], [Event Name], [Actuals Seed/Event Name])",
          "name": "Actual Earned Media Value"},
         {"id": "sc-aclift",
          "formula": "Lookup([Actuals Seed/Actual Brand Lift %], [Event Name], [Actuals Seed/Event Name])",
          "name": "Actual Brand Lift %"},
         {"id": "sc-acspend",
          "formula": "Lookup([Actuals Seed/Actual Spend], [Event Name], [Actuals Seed/Event Name])",
          "name": "Actual Spend"}]},
    "pdata", MARGIN, 640, CW, 300)

SC = "Scorecard"

# ---------------------------------------------------------- global header/footer

H_GAP = 16
H_COL_W = [140, 340, 210]   # logo, title block, period block
assert MARGIN + sum(H_COL_W) + H_GAP * (len(H_COL_W) - 1) <= PAGE_W - MARGIN, \
    "header columns overflow the page margin"
h_col_x = [MARGIN]
for w in H_COL_W[:-1]:
    h_col_x.append(h_col_x[-1] + w + H_GAP)

add({"id": "h-logo", "kind": "image",
     "source": {"kind": "url", "url": LOGO_DATAURI},
     "style": {"fit": "contain", "align": "start", "backgroundColor": "transparent",
               "padding": "none"}},
    "global-header", h_col_x[0], 18, H_COL_W[0], 46)

add(txt("h-title",
        '<span style="font-family: Aeonik; font-size: 22px; color: %s">'
        '**BRAND INVESTMENT SCORECARD**</span>' % NAVY,
        NAVY, valign="end"),
    "global-header", h_col_x[1], 14, H_COL_W[1], 30)
add(txt("h-sub",
        '<span style="font-size: 12px; color: %s">Marketing event &amp; '
        'sponsorship tracking</span>' % TEXT_MUTED, TEXT_MUTED),
    "global-header", h_col_x[1], 46, H_COL_W[1], 20)

add(txt("h-period",
        '<span style="font-size: 11px; color: %s">**Reporting period**</span>  \n'
        '<span style="font-size: 13px; color: %s">FY2026</span>' % (TEXT_MUTED, NAVY),
        NAVY, align="end"),
    "global-header", h_col_x[2], 18, H_COL_W[2], 44)

add({"id": "h-rule", "kind": "divider", "style": {"color": ACCENT}},
    "global-header", MARGIN, 80, CW, 2)

add({"id": "f-rule", "kind": "divider", "style": {"color": BORDER}},
    "global-footer", MARGIN, 6, CW, 1)
add(txt("f-note",
        '<span style="font-size: 10px; color: %s">Pacific Life Brand Investment '
        'Scorecard — generated from the live Sigma workbook. Confidential, '
        'internal use only.</span>' % TEXT_MUTED, TEXT_MUTED),
    "global-footer", MARGIN, 14, CW - 120, 36)
add(txt("f-src",
        '<span style="font-size: 10px; color: %s">Source: %s</span>'
        % (TEXT_MUTED, SOURCE_WORKBOOK_URL), TEXT_MUTED, align="end"),
    "global-footer", MARGIN, 30, CW, 20)


# ====================================================================== page 1

SECT = '<span style="color: %s; font-size: 13px">**%%s**</span>' % ACCENT

y = 0
kpi_w = (CW - 5 * 8) / 6.0
kpi_defs = [
    ("kt-events", "Count([%s/Event Name])" % SC, "Total Events", NUM0),
    ("kt-req", "Sum([%s/Requested Budget])" % SC, "Requested", MONEYK),
    ("kt-appr", "Sum([%s/Approved Budget])" % SC, "Approved", MONEYK),
    ("kt-spend", "Sum([%s/Actual Spend])" % SC, "Spend to Date", MONEYK),
    ("kt-emv", "Sum([%s/Actual Earned Media Value])" % SC, "EMV to Date", MONEYK),
    ("kt-lift", "Avg([%s/Actual Brand Lift %%])" % SC, "Brand Lift %", PCT1),
]
for i, (eid, formula, name, fmt) in enumerate(kpi_defs):
    x = MARGIN + i * (kpi_w + 8)
    add(kpi(eid, "scorecard", formula, name, fmt=fmt, size=20), "p1", x, y, kpi_w, 84)
y += 96

add(txt("p1-h-pipe", SECT % "Sponsorship Pipeline"), "p1", MARGIN, y, CW, 20)
y += 24
add({"id": "p1-pipe", "kind": "table",
     "source": {"elementId": "scorecard", "kind": "table"},
     "columns": [
         {"id": "pp-name", "formula": "[%s/Event Name]" % SC, "name": "Event Name"},
         {"id": "pp-type", "formula": "[%s/Event Type]" % SC, "name": "Event Type"},
         {"id": "pp-date", "formula": "[%s/Event Date]" % SC, "name": "Event Date"},
         {"id": "pp-owner", "formula": "[%s/Requested By]" % SC, "name": "Requested By"},
         {"id": "pp-status", "formula": "[%s/Status]" % SC, "name": "Status"},
         {"id": "pp-req", "formula": "[%s/Requested Budget]" % SC, "name": "Requested",
          "format": MONEY0},
         {"id": "pp-appr", "formula": "[%s/Approved Budget]" % SC, "name": "Approved",
          "format": MONEY0}],
     "order": ["pp-name", "pp-type", "pp-date", "pp-owner", "pp-status", "pp-req", "pp-appr"],
     "tableComponents": {"summaryBar": "hidden"},
     "tableStyle": {"preset": "presentation", "cellSpacing": "small"},
     "name": {"visibility": "hidden"},
     "conditionalFormats": [
         {"type": "single", "columnIds": ["pp-status"], "condition": "=",
          "value": "Approved", "style": {"backgroundColor": "#DCF3E6"}},
         {"type": "single", "columnIds": ["pp-status"], "condition": "=",
          "value": "Denied", "style": {"backgroundColor": "#FBE1E1"}},
         {"type": "single", "columnIds": ["pp-status"], "condition": "=",
          "value": "Pending Brand Council Review", "style": {"backgroundColor": "#FBF3DC"}}],
     "style": {"backgroundColor": "#ffffff", "borderColor": BORDER, "borderWidth": 1,
               "borderRadius": "round"}},
    "p1", MARGIN, y, CW, 190)
y += 204

add(txt("p1-h-spot", SECT % "Event Spotlight — AT&T Pebble Beach Pro-Am"),
    "p1", MARGIN, y, CW, 20)
y += 24

LEFT_W = 356
RIGHT_X = MARGIN + LEFT_W + 20
RIGHT_W = CW - LEFT_W - 20

add(txt("p1-just",
        '<span style="font-size: 11px; color: %s">**Why we invested**</span>  \n'
        '<span style="font-size: 12px; color: %s">Marquee PGA Tour pairing event; '
        'strong overlap with our target affluent demographic.</span>' % (TEXT_MUTED, TEXT_DARK),
        TEXT_DARK, bg="#f1f3f9"),
    "p1", MARGIN, y, LEFT_W, 74)
add(txt("p1-review",
        '<span style="font-size: 11px; color: %s">**Brand Council review** — Karen Ito</span>  \n'
        '<span style="font-size: 12px; color: %s">Strong ROI history with this event; '
        'approve at requested budget.</span>' % (TEXT_MUTED, TEXT_DARK),
        TEXT_DARK, bg="#f1f3f9"),
    "p1", MARGIN, y + 82, LEFT_W, 74)

spot_kpis = [
    ("ks-spend", "[%s/Actual Spend]" % SC, "[%s/Approved Budget]" % SC, "Spend vs. Budget", MONEYK),
    ("ks-impr", "[%s/Actual Impressions]" % SC, "[%s/Target Impressions]" % SC, "Impressions", NUM0),
    ("ks-eng", "[%s/Actual Engagements]" % SC, "[%s/Target Engagements]" % SC, "Engagements", NUM0),
    ("ks-leads", "[%s/Actual Leads and Meetings]" % SC, "[%s/Target Leads and Meetings]" % SC,
     "Leads / Meetings", NUM0),
    ("ks-emv", "[%s/Actual Earned Media Value]" % SC, "[%s/Target Earned Media Value]" % SC,
     "Earned Media Value", MONEYK),
    ("ks-lift", "[%s/Actual Brand Lift %%]" % SC, "[%s/Target Brand Lift %%]" % SC,
     "Brand Lift %", PCT1),
]
sk_w = (RIGHT_W - 2 * 8) / 3.0
sk_h = 96
for i, (eid, actual_f, target_f, name, fmt) in enumerate(spot_kpis):
    col, row = i % 3, i // 3
    x = RIGHT_X + col * (sk_w + 8)
    yy = y + row * (sk_h + 8)
    spec = kpi(eid, "scorecard", actual_f, name, fmt=fmt, size=18,
               comparison_formula=target_f, comparison_name="Target",
               filter_event="AT&T Pebble Beach Pro-Am")
    add(spec, "p1", x, yy, sk_w, sk_h)
y += 2 * (sk_h + 8) + 8

add({"id": "spend-bar", "kind": "bar-chart",
     "source": {"elementId": "scorecard", "kind": "table"},
     "columns": [
         {"id": "sb-status", "formula": "[%s/Status]" % SC, "name": "Status"},
         {"id": "sb-name", "formula": "[%s/Event Name]" % SC, "name": "Event Name"},
         {"id": "sb-req", "formula": "[%s/Requested Budget]" % SC, "name": "Requested Budget",
          "format": MONEY0}],
     "yAxis": {"columnIds": ["sb-req"]},
     "xAxis": {"columnId": "sb-name",
               "sort": {"by": "sb-req", "direction": "descending"},
               "format": {"labels": {"labelAngle": -20}}},
     "color": {"by": "category", "column": "sb-status", "scheme": CATEGORICAL},
     "name": {"text": "Requested Budget by Event", "fontWeight": "bold", "fontSize": 13},
     "legend": {"visibility": "shown"},
     "style": {"backgroundColor": "#ffffff", "borderColor": BORDER, "borderWidth": 1,
               "borderRadius": "round"}},
    "p1", MARGIN, y, CW, 150)


# ====================================================================== page 2

y = 0
add(txt("p2-h1", "# Decision Log", NAVY), "p2", MARGIN, y, CW, 46)
y += 54

add({"id": "decisions-log", "kind": "table",
     "source": {"elementId": "scorecard", "kind": "table"},
     "columns": [
         {"id": "dl-name", "formula": "[%s/Event Name]" % SC, "name": "Event Name"},
         {"id": "dl-status", "formula": "[%s/Status]" % SC, "name": "Status"},
         {"id": "dl-reviewer", "formula": "[%s/Reviewer]" % SC, "name": "Reviewer"},
         {"id": "dl-comments", "formula": "[%s/Review Comments]" % SC, "name": "Comments"}],
     "tableComponents": {"summaryBar": "hidden"},
     "tableStyle": {"preset": "presentation", "cellSpacing": "small"},
     "name": {"visibility": "hidden"},
     "conditionalFormats": [
         {"type": "single", "columnIds": ["dl-status"], "condition": "=",
          "value": "Approved", "style": {"backgroundColor": "#DCF3E6"}},
         {"type": "single", "columnIds": ["dl-status"], "condition": "=",
          "value": "Denied", "style": {"backgroundColor": "#FBE1E1"}},
         {"type": "single", "columnIds": ["dl-status"], "condition": "=",
          "value": "Pending Brand Council Review", "style": {"backgroundColor": "#FBF3DC"}}],
     "style": {"backgroundColor": "#ffffff", "borderColor": BORDER, "borderWidth": 1,
               "borderRadius": "round"}},
    "p2", MARGIN, y, CW, 220)
y += 234

add(txt("p2-h2", SECT % "Targets vs. Actuals — Full Detail"), "p2", MARGIN, y, CW, 20)
y += 24
add({"id": "budget-detail", "kind": "table",
     "source": {"elementId": "scorecard", "kind": "table"},
     "columns": [
         {"id": "bd-name", "formula": "[%s/Event Name]" % SC, "name": "Event Name"},
         {"id": "bd-status", "formula": "[%s/Status]" % SC, "name": "Status"},
         {"id": "bd-req", "formula": "[%s/Requested Budget]" % SC, "name": "Requested Budget",
          "format": MONEY0},
         {"id": "bd-appr", "formula": "[%s/Approved Budget]" % SC, "name": "Approved Budget",
          "format": MONEY0},
         {"id": "bd-spend", "formula": "[%s/Actual Spend]" % SC, "name": "Actual Spend",
          "format": MONEY0}],
     "tableComponents": {"summaryBar": "hidden"},
     "tableStyle": {"preset": "presentation", "cellSpacing": "small"},
     "name": {"visibility": "hidden"},
     "style": {"backgroundColor": "#ffffff", "borderColor": BORDER, "borderWidth": 1,
               "borderRadius": "round"}},
    "p2", MARGIN, y, CW, 170)
y += 184

add(txt("p2-h3", SECT % "Performance vs. Target"), "p2", MARGIN, y, CW, 20)
y += 24
add({"id": "perf-detail", "kind": "table",
     "source": {"elementId": "scorecard", "kind": "table"},
     "columns": [
         {"id": "pd-name", "formula": "[%s/Event Name]" % SC, "name": "Event Name"},
         {"id": "pd-tgimpr", "formula": "[%s/Target Impressions]" % SC, "name": "Target Impressions",
          "format": NUM0},
         {"id": "pd-acimpr", "formula": "[%s/Actual Impressions]" % SC, "name": "Actual Impressions",
          "format": NUM0},
         {"id": "pd-tgemv", "formula": "[%s/Target Earned Media Value]" % SC, "name": "Target EMV",
          "format": MONEY0},
         {"id": "pd-acemv", "formula": "[%s/Actual Earned Media Value]" % SC, "name": "Actual EMV",
          "format": MONEY0},
         {"id": "pd-tglift", "formula": "[%s/Target Brand Lift %%]" % SC, "name": "Target Lift %",
          "format": PCT1},
         {"id": "pd-aclift", "formula": "[%s/Actual Brand Lift %%]" % SC, "name": "Actual Lift %",
          "format": PCT1}],
     "tableComponents": {"summaryBar": "hidden"},
     "tableStyle": {"preset": "presentation", "cellSpacing": "small"},
     "name": {"visibility": "hidden"},
     "style": {"backgroundColor": "#ffffff", "borderColor": BORDER, "borderWidth": 1,
               "borderRadius": "round"}},
    "p2", MARGIN, y, CW, 170)
y += 184

add(txt("p2-note",
        '<span style="font-size: 10px; color: %s">Every element, page dimension and '
        'margin on this report is declared in a report specification and created with '
        '`POST /v2/reports/spec` from the same data as the live workbook above.</span>'
        % TEXT_MUTED),
    "p2", MARGIN, y, CW, 30)


# =================================================================== assemble

def render_layout():
    out = ['<?xml version="1.0" encoding="utf-8"?>']
    for pid in ("p1", "p2", "pdata"):
        out.append('<Page id="%s">' % pid)
        for eid, x, yy, w, h in rows[pid]:
            out.append('  <Element elementId="%s" x="%d" y="%d" width="%d" height="%d"/>'
                       % (eid, round(x), round(yy), round(w), round(h)))
        out.append("</Page>")
    for pid, ptype in (("global-header", "header"), ("global-footer", "footer")):
        out.append('<Panel id="%s" type="%s">' % (pid, ptype))
        for eid, x, yy, w, h in rows[pid]:
            out.append('  <Element elementId="%s" x="%d" y="%d" width="%d" height="%d"/>'
                       % (eid, round(x), round(yy), round(w), round(h)))
        out.append("</Panel>")
    return "\n".join(out)


PAGES = [{"id": "p1", "name": "Executive Summary"},
         {"id": "p2", "name": "Decision Log & Detail"},
         {"id": "pdata", "name": "Data", "visibility": "hidden"}]

DOCUMENT = {
    "schemaVersion": 1,
    "kind": "report",
    "elements": elements,
    "pages": PAGES,
    "panels": [
        {"id": "global-header", "type": "header", "title": "Report header",
         "config": {"height": HEADER_H, "backgroundColor": ""}, "pages": ["p1", "p2"]},
        {"id": "global-footer", "type": "footer", "title": "Report footer",
         "config": {"height": FOOTER_H, "backgroundColor": ""}, "pages": ["p1", "p2"]},
    ],
    "settings": {"theme": {"overrides": {
        "colors": {"text": TEXT_DARK, "highlight": ACCENT, "success": GOOD,
                   "warning": WARN, "danger": BAD, "darkMode": "hidden"},
        "colorOverrides": [{"name": "backgroundCanvas", "color": "#FFFFFF"}],
        "categoricalScheme": CATEGORICAL,
        "space": {"unit": "small", "showElementPadding": "shown"},
    }}},
    "config": {"margin": MARGIN, "pageHeight": PAGE_H, "pageWidth": PAGE_W},
    "layout": render_layout(),
}

SPEC = {"name": "Pacific Life -- Brand Investment Scorecard Report",
        "folderId": FOLDER_ID,
        "document": DOCUMENT}


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "dump"
    if action == "dump":
        print(DOCUMENT["layout"])
        print("\nelements:", len(elements))
        return
    try:
        if action == "create":
            r = call("POST", "/v2/reports/spec", SPEC)
            rid = r.get("reportId")
            print("created report", rid)
            (HERE / "report_id.txt").write_text(rid or "")
        elif action == "update":
            call("PUT", "/v2/reports/%s/spec" % sys.argv[2], SPEC)
            print("updated", sys.argv[2])
        else:
            print("usage: build_paclife_report.py [create|update <reportId>|dump]")
    except SigmaError as exc:
        msg = exc.body
        try:
            msg = json.loads(exc.body).get("message", msg)
        except ValueError:
            pass
        print("%s failed:\n%s" % (action, msg[:3000]))
        sys.exit(1)


if __name__ == "__main__":
    main()
