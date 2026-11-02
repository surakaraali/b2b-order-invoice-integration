-- Step 12: the two incidents of the period and their effect. NFR-REL-04 and NFR-REL-05 require that an ERP or an
-- integrator outage delays work but loses nothing: every affected order and invoice must have been processed afterwards.

WITH erp AS (
    SELECT n.incident_id,
           count(*)                                                                    AS affected,
           max(date_diff('second', r.occurred_at, d.occurred_at)) / 60.0               AS longest_delay_minutes,
           count(*) FILTER (WHERE d.order_id IS NULL)                                  AS not_processed
    FROM incidents n
    JOIN order_status_history r ON r.sequence = 1 AND r.occurred_at >= n.started_at AND r.occurred_at < n.ended_at
    LEFT JOIN order_status_history d ON d.order_id = r.order_id AND d.sequence = 2
    WHERE n.system = 'ERP'
    GROUP BY n.incident_id
),
integrator AS (
    SELECT n.incident_id,
           count(DISTINCT c.ettn)                                                      AS affected,
           max(date_diff('second', i.created_at, i.accepted_at)) / 60.0                AS longest_delay_minutes,
           count(DISTINCT c.ettn) FILTER (WHERE i.accepted_at IS NULL)                 AS not_processed
    FROM incidents n
    JOIN integrator_calls c ON c.result = 'TIMEOUT' AND c.called_at >= n.started_at AND c.called_at < n.ended_at
    JOIN invoices i USING (ettn)
    WHERE n.system = 'INTEGRATOR'
    GROUP BY n.incident_id
),
effects AS (
    SELECT *, 'orders waiting for a first decision' AS affected_unit FROM erp
    UNION ALL
    SELECT *, 'invoices waiting to be sent' FROM integrator
)
SELECT n.incident_id, n.system, n.started_at, n.ended_at,
       date_diff('minute', n.started_at, n.ended_at)    AS duration_minutes,
       n.description,
       e.affected, e.affected_unit,
       round(e.longest_delay_minutes, 1)                AS longest_delay_minutes,
       e.not_processed
FROM incidents n
JOIN effects e USING (incident_id)
ORDER BY n.started_at;
