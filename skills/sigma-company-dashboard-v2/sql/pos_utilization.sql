-- Medical utilization by place of service: blended PMPM cost across the
-- Medical plan's enrolled population, split Office / Outpatient / Inpatient /
-- Emergency Room / Urgent Care, trailing 12 months. This is the chart a
-- benefits broker's clinical/analytics team builds every renewal cycle to
-- show a client group where their medical dollar is actually going -- the
-- outpatient shift (rising every month) and the ER-vs-urgent-care mix
-- (winter respiratory season spikes ER, urgent care absorbs some of it) are
-- the two stories real "Medical Utilization" decks lead with.
SELECT
    CAST(month_name AS VARCHAR)        AS "Month",
    CAST(place_of_service AS VARCHAR)  AS "Place of Service",
    CAST(pmpm_cost AS NUMBER(8,1))     AS "PMPM Cost"
FROM (
    SELECT 'Sep' AS month_name, 1 AS month_order, 'Office' AS place_of_service, 98.0 AS pmpm_cost
    UNION ALL SELECT 'Oct', 2, 'Office', 100.0
    UNION ALL SELECT 'Nov', 3, 'Office', 92.1
    UNION ALL SELECT 'Dec', 4, 'Office', 86.2
    UNION ALL SELECT 'Jan', 5, 'Office', 90.2
    UNION ALL SELECT 'Feb', 6, 'Office', 102.9
    UNION ALL SELECT 'Mar', 7, 'Office', 105.8
    UNION ALL SELECT 'Apr', 8, 'Office', 103.9
    UNION ALL SELECT 'May', 9, 'Office', 100.9
    UNION ALL SELECT 'Jun', 10, 'Office', 99.0
    UNION ALL SELECT 'Jul', 11, 'Office', 98.0
    UNION ALL SELECT 'Aug', 12, 'Office', 97.0
    UNION ALL SELECT 'Sep', 1, 'Outpatient', 153.3
    UNION ALL SELECT 'Oct', 2, 'Outpatient', 154.8
    UNION ALL SELECT 'Nov', 3, 'Outpatient', 156.4
    UNION ALL SELECT 'Dec', 4, 'Outpatient', 153.3
    UNION ALL SELECT 'Jan', 5, 'Outpatient', 158.0
    UNION ALL SELECT 'Feb', 6, 'Outpatient', 161.2
    UNION ALL SELECT 'Mar', 7, 'Outpatient', 162.7
    UNION ALL SELECT 'Apr', 8, 'Outpatient', 164.3
    UNION ALL SELECT 'May', 9, 'Outpatient', 165.9
    UNION ALL SELECT 'Jun', 10, 'Outpatient', 167.5
    UNION ALL SELECT 'Jul', 11, 'Outpatient', 169.1
    UNION ALL SELECT 'Aug', 12, 'Outpatient', 170.6
    UNION ALL SELECT 'Sep', 1, 'Inpatient', 142.1
    UNION ALL SELECT 'Oct', 2, 'Inpatient', 145.0
    UNION ALL SELECT 'Nov', 3, 'Inpatient', 155.4
    UNION ALL SELECT 'Dec', 4, 'Inpatient', 174.6
    UNION ALL SELECT 'Jan', 5, 'Inpatient', 170.2
    UNION ALL SELECT 'Feb', 6, 'Inpatient', 151.0
    UNION ALL SELECT 'Mar', 7, 'Inpatient', 139.1
    UNION ALL SELECT 'Apr', 8, 'Inpatient', 133.2
    UNION ALL SELECT 'May', 9, 'Inpatient', 131.7
    UNION ALL SELECT 'Jun', 10, 'Inpatient', 134.7
    UNION ALL SELECT 'Jul', 11, 'Inpatient', 137.6
    UNION ALL SELECT 'Aug', 12, 'Inpatient', 140.6
    UNION ALL SELECT 'Sep', 1, 'Emergency Room', 38.6
    UNION ALL SELECT 'Oct', 2, 'Emergency Room', 41.2
    UNION ALL SELECT 'Nov', 3, 'Emergency Room', 48.3
    UNION ALL SELECT 'Dec', 4, 'Emergency Room', 56.7
    UNION ALL SELECT 'Jan', 5, 'Emergency Room', 53.8
    UNION ALL SELECT 'Feb', 6, 'Emergency Room', 44.1
    UNION ALL SELECT 'Mar', 7, 'Emergency Room', 37.0
    UNION ALL SELECT 'Apr', 8, 'Emergency Room', 34.4
    UNION ALL SELECT 'May', 9, 'Emergency Room', 35.7
    UNION ALL SELECT 'Jun', 10, 'Emergency Room', 37.8
    UNION ALL SELECT 'Jul', 11, 'Emergency Room', 39.5
    UNION ALL SELECT 'Aug', 12, 'Emergency Room', 41.2
    UNION ALL SELECT 'Sep', 1, 'Urgent Care', 19.8
    UNION ALL SELECT 'Oct', 2, 'Urgent Care', 20.7
    UNION ALL SELECT 'Nov', 3, 'Urgent Care', 23.1
    UNION ALL SELECT 'Dec', 4, 'Urgent Care', 25.3
    UNION ALL SELECT 'Jan', 5, 'Urgent Care', 24.6
    UNION ALL SELECT 'Feb', 6, 'Urgent Care', 22.0
    UNION ALL SELECT 'Mar', 7, 'Urgent Care', 20.9
    UNION ALL SELECT 'Apr', 8, 'Urgent Care', 21.6
    UNION ALL SELECT 'May', 9, 'Urgent Care', 22.4
    UNION ALL SELECT 'Jun', 10, 'Urgent Care', 23.1
    UNION ALL SELECT 'Jul', 11, 'Urgent Care', 23.8
    UNION ALL SELECT 'Aug', 12, 'Urgent Care', 24.2
)
ORDER BY place_of_service, month_order
