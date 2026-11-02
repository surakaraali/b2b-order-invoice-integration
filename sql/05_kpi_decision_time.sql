-- Step 5: G3, faster acknowledgement. Time from RECEIVED to the first decision, and approval tasks against their
-- due time of 4 business hours (RULE-08). Targets: under 2 minutes for automatic decisions, approvals within due.

WITH first_decision AS (
    SELECT d.order_id, r.occurred_at AS received_at, d.occurred_at AS decided_at, d.status,
           date_diff('millisecond', r.occurred_at, d.occurred_at) / 1000.0 AS seconds
    FROM order_status_history d
    JOIN order_status_history r ON r.order_id = d.order_id AND r.sequence = 1
    WHERE d.sequence = 2
),
erp_incident AS (
    SELECT started_at, ended_at FROM incidents WHERE system = 'ERP'
),
tasks AS (
    SELECT *, decided_at <= due_at AS on_time FROM approval_tasks WHERE decided_at IS NOT NULL
)
SELECT 1 AS n, 'Orders with a first decision' AS metric, count(*)::DOUBLE AS value, 'orders' AS unit, '' AS target
FROM first_decision
UNION ALL
SELECT 2, 'Median time to the first decision', round(median(seconds), 1), 'seconds', '' FROM first_decision
UNION ALL
SELECT 3, '95th percentile time to the first decision', round(quantile_cont(seconds, 0.95), 1), 'seconds',
       'under 60 (NFR-PERF-04)' FROM first_decision
UNION ALL
SELECT 4, 'First decision within 2 minutes', round(100.0 * avg((seconds <= 120)::INTEGER), 2), '% of orders',
       '100 (G3)' FROM first_decision
UNION ALL
SELECT 5, 'Orders received during the ERP incident', count(*), 'orders', ''
FROM first_decision f, erp_incident e WHERE f.received_at >= e.started_at AND f.received_at < e.ended_at
UNION ALL
SELECT 6, 'Longest wait for a decision during the ERP incident', round(max(f.seconds) / 60, 1), 'minutes', ''
FROM first_decision f, erp_incident e WHERE f.received_at >= e.started_at AND f.received_at < e.ended_at
UNION ALL
SELECT 7, 'Orders sent to approval', count(*), 'orders', '' FROM approval_tasks
UNION ALL
SELECT 8, 'Approval tasks decided within 4 business hours', round(100.0 * avg(on_time::INTEGER), 1), '% of tasks',
       '100 (RULE-08)' FROM tasks
UNION ALL
SELECT 9, 'Approval tasks escalated to the sales manager', count(*) FILTER (WHERE escalated_at IS NOT NULL), 'tasks', ''
FROM approval_tasks
UNION ALL
SELECT 10, 'Median clock time to an approval decision', round(median(date_diff('minute', created_at, decided_at)) / 60.0, 1),
       'hours', '' FROM tasks
UNION ALL
SELECT 11, 'Approvals on time, credit limit cases', round(100.0 * avg(on_time::INTEGER) FILTER (WHERE reason_code = 'CREDIT_LIMIT'), 1),
       '% of tasks', '' FROM tasks
UNION ALL
SELECT 12, 'Approvals on time, partial stock cases', round(100.0 * avg(on_time::INTEGER) FILTER (WHERE reason_code = 'PARTIAL_STOCK'), 1),
       '% of tasks', '' FROM tasks
ORDER BY n;
