-- Step 13: scorecard of the six BRD goals over the last four weeks of the period (weeks 10 to 13, 7 June to 3 July).
-- G1 has a six-month target date; the others apply from go-live. Status compares the result with the target.

WITH p AS (SELECT * FROM report_params),
recent AS (
    SELECT day FROM calendar WHERE period_week BETWEEN 10 AND 13
),
working_days AS (
    SELECT count(*) AS n FROM calendar WHERE period_week BETWEEN 10 AND 13 AND is_working_day
),
g1 AS (
    SELECT round(100.0 * sum(line_count) FILTER (WHERE channel <> 'MANUAL') / sum(line_count), 1) AS v
    FROM orders WHERE CAST(received_at AS DATE) IN (SELECT day FROM recent)
),
g2 AS (
    SELECT round(100.0 * avg(corrected_after_entry::INTEGER), 2) AS v,
           round(100.0 * avg(corrected_after_entry::INTEGER) FILTER (WHERE channel <> 'MANUAL'), 2) AS v_integrated
    FROM orders WHERE CAST(received_at AS DATE) IN (SELECT day FROM recent)
),
g3 AS (
    SELECT round(quantile_cont(date_diff('millisecond', r.occurred_at, d.occurred_at) / 1000.0, 0.95), 1) AS p95_seconds
    FROM order_status_history d
    JOIN order_status_history r ON r.order_id = d.order_id AND r.sequence = 1
    WHERE d.sequence = 2 AND CAST(r.occurred_at AS DATE) IN (SELECT day FROM recent)
),
g3_tasks AS (
    SELECT round(100.0 * avg((decided_at <= due_at)::INTEGER), 1) AS on_time_pct
    FROM approval_tasks WHERE decided_at IS NOT NULL AND CAST(created_at AS DATE) IN (SELECT day FROM recent)
),
g4 AS (
    SELECT round(sum(phone_stock_questions) / sum(working_days), 1) AS v
    FROM support_tally_weekly WHERE week_start IN (SELECT day FROM recent)
),
g5 AS (
    SELECT round(100.0 * avg((CAST(i.delivered_at AS DATE) = CAST(s.confirmed_at AS DATE))::INTEGER), 1) AS same_day_pct,
           round(median(date_diff('minute', s.confirmed_at, i.delivered_at)) / 60.0, 2)            AS median_hours
    FROM invoices i JOIN shipments s USING (order_id)
    WHERE i.delivered_at IS NOT NULL AND CAST(s.confirmed_at AS DATE) IN (SELECT day FROM recent)
),
g6 AS (
    SELECT count(*) AS v FROM acknowledgements
    WHERE match_result = 'MISMATCH' AND strftime(acknowledged_at, '%Y-%m') = '2027-06'
)
SELECT 'G1' AS goal, 'Order lines received through the API or the portal' AS metric,
       '0%' AS baseline, 'at least 80% by October 2027' AS target,
       g1.v || '%' AS result,
       CASE WHEN g1.v >= 80 THEN 'Met' ELSE 'On the way; target date not reached' END AS status
FROM g1
UNION ALL
SELECT 'G2', 'Orders corrected after entry', '4%', 'below 0.5%',
       g2.v || '% overall, ' || g2.v_integrated || '% for integrated orders',
       CASE WHEN g2.v < 0.5 THEN 'Met' WHEN g2.v_integrated < 0.5 THEN 'Met for integrated orders only' ELSE 'Not met' END
FROM g2
UNION ALL
SELECT 'G3', 'Time to first status; approvals within 4 business hours', 'about 1 working day',
       'under 2 minutes; approvals within 4 business hours',
       'p95 ' || g3.p95_seconds || ' s; ' || g3_tasks.on_time_pct || '% of approvals on time',
       CASE WHEN g3.p95_seconds < 120 AND g3_tasks.on_time_pct >= 100 THEN 'Met'
            WHEN g3.p95_seconds < 120 THEN 'Met for automatic decisions; approvals miss the 4-hour target'
            ELSE 'Not met' END
FROM g3, g3_tasks
UNION ALL
SELECT 'G4', 'Stock questions by phone per working day', 'about 60', 'below 6',
       g4.v || ' a day', CASE WHEN g4.v < 6 THEN 'Met' ELSE 'Not met' END
FROM g4
UNION ALL
SELECT 'G5', 'Invoice in the dealer''s inbox on the day of shipment', '1.5 working days', 'same day',
       g5.same_day_pct || '% same day, median ' || g5.median_hours || ' hours',
       CASE WHEN g5.same_day_pct >= 95 THEN 'Met' ELSE 'Not met' END
FROM g5
UNION ALL
SELECT 'G6', 'Reconciliation mismatches in June 2027', 'about 45 a month', 'below 5 a month',
       g6.v || ' in June', CASE WHEN g6.v < 5 THEN 'Met' ELSE 'Not met' END
FROM g6;
