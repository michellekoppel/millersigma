#!/usr/bin/env python3
"""BODi Nutrition Program Performance — pixel-perfect Sigma REPORT (not workbook).

6 pages, US Letter portrait (816x1056 @96dpi), built via POST /v2/reports/spec.
All figures are LIVE, sourced from the same synthetic dataset as the
"BODi — Nutrition Business" workbook (reuses build_bodi.CTE_CHAIN) — nothing
here is copied from a real external source. This is demonstration data, not
real BODi financials; the Methodology page says so explicitly.

Text elements in the report schema only support {id, kind, body,
verticalAlign, overflow} — color/alignment/size must be inline HTML inside
`body` (a documented subset: <span style="color;font-size;font-family">,
<p style="text-align">, headings as # / ## / ### or <p class="h-med"
style="text-align:...">). There is no element-level `style.color`.

Usage:
  python3 build_report.py create             # POST a new report
  python3 build_report.py update <report-id> # PUT to an existing report id
"""
import base64
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import build_bodi as b

OUT = pathlib.Path(__file__).parent / "report_spec.json"
CONN = b.CONN
FOLDER = b.FOLDER

PAGE_W, PAGE_H = 816, 1056
HEADER_H = 84
FOOTER_Y = 1000
CONTENT_X = 56
CONTENT_W = 704  # 816 - 56*2
TOTAL_PAGES = 6

CUR, CUR2, INT, PCT1, PCT2 = b.CUR, b.CUR2, b.INT, b.PCT1, b.PCT2
INK, BLACK, GREEN, GREEN_D, GREEN_LIGHT, MINT, WHITE = b.INK, b.BLACK, b.GREEN, b.GREEN_D, b.GREEN_LIGHT, b.MINT, b.WHITE
GRAY, LINE = "#8A8A8A", "#E8E8E8"
LOGO_URI = b.LOGO_URI
FONT = "Helvetica"

_uid = [0]
def uid(p="e"):
    _uid[0] += 1
    return f"{p}{_uid[0]}"

def datauri_svg(svg):
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()

def solid_rect(w, h, color, extra=""):
    return datauri_svg(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}"><rect width="{w}" height="{h}" fill="{color}"/>{extra}</svg>')

# ---------------------------------------------------------------- elements
def rlx(elid, x, y, w, h):
    return f'  <Element elementId="{elid}" x="{x}" y="{y}" width="{w}" height="{h}"/>'

def txt(elid, body, valign="start"):
    return {"id": elid, "kind": "text", "body": body, "verticalAlign": valign}

def span(text, color=INK, size=None, weight=None, family=FONT):
    style = f"color:{color};font-family:{family}"
    if size: style += f";font-size:{size}px"
    inner = f'<span style="{style}">{text}</span>'
    if weight == "bold":
        return f"**{inner}**"
    return inner

def para(inner, align="start"):
    if align == "start":
        return inner  # default alignment — a <p> wrapper with no non-default style is rejected
    ta = {"middle": "center", "end": "right"}[align]
    return f'<p style="text-align:{ta}">{inner}</p>'

def heading(level, inner, align=None):
    if align:
        ta = {"start": "left", "middle": "center", "end": "right"}[align]
        cls = {1: "h-large", 2: "h-med", 3: "h-small"}.get(level, "h-med")
        return f'<p class="{cls}" style="text-align:{ta}">{inner}</p>'
    return ("#" * level) + " " + inner

def image_el(elid, url, fit="contain"):
    return {"id": elid, "kind": "image", "source": {"kind": "url", "url": url}, "style": {"fit": fit}}

def divider_el(elid, color=LINE):
    return {"id": elid, "kind": "divider", "style": {"color": color}}

def sql_table(elid, name, sql, cols):
    return b.sql_table(elid, name, sql, cols)

# ======================================================================
# Shared chrome — redrawn per content page (2-6); the cover (page 1) draws its own
# ======================================================================
def page_chrome(pid, section, page_num):
    els, lay = [], []
    hdr_svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{PAGE_W}" height="{HEADER_H}"><rect width="{PAGE_W}" height="{HEADER_H}" fill="{BLACK}"/><rect y="{HEADER_H-4}" width="{PAGE_W}" height="4" fill="{GREEN}"/></svg>'
    hdr_bg = image_el(f"{pid}-hdrbg", datauri_svg(hdr_svg), fit="stretch")
    logo = image_el(f"{pid}-logo", LOGO_URI, fit="contain")
    eyebrow = txt(f"{pid}-eyebrow", span("NUTRITION PROGRAM PERFORMANCE", color="#C8C8C8", size=10), valign="end")
    label = txt(f"{pid}-label", span(section.upper(), color=WHITE, size=20, weight="bold"), valign="start")
    footer_rule = divider_el(f"{pid}-frule", LINE)
    footer_l = txt(f"{pid}-footl", span("BODi · Nutrition Program Performance — Demonstration Data", color=GRAY, size=9))
    footer_r = txt(f"{pid}-footr", para(span(f"Page {page_num} of {TOTAL_PAGES}", color=GRAY, size=9), align="end"))

    els += [hdr_bg, logo, eyebrow, label, footer_rule, footer_l, footer_r]
    lay += [
        rlx(f"{pid}-hdrbg", 0, 0, PAGE_W, HEADER_H),
        rlx(f"{pid}-logo", CONTENT_X, 16, 90, 18),
        rlx(f"{pid}-eyebrow", 340, 14, 420, 14),
        rlx(f"{pid}-label", 340, 30, 420, 30),
        rlx(f"{pid}-frule", CONTENT_X, FOOTER_Y, CONTENT_W, 1),
        rlx(f"{pid}-footl", CONTENT_X, FOOTER_Y + 8, 420, 16),
        rlx(f"{pid}-footr", CONTENT_X + 300, FOOTER_Y + 8, 404, 16),
    ]
    return els, lay


# ======================================================================
# SQL — reuses build_bodi.CTE_CHAIN so every figure ties back to `fact`
# ======================================================================
QTR_SQL = b.CTE_CHAIN + """
, qtr AS (
  SELECT DATE_TRUNC('quarter', calendar_month) AS qtr,
    nutrition_program,
    COUNT(DISTINCT IFF(nutrition_active, member_id, NULL)) AS active_subs,
    SUM(product_revenue) AS revenue
  FROM fc6
  WHERE calendar_month < DATE_TRUNC('quarter', CURRENT_DATE())
    AND calendar_month >= DATEADD('month', -18, DATE_TRUNC('quarter', CURRENT_DATE()))
    AND nutrition_program <> 'None'
  GROUP BY 1, 2
)
SELECT qtr, nutrition_program, active_subs, revenue FROM qtr ORDER BY qtr, nutrition_program
"""

QTR_TOTAL_SQL = b.CTE_CHAIN + """
, qtr AS (
  SELECT DATE_TRUNC('quarter', calendar_month) AS qtr,
    COUNT(DISTINCT IFF(nutrition_active, member_id, NULL)) AS active_subs,
    SUM(product_revenue) AS revenue
  FROM fc6
  WHERE calendar_month < DATE_TRUNC('quarter', CURRENT_DATE())
    AND calendar_month >= DATEADD('month', -18, DATE_TRUNC('quarter', CURRENT_DATE()))
  GROUP BY 1
)
SELECT
  qtr,
  TO_CHAR(qtr, 'YYYY') || ' Q' || DATE_PART('quarter', qtr) AS qtr_label,
  active_subs,
  revenue,
  ROUND(revenue / active_subs / 3, 0) AS revenue_per_sub_mo,
  LAG(active_subs) OVER (ORDER BY qtr) AS prior_subs,
  ROUND((active_subs - LAG(active_subs) OVER (ORDER BY qtr)) / NULLIF(LAG(active_subs) OVER (ORDER BY qtr), 0), 3) AS growth_pct
FROM qtr
ORDER BY qtr
"""

RETENTION_SQL = b.CTE_CHAIN + """
SELECT fitness_program, months_since_signup,
  COUNT(DISTINCT IFF(nutrition_subscriber, member_id, NULL)) AS cohort_size,
  COUNT(DISTINCT IFF(nutrition_active, member_id, NULL)) AS still_active,
  ROUND(COUNT(DISTINCT IFF(nutrition_active, member_id, NULL)) / NULLIF(COUNT(DISTINCT IFF(nutrition_subscriber, member_id, NULL)), 0), 3) AS retention_rate
FROM fc6
WHERE nutrition_subscriber AND months_since_signup IN (3, 6, 12)
GROUP BY 1, 2
ORDER BY 1, 2
"""

COACH_SQL = b.CTE_CHAIN + """
SELECT coach_attached,
  COUNT(DISTINCT member_id) AS total,
  COUNT(DISTINCT IFF(nutrition_subscriber, member_id, NULL)) AS attached,
  ROUND(COUNT(DISTINCT IFF(nutrition_subscriber, member_id, NULL)) / COUNT(DISTINCT member_id), 3) AS attach_rate
FROM fc6
WHERE is_current_month
GROUP BY 1
"""

qtr_tbl = sql_table("rp-qtr", "Quarterly By Program", QTR_SQL,
                     [("q-q", "QTR", "Qtr"), ("q-prog", "NUTRITION_PROGRAM", "Nutrition Program"),
                      ("q-subs", "ACTIVE_SUBS", "Active Subs"), ("q-rev", "REVENUE", "Revenue")])
qtr_total_tbl = sql_table("rp-qtrtotal", "Quarterly Total", QTR_TOTAL_SQL,
                           [("qt-q", "QTR", "Qtr"), ("qt-label", "QTR_LABEL", "Qtr Label"),
                            ("qt-subs", "ACTIVE_SUBS", "Active Subs"), ("qt-rev", "REVENUE", "Revenue"),
                            ("qt-rpsm", "REVENUE_PER_SUB_MO", "Revenue Per Sub Mo"), ("qt-prior", "PRIOR_SUBS", "Prior Subs"),
                            ("qt-growth", "GROWTH_PCT", "Growth Pct")])
retention_tbl = sql_table("rp-retention", "Retention By Program", RETENTION_SQL,
                           [("rt-prog", "FITNESS_PROGRAM", "Fitness Program"), ("rt-mo", "MONTHS_SINCE_SIGNUP", "Months Since Signup"),
                            ("rt-cohort", "COHORT_SIZE", "Cohort Size"), ("rt-active", "STILL_ACTIVE", "Still Active"),
                            ("rt-rate", "RETENTION_RATE", "Retention Rate")])
coach_tbl = sql_table("rp-coach", "Coach Attach", COACH_SQL,
                       [("c-coach", "COACH_ATTACHED", "Coach Attached"), ("c-total", "TOTAL", "Total"),
                        ("c-attached", "ATTACHED", "Attached"), ("c-rate", "ATTACH_RATE", "Attach Rate")])

# `fact` itself, reused directly for page-2 live KPI tiles (same table the
# workbook uses — not a copy, so the report and workbook never disagree)
fact_tbl = b.fact_tbl
MF = "Fact"
CUR_F = f"[{MF}/Is Current Month]"
PRI_F = f"[{MF}/Is Prior Month]"

# ======================================================================
# Page 1 — Cover
# ======================================================================
def build_cover():
    els, lay = [], []
    els.append(image_el("cv-bg", solid_rect(PAGE_W, PAGE_H, BLACK), fit="stretch"))
    lay.append(rlx("cv-bg", 0, 0, PAGE_W, PAGE_H))

    els.append(image_el("cv-logo", LOGO_URI, fit="contain"))
    lay.append(rlx("cv-logo", CONTENT_X, 80, 160, 32))

    els.append(txt("cv-tag", para(span("CONFIDENTIAL · DEMONSTRATION DATA", color=GREEN_LIGHT, size=11, weight="bold"))))
    lay.append(rlx("cv-tag", CONTENT_X, 420, 500, 18))

    els.append(txt("cv-title1", heading(1, span("Nutrition Program", color=WHITE, size=44, weight="bold"))))
    lay.append(rlx("cv-title1", CONTENT_X, 448, 620, 60))
    els.append(txt("cv-title2", heading(1, span("Performance", color=WHITE, size=44, weight="bold"))))
    lay.append(rlx("cv-title2", CONTENT_X, 508, 620, 60))

    els.append(divider_el("cv-rule", GREEN))
    lay.append(rlx("cv-rule", CONTENT_X, 610, 80, 4))

    els.append(txt("cv-sub", para(span(
        "A Sigma analysis of BODi's nutrition subscription business — subscriber growth, "
        "revenue per account, program retention, and bundle performance across a rolling 24-month window.",
        color="#C8C8C8", size=15))))
    lay.append(rlx("cv-sub", CONTENT_X, 634, 600, 70))

    els.append(txt("cv-foot", para(span("Prepared for BODi · Built in Sigma · September 2026", color=GRAY, size=11))))
    lay.append(rlx("cv-foot", CONTENT_X, PAGE_H - 96, 600, 20))
    return els, lay

# ======================================================================
# Page 2 — Executive Summary
# ======================================================================
def report_kpi(elid, title, value_formula, fmt, comp_formula, x, y, w, h):
    cols = [{"id": f"{elid}v", "formula": value_formula, "name": title, "format": fmt}]
    kv = {"id": elid, "kind": "kpi-chart", "source": {"elementId": "fact", "kind": "table"},
          "value": {"columnId": f"{elid}v", "color": WHITE, "fontSize": 24},
          "name": {"text": title, "fontSize": 9, "color": "#C8C8C8"},
          "style": {"backgroundColor": INK, "borderRadius": "square"}}
    if comp_formula:
        cols.append({"id": f"{elid}c", "formula": comp_formula, "name": "Prior Month", "format": fmt})
        kv["comparisonColumn"] = {"columnId": f"{elid}c"}
        kv["comparison"] = {"display": "delta", "colorGood": GREEN_LIGHT, "colorBad": "#EB001B", "fontSize": 11}
    kv["columns"] = cols
    return [kv], [rlx(elid, x, y, w, h)]

def build_exec_summary(page_num=2):
    els, lay = page_chrome("p2", "Executive Summary", page_num)

    els.append(txt("p2-h1", heading(2, span(
        "Subscriber growth is decelerating as the base matures", color=INK, size=22, weight="bold"))))
    lay.append(rlx("p2-h1", CONTENT_X, 104, CONTENT_W, 44))

    body = ("Nutrition subscriptions have grown for six straight quarters, but the pace has cooled sharply — "
            "quarter-over-quarter growth ran from +38% down to roughly flat (+0.5% last quarter) as the earliest "
            "cohorts finish their programs faster than new members join. Revenue per subscriber has moved much "
            "less than subscriber counts over the same window — down about 7% from its peak, not eroded away — "
            "so the deceleration reads as a maturing base, not a monetization problem.")
    els.append(txt("p2-body", para(span(body, color=INK, size=12))))
    lay.append(rlx("p2-body", CONTENT_X, 154, CONTENT_W, 90))

    kpi_defs = [
        ("p2-k1", "ACTIVE SUBSCRIBERS",
         f"CountDistinct(If({CUR_F} And [{MF}/Nutrition Active],[{MF}/Member Id],Null))",
         f"CountDistinct(If({PRI_F} And [{MF}/Nutrition Active],[{MF}/Member Id],Null))", INT),
        ("p2-k2", "PRODUCT REVENUE",
         f"SumIf([{MF}/Product Revenue],{CUR_F})", f"SumIf([{MF}/Product Revenue],{PRI_F})", CUR),
        ("p2-k3", "ATTACH RATE",
         f"CountDistinct(If({CUR_F} And [{MF}/Nutrition Active],[{MF}/Member Id],Null))/CountDistinct(If({CUR_F},[{MF}/Member Id],Null))",
         f"CountDistinct(If({PRI_F} And [{MF}/Nutrition Active],[{MF}/Member Id],Null))/CountDistinct(If({PRI_F},[{MF}/Member Id],Null))", PCT1),
        ("p2-k4", "BLENDED RETENTION",
         f"CountDistinct(If({CUR_F} And [{MF}/Nutrition Active],[{MF}/Member Id],Null))/CountDistinct(If([{MF}/Nutrition Subscriber],[{MF}/Member Id],Null))",
         f"CountDistinct(If({PRI_F} And [{MF}/Nutrition Active],[{MF}/Member Id],Null))/CountDistinct(If([{MF}/Nutrition Subscriber],[{MF}/Member Id],Null))", PCT1),
    ]
    kw = (CONTENT_W - 3 * 12) / 4
    for i, (elid, title, cur, pri, fmt) in enumerate(kpi_defs):
        e, l = report_kpi(elid, title, cur, fmt, pri, CONTENT_X + i * (kw + 12), 258, kw, 112)
        els += e; lay += l

    els.append(txt("p2-h2", heading(3, span("What the data shows", color=INK, size=14, weight="bold"))))
    lay.append(rlx("p2-h2", CONTENT_X, 392, CONTENT_W, 26))

    body2 = ("Coach-attached members convert to a nutrition subscription at nearly a 15-point higher rate than "
             "members without a coach (see page 5) — the single biggest lever on attach in this dataset. Program "
             "choice matters even more for retention: 80 Day Obsession members are still active on their nutrition "
             "subscription at 12 months at more than 3x the rate of Barre Blend or 9 Week Control Freak members, "
             "and Insanity Max:30 members churn out of their nutrition subscription almost entirely by 12 months. "
             "Neither pattern is visible from a blended, all-programs KPI — both only show up once cohorts are "
             "split by the dimension that actually drives the behavior.")
    els.append(txt("p2-body2", para(span(body2, color=INK, size=12))))
    lay.append(rlx("p2-body2", CONTENT_X, 422, CONTENT_W, 130))

    els.append(divider_el("p2-rule", LINE))
    lay.append(rlx("p2-rule", CONTENT_X, 566, CONTENT_W, 1))

    body3 = ("The next four pages walk through subscriber growth and mix, revenue per subscriber, and retention "
             "by program and coach attachment — the same live figures behind the BODi — Nutrition Business "
             "workbook this report is paired with.")
    els.append(txt("p2-body3", para(span(body3, color=GRAY, size=11))))
    lay.append(rlx("p2-body3", CONTENT_X, 582, CONTENT_W, 50))

    return els, lay


CARD = {"backgroundColor": WHITE, "borderColor": LINE, "borderWidth": 1, "borderRadius": "square"}

def section_head(pid, y, title, body, body_h=70):
    els, lay = [], []
    els.append(txt(f"{pid}-h1", heading(2, span(title, color=INK, size=20, weight="bold"))))
    lay.append(rlx(f"{pid}-h1", CONTENT_X, y, CONTENT_W, 44))
    els.append(txt(f"{pid}-body", para(span(body, color=INK, size=12))))
    lay.append(rlx(f"{pid}-body", CONTENT_X, y + 50, CONTENT_W, body_h))
    return els, lay, y + 50 + body_h + 16


# ======================================================================
# Page 3 — Subscriber Growth & Mix
# ======================================================================
def build_growth(page_num=3):
    els, lay = page_chrome("p3", "Subscriber Growth & Mix", page_num)
    e, l, y = section_head("p3", 106,
        "Six straight quarters of growth, at a steadily slower pace",
        "Active nutrition subscribers have grown every quarter for the past six quarters, but quarter-over-"
        "quarter growth has cooled from +38% to roughly flat (+0.5% last quarter) as the earliest cohorts "
        "complete their programs faster than new members are joining. The mix across programs has stayed "
        "broadly stable — no single program is driving or dragging the trend.", body_h=90)
    els += e; lay += l

    bar1 = {"id": "p3-bar1", "kind": "bar-chart", "source": {"elementId": "rp-qtrtotal", "kind": "table"},
            "columns": [
                {"id": "p3b-q", "formula": "[Quarterly Total/Qtr Label]", "name": "Quarter"},
                {"id": "p3b-subs", "formula": "Sum([Quarterly Total/Active Subs])", "name": "Active Subscribers", "format": INT},
                {"id": "p3b-cat", "formula": '"Active Subscribers"', "name": "Series"}],
            "xAxis": {"columnId": "p3b-q"}, "yAxis": {"columnIds": ["p3b-subs"]},
            "color": {"by": "category", "column": "p3b-cat", "scheme": [GREEN_D]}, "legend": {"visibility": "hidden"},
            "name": {"text": "Active subscribers by quarter", "fontWeight": "bold", "fontSize": 12, "color": INK},
            "style": dict(CARD)}
    els.append(bar1); lay.append(rlx("p3-bar1", CONTENT_X, y, CONTENT_W, 180))
    y += 196

    tbl1 = {"id": "p3-tbl1", "kind": "table", "source": {"elementId": "rp-qtrtotal", "kind": "table"},
            "columns": [
                {"id": "p3t-q", "formula": "[Quarterly Total/Qtr Label]", "name": "Quarter"},
                {"id": "p3t-subs", "formula": "[Quarterly Total/Active Subs]", "name": "Active Subscribers", "format": INT},
                {"id": "p3t-growth", "formula": "[Quarterly Total/Growth Pct]", "name": "QoQ Growth", "format": PCT2}],
            "order": ["p3t-q", "p3t-subs", "p3t-growth"],
            "tableComponents": {"summaryBar": "hidden"},
            "tableStyle": {"preset": "presentation", "cellSpacing": "small"},
            "name": {"text": "Quarter-over-quarter growth", "fontWeight": "bold", "fontSize": 12, "color": INK},
            "style": dict(CARD)}
    els.append(tbl1); lay.append(rlx("p3-tbl1", CONTENT_X, y, CONTENT_W, 234))
    y += 250

    bar2 = {"id": "p3-bar2", "kind": "bar-chart", "source": {"elementId": "rp-qtr", "kind": "table"},
            "columns": [
                {"id": "p3c-q", "formula": "[Quarterly By Program/Qtr]", "name": "Quarter", "format": {"kind": "datetime", "formatString": "%b %Y"}},
                {"id": "p3c-prog", "formula": "[Quarterly By Program/Nutrition Program]", "name": "Nutrition Program"},
                {"id": "p3c-subs", "formula": "Sum([Quarterly By Program/Active Subs])", "name": "Active Subscribers", "format": INT}],
            "xAxis": {"columnId": "p3c-q"}, "yAxis": {"columnIds": ["p3c-subs"]},
            "color": {"by": "category", "column": "p3c-prog", "scheme": [GREEN_D, GREEN_LIGHT, "#8A8A8A"]},
            "stacking": "stacked", "legend": {"visibility": "visible"},
            "name": {"text": "Active subscriber mix by nutrition program", "fontWeight": "bold", "fontSize": 12, "color": INK},
            "style": dict(CARD)}
    els.append(bar2); lay.append(rlx("p3-bar2", CONTENT_X, y, CONTENT_W, 200))

    return els, lay


# ======================================================================
# Page 4 — Revenue per Subscriber
# ======================================================================
def build_revenue(page_num=4):
    els, lay = page_chrome("p4", "Revenue per Subscriber", page_num)
    e, l, y = section_head("p4", 106,
        "Revenue per subscriber has moved far less than subscriber growth",
        "Monthly revenue per active subscriber peaked at $120 two quarters into the window, drifted down to "
        "$112 by the most recent full quarter, and has ticked back up to $114 since — a swing of roughly 7%, "
        "against a subscriber count that grew nearly 80% over the same six quarters. That gap is the clearest "
        "sign the growth slowdown is a base-maturity effect, not a pricing or demand problem.", body_h=90)
    els += e; lay += l

    line1 = {"id": "p4-line1", "kind": "line-chart", "source": {"elementId": "rp-qtrtotal", "kind": "table"},
             "columns": [
                 {"id": "p4l-q", "formula": "[Quarterly Total/Qtr Label]", "name": "Quarter"},
                 {"id": "p4l-rpsm", "formula": "Sum([Quarterly Total/Revenue Per Sub Mo])", "name": "Revenue per Subscriber / Mo", "format": CUR2}],
             "xAxis": {"columnId": "p4l-q"}, "yAxis": {"columnIds": ["p4l-rpsm"], "format": {"scale": {"type": "linear", "zero": False}}},
             "name": {"text": "Revenue per active subscriber, per month", "fontWeight": "bold", "fontSize": 12, "color": INK},
             "legend": {"visibility": "hidden"}, "style": dict(CARD)}
    els.append(line1); lay.append(rlx("p4-line1", CONTENT_X, y, CONTENT_W, 200))
    y += 216

    bar1 = {"id": "p4-bar1", "kind": "bar-chart", "source": {"elementId": "rp-qtr", "kind": "table"},
            "columns": [
                {"id": "p4b-q", "formula": "[Quarterly By Program/Qtr]", "name": "Quarter", "format": {"kind": "datetime", "formatString": "%b %Y"}},
                {"id": "p4b-prog", "formula": "[Quarterly By Program/Nutrition Program]", "name": "Nutrition Program"},
                {"id": "p4b-rev", "formula": "Sum([Quarterly By Program/Revenue])", "name": "Revenue", "format": CUR}],
            "xAxis": {"columnId": "p4b-q"}, "yAxis": {"columnIds": ["p4b-rev"]},
            "color": {"by": "category", "column": "p4b-prog", "scheme": [GREEN_D, GREEN_LIGHT, "#8A8A8A"]},
            "stacking": "stacked", "legend": {"visibility": "visible"},
            "name": {"text": "Nutrition product revenue by program", "fontWeight": "bold", "fontSize": 12, "color": INK},
            "style": dict(CARD)}
    els.append(bar1); lay.append(rlx("p4-bar1", CONTENT_X, y, CONTENT_W, 200))

    return els, lay


# ======================================================================
# Page 5 — Retention by Program & Coach Attach
# ======================================================================
def build_retention(page_num=5):
    els, lay = page_chrome("p5", "Retention & Coach Attach", page_num)
    e, l, y = section_head("p5", 106,
        "Program choice and coach attachment are the two biggest levers",
        "Twelve-month retention on a nutrition subscription varies sharply by fitness program — 80 Day "
        "Obsession members are still active at more than 3x the rate of Barre Blend or 9 Week Control Freak "
        "members, and Insanity Max:30 members have almost entirely churned off their nutrition subscription "
        "by 12 months. Coach attachment tells a similar story on the front end: members with a coach convert "
        "to a nutrition subscription at nearly a 15-point higher rate than members without one.", body_h=90)
    els += e; lay += l

    bar1 = {"id": "p5-bar1", "kind": "bar-chart", "source": {"elementId": "rp-retention", "kind": "table"},
            "columns": [
                {"id": "p5b-prog", "formula": "[Retention By Program/Fitness Program]", "name": "Fitness Program"},
                {"id": "p5b-mo", "formula": "[Retention By Program/Months Since Signup]", "name": "Months Since Signup"},
                {"id": "p5b-rate", "formula": "Avg([Retention By Program/Retention Rate])", "name": "Retention Rate", "format": PCT1}],
            "xAxis": {"columnId": "p5b-prog", "sort": {"by": "p5b-rate", "direction": "descending"},
                      "format": {"labels": {"labelAngle": -30}}},
            "yAxis": {"columnIds": ["p5b-rate"]},
            "color": {"by": "category", "column": "p5b-mo", "scheme": [GREEN_LIGHT, GREEN, GREEN_D]},
            "stacking": "none", "legend": {"visibility": "visible"},
            "name": {"text": "Nutrition retention rate by fitness program (3 / 6 / 12 months)", "fontWeight": "bold", "fontSize": 12, "color": INK},
            "style": dict(CARD)}
    els.append(bar1); lay.append(rlx("p5-bar1", CONTENT_X, y, CONTENT_W, 240))
    y += 256

    bar2 = {"id": "p5-bar2", "kind": "bar-chart", "source": {"elementId": "rp-coach", "kind": "table"},
            "columns": [
                {"id": "p5c-coach", "formula": "If([Coach Attach/Coach Attached],\"Coach Attached\",\"No Coach\")", "name": "Coach Attached"},
                {"id": "p5c-coach2", "formula": "If([Coach Attach/Coach Attached],\"Coach Attached\",\"No Coach\")", "name": "Series"},
                {"id": "p5c-rate", "formula": "Avg([Coach Attach/Attach Rate])", "name": "Nutrition Attach Rate", "format": PCT1}],
            "xAxis": {"columnId": "p5c-coach", "sort": {"by": "p5c-rate", "direction": "descending"}},
            "yAxis": {"columnIds": ["p5c-rate"]},
            "color": {"by": "category", "column": "p5c-coach2", "scheme": [GREEN_D, "#8A8A8A"]},
            "legend": {"visibility": "hidden"},
            "name": {"text": "Nutrition attach rate — coached vs. uncoached members", "fontWeight": "bold", "fontSize": 12, "color": INK},
            "style": dict(CARD)}
    els.append(bar2); lay.append(rlx("p5-bar2", CONTENT_X, y, CONTENT_W, 170))

    return els, lay


# ======================================================================
# Page 6 — Methodology & Sources
# ======================================================================
def build_methodology(page_num=6):
    els, lay = page_chrome("p6", "Methodology & Sources", page_num)
    y = 106

    els.append(txt("p6-h1", heading(2, span("About this report", color=INK, size=20, weight="bold"))))
    lay.append(rlx("p6-h1", CONTENT_X, y, CONTENT_W, 40)); y += 48

    body1 = ("This report is built entirely in Sigma as a reports-as-code document — every table, chart, "
             "KPI and page is declared in a JSON specification and rendered by Sigma's report engine, with "
             "no manual layout. It is paired with the \"BODi — Nutrition Business\" Sigma workbook, which "
             "shares the same underlying data model and exposes these figures for interactive drill-down.")
    els.append(txt("p6-body1", para(span(body1, color=INK, size=12))))
    lay.append(rlx("p6-body1", CONTENT_X, y, CONTENT_W, 80)); y += 96

    els.append(divider_el("p6-rule1", LINE)); lay.append(rlx("p6-rule1", CONTENT_X, y, CONTENT_W, 1)); y += 20

    els.append(txt("p6-h2", heading(2, span("Data & disclosure", color=INK, size=20, weight="bold"))))
    lay.append(rlx("p6-h2", CONTENT_X, y, CONTENT_W, 40)); y += 48

    body2 = ("All figures in this report are drawn from a synthetic, deterministically generated dataset "
             "built for demonstration purposes and do not represent BODi's actual financial or operating "
             "results. The dataset models a cohort of members joining over a 24-month window, with signup "
             "channel, fitness program, coach attachment, and nutrition-program adoption assigned by seeded "
             "hash functions so results are reproducible from the same source SQL. Figures are queried live "
             "from Snowflake through Sigma at report-build time.")
    els.append(txt("p6-body2", para(span(body2, color=INK, size=12))))
    lay.append(rlx("p6-body2", CONTENT_X, y, CONTENT_W, 106)); y += 122

    els.append(divider_el("p6-rule2", LINE)); lay.append(rlx("p6-rule2", CONTENT_X, y, CONTENT_W, 1)); y += 20

    els.append(txt("p6-h3", heading(2, span("Definitions", color=INK, size=20, weight="bold"))))
    lay.append(rlx("p6-h3", CONTENT_X, y, CONTENT_W, 40)); y += 48

    defs = [
        ("Active subscriber", "A member with an active nutrition-product subscription in the given month."),
        ("Attach rate", "Share of all members in a period who are subscribed to a nutrition product."),
        ("Retention rate", "Share of nutrition subscribers still active N months after their nutrition signup month."),
        ("Revenue per subscriber", "Total nutrition product revenue in a month divided by active subscribers, per month."),
        ("Coach attached", "Member has an assigned BODi coach as of the current month."),
    ]
    body3 = "\n\n".join(f"**{span(term, color=INK, size=12)}** — {span(desc, color=GRAY, size=12)}" for term, desc in defs)
    els.append(txt("p6-body3", body3))
    lay.append(rlx("p6-body3", CONTENT_X, y, CONTENT_W, 170))

    return els, lay


def build_full_spec(name):
    cov_els, cov_lay = build_cover()
    ex_els, ex_lay = build_exec_summary()
    gr_els, gr_lay = build_growth()
    rv_els, rv_lay = build_revenue()
    rt_els, rt_lay = build_retention()
    mt_els, mt_lay = build_methodology()

    elements = [fact_tbl, qtr_tbl, qtr_total_tbl, retention_tbl, coach_tbl] + \
        cov_els + ex_els + gr_els + rv_els + rt_els + mt_els

    def pg(pid, layout_lines):
        return f'<Page id="{pid}">\n' + "\n".join(layout_lines) + f'\n</Page>'

    layout = '<?xml version="1.0" encoding="utf-8"?>\n' + "\n".join([
        pg("p1", cov_lay), pg("p2", ex_lay), pg("p3", gr_lay),
        pg("p4", rv_lay), pg("p5", rt_lay), pg("p6", mt_lay),
        pg("pdata", [
            rlx("fact", 0, 0, 100, 20), rlx("rp-qtr", 0, 20, 100, 20),
            rlx("rp-qtrtotal", 0, 40, 100, 20), rlx("rp-retention", 0, 60, 100, 20),
            rlx("rp-coach", 0, 80, 100, 20),
        ]),
    ])

    doc = {
        "schemaVersion": 1, "kind": "report", "elements": elements,
        "pages": [
            {"id": "p1", "name": "Cover"},
            {"id": "p2", "name": "Executive Summary"},
            {"id": "p3", "name": "Subscriber Growth & Mix"},
            {"id": "p4", "name": "Revenue per Subscriber"},
            {"id": "p5", "name": "Retention & Coach Attach"},
            {"id": "p6", "name": "Methodology & Sources"},
            {"id": "pdata", "name": "Data", "visibility": "hidden"},
        ],
        "settings": {"theme": {"overrides": {
            "categoricalScheme": [GREEN_D, GREEN, GREEN_LIGHT, INK, GRAY],
        }}},
        "config": {"margin": 0, "pageHeight": PAGE_H, "pageWidth": PAGE_W},
        "layout": layout,
    }
    return {"name": name, "folderId": FOLDER, "document": doc}


def build_smoke_spec():
    """Minimal 2-page spec (cover + exec summary) for early schema validation."""
    cov_els, cov_lay = build_cover()
    ex_els, ex_lay = build_exec_summary()
    elements = [fact_tbl] + cov_els + ex_els
    layout = f"""<?xml version="1.0" encoding="utf-8"?>
<Page id="p1">
{chr(10).join(cov_lay)}
</Page>
<Page id="p2">
{chr(10).join(ex_lay)}
</Page>
<Page id="pdata">
  <Element elementId="fact" x="0" y="0" width="100" height="20"/>
</Page>"""
    doc = {
        "schemaVersion": 1, "kind": "report", "elements": elements,
        "pages": [
            {"id": "p1", "name": "Cover"},
            {"id": "p2", "name": "Executive Summary"},
            {"id": "pdata", "name": "Data", "visibility": "hidden"},
        ],
        "config": {"margin": 0, "pageHeight": PAGE_H, "pageWidth": PAGE_W},
        "layout": layout,
    }
    return {"name": "BODi Nutrition Program Performance (SMOKE TEST - delete me)", "folderId": FOLDER, "document": doc}


NAME = "BODi — Nutrition Program Performance"

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "smoke"
    if cmd == "smoke":
        spec = build_smoke_spec()
    elif cmd in ("create", "update"):
        spec = build_full_spec(NAME)
    else:
        print("usage: build_report.py smoke|create|update <id>"); sys.exit(2)
    OUT.write_text(json.dumps(spec, indent=2))
    print("wrote", OUT, len(json.dumps(spec)), "bytes")
