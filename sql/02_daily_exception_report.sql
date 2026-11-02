-- Step 2: the daily exception report (UC-09, BRD section 7.6), as run on Monday 5 July 2027 at 07:00.
-- Five groups of items that would otherwise stall silently. Each line names the order, invoice or dealer to act on.
-- Group 1 reads "without an invoice" as "no invoice accepted by the integrator", so held and failed invoices are included.

WITH p AS (SELECT * FROM report_params),
report_day AS (
    SELECT c.working_day_index AS idx FROM calendar c, p WHERE c.day = p.report_date
),
previous_working_day AS (
    SELECT max(c.day) AS day FROM calendar c, p WHERE c.is_working_day AND c.day < p.report_date
),
-- 1. Shipped more than one working day ago, no invoice accepted by the integrator
g1 AS (
    SELECT '1 Shipped, invoice not sent'                          AS exception_group,
           s.order_id                                             AS reference,
           o.dealer_code,
           CASE WHEN i.ettn IS NULL               THEN 'No invoice created in the ERP'
                WHEN i.final_state = 'HELD'        THEN 'Invoice held: dealer tax number not on the GİB list'
                WHEN i.final_state = 'SEND_FAILED' THEN 'Invoice rejected by the integrator, not yet resent'
                ELSE 'Invoice created, not yet sent' END          AS detail,
           s.confirmed_at                                         AS since
    FROM shipments s
    JOIN orders o USING (order_id)
    LEFT JOIN invoices i USING (order_id)
    JOIN calendar c ON c.day = CAST(s.confirmed_at AS DATE)
    CROSS JOIN report_day r
    WHERE s.confirmed_at IS NOT NULL
      AND i.accepted_at IS NULL
      AND r.idx - c.working_day_index > 1
),
-- 2. Sent to the integrator more than 24 hours ago, not delivered
g2 AS (
    SELECT '2 Sent, not delivered within 24 hours',
           i.ettn,
           i.dealer_code,
           'Invoice ' || i.invoice_no || ' still ' || i.final_state || ' at Köprü e-Belge',
           i.accepted_at
    FROM invoices i, p
    WHERE i.accepted_at IS NOT NULL
      AND i.delivered_at IS NULL
      AND i.accepted_at < p.as_of - INTERVAL 24 HOUR
),
-- 3. Delivered, not acknowledged within 5 working days, by dealers whose connector acknowledges invoices
g3 AS (
    SELECT '3 Delivered, not acknowledged in 5 working days',
           i.ettn,
           i.dealer_code,
           'Invoice ' || i.invoice_no || ' for dealer order ' || o.dealer_order_no,
           i.delivered_at
    FROM invoices i
    JOIN orders o USING (order_id)
    JOIN dealers d ON d.dealer_code = i.dealer_code
    LEFT JOIN acknowledgements a USING (ettn)
    JOIN calendar c ON c.day = CAST(i.delivered_at AS DATE)
    CROSS JOIN report_day r
    WHERE i.delivered_at IS NOT NULL
      AND a.ettn IS NULL
      AND d.acknowledges_invoices
      AND o.channel = 'API'
      AND o.current_status <> 'CLOSED'           -- orders close automatically 30 days after INVOICED
      AND r.idx - c.working_day_index > 5
),
-- 4. Dealers whose webhook endpoint fails: events exhausted in the last 7 days and the latest attempt still failing
last_attempt AS (
    SELECT dealer_code, arg_max(result, attempted_at) AS last_result
    FROM webhook_deliveries GROUP BY dealer_code
),
exhausted AS (
    SELECT w.dealer_code, count(*) AS events, min(w.attempted_at) AS first_exhausted_at
    FROM webhook_deliveries w, p
    WHERE w.result = 'EXHAUSTED' AND w.attempted_at >= p.as_of - INTERVAL 7 DAY
    GROUP BY w.dealer_code
),
g4 AS (
    SELECT '4 Webhook endpoint failing',
           e.dealer_code,
           e.dealer_code,
           e.events || ' events failed all 6 attempts; latest attempt ' || l.last_result,
           e.first_exhausted_at
    FROM exhausted e JOIN last_attempt l USING (dealer_code)
    WHERE l.last_result <> 'DELIVERED'
),
-- 5. Shipment confirmation late or missing: confirmed yesterday more than 24 hours after pickup, or not confirmed at all
g5 AS (
    SELECT '5 Shipment confirmation late or missing',
           s.order_id,
           o.dealer_code,
           CASE WHEN s.confirmed_at IS NULL THEN 'Picked up by the carrier, not confirmed in the ERP'
                ELSE 'Confirmed ' || round(date_diff('minute', s.carrier_pickup_at, s.confirmed_at) / 60.0, 1)
                     || ' hours after carrier pickup' END,
           s.carrier_pickup_at
    FROM shipments s
    JOIN orders o USING (order_id)
    CROSS JOIN p
    CROSS JOIN previous_working_day y
    WHERE (s.confirmed_at IS NULL AND s.carrier_pickup_at < p.as_of - INTERVAL 24 HOUR)
       OR (CAST(s.confirmed_at AS DATE) = y.day AND s.confirmed_at - s.carrier_pickup_at > INTERVAL 24 HOUR)
),
all_groups AS (
    SELECT * FROM g1 UNION ALL SELECT * FROM g2 UNION ALL SELECT * FROM g3
    UNION ALL SELECT * FROM g4 UNION ALL SELECT * FROM g5
)
SELECT a.exception_group, a.reference, a.dealer_code, a.detail,
       a.since, date_diff('hour', a.since, p.as_of) AS age_hours
FROM all_groups a, p
ORDER BY a.exception_group, a.since;
