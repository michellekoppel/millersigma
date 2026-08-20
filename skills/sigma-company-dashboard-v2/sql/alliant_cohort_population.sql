-- Synthetic per-member population for the Alliant "Population Builder" cohort
-- page. 2,000 members, deterministic (HASH-seeded, no RANDOM) so segment
-- counts and PMPM cost are stable across runs and safe to quote live in a
-- demo. Column value domains are deliberately aligned with the other 5
-- pages' pre-aggregated tables already in this workbook:
--   * Age Band matches tbl-age's exact 4 bands ('<35','36-49','50-64','65+').
--   * Plan matches tbl-plan's 'Plan 1'/'Plan 2'/'Plan 3'.
--   * Gender matches tbl-gender-split's 'Female'/'Male'.
--   * Group Name matches tbl-group's real 3-value domain (GEICO, FIS Global,
--     Contoso Logistics) -- NOT the 2-value GEICO/FIS Global domain assumed
--     in the build brief, so this new table stays consistent with every
--     other page's Group filter instead of silently disagreeing with it.
WITH seq AS (
    SELECT SEQ4() AS i FROM TABLE(GENERATOR(ROWCOUNT => 2000))
),
base AS (
    SELECT
        i,
        'MBR-' || LPAD(CAST(i + 500001 AS VARCHAR), 7, '0') AS member_id,
        ABS(HASH(i, 11)) % 100 AS r_group,
        ABS(HASH(i, 22)) % 100 AS r_tier,
        ABS(HASH(i, 33)) % 100 AS r_age,
        ABS(HASH(i, 44)) % 100 AS r_gender,
        ABS(HASH(i, 55)) % 100 AS r_rel,
        ABS(HASH(i, 66)) % 100 AS r_plan,
        ABS(HASH(i, 77)) % 100 AS r_tenure,
        ABS(HASH(i, 88)) % 401 AS r_noise
    FROM seq
),
labelled AS (
    SELECT
        member_id,
        CASE
            WHEN r_group < 55 THEN 'GEICO'
            WHEN r_group < 85 THEN 'FIS Global'
            ELSE 'Contoso Logistics'
        END AS group_name,
        CASE
            WHEN r_tier < 50 THEN 'EE Only'
            WHEN r_tier < 62 THEN '+Spouse'
            WHEN r_tier < 78 THEN '+Child(ren)'
            ELSE 'Family'
        END AS coverage_tier,
        CASE
            WHEN r_age < 29 THEN '<35'
            WHEN r_age < 63 THEN '36-49'
            WHEN r_age < 96 THEN '50-64'
            ELSE '65+'
        END AS age_band,
        CASE WHEN r_gender < 62 THEN 'Female' ELSE 'Male' END AS gender,
        r_rel,
        CASE
            WHEN r_plan < 59 THEN 'Plan 1'
            WHEN r_plan < 79 THEN 'Plan 2'
            ELSE 'Plan 3'
        END AS plan_name,
        CASE
            WHEN r_tenure < 20 THEN 'New Enrollee'
            WHEN r_tenure < 55 THEN 'Established'
            WHEN r_tenure < 85 THEN 'Long-Tenured'
            ELSE 'Legacy Member'
        END AS tenure_band,
        r_noise
    FROM base
)
SELECT
    member_id                                     AS "MEMBER_ID",
    group_name                                    AS "GROUP_NAME",
    coverage_tier                                 AS "COVERAGE_TIER",
    age_band                                      AS "AGE_BAND",
    gender                                        AS "GENDER",
    -- EE Only members are, by definition, the employee themselves; every
    -- other tier is a real household mix skewed toward the employee.
    CASE
        WHEN coverage_tier = 'EE Only' THEN 'Employee'
        WHEN r_rel < 40 THEN 'Employee'
        WHEN r_rel < 70 THEN 'Spouse'
        ELSE 'Dependent'
    END                                            AS "RELATIONSHIP",
    plan_name                                     AS "PLAN_NAME",
    tenure_band                                   AS "TENURE_BAND",
    -- PMPM claims cost: rises with age band, scaled by plan richness, plus
    -- a bounded deterministic noise term so no two members with the same
    -- band/plan land on an identical dollar.
    GREATEST(75, ROUND(
        (CASE age_band
            WHEN '<35' THEN 300
            WHEN '36-49' THEN 450
            WHEN '50-64' THEN 650
            ELSE 900
         END)
        * (CASE plan_name
            WHEN 'Plan 1' THEN 0.85
            WHEN 'Plan 2' THEN 1.00
            ELSE 1.25
           END)
        + (r_noise - 200)
    , 2))                                          AS "PMPM_COST"
FROM labelled
