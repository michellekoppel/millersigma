#!/usr/bin/env python3
"""BODi Nutrition Business workbook generator (workbooks-as-code, 2026-08 schema).

ONE page, three tabs: Command Center / Cohort Builder (marketing) /
Bundle & Promo Scenario Builder. ONE synthetic population (deterministic,
hash-seeded — no RANDOM()) exposed at two SQL grains:
  - `fact`       member x month  (~78K rows) — trends, retention curves, revenue over time
  - `member_snap` member grain    (~6K rows)  — cohort builder population + scenario baseline
Both are generated from the SAME layered CTE chain so the numbers agree.

Usage:
  python3 build_bodi.py probe    # tiny 1-page smoke test (SQL resolves?)
  python3 build_bodi.py create   # full build, POST new workbook
  python3 build_bodi.py update <workbook-id>   # PUT to an existing workbook id
"""
import json
import os
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
CONN = "9e79f38b-a310-405c-aad9-72f762ac6ff1"          # "Snowflake" connection, papercrane org
FOLDER = "004d8497-18ea-4cf6-a8c5-deca403c22d9"        # Michelle Koppel — My Documents (home folder)
OUT = pathlib.Path(__file__).parent / "spec.json"

# ---------------------------------------------------------------- formats
CUR = {"kind": "number", "formatString": "$.3~s", "currencySymbol": "$", "decimalSymbol": ".", "digitGroupingSymbol": ",", "digitGroupingSize": [3]}
CUR2 = {"kind": "number", "formatString": "$,.2f", "currencySymbol": "$", "decimalSymbol": ".", "digitGroupingSymbol": ",", "digitGroupingSize": [3]}
NUM = {"kind": "number", "formatString": ",.3~s"}
INT = {"kind": "number", "formatString": ",d"}
PCT1 = {"kind": "number", "formatString": ".1%"}
PCT2 = {"kind": "number", "formatString": "+,.1%"}

# ---------------------------------------------------------------- palette
# BODi's own brand colors, scraped from shop.bodi.com (not guessed):
#   #161819 near-black (nav/header bg, body text) · #000000 pure black
#   #208468 primary green (CTAs, "widget_primary_color") · #108474 darker/secondary green
#   #E8E8E8 light gray hairline · #EDF5F5 pale mint ("widget_secondary_color")
#   #EB001B their own red (sale/alert badges) — used here for BAD/alerts, not guessed
INK = "#161819"
BLACK = "#000000"
GREEN = "#208468"
GREEN_D = "#108474"
GREEN_LIGHT = "#5FBE9A"   # a lighter tint of the scraped green, for chart variety — not itself scraped
MINT = "#EDF5F5"
WHITE = "#FFFFFF"
GOOD = GREEN
BAD = "#EB001B"
CARD = {"backgroundColor": WHITE, "borderColor": "#E8E8E8", "borderWidth": 1, "borderRadius": "round"}
TINT = {"backgroundColor": MINT, "borderColor": "#E8E8E8", "borderWidth": 1, "borderRadius": "round"}
LOGO_URI = (pathlib.Path(__file__).parent / "assets" / "bodi_logo_datauri.txt").read_text().strip()

import base64
def grad(a, b):
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 240" preserveAspectRatio="xMidYMid slice"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{a}"/><stop offset="1" stop-color="{b}"/></linearGradient></defs><rect width="400" height="240" fill="url(#g)"/></svg>'
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
KG = [grad(BLACK, GREEN), grad(INK, GREEN_D), grad(GREEN_D, GREEN), grad(BLACK, GREEN_LIGHT), grad(INK, GREEN)]

# ======================================================================
# SQL — one deterministic synthetic population, two grains
# ======================================================================

BUNDLES = [
    # name, window month_idx (signup), eligible fitness programs, discount_pct, attach_boost
    ("Shake & Bar Starter Bundle", "(6,7)", "('21 Day Fix','Barre Blend')", 0.20, 0.15),
    ("Portion Fix Kickstart Bundle", "(14,15)", "('21 Day Fix','9 Week Control Freak')", 0.15, 0.12),
    ("2B Mindset + Shakeology Combo", "(20,21)", "('LIIFT4','P90X','Insanity Max:30')", 0.25, 0.18),
]

def _bundle_case(col):
    parts = [f"WHEN signup_month_idx IN {w} AND fitness_program IN {p} THEN {col}" for _, w, p, d, b in
             [(n, w, p, d, b) for n, w, p, d, b in BUNDLES]]
    return parts

def bundle_name_case():
    lines = [f"WHEN signup_month_idx IN {w} AND fitness_program IN {p} THEN '{n}'" for n, w, p, d, b in BUNDLES]
    return "CASE " + " ".join(lines) + " ELSE NULL END"

def bundle_discount_case():
    lines = [f"WHEN signup_month_idx IN {w} AND fitness_program IN {p} THEN {d}" for n, w, p, d, b in BUNDLES]
    return "CASE " + " ".join(lines) + " ELSE 0.0 END"

def bundle_boost_case():
    lines = [f"WHEN signup_month_idx IN {w} AND fitness_program IN {p} THEN {b}" for n, w, p, d, b in BUNDLES]
    return "CASE " + " ".join(lines) + " ELSE 0.0 END"

CTE_CHAIN = f"""
WITH months AS (
  SELECT (ROW_NUMBER() OVER (ORDER BY SEQ4())) - 1 AS month_idx
  FROM TABLE(GENERATOR(ROWCOUNT => 24))
),
members0 AS (
  SELECT (ROW_NUMBER() OVER (ORDER BY SEQ4())) AS member_id
  FROM TABLE(GENERATOR(ROWCOUNT => 6000))
),
members AS (
  SELECT member_id,
    MOD(ABS(HASH(member_id, 1)), 10000) / 10000.0 AS r1,
    MOD(ABS(HASH(member_id, 2)), 10000) / 10000.0 AS r2,
    MOD(ABS(HASH(member_id, 3)), 10000) / 10000.0 AS r3,
    MOD(ABS(HASH(member_id, 4)), 10000) / 10000.0 AS r4,
    MOD(ABS(HASH(member_id, 5)), 10000) / 10000.0 AS r5,
    MOD(ABS(HASH(member_id, 6)), 10000) / 10000.0 AS r6,
    MOD(ABS(HASH(member_id, 7)), 10000) / 10000.0 AS r7,
    MOD(ABS(HASH(member_id, 8)), 10000) / 10000.0 AS r8,
    MOD(ABS(HASH(member_id, 9)), 10000) / 10000.0 AS r9,
    MOD(ABS(HASH(member_id, 10)), 10000) / 10000.0 AS r10,
    MOD(ABS(HASH(member_id, 11)), 10000) / 10000.0 AS r11,
    MOD(ABS(HASH(member_id, 12)), 10000) / 10000.0 AS r12,
    MOD(ABS(HASH(member_id, 13)), 10000) / 10000.0 AS r13
  FROM members0
),
mem AS (
  SELECT
    member_id, r4, r5, r6, r7, r8, r9, r10, r11, r12, r13,
    FLOOR(r1 * 24)::INT AS signup_month_idx,
    CASE WHEN r2 < 0.28 THEN 'Organic'
         WHEN r2 < 0.52 THEN 'Paid Social'
         WHEN r2 < 0.62 THEN 'Influencer'
         WHEN r2 < 0.72 THEN 'Affiliate'
         WHEN r2 < 0.90 THEN 'Coach Referral'
         ELSE 'Retail' END AS signup_channel,
    CASE WHEN r3 < 0.22 THEN '21 Day Fix'
         WHEN r3 < 0.38 THEN 'LIIFT4'
         WHEN r3 < 0.48 THEN '80 Day Obsession'
         WHEN r3 < 0.62 THEN 'P90X'
         WHEN r3 < 0.74 THEN 'Insanity Max:30'
         WHEN r3 < 0.87 THEN 'Barre Blend'
         ELSE '9 Week Control Freak' END AS fitness_program
  FROM members
),
prog_dim AS (
  SELECT * FROM VALUES
    ('21 Day Fix', 1, 0.62, 9, 0.70),
    ('LIIFT4', 2, 0.38, 7, 0.60),
    ('80 Day Obsession', 3, 0.55, 10, 0.65),
    ('P90X', 3, 0.30, 6, 0.55),
    ('Insanity Max:30', 2, 0.28, 5, 0.50),
    ('Barre Blend', 2, 0.45, 8, 0.68),
    ('9 Week Control Freak', 3, 0.50, 8, 0.62)
  AS t(fitness_program, program_length_months, base_attach_prob, avg_tenure_months, completion_prob)
),
mem2 AS (
  SELECT mem.*, pd.program_length_months, pd.base_attach_prob, pd.avg_tenure_months, pd.completion_prob
  FROM mem JOIN prog_dim pd ON pd.fitness_program = mem.fitness_program
),
mem3 AS (
  SELECT mem2.*,
    (signup_channel = 'Coach Referral' OR r4 < 0.30) AS coach_attached
  FROM mem2
),
mem4 AS (
  SELECT mem3.*,
    {bundle_name_case()} AS bundle_name_if_eligible,
    {bundle_discount_case()} AS promo_discount_pct,
    {bundle_boost_case()} AS bundle_attach_boost
  FROM mem3
),
mem5 AS (
  SELECT mem4.*,
    (bundle_name_if_eligible IS NOT NULL) AS bundle_eligible,
    (bundle_name_if_eligible IS NOT NULL AND r5 < 0.5) AS bundle_flag
  FROM mem4
),
mem6 AS (
  SELECT mem5.*,
    IFF(bundle_flag, bundle_name_if_eligible, NULL) AS bundle_name_raw,
    GREATEST(0.03, LEAST(0.95,
      base_attach_prob
      + IFF(coach_attached, 0.12, 0)
      + IFF(signup_channel = 'Coach Referral', 0.05, 0)
      + IFF(bundle_flag, bundle_attach_boost, 0)
    )) AS adjusted_attach_prob
  FROM mem5
),
mem7 AS (
  SELECT mem6.*, (r6 < adjusted_attach_prob) AS nutrition_subscriber
  FROM mem6
),
mem8 AS (
  SELECT mem7.*,
    CASE WHEN NOT nutrition_subscriber THEN 'None'
      WHEN fitness_program IN ('21 Day Fix','9 Week Control Freak') THEN
        CASE WHEN r7 < 0.55 THEN 'Portion Fix' WHEN r7 < 0.85 THEN 'Ultimate Portion Fix' ELSE '2B Mindset' END
      WHEN fitness_program IN ('LIIFT4','P90X','Insanity Max:30') THEN
        CASE WHEN r7 < 0.65 THEN '2B Mindset' WHEN r7 < 0.85 THEN 'Portion Fix' ELSE 'Ultimate Portion Fix' END
      ELSE
        CASE WHEN r7 < 0.5 THEN '2B Mindset' WHEN r7 < 0.8 THEN 'Portion Fix' ELSE 'Ultimate Portion Fix' END
    END AS nutrition_program
  FROM mem7
),
mem9 AS (
  SELECT mem8.*,
    (nutrition_subscriber AND r8 < 0.68) AS shakeology_flag,
    (nutrition_program <> 'None') AS mealplan_flag,
    ((nutrition_subscriber AND r9 < 0.35) OR (NOT nutrition_subscriber AND r9 < 0.04)) AS bars_flag,
    GREATEST(2, ROUND(avg_tenure_months * (0.4 + r10 * 1.3)))::INT AS nutrition_tenure_months,
    (r11 < completion_prob) AS will_complete
  FROM mem8
),
mem10 AS (
  SELECT mem9.*, (signup_month_idx + nutrition_tenure_months) AS churn_month_idx
  FROM mem9
),
fact_rows AS (
  SELECT
    mem10.*, months.month_idx,
    (months.month_idx - mem10.signup_month_idx) AS months_since_signup,
    (months.month_idx = 23) AS is_current_month,
    (months.month_idx = 22) AS is_prior_month,
    (months.month_idx = 11) AS is_year_ago_month,
    DATEADD('month', mem10.signup_month_idx - 23, DATE_TRUNC('month', CURRENT_DATE())) AS signup_date,
    TO_CHAR(DATEADD('month', mem10.signup_month_idx - 23, DATE_TRUNC('month', CURRENT_DATE())), 'Mon YYYY') AS signup_cohort,
    ('Q' || DATE_PART('quarter', DATEADD('month', mem10.signup_month_idx - 23, DATE_TRUNC('month', CURRENT_DATE()))) || ' '
      || DATE_PART('year', DATEADD('month', mem10.signup_month_idx - 23, DATE_TRUNC('month', CURRENT_DATE())))) AS signup_cohort_qtr,
    DATEADD('month', months.month_idx - 23, DATE_TRUNC('month', CURRENT_DATE())) AS calendar_month
  FROM mem10
  CROSS JOIN months
  WHERE months.month_idx >= mem10.signup_month_idx
),
fc1 AS (
  SELECT fact_rows.*,
    CASE
      WHEN months_since_signup = 0 THEN 'Started'
      WHEN months_since_signup < program_length_months THEN 'Mid-Program'
      WHEN will_complete THEN 'Completed'
      ELSE 'Dropped'
    END AS program_stage,
    (months_since_signup >= program_length_months AND will_complete) AS completed_flag,
    (months_since_signup >= program_length_months AND NOT will_complete) AS dropped_flag
  FROM fact_rows
),
fc2 AS (
  SELECT fc1.*,
    GREATEST(20, LEAST(100, ROUND(55 + IFF(coach_attached, 15, 0) + IFF(completed_flag, 20, 0) + (r12 * 10 - 5)))) AS adherence_pct
  FROM fc1
),
fc3 AS (
  SELECT fc2.*,
    ROUND(-(2 + (adherence_pct / 100.0) * 6 + r13 * 3), 1) AS weight_change_pct
  FROM fc2
),
fc4 AS (
  SELECT fc3.*,
    (nutrition_subscriber AND months_since_signup < nutrition_tenure_months) AS nutrition_active,
    (nutrition_subscriber AND months_since_signup = nutrition_tenure_months - 1) AS nutrition_churned_this_month
  FROM fc3
),
fc5 AS (
  SELECT fc4.*,
    ROUND(IFF(nutrition_active AND shakeology_flag, 129 * IFF(months_since_signup = 0 AND bundle_flag, 1 - promo_discount_pct, 1), 0), 2) AS shake_revenue,
    ROUND(IFF(nutrition_active AND mealplan_flag, 44 * IFF(months_since_signup = 0 AND bundle_flag, 1 - promo_discount_pct, 1), 0), 2) AS mealplan_revenue,
    ROUND(IFF(nutrition_active AND bars_flag, 39 * IFF(months_since_signup = 0 AND bundle_flag, 1 - promo_discount_pct, 1), 0), 2) AS bars_revenue
  FROM fc4
),
fc6 AS (
  SELECT fc5.*,
    ROUND(shake_revenue + mealplan_revenue + bars_revenue, 2) AS product_revenue,
    ROUND(IFF(months_since_signup > 0 AND nutrition_active, shake_revenue + mealplan_revenue + bars_revenue, 0), 2) AS reorder_revenue,
    (months_since_signup = 0) AS first_purchase_flag,
    (months_since_signup > 0) AS reorder_flag,
    CASE
      WHEN shakeology_flag THEN GET(ARRAY_CONSTRUCT('Shakeology - Chocolate','Shakeology - Vanilla','Shakeology - Vegan Chocolate'), MOD(member_id, 3))::string
      WHEN mealplan_flag THEN nutrition_program || ' Program Kit'
      WHEN bars_flag THEN 'Beachbar & Boost Bundle'
      ELSE NULL
    END AS primary_sku,
    CASE WHEN shakeology_flag THEN 0.62 WHEN mealplan_flag THEN 0.70 WHEN bars_flag THEN 0.55 ELSE NULL END AS sku_margin_pct,
    GREATEST(7, ROUND(30 * (2 - adherence_pct / 100.0)))::INT AS time_to_first_reorder_days,
    COALESCE(bundle_name_raw, 'None') AS bundle_name,
    COALESCE(bundle_name_if_eligible, 'Not Eligible') AS bundle_campaign
  FROM fc5
)
"""

FACT_SQL = CTE_CHAIN + """
SELECT
  member_id, signup_date, signup_cohort, signup_cohort_qtr, calendar_month, months_since_signup, is_current_month,
  is_prior_month, is_year_ago_month,
  signup_channel, coach_attached, fitness_program, program_stage, completed_flag, dropped_flag,
  adherence_pct, weight_change_pct,
  nutrition_subscriber, nutrition_program, nutrition_active, nutrition_churned_this_month,
  shakeology_flag, mealplan_flag, bars_flag,
  bundle_eligible, bundle_name, bundle_campaign, bundle_flag, promo_discount_pct,
  first_purchase_flag, reorder_flag,
  shake_revenue, mealplan_revenue, bars_revenue, product_revenue, reorder_revenue,
  primary_sku, sku_margin_pct, time_to_first_reorder_days
FROM fc6
"""

SNAP_SQL = CTE_CHAIN + """
SELECT
  member_id,
  MAX(signup_date) AS signup_date,
  MAX(signup_cohort) AS signup_cohort,
  MAX(signup_channel) AS signup_channel,
  (MAX(IFF(coach_attached, 1, 0)) = 1) AS coach_attached,
  MAX(fitness_program) AS fitness_program,
  (MAX(IFF(nutrition_subscriber, 1, 0)) = 1) AS nutrition_subscriber,
  MAX(nutrition_program) AS nutrition_program,
  (MAX(IFF(bundle_eligible, 1, 0)) = 1) AS bundle_eligible,
  MAX(bundle_name) AS bundle_name,
  MAX(bundle_campaign) AS bundle_campaign,
  (MAX(IFF(bundle_flag, 1, 0)) = 1) AS bundle_flag,
  MAX(promo_discount_pct) AS promo_discount_pct,
  MAX(primary_sku) AS primary_sku,
  MAX(IFF(is_current_month, program_stage, NULL)) AS program_stage_now,
  (MAX(IFF(is_current_month, IFF(nutrition_active, 1, 0), NULL)) = 1) AS nutrition_active_now,
  MAX(IFF(is_current_month, adherence_pct, NULL)) AS adherence_pct_now,
  MAX(IFF(is_current_month, weight_change_pct, NULL)) AS weight_change_pct_now,
  MAX(IFF(first_purchase_flag, product_revenue, NULL)) AS initial_purchase_revenue,
  SUM(product_revenue) AS lifetime_revenue,
  SUM(reorder_revenue) AS lifetime_reorder_revenue,
  MAX(time_to_first_reorder_days) AS time_to_first_reorder_days
FROM fc6
GROUP BY member_id
"""

# TRANSACTIONS_SQL — one row per real purchase EVENT, not per member-month.
# Unpivots fc6's three revenue columns (shake/mealplan/bars) into individual
# transaction records, one branch per product line, kept only where that
# line actually has revenue > 0 that month. UNIT_PRICE is a FIXED catalog
# price per product line (129 / 44 / 39 — the same constants `fc6` uses and
# that "Price Base" in the Pricing Scenario tab lists as CURRENT_PRICE), so
# it never varies by transaction. QUANTITY is 1-3 units (deterministically
# hashed, mostly 1). Any bundle discount at first purchase is applied to the
# line's AMOUNT only (a percent off the order), never to UNIT_PRICE itself —
# AMOUNT = UNIT_PRICE * QUANTITY * (1 - discount, when a bundle applies).
TRANSACTIONS_SQL = CTE_CHAIN + """
, txns AS (
  SELECT member_id, calendar_month, signup_channel, coach_attached, fitness_program, nutrition_program,
         bundle_name, first_purchase_flag, reorder_flag, bundle_flag, promo_discount_pct,
         'Shakeology' AS product_line,
         GET(ARRAY_CONSTRUCT('Shakeology - Chocolate','Shakeology - Vanilla','Shakeology - Vegan Chocolate'), MOD(member_id, 3))::string AS sku,
         129.0 AS unit_price
  FROM fc6
  WHERE shake_revenue > 0

  UNION ALL

  SELECT member_id, calendar_month, signup_channel, coach_attached, fitness_program, nutrition_program,
         bundle_name, first_purchase_flag, reorder_flag, bundle_flag, promo_discount_pct,
         'Meal Plan' AS product_line,
         (nutrition_program || ' Program Kit') AS sku,
         44.0 AS unit_price
  FROM fc6
  WHERE mealplan_revenue > 0

  UNION ALL

  SELECT member_id, calendar_month, signup_channel, coach_attached, fitness_program, nutrition_program,
         bundle_name, first_purchase_flag, reorder_flag, bundle_flag, promo_discount_pct,
         'Bars & Supplements' AS product_line,
         'Beachbar & Boost Bundle' AS sku,
         39.0 AS unit_price
  FROM fc6
  WHERE bars_revenue > 0
),
txns2 AS (
  SELECT *,
    CASE WHEN MOD(ABS(HASH(member_id, calendar_month, sku, 99)), 100) < 70 THEN 1
         WHEN MOD(ABS(HASH(member_id, calendar_month, sku, 99)), 100) < 90 THEN 2
         ELSE 3 END AS quantity
  FROM txns
)
SELECT
  MD5(member_id || '|' || calendar_month::string || '|' || product_line) AS transaction_id,
  member_id,
  DATEADD('day', MOD(ABS(HASH(member_id, calendar_month, product_line)), 28), calendar_month) AS transaction_date,
  product_line,
  sku,
  unit_price,
  quantity,
  ROUND(unit_price * quantity * IFF(bundle_flag AND first_purchase_flag, 1 - promo_discount_pct, 1), 2) AS amount,
  first_purchase_flag AS is_first_purchase,
  reorder_flag AS is_reorder,
  (bundle_flag AND first_purchase_flag) AS is_bundle_purchase,
  IFF(bundle_flag AND first_purchase_flag, promo_discount_pct, 0.0) AS promo_discount_pct,
  IFF(bundle_flag AND first_purchase_flag, bundle_name, 'None') AS bundle_name,
  fitness_program,
  nutrition_program,
  signup_channel,
  coach_attached
FROM txns2
ORDER BY member_id, transaction_date
"""

# ======================================================================
# Sigma elements — the two base tables
# ======================================================================

FACT_COLS = [
    ("f-member", "MEMBER_ID", "Member Id"), ("f-signup", "SIGNUP_DATE", "Signup Date"),
    ("f-cohort", "SIGNUP_COHORT", "Signup Cohort"), ("f-cohortq", "SIGNUP_COHORT_QTR", "Signup Cohort Qtr"),
    ("f-cal", "CALENDAR_MONTH", "Calendar Month"),
    ("f-msince", "MONTHS_SINCE_SIGNUP", "Months Since Signup"), ("f-iscur", "IS_CURRENT_MONTH", "Is Current Month"),
    ("f-isprior", "IS_PRIOR_MONTH", "Is Prior Month"), ("f-isyearago", "IS_YEAR_AGO_MONTH", "Is Year Ago Month"),
    ("f-chan", "SIGNUP_CHANNEL", "Signup Channel"), ("f-coach", "COACH_ATTACHED", "Coach Attached"),
    ("f-fitprog", "FITNESS_PROGRAM", "Fitness Program"), ("f-stage", "PROGRAM_STAGE", "Program Stage"),
    ("f-completed", "COMPLETED_FLAG", "Completed Flag"), ("f-dropped", "DROPPED_FLAG", "Dropped Flag"),
    ("f-adherence", "ADHERENCE_PCT", "Adherence Pct"), ("f-weight", "WEIGHT_CHANGE_PCT", "Weight Change Pct"),
    ("f-nutsub", "NUTRITION_SUBSCRIBER", "Nutrition Subscriber"), ("f-nutprog", "NUTRITION_PROGRAM", "Nutrition Program"),
    ("f-nutactive", "NUTRITION_ACTIVE", "Nutrition Active"), ("f-nutchurn", "NUTRITION_CHURNED_THIS_MONTH", "Nutrition Churned This Month"),
    ("f-shake", "SHAKEOLOGY_FLAG", "Shakeology Flag"), ("f-meal", "MEALPLAN_FLAG", "Mealplan Flag"), ("f-bars", "BARS_FLAG", "Bars Flag"),
    ("f-bunelig", "BUNDLE_ELIGIBLE", "Bundle Eligible"), ("f-bunname", "BUNDLE_NAME", "Bundle Name"),
    ("f-buncamp", "BUNDLE_CAMPAIGN", "Bundle Campaign"),
    ("f-bunflag", "BUNDLE_FLAG", "Bundle Flag"), ("f-discount", "PROMO_DISCOUNT_PCT", "Promo Discount Pct"),
    ("f-firstp", "FIRST_PURCHASE_FLAG", "First Purchase Flag"), ("f-reorderf", "REORDER_FLAG", "Reorder Flag"),
    ("f-shakerev", "SHAKE_REVENUE", "Shake Revenue"), ("f-mealrev", "MEALPLAN_REVENUE", "Mealplan Revenue"),
    ("f-barsrev", "BARS_REVENUE", "Bars Revenue"), ("f-prodrev", "PRODUCT_REVENUE", "Product Revenue"),
    ("f-reorderrev", "REORDER_REVENUE", "Reorder Revenue"), ("f-sku", "PRIMARY_SKU", "Primary Sku"),
    ("f-margin", "SKU_MARGIN_PCT", "Sku Margin Pct"), ("f-ttfr", "TIME_TO_FIRST_REORDER_DAYS", "Time To First Reorder Days"),
]
SNAP_COLS = [
    ("s-member", "MEMBER_ID", "Member Id"), ("s-signup", "SIGNUP_DATE", "Signup Date"),
    ("s-cohort", "SIGNUP_COHORT", "Signup Cohort"), ("s-chan", "SIGNUP_CHANNEL", "Signup Channel"),
    ("s-coach", "COACH_ATTACHED", "Coach Attached"), ("s-fitprog", "FITNESS_PROGRAM", "Fitness Program"),
    ("s-nutsub", "NUTRITION_SUBSCRIBER", "Nutrition Subscriber"), ("s-nutprog", "NUTRITION_PROGRAM", "Nutrition Program"),
    ("s-bunelig", "BUNDLE_ELIGIBLE", "Bundle Eligible"), ("s-bunname", "BUNDLE_NAME", "Bundle Name"),
    ("s-buncamp", "BUNDLE_CAMPAIGN", "Bundle Campaign"),
    ("s-bunflag", "BUNDLE_FLAG", "Bundle Flag"), ("s-discount", "PROMO_DISCOUNT_PCT", "Promo Discount Pct"),
    ("s-sku", "PRIMARY_SKU", "Primary Sku"),
    ("s-stagenow", "PROGRAM_STAGE_NOW", "Program Stage Now"), ("s-activenow", "NUTRITION_ACTIVE_NOW", "Nutrition Active Now"),
    ("s-adherencenow", "ADHERENCE_PCT_NOW", "Adherence Pct Now"), ("s-weightnow", "WEIGHT_CHANGE_PCT_NOW", "Weight Change Pct Now"),
    ("s-initrev", "INITIAL_PURCHASE_REVENUE", "Initial Purchase Revenue"), ("s-liferev", "LIFETIME_REVENUE", "Lifetime Revenue"),
    ("s-lifereorder", "LIFETIME_REORDER_REVENUE", "Lifetime Reorder Revenue"), ("s-ttfr", "TIME_TO_FIRST_REORDER_DAYS", "Time To First Reorder Days"),
]

def sql_table(elid, name, sql, cols):
    return {"id": elid, "kind": "table", "name": name, "visibleAsSource": True,
            "source": {"connectionId": CONN, "kind": "sql", "statement": sql},
            "columns": [{"id": c, "formula": f"[Custom SQL/{s}]", "name": d} for c, s, d in cols],
            "order": [c[0] for c in cols]}

fact_tbl = sql_table("fact", "Fact", FACT_SQL, FACT_COLS)
snap_tbl = sql_table("snap", "Member Snapshot", SNAP_SQL, SNAP_COLS)

# ======================================================================
# probe — minimal build to prove the SQL resolves at CREATE time
# ======================================================================

def probe_spec():
    kpi_cols = [
        {"id": "p-members", "formula": "CountDistinct([Member Snapshot/Member Id])", "name": "Members"},
        {"id": "p-attach", "formula": "CountDistinct(If([Member Snapshot/Nutrition Subscriber],[Member Snapshot/Member Id],Null))/CountDistinct([Member Snapshot/Member Id])", "name": "Attach Rate"},
    ]
    kpi = {"id": "kpi1", "kind": "kpi-chart", "source": {"elementId": "snap", "kind": "table"},
           "columns": kpi_cols,
           "value": {"columnId": "p-members"}, "name": {"text": "Members (probe)"}}
    kpi2 = {"id": "kpi2", "kind": "kpi-chart", "source": {"elementId": "snap", "kind": "table"},
            "columns": [kpi_cols[1]], "value": {"columnId": "p-attach"}, "name": {"text": "Attach rate (probe)"}}
    title = {"id": "ttl", "kind": "text", "body": "# BODi probe", "verticalAlign": "middle"}
    elements = [fact_tbl, snap_tbl, title, kpi, kpi2]
    layout = """<?xml version="1.0" encoding="utf-8"?>
<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="pg">
  <Element elementId="ttl" gridColumn="1 / 25" gridRow="1 / 3"/>
  <Element elementId="kpi1" gridColumn="1 / 13" gridRow="3 / 11"/>
  <Element elementId="kpi2" gridColumn="13 / 25" gridRow="3 / 11"/>
</Page>
<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="pgdata">
  <Element elementId="fact" gridColumn="1 / 25" gridRow="1 / 5"/>
  <Element elementId="snap" gridColumn="1 / 25" gridRow="5 / 10"/>
</Page>"""
    doc = {"schemaVersion": 1, "kind": "workbook", "elements": elements,
           "pages": [{"id": "pg", "name": "Probe"}, {"id": "pgdata", "name": "Data", "visibility": "hidden"}],
           "layout": layout}
    return {"name": "BODi probe (delete me)", "folderId": FOLDER, "document": doc}


# ======================================================================
# Element helpers
# ======================================================================
_uid = [0]
def uid(prefix):
    _uid[0] += 1
    return f"{prefix}{_uid[0]}"

def gcard(elid, source, title, value_formula, fmt, comp_formula, bg, sub=None,
          trend_formula=None, trend_date_formula=None, col=(1, 25), row=(1, 9)):
    """Gradient comparative KPI card — Command Center look. Optional trend sparkline."""
    cid = f"c-{elid}"
    cont = {"id": cid, "kind": "container", "style": {"borderRadius": "round"},
            "backgroundImage": {"source": {"kind": "url", "url": bg}, "style": {"fit": "cover"}}}
    cols = [{"id": f"k-{elid}v", "formula": value_formula, "name": title, "format": fmt}]
    kv = {"id": f"k-{elid}", "kind": "kpi-chart", "source": {"elementId": source, "kind": "table"},
          "value": {"columnId": f"k-{elid}v", "color": WHITE, "fontSize": 24},
          "name": {"text": title, "fontSize": 12, "color": WHITE},
          "style": {"backgroundColor": "transparent"}}
    if comp_formula:
        cols.append({"id": f"k-{elid}c", "formula": comp_formula, "name": "Comparison", "format": fmt})
        kv["comparisonColumn"] = {"columnId": f"k-{elid}c"}
        kv["comparison"] = {"display": "delta", "colorGood": "#D9F2E6", "colorBad": "#FFDCD3", "fontSize": 12}
    kv["columns"] = cols
    els = [cont, kv]
    sub_el = None
    if sub:
        sub_el = {"id": f"sub-{elid}", "kind": "text", "body": sub, "verticalAlign": "start", "style": {"color": "#EAF6F3"}}
        els.append(sub_el)
    if trend_formula:
        ln = {"id": f"ln-{elid}", "kind": "line-chart", "source": {"elementId": source, "kind": "table"},
              "columns": [{"id": f"ln-{elid}m", "formula": trend_date_formula, "name": "Month",
                           "format": {"kind": "datetime", "formatString": "%b %Y"}},
                          {"id": f"ln-{elid}v", "formula": trend_formula, "name": "Trend"}],
              "xAxis": {"columnId": f"ln-{elid}m", "format": {"marks": "none", "labels": "hidden"}},
              "yAxis": {"columnIds": [f"ln-{elid}v"], "format": {"labels": "hidden", "marks": "none", "scale": {"type": "linear", "zero": False}}},
              "name": {"visibility": "hidden"}, "legend": {"visibility": "hidden"},
              "lineAreaStyle": {"interpolation": "monotone"}, "style": {"backgroundColor": "transparent"}}
        els.append(ln)
        body = (f'    <Element elementId="k-{elid}" gridColumn="1 / 13" gridRow="1 / 6"/>\n'
                + (f'    <Element elementId="sub-{elid}" gridColumn="1 / 13" gridRow="6 / 7"/>\n' if sub_el else "")
                + f'    <Element elementId="ln-{elid}" gridColumn="1 / 13" gridRow="7 / 10"/>\n')
    else:
        body = (f'    <Element elementId="k-{elid}" gridColumn="1 / 13" gridRow="1 / 8"/>\n'
                + (f'    <Element elementId="sub-{elid}" gridColumn="1 / 13" gridRow="8 / 10"/>\n' if sub_el else ""))
    layout = (f'  <Container elementId="{cid}" type="grid" gridColumn="{col[0]} / {col[1]}" gridRow="{row[0]} / {row[1]}" '
              f'gridTemplateColumns="repeat(12,1fr)" gridTemplateRows="auto">\n{body}  </Container>')
    return els, layout

def plain_kpi(elid, source, title, value_formula, fmt, comp_formula=None, col=(1, 25), row=(1, 9)):
    """Clean light comparison-delta KPI — data-app look (Cohort/Scenario tabs)."""
    cols = [{"id": f"k-{elid}v", "formula": value_formula, "name": title, "format": fmt}]
    kv = {"id": f"k-{elid}", "kind": "kpi-chart", "source": {"elementId": source, "kind": "table"},
          "value": {"columnId": f"k-{elid}v", "color": INK, "fontSize": 26},
          "name": {"text": title, "fontSize": 12, "color": GREEN_D},
          "style": {**CARD}}
    if comp_formula:
        cols.append({"id": f"k-{elid}c", "formula": comp_formula, "name": "Comparison", "format": fmt})
        kv["comparisonColumn"] = {"columnId": f"k-{elid}c"}
        kv["comparison"] = {"display": "delta", "colorGood": GOOD, "colorBad": BAD, "fontSize": 12}
    kv["columns"] = cols
    layout = f'  <Element elementId="k-{elid}" gridColumn="{col[0]} / {col[1]}" gridRow="{row[0]} / {row[1]}"/>'
    return [kv], layout

def text_el(elid, body, color=INK, valign="middle"):
    return {"id": elid, "kind": "text", "body": body, "verticalAlign": valign, "style": {"color": color}}

def divider_el(elid):
    return {"id": elid, "kind": "divider"}

def container_wrap(cid, children_layout, col, row, cols_grid=24, style=None, bg_url=None):
    c = {"id": cid, "kind": "container", "style": style or dict(CARD)}
    if bg_url:
        c["backgroundImage"] = {"source": {"kind": "url", "url": bg_url}, "style": {"fit": "cover"}}
    layout = (f'  <Container elementId="{cid}" type="grid" gridColumn="{col[0]} / {col[1]}" gridRow="{row[0]} / {row[1]}" '
              f'gridTemplateColumns="repeat({cols_grid},1fr)" gridTemplateRows="auto">\n{children_layout}\n  </Container>')
    return c, layout

def elx(elid, col, row):
    return f'    <Element elementId="{elid}" gridColumn="{col[0]} / {col[1]}" gridRow="{row[0]} / {row[1]}"/>'


# ======================================================================
# TAB 1 — Command Center
# ======================================================================
MF = "Fact"
CUR_F = f'[{MF}/Is Current Month]'
PRI_F = f'[{MF}/Is Prior Month]'

def build_command_center():
    els, lays = [], []

    KDEFS = [
        ("subs", "ACTIVE NUTRITION SUBSCRIBERS",
         f'CountDistinct(If({CUR_F} And [{MF}/Nutrition Active],[{MF}/Member Id],Null))',
         f'CountDistinct(If({PRI_F} And [{MF}/Nutrition Active],[{MF}/Member Id],Null))',
         INT, f'CountDistinct(If([{MF}/Nutrition Active],[{MF}/Member Id],Null))'),
        ("retention", "BLENDED NUTRITION RETENTION",
         f'CountDistinct(If({CUR_F} And [{MF}/Nutrition Active],[{MF}/Member Id],Null))/CountDistinct(If([{MF}/Nutrition Subscriber],[{MF}/Member Id],Null))',
         f'CountDistinct(If({PRI_F} And [{MF}/Nutrition Active],[{MF}/Member Id],Null))/CountDistinct(If([{MF}/Nutrition Subscriber],[{MF}/Member Id],Null))',
         PCT1, f'CountDistinct(If([{MF}/Nutrition Active],[{MF}/Member Id],Null))/CountDistinct(If([{MF}/Nutrition Subscriber],[{MF}/Member Id],Null))'),
        ("attach", "NUTRITION ATTACH RATE",
         f'CountDistinct(If({CUR_F} And [{MF}/Nutrition Active],[{MF}/Member Id],Null))/CountDistinct(If({CUR_F},[{MF}/Member Id],Null))',
         f'CountDistinct(If({PRI_F} And [{MF}/Nutrition Active],[{MF}/Member Id],Null))/CountDistinct(If({PRI_F},[{MF}/Member Id],Null))',
         PCT1, f'CountDistinct(If([{MF}/Nutrition Active],[{MF}/Member Id],Null))/CountDistinct([{MF}/Member Id])'),
        ("rev", "NUTRITION PRODUCT REVENUE",
         f'SumIf([{MF}/Product Revenue],{CUR_F})', f'SumIf([{MF}/Product Revenue],{PRI_F})',
         CUR, f'Sum([{MF}/Product Revenue])'),
        ("reorderrev", "REORDER REVENUE",
         f'SumIf([{MF}/Reorder Revenue],{CUR_F})', f'SumIf([{MF}/Reorder Revenue],{PRI_F})',
         CUR, f'Sum([{MF}/Reorder Revenue])'),
        ("completion", "AVG PROGRAM COMPLETION RATE",
         f'CountDistinct(If({CUR_F} And [{MF}/Completed Flag],[{MF}/Member Id],Null))/CountDistinct(If({CUR_F} And ([{MF}/Completed Flag] Or [{MF}/Dropped Flag]),[{MF}/Member Id],Null))',
         f'CountDistinct(If({PRI_F} And [{MF}/Completed Flag],[{MF}/Member Id],Null))/CountDistinct(If({PRI_F} And ([{MF}/Completed Flag] Or [{MF}/Dropped Flag]),[{MF}/Member Id],Null))',
         PCT1, f'CountDistinct(If([{MF}/Completed Flag],[{MF}/Member Id],Null))/CountDistinct(If([{MF}/Completed Flag] Or [{MF}/Dropped Flag],[{MF}/Member Id],Null))'),
    ]
    for i, (key, title, curf, prif, fmt, trendf) in enumerate(KDEFS):
        e, l = gcard(key, "fact", title, curf, fmt, prif, KG[i % len(KG)],
                     trend_formula=trendf, trend_date_formula=f'[{MF}/Calendar Month]',
                     col=(1 + i * 4, 1 + (i + 1) * 4), row=(1, 12))
        els += e; lays.append(l)

    hdr = text_el("cc-hdr", "## Command Center\nHow's the nutrition business doing?", color=INK)
    lays.append(elx("cc-hdr", (1, 25), (13, 15)))
    els.append(hdr)

    # trend chart 1 — subscriber growth/churn by nutrition program, stacked area
    area1 = {"id": "area-subs", "kind": "area-chart",
             "source": {"elementId": "fact", "kind": "table"},
             "columns": [
                 {"id": "a1-m", "formula": f"[{MF}/Calendar Month]", "name": "Month", "format": {"kind": "datetime", "formatString": "%b %Y"}},
                 {"id": "a1-prog", "formula": f"[{MF}/Nutrition Program]", "name": "Nutrition Program"},
                 {"id": "a1-v", "formula": f"CountDistinct(If([{MF}/Nutrition Active],[{MF}/Member Id],Null))", "name": "Active Subscribers", "format": INT}],
             "xAxis": {"columnId": "a1-m"}, "yAxis": {"columnIds": ["a1-v"]},
             "color": {"by": "category", "column": "a1-prog", "scheme": [GREEN_D, GREEN, GREEN_LIGHT, "#C8C8C8"]},
             "stacking": "stacked", "legend": {"visibility": "visible"},
             "name": {"text": "Subscriber growth & churn by nutrition program (24 mo)", "fontWeight": "bold", "fontSize": 14, "color": INK},
             "style": dict(CARD)}
    els.append(area1); lays.append(elx("area-subs", (1, 9), (16, 42)))

    # trend chart 2 — revenue by product line, stacked bar
    bar2 = {"id": "bar-rev", "kind": "bar-chart", "source": {"elementId": "fact", "kind": "table"},
            "columns": [
                {"id": "b2-m", "formula": f"[{MF}/Calendar Month]", "name": "Month", "format": {"kind": "datetime", "formatString": "%b %Y"}},
                {"id": "b2-shake", "formula": f"Sum([{MF}/Shake Revenue])", "name": "Shakeology", "format": CUR},
                {"id": "b2-meal", "formula": f"Sum([{MF}/Mealplan Revenue])", "name": "Meal Plans", "format": CUR},
                {"id": "b2-bars", "formula": f"Sum([{MF}/Bars Revenue])", "name": "Bars & Supplements", "format": CUR}],
            "xAxis": {"columnId": "b2-m"}, "yAxis": {"columnIds": ["b2-shake", "b2-meal", "b2-bars"]},
            "stacking": "stacked", "legend": {"visibility": "visible"},
            "name": {"text": "Revenue by product line — Shakeology vs meal plans vs bars/supplements", "fontWeight": "bold", "fontSize": 14, "color": INK},
            "style": dict(CARD)}
    els.append(bar2); lays.append(elx("bar-rev", (9, 17), (16, 42)))

    # trend chart 3 — cohort retention curves overlaid by launch cohort (quarter)
    line3 = {"id": "line-retention", "kind": "line-chart", "source": {"elementId": "fact", "kind": "table"},
             "columns": [
                 {"id": "l3-x", "formula": f"[{MF}/Months Since Signup]", "name": "Months Since Signup"},
                 {"id": "l3-cohort", "formula": f"[{MF}/Signup Cohort Qtr]", "name": "Launch Cohort"},
                 {"id": "l3-v", "formula": f"CountDistinct(If([{MF}/Nutrition Active],[{MF}/Member Id],Null))/CountDistinct(If([{MF}/Nutrition Subscriber],[{MF}/Member Id],Null))",
                  "name": "Retention Rate", "format": PCT1}],
             "xAxis": {"columnId": "l3-x"}, "yAxis": {"columnIds": ["l3-v"]},
             "color": {"by": "category", "column": "l3-cohort", "scheme": [GREEN_D, GREEN, GREEN_LIGHT, INK, "#4A4A4A", "#8A8A8A", "#0B5C47", "#9FDBC0"]},
             "legend": {"visibility": "visible"}, "lineAreaStyle": {"interpolation": "monotone"},
             "name": {"text": "Cohort retention curves — overlaid by program launch cohort", "fontWeight": "bold", "fontSize": 14, "color": INK},
             "style": dict(CARD)}
    els.append(line3); lays.append(elx("line-retention", (17, 25), (16, 42)))

    # alerts / callouts — grouped table with conditional formatting
    alerts_hdr = text_el("cc-alerts-hdr", "**Alerts — programs outside normal attach/retention range**", color=BAD)
    lays.append(elx("cc-alerts-hdr", (1, 25), (43, 45)))
    els.append(alerts_hdr)
    alerts = {"id": "tbl-alerts", "kind": "table", "source": {"elementId": "fact", "kind": "table"},
              "columns": [
                  {"id": "al-prog", "formula": f"[{MF}/Fitness Program]", "name": "Fitness Program"},
                  {"id": "al-attach", "formula": f"CountDistinct(If({CUR_F} And [{MF}/Nutrition Active],[{MF}/Member Id],Null))/CountDistinct(If({CUR_F},[{MF}/Member Id],Null))", "name": "Attach Rate", "format": PCT1},
                  {"id": "al-ret", "formula": f"CountDistinct(If({CUR_F} And [{MF}/Nutrition Active],[{MF}/Member Id],Null))/CountDistinct(If([{MF}/Nutrition Subscriber],[{MF}/Member Id],Null))", "name": "Retention Rate", "format": PCT1},
                  {"id": "al-comp", "formula": f"CountDistinct(If({CUR_F} And [{MF}/Completed Flag],[{MF}/Member Id],Null))/CountDistinct(If({CUR_F} And ([{MF}/Completed Flag] Or [{MF}/Dropped Flag]),[{MF}/Member Id],Null))", "name": "Completion Rate", "format": PCT1}],
              "groupings": [{"id": "grp-alerts", "groupBy": ["al-prog"], "calculations": ["al-attach", "al-ret", "al-comp"],
                              "sort": [{"columnId": "al-attach", "direction": "ascending"}]}],
              "conditionalFormats": [
                  {"type": "single", "columnIds": ["al-attach"], "condition": "<", "value": 0.35, "style": {"backgroundColor": "#FDE1DB", "textColor": BAD}},
                  {"type": "single", "columnIds": ["al-ret"], "condition": "<", "value": 0.45, "style": {"backgroundColor": "#FDE1DB", "textColor": BAD}},
                  {"type": "single", "columnIds": ["al-comp"], "condition": "<", "value": 0.45, "style": {"backgroundColor": "#FDE1DB", "textColor": BAD}}],
              "name": {"text": "By fitness program — lowest attach first", "fontWeight": "bold", "fontSize": 13, "color": INK},
              "style": dict(CARD)}
    els.append(alerts); lays.append(elx("tbl-alerts", (1, 13), (45, 58)))

    # drill-through buttons
    btn_cohort = {"id": "btn-to-cohort", "kind": "button", "text": "Open Cohort Builder →", "appearance": "outline",
                  "actions": [{"id": "act1", "trigger": "on-click", "effects": [
                      {"effect": "select-tab", "tabbedContainerElementId": "tc-main", "selectedTab": {"type": "tab", "index": 1}}]}]}
    btn_promo = {"id": "btn-to-promo", "kind": "button", "text": "Open Bundle/Promo Scenario Builder →", "appearance": "outline",
                 "actions": [{"id": "act2", "trigger": "on-click", "effects": [
                     {"effect": "select-tab", "tabbedContainerElementId": "tc-main", "selectedTab": {"type": "tab", "index": 2}}]}]}
    els += [btn_cohort, btn_promo]
    lays.append(elx("btn-to-cohort", (13, 19), (45, 47)))
    lays.append(elx("btn-to-promo", (19, 25), (45, 47)))

    layout = "\n".join(lays)
    return els, layout


# ======================================================================
# TAB 2 — Cohort Builder (marketing population segmentation)
# ======================================================================
SF = "Member Snapshot"

def list_ctrl(controlId, elid, name, columnId, values_hint=None):
    return {"kind": "control", "controlId": controlId, "id": elid, "name": name, "controlType": "list",
            "mode": "include", "selectionMode": "multiple", "values": values_hint or [],
            "filters": [{"source": {"kind": "table", "elementId": "snap"}, "columnId": columnId}],
            "source": {"kind": "source", "source": {"kind": "table", "elementId": "snap"}, "columnId": columnId}}

def build_cohort_tab():
    els, lays = [], []
    els.append(text_el("cb-hdr", "## Cohort Builder — Marketing\nSegment the member population, save a named cohort, and hand it to campaign tools.", color=INK))
    lays.append(elx("cb-hdr", (1, 25), (1, 4)))

    # NOTE: a code-created `list` control's `values` is its SELECTED set, not
    # a picklist of options — omitting it (or leaving it []) means "nothing
    # selected", and with mode:"include" that filters the whole population to
    # ZERO rows by default (verified empirically: every element downstream of
    # `snap` read 0 rows until every control below had all its real category
    # values pre-selected). Pre-select every real value so the tab starts
    # unfiltered; users narrow down by deselecting, same as any multi-select.
    ctrl_defs = [
        ("FitnessProgramF", "ctrl-fitprog", "Fitness Program", "s-fitprog",
         ["21 Day Fix", "LIIFT4", "80 Day Obsession", "P90X", "Insanity Max:30", "Barre Blend", "9 Week Control Freak"]),
        ("NutritionProgramF", "ctrl-nutprog", "Nutrition Program", "s-nutprog",
         ["2B Mindset", "Portion Fix", "Ultimate Portion Fix", "None"]),
        ("ChannelF", "ctrl-chan", "Signup Channel", "s-chan",
         ["Organic", "Paid Social", "Influencer", "Affiliate", "Coach Referral", "Retail"]),
        ("CoachF", "ctrl-coach", "Coach Attached", "s-coach", [True, False]),
        ("BundleF", "ctrl-bundle", "Bundle Name", "s-bunname",
         ["Shake & Bar Starter Bundle", "Portion Fix Kickstart Bundle", "2B Mindset + Shakeology Combo", "None"]),
        ("StageF", "ctrl-stage", "Program Stage", "s-stagenow",
         ["Started", "Mid-Program", "Completed", "Dropped"]),
    ]
    for i, (cid, elid, name, col, vals) in enumerate(ctrl_defs):
        els.append(list_ctrl(cid, elid, name, col, values_hint=vals))
        band = 5 + (i // 3) * 3
        lays.append(elx(elid, (1 + (i % 3) * 8, 1 + (i % 3 + 1) * 8), (band, band + 2)))

    adherence_ctrl = {"kind": "control", "controlId": "AdherenceRange", "id": "ctrl-adh", "name": "Min Adherence %",
                       "controlType": "number-range",
                       "filters": [{"source": {"kind": "table", "elementId": "snap"}, "columnId": "s-adherencenow"}]}
    els.append(adherence_ctrl); lays.append(elx("ctrl-adh", (1, 9), (11, 13)))

    name_ctrl = {"kind": "control", "controlId": "CohortName", "id": "ctrl-cname", "name": "Cohort Name",
                 "controlType": "text", "mode": "equals", "case": "insensitive",
                 "includeNulls": "when-no-value-is-selected", "showOperators": False}
    desc_ctrl = {"kind": "control", "controlId": "CohortDesc", "id": "ctrl-cdesc", "name": "Description",
                 "controlType": "text", "mode": "equals", "case": "insensitive",
                 "includeNulls": "when-no-value-is-selected", "showOperators": False}
    els += [name_ctrl, desc_ctrl]
    lays.append(elx("ctrl-cname", (9, 18), (11, 13)))
    lays.append(elx("ctrl-cdesc", (18, 25), (11, 13)))

    save_btn = {"id": "btn-save-cohort", "kind": "button", "text": "Save cohort", "appearance": "filled",
                "actions": [{"id": "actsave", "trigger": "on-click", "effects": [{
                    "effect": "insert-rows", "tableElementId": "cohort_saves",
                    "values": {
                        "cs-name": {"type": "control", "control": "CohortName"},
                        "cs-desc": {"type": "control", "control": "CohortDesc"},
                        "cs-size": {"type": "formula", "formula": f"CountDistinct([{SF}/Member Id])"},
                        "cs-attach": {"type": "formula", "formula": f"CountDistinct(If([{SF}/Nutrition Subscriber],[{SF}/Member Id],Null))/CountDistinct([{SF}/Member Id])"},
                        "cs-liferev": {"type": "formula", "formula": f"Avg([{SF}/Lifetime Revenue])"},
                        "cs-retention": {"type": "formula", "formula": f"CountDistinct(If([{SF}/Nutrition Active Now],[{SF}/Member Id],Null))/CountDistinct(If([{SF}/Nutrition Subscriber],[{SF}/Member Id],Null))"},
                    }}]}]}
    els.append(save_btn); lays.append(elx("btn-save-cohort", (1, 9), (14, 16)))

    # reactive KPIs (auto-filtered because the controls above filter `snap`)
    kdefs = [
        ("cohort-size", "COHORT SIZE", f"CountDistinct([{SF}/Member Id])", INT),
        ("cohort-attach", "NUTRITION ATTACH (COHORT)", f"CountDistinct(If([{SF}/Nutrition Subscriber],[{SF}/Member Id],Null))/CountDistinct([{SF}/Member Id])", PCT1),
        ("cohort-liferev", "AVG LIFETIME REVENUE", f"Avg([{SF}/Lifetime Revenue])", CUR2),
        ("cohort-retention", "BLENDED RETENTION (COHORT)", f"CountDistinct(If([{SF}/Nutrition Active Now],[{SF}/Member Id],Null))/CountDistinct(If([{SF}/Nutrition Subscriber],[{SF}/Member Id],Null))", PCT1),
    ]
    for i, (key, title, formula, fmt) in enumerate(kdefs):
        e, l = plain_kpi(key, "snap", title, formula, fmt, col=(1 + i * 6, 1 + (i + 1) * 6), row=(17, 25))
        els += e; lays.append(l)

    dist = {"id": "bar-cohort-dist", "kind": "bar-chart", "source": {"elementId": "snap", "kind": "table"},
            "columns": [{"id": "cd-prog", "formula": f"[{SF}/Fitness Program]", "name": "Fitness Program"},
                        {"id": "cd-cat", "formula": '"Members"', "name": "Series"},
                        {"id": "cd-v", "formula": f"CountDistinct([{SF}/Member Id])", "name": "Members", "format": INT}],
            "xAxis": {"columnId": "cd-prog", "sort": {"by": "cd-v", "direction": "descending"}}, "yAxis": {"columnIds": ["cd-v"]},
            "color": {"by": "category", "column": "cd-cat", "scheme": [GREEN]}, "legend": {"visibility": "hidden"},
            "name": {"text": "Cohort by fitness program", "fontWeight": "bold", "fontSize": 13, "color": INK}, "style": dict(CARD)}
    els.append(dist); lays.append(elx("bar-cohort-dist", (1, 13), (26, 41)))

    detail = {"id": "tbl-cohort-detail", "kind": "table", "source": {"elementId": "snap", "kind": "table"},
              "columns": [
                  {"id": "dt-id", "formula": f"[{SF}/Member Id]", "name": "Member Id"},
                  {"id": "dt-fit", "formula": f"[{SF}/Fitness Program]", "name": "Fitness Program"},
                  {"id": "dt-nut", "formula": f"[{SF}/Nutrition Program]", "name": "Nutrition Program"},
                  {"id": "dt-chan", "formula": f"[{SF}/Signup Channel]", "name": "Channel"},
                  {"id": "dt-rev", "formula": f"[{SF}/Lifetime Revenue]", "name": "Lifetime Revenue", "format": CUR2}],
              "groupings": [{"id": "grp-detail", "groupBy": ["dt-id", "dt-fit", "dt-nut", "dt-chan", "dt-rev"], "calculations": [],
                              "sort": [{"columnId": "dt-rev", "direction": "descending"}]}],
              "name": {"text": "Top members in cohort (by lifetime revenue)", "fontWeight": "bold", "fontSize": 13, "color": INK}, "style": dict(CARD)}
    els.append(detail); lays.append(elx("tbl-cohort-detail", (13, 25), (26, 41)))

    els.append(text_el("cb-saved-hdr", "**Saved cohorts**", color=INK))
    lays.append(elx("cb-saved-hdr", (1, 25), (42, 43)))
    cohort_saves = {"id": "cohort_saves", "kind": "input-table", "source": {"kind": "empty", "connectionId": CONN},
                     "inputMode": "explore", "name": "Saved Cohorts",
                     "columns": [
                         {"id": "cs-name", "type": "text", "name": "Cohort Name"},
                         {"id": "cs-desc", "type": "text", "name": "Description"},
                         {"id": "cs-size", "type": "number", "name": "Cohort Size"},
                         {"id": "cs-attach", "type": "number", "name": "Attach Rate"},
                         {"id": "cs-liferev", "type": "number", "name": "Avg Lifetime Revenue"},
                         {"id": "cs-retention", "type": "number", "name": "Retention Rate"},
                         {"id": "CREATED_AT"}, {"id": "CREATED_BY"}]}
    els.append(cohort_saves)
    lays.append(elx("cohort_saves", (1, 25), (43, 54)))

    els.append(text_el("cb-chat-hdr", "**Cohort Copilot** — ask it to build and save a segment for you", color=GREEN_D))
    lays.append(elx("cb-chat-hdr", (1, 25), (55, 56)))
    chat = {"id": "chat-cohort", "kind": "chat", "agentId": "ag-cohort"}
    els.append(chat); lays.append(elx("chat-cohort", (1, 25), (56, 70)))

    layout = "\n".join(lays)
    return els, layout


# ======================================================================
# TAB 3 — Bundle & Promo Scenario Builder
# ======================================================================

def build_scenario_tab():
    els, lays = [], []
    els.append(text_el("sb-hdr", "## Bundle & Promo Scenario Builder\nBaseline performance for each bundle campaign (adopters vs. eligible members who declined), plus a live what-if model.", color=INK))
    lays.append(elx("sb-hdr", (1, 25), (1, 4)))

    # baseline pivot — safe grain: `snap` is 1 row/member, so grouping/pivoting it never fans out.
    baseline = {"id": "bundle_baseline", "kind": "pivot-table", "name": "Bundle Baseline", "visibleAsSource": True,
                "source": {"elementId": "snap", "kind": "table"},
                "columns": [
                    {"id": "pv-camp", "formula": f"[{SF}/Bundle Campaign]", "name": "Campaign"},
                    {"id": "pv-pool", "formula": f"CountDistinct([{SF}/Member Id])", "name": "Eligible Pool", "format": INT},
                    {"id": "pv-adopters", "formula": f"CountDistinct(If([{SF}/Bundle Flag],[{SF}/Member Id],Null))", "name": "Adopters", "format": INT},
                    {"id": "pv-revadopt", "formula": f"Avg(If([{SF}/Bundle Flag],[{SF}/Initial Purchase Revenue],Null))", "name": "Avg Rev — Adopter", "format": CUR2},
                    {"id": "pv-revstand", "formula": f"Avg(If(Not [{SF}/Bundle Flag],[{SF}/Initial Purchase Revenue],Null))", "name": "Avg Rev — Standalone", "format": CUR2},
                    {"id": "pv-disc", "formula": f"Avg(If([{SF}/Bundle Flag],[{SF}/Promo Discount Pct],Null))", "name": "Baseline Discount", "format": PCT1},
                    {"id": "pv-retadopt", "formula": f"Avg(If([{SF}/Bundle Flag],If([{SF}/Nutrition Active Now],1,0),Null))", "name": "Retention — Adopter", "format": PCT1},
                    {"id": "pv-retstand", "formula": f"Avg(If(Not [{SF}/Bundle Flag],If([{SF}/Nutrition Active Now],1,0),Null))", "name": "Retention — Standalone", "format": PCT1}],
                "rowsBy": [{"id": "pv-camp"}],
                "values": ["pv-pool", "pv-adopters", "pv-revadopt", "pv-revstand", "pv-disc", "pv-retadopt", "pv-retstand"],
                "conditionalFormats": [{"type": "single", "columnIds": ["pv-pool"], "condition": "IsNotNull", "style": {"backgroundColor": MINT}}],
                "name": {"text": "Baseline — adopters vs. standalone, by campaign", "fontWeight": "bold", "fontSize": 13, "color": INK},
                "style": dict(CARD)}
    els.append(baseline); lays.append(elx("bundle_baseline", (1, 25), (5, 15)))

    assum = {"id": "bundle_assum", "kind": "input-table", "source": {"kind": "linked", "from": "bundle_baseline"},
             "inputMode": "explore", "name": "Assumptions",
             "columns": [
                 {"id": "ia-camp", "key": "pv-camp"},
                 {"id": "ia-pool", "key": "pv-pool"},
                 {"id": "ia-adopters", "key": "pv-adopters"},
                 {"id": "ia-revadopt", "key": "pv-revadopt"},
                 {"id": "ia-revstand", "key": "pv-revstand"},
                 {"id": "ia-disc", "key": "pv-disc"},
                 {"id": "ia-retadopt", "key": "pv-retadopt"},
                 {"id": "ia-retstand", "key": "pv-retstand"},
                 {"id": "ia-newadopt", "type": "number", "name": "New Adoption Rate %"},
                 {"id": "ia-newdisc", "type": "number", "name": "New Discount %"},
                 {"id": "ia-baseadopt", "formula": "([Adopters]/[Eligible Pool])*100", "name": "Base Case Adoption %"},
                 {"id": "ia-basedisc", "formula": "[Baseline Discount]*100", "name": "Base Case Discount %"},
                 {"id": "ia-effadopt", "formula": "Coalesce([New Adoption Rate %],[Base Case Adoption %])", "name": "Effective Adoption %"},
                 {"id": "ia-effdisc", "formula": "Coalesce([New Discount %],[Base Case Discount %])", "name": "Effective Discount %"},
                 {"id": "ia-projadopters", "formula": "[Eligible Pool]*([Effective Adoption %]/100)", "name": "Projected Adopters"},
                 {"id": "ia-baserev", "formula": "[Adopters]*[Avg Rev — Adopter]*(1-[Baseline Discount]) + ([Eligible Pool]-[Adopters])*[Avg Rev — Standalone]", "name": "Baseline Revenue"},
                 {"id": "ia-projrev", "formula": "[Projected Adopters]*[Avg Rev — Adopter]*(1-[Effective Discount %]/100) + ([Eligible Pool]-[Projected Adopters])*[Avg Rev — Standalone]", "name": "Projected Revenue"},
                 {"id": "ia-delta", "formula": "[Projected Revenue]-[Baseline Revenue]", "name": "Revenue Δ vs Baseline"}],
             "order": ["ia-camp", "ia-pool", "ia-adopters", "ia-baseadopt", "ia-newadopt", "ia-effadopt",
                       "ia-basedisc", "ia-newdisc", "ia-effdisc", "ia-projadopters", "ia-baserev", "ia-projrev", "ia-delta"]}
    els.append(assum); lays.append(elx("bundle_assum", (1, 25), (16, 30)))

    els.append(text_el("sb-instr", "Type a **New Adoption Rate %** and/or **New Discount %** per campaign — the projection updates live. Leave blank to hold the observed baseline.", color=GREEN_D))
    lays.append(elx("sb-instr", (1, 25), (31, 33)))

    kdefs = [
        ("proj-rev", "PROJECTED REVENUE", "Sum([Assumptions/Projected Revenue])", CUR, "Sum([Assumptions/Baseline Revenue])"),
        ("uplift", "UPLIFT VS BASELINE", "Sum([Assumptions/Projected Revenue])/Sum([Assumptions/Baseline Revenue])-1", PCT2, None),
        ("proj-adopt", "PROJECTED ADOPTERS", "Sum([Assumptions/Projected Adopters])", INT, "Sum([Assumptions/Adopters])"),
    ]
    for i, (key, title, formula, fmt, comp) in enumerate(kdefs):
        e, l = plain_kpi(key, "bundle_assum", title, formula, fmt, comp_formula=comp, col=(1 + i * 8, 1 + (i + 1) * 8), row=(34, 42))
        els += e; lays.append(l)

    cmp_bar = {"id": "bar-scenario", "kind": "bar-chart", "source": {"elementId": "bundle_assum", "kind": "table"},
               "columns": [
                   {"id": "sc-camp", "formula": "[Assumptions/Campaign]", "name": "Campaign"},
                   {"id": "sc-base", "formula": "Sum([Assumptions/Baseline Revenue])", "name": "Baseline Revenue", "format": CUR},
                   {"id": "sc-proj", "formula": "Sum([Assumptions/Projected Revenue])", "name": "Projected Revenue", "format": CUR}],
               "xAxis": {"columnId": "sc-camp"}, "yAxis": {"columnIds": ["sc-base", "sc-proj"]},
               "stacking": "none", "legend": {"visibility": "visible"},
               "name": {"text": "Baseline vs. projected revenue by campaign", "fontWeight": "bold", "fontSize": 13, "color": INK},
               "style": dict(CARD)}
    els.append(cmp_bar); lays.append(elx("bar-scenario", (1, 25), (43, 58)))

    # scenario run log (append-only) + modal
    run_name = {"kind": "control", "controlId": "ScenarioRunName", "id": "ctrl-runname", "name": "Run Name",
                "controlType": "text", "mode": "equals", "case": "insensitive",
                "includeNulls": "when-no-value-is-selected", "showOperators": False}
    run_notes = {"kind": "control", "controlId": "ScenarioRunNotes", "id": "ctrl-runnotes", "name": "Notes",
                 "controlType": "text", "mode": "equals", "case": "insensitive",
                 "includeNulls": "when-no-value-is-selected", "showOperators": False}
    open_btn = {"id": "btn-open-run", "kind": "button", "text": "Log this scenario run", "appearance": "filled",
                "actions": [{"id": "actopen", "trigger": "on-click", "effects": [{"effect": "open-overlay", "overlayId": "modalRun"}]}]}
    els += [open_btn]
    lays.append(elx("btn-open-run", (1, 9), (59, 61)))

    save_run = {"id": "btn-save-run", "kind": "button", "text": "Save", "appearance": "filled",
                "actions": [{"id": "actsaverun", "trigger": "on-click", "effects": [
                    {"effect": "insert-rows", "tableElementId": "scenario_log", "values": {
                        "sl-name": {"type": "control", "control": "ScenarioRunName"},
                        "sl-notes": {"type": "control", "control": "ScenarioRunNotes"}}},
                    {"effect": "clear-control", "scope": {"type": "control", "controlId": "ScenarioRunName"}},
                    {"effect": "clear-control", "scope": {"type": "control", "controlId": "ScenarioRunNotes"}},
                    {"effect": "close-overlay"}]}]}
    cancel_run = {"id": "btn-cancel-run", "kind": "button", "text": "Cancel", "appearance": "outline",
                  "actions": [{"id": "actcancelrun", "trigger": "on-click", "effects": [{"effect": "close-overlay"}]}]}
    modal_title = text_el("modal-run-title", "### Log a scenario run\nName this what-if (e.g. \"Portion Fix retest — 15% adoption / 10% discount\") for future reference.")
    modal_els = [modal_title, run_name, run_notes, save_run, cancel_run]
    modal_layout = ('<Page type="grid" gridTemplateColumns="repeat(24,1fr)" gridTemplateRows="auto" id="modalRun">\n'
                     + elx("modal-run-title", (1, 25), (1, 3)) + "\n"
                     + elx("ctrl-runname", (1, 25), (3, 5)) + "\n"
                     + elx("ctrl-runnotes", (1, 25), (5, 8)) + "\n"
                     + elx("btn-cancel-run", (13, 19), (8, 10)) + "\n"
                     + elx("btn-save-run", (19, 25), (8, 10)) + "\n</Page>")

    scenario_log = {"id": "scenario_log", "kind": "input-table", "source": {"kind": "empty", "connectionId": CONN},
                     "inputMode": "explore", "name": "Scenario Log",
                     "columns": [{"id": "sl-name", "type": "text", "name": "Run Name"},
                                 {"id": "sl-notes", "type": "text", "name": "Notes"},
                                 {"id": "CREATED_AT"}, {"id": "CREATED_BY"}]}
    els.append(scenario_log); lays.append(elx("scenario_log", (10, 25), (59, 65)))

    els.append(text_el("sb-chat-hdr", "**Scenario Copilot** — ask about baseline vs. projected performance, or log a run", color=GREEN_D))
    lays.append(elx("sb-chat-hdr", (1, 25), (66, 67)))
    chat = {"id": "chat-scenario", "kind": "chat", "agentId": "ag-scenario"}
    els.append(chat); lays.append(elx("chat-scenario", (1, 25), (67, 81)))

    layout = "\n".join(lays)
    return els, layout, modal_els, modal_layout


# ======================================================================
# Agents
# ======================================================================

def build_agents():
    filter_tools = []
    for tool_id, ctrl, label in [
        ("t-fitprog", "FitnessProgramF", "fitness program"),
        ("t-nutprog", "NutritionProgramF", "nutrition program"),
        ("t-chan", "ChannelF", "signup channel"),
        ("t-coach", "CoachF", "coach-attached status"),
        ("t-bundle", "BundleF", "bundle name"),
        ("t-stage", "StageF", "program stage"),
    ]:
        filter_tools.append({"toolId": tool_id, "kind": "action", "name": f"Filter by {label}",
                              "description": f"Add a {label} value to the cohort filter.",
                              "steps": [{"kind": "effect", "effect": "set-control-value", "control": ctrl,
                                         "value": {"type": "agent-input", "inputName": f"Which {label}"}, "selectionMode": "add"}]})
    name_tool = {"toolId": "t-name", "kind": "action", "name": "Set cohort name and description",
                 "description": "Set the name and description for the cohort about to be saved.",
                 "steps": [
                     {"kind": "effect", "effect": "set-control-value", "control": "CohortName", "value": {"type": "agent-input", "inputName": "Cohort name"}},
                     {"kind": "effect", "effect": "set-control-value", "control": "CohortDesc", "value": {"type": "agent-input", "inputName": "Cohort description"}}]}
    save_tool = {"toolId": "t-save", "kind": "action", "name": "Save the cohort",
                 "description": "Save the currently filtered cohort as a named, reusable segment.",
                 "steps": [{"kind": "effect", "effect": "insert-rows", "tableElementId": "cohort_saves", "values": {
                     "cs-name": {"type": "control", "control": "CohortName"},
                     "cs-desc": {"type": "control", "control": "CohortDesc"},
                     "cs-size": {"type": "formula", "formula": f"CountDistinct([{SF}/Member Id])"},
                     "cs-attach": {"type": "formula", "formula": f"CountDistinct(If([{SF}/Nutrition Subscriber],[{SF}/Member Id],Null))/CountDistinct([{SF}/Member Id])"},
                     "cs-liferev": {"type": "formula", "formula": f"Avg([{SF}/Lifetime Revenue])"},
                     "cs-retention": {"type": "formula", "formula": f"CountDistinct(If([{SF}/Nutrition Active Now],[{SF}/Member Id],Null))/CountDistinct(If([{SF}/Nutrition Subscriber],[{SF}/Member Id],Null))"},
                 }}]}
    ag_cohort = {"id": "ag-cohort", "name": "Cohort Copilot",
                 "description": "Builds and saves marketing cohorts of BODi members.",
                 "instructions": ("You help a marketing user build a member cohort for campaign targeting. Members are BODi "
                                  "fitness-program subscribers (21 Day Fix, LIIFT4, 80 Day Obsession, P90X, Insanity Max:30, "
                                  "Barre Blend, 9 Week Control Freak) who may or may not also subscribe to a nutrition program "
                                  "(2B Mindset, Portion Fix, Ultimate Portion Fix). Use the filter tools to narrow the population, "
                                  "then set a name/description and save. Report the resulting cohort size and attach rate."),
                 "dataSources": [{"kind": "table", "elementId": "snap"}],
                 "tools": filter_tools + [name_tool, save_tool]}

    scen_tool = {"toolId": "t-log-run", "kind": "action", "name": "Log a scenario run",
                 "description": "Record a named what-if scenario run with notes for later reference.",
                 "steps": [{"kind": "effect", "effect": "insert-rows", "tableElementId": "scenario_log", "values": {
                     "sl-name": {"type": "agent-input", "inputName": "Run name"},
                     "sl-notes": {"type": "agent-input", "inputName": "Notes"}}}]}
    ag_scenario = {"id": "ag-scenario", "name": "Scenario Copilot",
                   "description": "Analyzes bundle/promo baseline vs. projected performance.",
                   "instructions": ("You help analyze BODi's nutrition bundle/promo campaigns: Shake & Bar Starter Bundle, "
                                    "Portion Fix Kickstart Bundle, and 2B Mindset + Shakeology Combo. `Bundle Baseline` compares "
                                    "adopters vs. eligible members who declined (standalone) for each campaign — pool size, "
                                    "adopter counts, average revenue, discount, and nutrition retention. `Assumptions` is the "
                                    "live what-if grid (edit New Adoption Rate % / New Discount % per campaign to project impact). "
                                    "Explain whether a bundle lifted attach/retention or mainly cannibalized standalone revenue, "
                                    "and log notable what-if runs on request."),
                   "dataSources": [{"kind": "table", "elementId": "bundle_baseline"}, {"kind": "table", "elementId": "bundle_assum"}],
                   "tools": [scen_tool]}
    return [ag_cohort, ag_scenario]


# ======================================================================
# Assembly
# ======================================================================

def build_full_spec():
    cc_els, cc_lay = build_command_center()
    cb_els, cb_lay = build_cohort_tab()
    sb_els, sb_lay, modal_els, modal_lay = build_scenario_tab()
    agents = build_agents()

    header_bg = {"id": "c-header", "kind": "container", "style": {"backgroundColor": BLACK}}
    logo = {"id": "logo", "kind": "image", "source": {"kind": "url", "url": LOGO_URI}, "style": {"fit": "contain"}}
    header = text_el("hdr-title", "# Nutrition Business", color=WHITE)
    subhdr = text_el("hdr-sub", "Command Center · Cohort Builder · Bundle & Promo Scenario Builder", color="#C8C8C8")

    tabbed = {"id": "tc-main", "kind": "tabbed-container",
              "tabs": [{"name": "Command Center"}, {"name": "Cohort Builder"}, {"name": "Bundle & Promo Scenario Builder"}],
              "tabBar": {"alignment": "start"}}

    elements = [fact_tbl, snap_tbl, header_bg, logo, header, subhdr, tabbed] + cc_els + cb_els + sb_els + modal_els

    layout = f"""<?xml version="1.0" encoding="utf-8"?>
<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="main">
  <Container elementId="c-header" type="grid" gridColumn="1 / 25" gridRow="1 / 5" gridTemplateColumns="repeat(24,1fr)" gridTemplateRows="auto">
    <Element elementId="logo" gridColumn="1 / 5" gridRow="1 / 5"/>
    <Element elementId="hdr-title" gridColumn="5 / 20" gridRow="1 / 3"/>
    <Element elementId="hdr-sub" gridColumn="5 / 20" gridRow="3 / 5"/>
  </Container>
  <TabbedContainer elementId="tc-main" type="tabbed-container" gridColumn="1 / 25" gridRow="5 / 92">
    <Tab gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto">
{cc_lay}
    </Tab>
    <Tab gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto">
{cb_lay}
    </Tab>
    <Tab gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto">
{sb_lay}
    </Tab>
  </TabbedContainer>
</Page>
<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="pgdata">
  <Element elementId="fact" gridColumn="1 / 25" gridRow="1 / 5"/>
  <Element elementId="snap" gridColumn="1 / 25" gridRow="5 / 10"/>
</Page>
{modal_lay}"""

    overlays = [{"id": "modalRun", "type": "modal", "name": "Log a scenario run",
                 "modal": {"width": "small", "header": {"title": "Log a scenario run", "showCloseIcon": "shown"},
                           "footer": {"primaryCta": {"visible": "hidden"}, "secondaryCta": {"visible": "hidden"}}}}]

    doc = {"schemaVersion": 1, "kind": "workbook", "elements": elements,
           "pages": [{"id": "main", "name": "Nutrition Business"}, {"id": "pgdata", "name": "Data", "visibility": "hidden"}],
           "overlays": overlays, "agents": agents,
           "settings": {"theme": {"overrides": {
               "pageWidth": "full",
               "colors": {"text": INK, "highlight": GREEN, "success": GREEN, "warning": "#EE9441", "danger": BAD},
               "categoricalScheme": [GREEN, GREEN_D, GREEN_LIGHT, INK, "#8A8A8A", "#0B5C47"],
           }}},
           "layout": layout}
    return {"name": "BODi — Nutrition Business", "folderId": FOLDER, "document": doc}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "probe"
    if cmd == "probe":
        spec = probe_spec()
    elif cmd in ("create", "update"):
        spec = build_full_spec()
    else:
        print("usage: build_bodi.py probe|create|update <workbook-id>"); sys.exit(2)
    OUT.write_text(json.dumps(spec, indent=2))
    print("wrote", OUT, "-", len(json.dumps(spec)), "bytes")
    if cmd == "create":
        r = subprocess.run(["scripts/api/publish-workbook.sh", "post", str(OUT)], cwd=REPO, capture_output=True, text=True)
        print(r.stdout); print(r.stderr, file=sys.stderr); sys.exit(r.returncode)
    elif cmd == "update":
        wbid = sys.argv[2] if len(sys.argv) > 2 else None
        if not wbid:
            print("usage: build_bodi.py update <workbook-id>"); sys.exit(2)
        r = subprocess.run(["scripts/api/publish-workbook.sh", "update", wbid, str(OUT)], cwd=REPO, capture_output=True, text=True)
        print(r.stdout); print(r.stderr, file=sys.stderr); sys.exit(r.returncode)
