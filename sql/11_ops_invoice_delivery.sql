-- Step 11: how each invoice reached the dealer (UC-06), and the legal deadline. Under VUK article 231/5 an invoice is
-- issued within 7 days of delivery; the integration alerts on day 5 (NFR-COMPL-01). Invoices are counted by their path.

WITH calls AS (
    SELECT ettn,
           count(*) FILTER (WHERE result = 'TIMEOUT')                                         AS timeouts,
           count(*) FILTER (WHERE operation = 'SendInvoice' AND result = 'FAULT')             AS send_faults,
           count(*) FILTER (WHERE operation = 'GetInvoiceStatus' AND status_returned = 'ERROR') AS delivery_errors
    FROM integrator_calls
    GROUP BY ettn
),
classified AS (
    SELECT i.*, s.confirmed_at, s.carrier_pickup_at,
           CASE WHEN i.final_state <> 'DELIVERED'                    THEN 'Open at report time: ' || i.final_state
                WHEN i.held_at IS NOT NULL                           THEN 'Delivered after a tax number hold'
                WHEN coalesce(c.send_faults, 0) > 0                  THEN 'Delivered after a rejected send was fixed'
                WHEN coalesce(c.delivery_errors, 0) > 0              THEN 'Delivered after a delivery error and resend'
                WHEN coalesce(c.timeouts, 0) > 0                     THEN 'Delivered after the integrator incident'
                WHEN s.confirmed_at - s.carrier_pickup_at > INTERVAL 24 HOUR THEN 'Delivered after a late shipment confirmation'
                WHEN i.created_at - s.confirmed_at > INTERVAL 1 DAY  THEN 'Delivered, invoice created late in the ERP'
                WHEN i.delivered_at - i.accepted_at > INTERVAL 24 HOUR THEN 'Delivered, more than 24 hours at the integrator'
                ELSE 'Delivered first time' END                        AS outcome,
           date_diff('day', CAST(s.carrier_pickup_at AS DATE),       -- the goods left with the carrier
                     CAST(coalesce(i.delivered_at, p.as_of) AS DATE))   AS days_from_shipment
    FROM invoices i
    JOIN shipments s USING (order_id)
    LEFT JOIN calls c USING (ettn)
    CROSS JOIN report_params p
)
SELECT outcome,
       count(*)                                                     AS invoices,
       round(100.0 * count(*) / sum(count(*)) OVER (), 2)           AS share_pct,
       round(median(date_diff('minute', confirmed_at, delivered_at)) / 60.0, 2) AS median_hours_to_inbox,
       count(*) FILTER (WHERE days_from_shipment >= 5)              AS reached_day5_alert,
       count(*) FILTER (WHERE days_from_shipment > 7)               AS beyond_7_day_limit
FROM classified
GROUP BY outcome
ORDER BY invoices DESC;
