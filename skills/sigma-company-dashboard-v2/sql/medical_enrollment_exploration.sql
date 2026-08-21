-- Standalone, row-level synthetic dataset for AD HOC exploration of Alliant's
-- medical enrollment population. NOT wired into any workbook -- run this
-- directly in a Snowflake worksheet or a Sigma "New Table from SQL" to poke
-- around freely (pivot, filter, chart) outside the built dashboard pages.
--
-- 2,500 members, deterministic (HASH-seeded, no RANDOM()) so results are
-- stable across re-runs. Category weights are matched to the real splits
-- already shown on the "Medical Enrollment Overview" page so anything you
-- compute here will agree with that page:
--   * Group Name split   ~51% GEICO / 32% FIS Global / 17% Contoso Logistics
--     (matches the real 16,438 / 10,191 / 5,588 member counts on that page).
--   * Coverage Tier      EE 50.0% / ES 11.1% / EC 16.7% / EF 22.2%
--   * Age Band           <35 25.9% / 36-49 34.7% / 50-64 34.1% / 65+ 5.3%
--   * Plan mix           Plan 1 60% / Plan 2 20% / Plan 3 20%
--   * Waived coverage    25% (uniform across groups)
--   * Gender             62% Female / 38% Male
-- State/County/Plan Type/Employee Type domains match the other filter
-- controls already on that page (California/Texas/Florida/New York/Illinois;
-- County 1-5; PPO/HDHP/HMO; Full-Time/Part-Time/Union).

WITH seq AS (
    SELECT SEQ4() AS i FROM TABLE(GENERATOR(ROWCOUNT => 2500))
),
base AS (
    SELECT
        i,
        'MBR-' || LPAD(CAST(i + 100001 AS VARCHAR), 7, '0') AS member_id,
        ABS(HASH(i, 11)) % 1000  AS r_group,   -- group name
        ABS(HASH(i, 22)) % 1000  AS r_tier,    -- coverage tier
        ABS(HASH(i, 33)) % 1000  AS r_age,     -- age band
        ABS(HASH(i, 44)) % 1000  AS r_gender,
        ABS(HASH(i, 55)) % 1000  AS r_rel,     -- relationship within tier
        ABS(HASH(i, 66)) % 1000  AS r_plan,
        ABS(HASH(i, 77)) % 1000  AS r_waived,
        ABS(HASH(i, 88)) % 1000  AS r_state,
        ABS(HASH(i, 99)) % 1000  AS r_county,
        ABS(HASH(i, 111)) % 1000 AS r_plantype,
        ABS(HASH(i, 122)) % 1000 AS r_emptype,
        ABS(HASH(i, 133)) % 5000 AS r_age_noise,   -- for exact age within band
        ABS(HASH(i, 144)) % 4380 AS r_tenure_days, -- 0-12 years, in days
        ABS(HASH(i, 155)) % 700  AS r_enroll_offset -- enrollment date jitter
    FROM seq
),
labelled AS (
    SELECT
        member_id,
        CASE
            WHEN r_group < 510 THEN 'GEICO'
            WHEN r_group < 830 THEN 'FIS Global'
            ELSE 'Contoso Logistics'
        END AS group_name,
        CASE
            WHEN r_tier < 500 THEN 'EE'
            WHEN r_tier < 611 THEN 'ES'
            WHEN r_tier < 778 THEN 'EC'
            ELSE 'EF'
        END AS coverage_tier,
        CASE
            WHEN r_age < 259 THEN '<35'
            WHEN r_age < 606 THEN '36-49'
            WHEN r_age < 947 THEN '50-64'
            ELSE '65+'
        END AS age_band,
        CASE WHEN r_gender < 620 THEN 'Female' ELSE 'Male' END AS gender,
        r_rel,
        CASE
            WHEN r_plan < 600 THEN 'Plan 1'
            WHEN r_plan < 800 THEN 'Plan 2'
            ELSE 'Plan 3'
        END AS plan_name,
        CASE WHEN r_waived < 250 THEN 'Waived' ELSE 'Covered' END AS waived_coverage,
        CASE
            WHEN r_state < 300 THEN 'California'
            WHEN r_state < 520 THEN 'Texas'
            WHEN r_state < 700 THEN 'Florida'
            WHEN r_state < 860 THEN 'New York'
            ELSE 'Illinois'
        END AS state_name,
        CASE
            WHEN r_county < 580 THEN 'County 1'
            WHEN r_county < 790 THEN 'County 2'
            WHEN r_county < 990 THEN 'County 3'
            WHEN r_county < 1000 THEN 'County 4'
            ELSE 'County 5'
        END AS county_name,
        CASE
            WHEN r_plantype < 500 THEN 'PPO'
            WHEN r_plantype < 800 THEN 'HDHP'
            ELSE 'HMO'
        END AS plan_type,
        CASE
            WHEN r_emptype < 750 THEN 'Full-Time'
            WHEN r_emptype < 920 THEN 'Part-Time'
            ELSE 'Union'
        END AS employee_type,
        r_age_noise,
        r_tenure_days,
        r_enroll_offset
    FROM base
)
SELECT
    member_id                                     AS "MEMBER_ID",
    group_name                                    AS "GROUP_NAME",
    state_name                                     AS "STATE",
    county_name                                    AS "COUNTY",
    coverage_tier                                  AS "COVERAGE_TIER",
    -- EE (employee-only) is by definition the employee; every richer tier is
    -- a real household mix skewed toward the employee.
    CASE
        WHEN coverage_tier = 'EE' THEN 'Employee'
        WHEN r_rel < 400 THEN 'Employee'
        WHEN r_rel < 700 THEN 'Spouse'
        ELSE 'Dependent'
    END                                             AS "RELATIONSHIP",
    -- Dependents on the policy: 0 for EE-only, rising with richer tiers.
    CASE coverage_tier
        WHEN 'EE' THEN 0
        WHEN 'ES' THEN 1
        WHEN 'EC' THEN 1 + (r_rel % 3)
        ELSE 2 + (r_rel % 3)
    END                                             AS "DEPENDENT_COUNT",
    plan_name                                      AS "PLAN_NAME",
    plan_type                                       AS "PLAN_TYPE",
    employee_type                                   AS "EMPLOYEE_TYPE",
    gender                                          AS "GENDER",
    age_band                                        AS "AGE_BAND",
    -- exact age within its band, deterministic
    (CASE age_band
        WHEN '<35'    THEN 22
        WHEN '36-49'  THEN 36
        WHEN '50-64'  THEN 50
        ELSE 65
     END) + MOD(r_age_noise,
        CASE age_band
            WHEN '<35'   THEN 13
            WHEN '36-49' THEN 14
            WHEN '50-64' THEN 15
            ELSE 20
        END)                                        AS "EMPLOYEE_AGE",
    waived_coverage                                 AS "WAIVED_COVERAGE",
    ROUND(r_tenure_days / 365.0, 1)                 AS "TENURE_YEARS",
    DATEADD(day, -1 * (r_tenure_days + r_enroll_offset), CURRENT_DATE()) AS "ENROLLMENT_DATE"
FROM labelled
ORDER BY member_id;
