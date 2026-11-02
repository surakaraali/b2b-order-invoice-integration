-- Step 7: G5, faster invoice matching. From shipment confirmation to the e-Invoice in the dealer's GİB inbox, and from
-- delivery to the invoice.issued webhook. Baseline 1.5 working days; target same day, notification within 1 hour.

WITH delivered AS (
    SELECT i.order_id, i.delivered_at, s.confirmed_at, c.period_week,
           date_diff('minute', s.confirmed_at, i.delivered_at) / 60.0    AS hours_to_inbox,
           CAST(i.delivered_at AS DATE) = CAST(s.confirmed_at AS DATE)    AS same_day
    FROM invoices i
    JOIN shipments s USING (order_id)
    JOIN calendar c ON c.day = CAST(s.confirmed_at AS DATE)
    WHERE i.delivered_at IS NOT NULL
),
webhook AS (
    SELECT order_id, min(attempted_at) FILTER (WHERE result = 'DELIVERED') AS notified_at
    FROM webhook_deliveries
    WHERE event_type = 'invoice.issued'
    GROUP BY order_id
)
SELECT d.period_week                                                   AS week,
       count(*)                                                        AS invoices_delivered,
       round(100.0 * avg(d.same_day::INTEGER), 1)                      AS same_day_pct,
       round(median(d.hours_to_inbox), 2)                              AS median_hours,
       round(quantile_cont(d.hours_to_inbox, 0.95), 2)                 AS p95_hours,
       count(w.order_id)                                               AS webhook_notifications,
       round(100.0 * avg((w.notified_at <= d.delivered_at + INTERVAL 1 HOUR)::INTEGER)
             FILTER (WHERE w.order_id IS NOT NULL), 1)                 AS notified_within_1h_pct
FROM delivered d
LEFT JOIN webhook w USING (order_id)
GROUP BY d.period_week
ORDER BY week;
