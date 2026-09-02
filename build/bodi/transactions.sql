
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
    CASE WHEN signup_month_idx IN (6,7) AND fitness_program IN ('21 Day Fix','Barre Blend') THEN 'Shake & Bar Starter Bundle' WHEN signup_month_idx IN (14,15) AND fitness_program IN ('21 Day Fix','9 Week Control Freak') THEN 'Portion Fix Kickstart Bundle' WHEN signup_month_idx IN (20,21) AND fitness_program IN ('LIIFT4','P90X','Insanity Max:30') THEN '2B Mindset + Shakeology Combo' ELSE NULL END AS bundle_name_if_eligible,
    CASE WHEN signup_month_idx IN (6,7) AND fitness_program IN ('21 Day Fix','Barre Blend') THEN 0.2 WHEN signup_month_idx IN (14,15) AND fitness_program IN ('21 Day Fix','9 Week Control Freak') THEN 0.15 WHEN signup_month_idx IN (20,21) AND fitness_program IN ('LIIFT4','P90X','Insanity Max:30') THEN 0.25 ELSE 0.0 END AS promo_discount_pct,
    CASE WHEN signup_month_idx IN (6,7) AND fitness_program IN ('21 Day Fix','Barre Blend') THEN 0.15 WHEN signup_month_idx IN (14,15) AND fitness_program IN ('21 Day Fix','9 Week Control Freak') THEN 0.12 WHEN signup_month_idx IN (20,21) AND fitness_program IN ('LIIFT4','P90X','Insanity Max:30') THEN 0.18 ELSE 0.0 END AS bundle_attach_boost
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
