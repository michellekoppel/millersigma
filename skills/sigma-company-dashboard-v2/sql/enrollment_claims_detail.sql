-- Member-month grain enrollment & claims detail, the ONE base table shared by
-- the four rebuilt pages (Enrollment Overview, Medical Utilization, Medical
-- Trend, Executive Summary) and their persistent Filters panel -- every
-- control on those pages filters THIS table, so cross-filtering is real, not
-- decorative (see HANDOFF.md section 3, "ONE BASE TABLE").
--
-- Pure generated SQL (SEQ4 + deterministic HASH, no RANDOM()) so it compiles
-- on any Snowflake connection and produces stable numbers safe to quote live.
-- 6,000 synthetic members x 24 months = 144,000 rows. Two client groups:
-- FIS Global (smaller book) and GEICO (larger book) -- the two group names
-- that appear across the four original screenshots. Member-level attributes
-- (state, age band, gender, relationship, division, plan, tier, coverage
-- status, tenure) are drawn once per member via HASH(member_index, salt) so
-- they stay constant across that member's 24 monthly rows; MEDC diagnosis
-- category and place-of-service are drawn per member-month (a person's
-- claims land in different categories/settings month to month).
--
-- Deliberate scale note: this is a smaller synthetic population than the
-- enterprise-scale headcounts implied by the original mockups (~16K / ~47K
-- lives) -- kept intentionally in the low thousands so every chart on every
-- page queries fast. Proportions/shapes (waived %, tier mix, age mix, gender
-- mix) are calibrated to match the mockups; absolute dollar/headcount scale
-- is not chased digit-for-digit. See build notes.
WITH seq0 AS (
    SELECT SEQ4() AS i FROM TABLE(GENERATOR(ROWCOUNT => 144000))
),
seq AS (
    SELECT i, FLOOR(i / 24) AS member_index, MOD(i, 24) AS month_index
    FROM seq0
),
member AS (
    SELECT
        member_index, month_index,
        'M-' || LPAD(CAST(member_index + 500001 AS VARCHAR), 7, '0') AS member_id,
        ABS(HASH(member_index, 1))  % 100 AS r_group,
        ABS(HASH(member_index, 2))  % 100 AS r_state,
        ABS(HASH(member_index, 3))  % 100 AS r_age,
        ABS(HASH(member_index, 4))  % 1000 AS r_age_sub,
        ABS(HASH(member_index, 5))  % 100 AS r_gender,
        ABS(HASH(member_index, 6))  % 100 AS r_rel,
        ABS(HASH(member_index, 7))  % 100 AS r_div,
        ABS(HASH(member_index, 8))  % 100 AS r_plan,
        ABS(HASH(member_index, 9))  % 100 AS r_ptype,
        ABS(HASH(member_index, 10)) % 100 AS r_etype,
        ABS(HASH(member_index, 11)) % 100 AS r_tier,
        ABS(HASH(member_index, 12)) % 100 AS r_waived,
        ABS(HASH(member_index, 13)) % 100 AS r_county,
        ABS(HASH(member_index, 14)) % 240 AS r_tenure,
        ABS(HASH(member_index, month_index, 15)) % 100 AS r_medc,
        ABS(HASH(member_index, month_index, 16)) % 100 AS r_pos,
        ABS(HASH(member_index, month_index, 17)) % 1000 AS r_claims,
        ABS(HASH(member_index, month_index, 18)) % 1000 AS r_spend_noise
    FROM seq
),
labelled AS (
    SELECT
        *,
        CASE WHEN r_group < 70 THEN 'GEICO' ELSE 'FIS Global' END AS group_name,
        CASE WHEN r_state < 28 THEN 'CA' WHEN r_state < 48 THEN 'TX'
             WHEN r_state < 64 THEN 'FL' WHEN r_state < 78 THEN 'NY'
             WHEN r_state < 90 THEN 'IL' ELSE 'PA' END AS state,
        CASE WHEN r_county < 40 THEN 'Orange County'
             WHEN r_county < 65 THEN 'Cook County'
             WHEN r_county < 80 THEN 'Harris County'
             WHEN r_county < 92 THEN 'Maricopa County'
             ELSE 'Fulton County' END AS county,
        CASE WHEN r_age < 26 THEN '<35' WHEN r_age < 61 THEN '36-49'
             WHEN r_age < 95 THEN '50-64' ELSE '65+' END AS age_band,
        CASE WHEN r_age < 26 THEN 'Gen Z' WHEN r_age < 61 THEN 'Millennials'
             WHEN r_age < 95 THEN 'Generation X' ELSE 'Baby Boomers' END AS generation,
        ROUND(
            CASE WHEN r_age < 26 THEN 22 + r_age_sub / 1000.0 * 12
                 WHEN r_age < 61 THEN 36 + r_age_sub / 1000.0 * 13
                 WHEN r_age < 95 THEN 50 + r_age_sub / 1000.0 * 14
                 ELSE 65 + r_age_sub / 1000.0 * 12 END, 1) AS age_years,
        CASE WHEN r_gender < 62 THEN 'Female' ELSE 'Male' END AS gender,
        CASE WHEN r_rel < 55 THEN 'Employee' WHEN r_rel < 70 THEN 'Spouse'
             ELSE 'Dependent' END AS relationship,
        CASE WHEN r_div < 25 THEN 'Corporate Support'
             WHEN r_div < 60 THEN 'Field Operations'
             WHEN r_div < 80 THEN 'Technology' ELSE 'Retail Operations' END AS division,
        CASE WHEN r_plan < 60 THEN 'Plan 1' WHEN r_plan < 80 THEN 'Plan 2'
             ELSE 'Plan 3' END AS plan,
        CASE WHEN r_ptype < 55 THEN 'PPO' WHEN r_ptype < 85 THEN 'HDHP'
             ELSE 'HMO' END AS plan_type,
        CASE WHEN r_etype < 88 THEN 'Full-Time' ELSE 'Part-Time' END AS employee_type,
        CASE WHEN r_tier < 50 THEN 'EE' WHEN r_tier < 61 THEN 'ES'
             WHEN r_tier < 78 THEN 'EC' ELSE 'EF' END AS tier,
        CASE WHEN r_waived < 20 THEN 'Waived' ELSE 'Enrolled' END AS coverage_status,
        ROUND(r_tenure / 12.0, 1) AS tenure_years,
        CASE WHEN r_medc < 22 THEN 'Musculoskeletal'
             WHEN r_medc < 37 THEN 'Administrative'
             WHEN r_medc < 50 THEN 'Cardiovascular'
             WHEN r_medc < 62 THEN 'General Surgery'
             WHEN r_medc < 73 THEN 'Neurologic'
             WHEN r_medc < 83 THEN 'Female Reproductive'
             WHEN r_medc < 92 THEN 'Respiratory'
             ELSE 'Endocrine' END AS medc_category,
        CASE WHEN r_pos < 34 THEN 'Office'
             WHEN r_pos < 52 THEN 'On Campus-Outpatient Hospital'
             WHEN r_pos < 66 THEN 'Independent Laboratory'
             WHEN r_pos < 78 THEN 'Inpatient Hospital'
             WHEN r_pos < 88 THEN 'Emergency Room-Hospital'
             WHEN r_pos < 95 THEN 'Urgent Care Facility'
             ELSE 'Ambulatory Surgical Center' END AS place_of_service
    FROM member
),
priced AS (
    SELECT
        *,
        DATEADD('month', month_index, DATE '2024-06-01') AS month_date,
        CASE WHEN month_index >= 12 THEN 'Current Period' ELSE 'Prior Period' END AS period_name,
        -- age-band PMPM baseline
        CASE age_band WHEN '<35' THEN 340 WHEN '36-49' THEN 460
             WHEN '50-64' THEN 600 ELSE 820 END AS age_pmpm,
        -- place-of-service cost multiplier, weighted-average ~1.0
        CASE place_of_service
             WHEN 'Office' THEN 0.55
             WHEN 'On Campus-Outpatient Hospital' THEN 1.35
             WHEN 'Independent Laboratory' THEN 0.30
             WHEN 'Inpatient Hospital' THEN 2.30
             WHEN 'Emergency Room-Hospital' THEN 1.40
             WHEN 'Urgent Care Facility' THEN 0.65
             ELSE 1.55 END AS pos_mult,
        -- medical trend grows across the full 24-month window (not reset each
        -- year) so Current Period genuinely runs ~6% hotter than Prior Period,
        -- plus a light within-year seasonal wiggle.
        (1 + 0.005 * month_index) * (1 + 0.04 * SIN(2 * PI() * (MOD(month_index, 12) / 12.0))) AS trend,
        0.7 + (r_spend_noise / 1000.0) * 0.6 AS noise
    FROM labelled
)
SELECT
    group_name                                AS "Group Name",
    member_id                                 AS "Member ID",
    month_date                                 AS "Month",
    month_index                                AS "Month Index",
    period_name                                AS "Period Name",
    state                                       AS "State",
    county                                      AS "County",
    age_band                                    AS "Age Band",
    generation                                  AS "Generation",
    age_years                                   AS "Age Years",
    gender                                      AS "Gender",
    relationship                                AS "Relationship",
    division                                    AS "Division",
    plan                                        AS "Plan",
    plan_type                                   AS "Plan Type",
    employee_type                               AS "Employee Type",
    tier                                        AS "Tier",
    tenure_years                                AS "Tenure Years",
    coverage_status                             AS "Coverage Status",
    medc_category                               AS "MEDC Category",
    place_of_service                            AS "Place of Service",
    CASE WHEN coverage_status = 'Waived' THEN 0
         ELSE ROUND(age_pmpm * pos_mult * trend * noise, 2) END AS "Medical Spend",
    -- pharmacy trend runs opposite medical (formulary/generic-substitution
    -- savings), landing pharmacy spend a few percent BELOW prior period even
    -- though medical spend rises -- matches the Current-vs-Prior mockup shape.
    CASE WHEN coverage_status = 'Waived' THEN 0
         ELSE ROUND(age_pmpm * pos_mult * trend * noise * 0.34
                     * (1 - 0.22 * (month_index / 23.0)), 2) END AS "Pharmacy Spend",
    CASE WHEN coverage_status = 'Waived' THEN 0
         ELSE MOD(r_claims, 4) END              AS "Claims Count",
    CASE WHEN coverage_status = 'Enrolled' THEN 1 ELSE 0 END AS "Enrolled Flag"
FROM priced
