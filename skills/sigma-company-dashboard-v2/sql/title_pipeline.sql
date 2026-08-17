-- Title order lifecycle funnel: a monthly snapshot of open orders flowing
-- through the title & settlement production stages, from Opened to Policy
-- Issued. The step-down between stages is real-world fallout (cancellations,
-- refis falling through, files that never clear to close). Pull-through =
-- Policy Issued / Opened. Counts are a representative monthly volume for a
-- national title insurer at First American's scale (~1M policies/yr).
SELECT
    CAST(stage AS VARCHAR)        AS "Stage",
    CAST(stage_order AS NUMBER)   AS "Stage Order",
    CAST(orders AS NUMBER)        AS "Orders"
FROM (
                 SELECT 'Opened'              AS stage, 1 AS stage_order, 100000 AS orders
    UNION ALL SELECT 'Title Search',        2, 95600
    UNION ALL SELECT 'Examination',         3, 91200
    UNION ALL SELECT 'Commitment Issued',   4, 85800
    UNION ALL SELECT 'Clear to Close',      5, 78400
    UNION ALL SELECT 'Closing / Settlement',6, 72300
    UNION ALL SELECT 'Policy Issued',       7, 69100
)
ORDER BY stage_order
