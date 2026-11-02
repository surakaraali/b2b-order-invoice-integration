-- Step 1: data quality checks. Every check states what it expects; the analysis below is only trusted if all pass.

WITH checks AS (
    SELECT 1 AS n, 'Orders loaded' AS check_name,
           (SELECT count(*) FROM orders) AS found, 'more than 0' AS expected,
           (SELECT count(*) FROM orders) > 0 AS passed
    UNION ALL
    SELECT 2, 'Duplicate order ids',
           (SELECT count(*) - count(DISTINCT order_id) FROM orders), '0', NULL
    UNION ALL
    SELECT 3, 'Dealer order number used twice by one dealer (non-rejected orders)',
           (SELECT count(*) FROM (SELECT dealer_code, dealer_order_no FROM orders WHERE current_status <> 'REJECTED'
                                  GROUP BY ALL HAVING count(*) > 1)), '0', NULL
    UNION ALL
    SELECT 4, 'Order lines without an order',
           (SELECT count(*) FROM order_lines l ANTI JOIN orders o USING (order_id)), '0', NULL
    UNION ALL
    SELECT 5, 'Orders whose line count does not match their lines',
           (SELECT count(*) FROM orders o
             WHERE o.line_count <> (SELECT count(*) FROM order_lines l WHERE l.order_id = o.order_id)), '0', NULL
    UNION ALL
    SELECT 6, 'Orders whose net amount differs from the sum of their lines',
           (SELECT count(*) FROM orders o
             WHERE o.net_amount <> (SELECT sum(line_net) FROM order_lines l WHERE l.order_id = o.order_id)), '0', NULL
    UNION ALL
    SELECT 7, 'Orders whose gross amount is not net plus VAT',
           (SELECT count(*) FROM orders WHERE gross_amount <> net_amount + vat_amount), '0', NULL
    UNION ALL
    SELECT 8, 'Orders without RECEIVED as the first status',
           (SELECT count(*) FROM orders o
             WHERE NOT EXISTS (SELECT 1 FROM order_status_history h
                                WHERE h.order_id = o.order_id AND h.sequence = 1 AND h.status = 'RECEIVED')), '0', NULL
    UNION ALL
    SELECT 9, 'Orders with gaps in the status sequence',
           (SELECT count(*) FROM (SELECT order_id FROM order_status_history GROUP BY order_id
                                  HAVING max(sequence) <> count(*))), '0', NULL
    UNION ALL
    SELECT 10, 'Status changes earlier than the previous one',
           (SELECT count(*) FROM (SELECT occurred_at < lag(occurred_at) OVER (PARTITION BY order_id ORDER BY sequence) AS back
                                  FROM order_status_history) WHERE back), '0', NULL
    UNION ALL
    SELECT 11, 'Current status differs from the last history entry',
           (SELECT count(*) FROM orders o
              JOIN (SELECT order_id, arg_max(status, sequence) AS last_status FROM order_status_history GROUP BY order_id) h
             USING (order_id) WHERE o.current_status <> h.last_status), '0', NULL
    UNION ALL
    SELECT 12, 'Shipments for orders that were never allocated',
           (SELECT count(*) FROM shipments s
             WHERE NOT EXISTS (SELECT 1 FROM order_status_history h WHERE h.order_id = s.order_id AND h.status = 'ALLOCATED')),
           '0', NULL
    UNION ALL
    SELECT 13, 'Invoices without a confirmed shipment',
           (SELECT count(*) FROM invoices i LEFT JOIN shipments s USING (order_id) WHERE s.confirmed_at IS NULL), '0', NULL
    UNION ALL
    SELECT 14, 'Orders with more than one invoice (RULE-13: one per shipment)',
           (SELECT count(*) FROM (SELECT order_id FROM invoices GROUP BY order_id HAVING count(*) > 1)), '0', NULL
    UNION ALL
    SELECT 15, 'Invoice amounts that differ from the order',
           (SELECT count(*) FROM invoices i JOIN orders o USING (order_id) WHERE i.gross_amount <> o.gross_amount), '0', NULL
    UNION ALL
    SELECT 16, 'Invoices delivered before they were accepted by the integrator',
           (SELECT count(*) FROM invoices WHERE delivered_at < accepted_at), '0', NULL
    UNION ALL
    SELECT 17, 'Acknowledgements for invoices that were not delivered',
           (SELECT count(*) FROM acknowledgements a JOIN invoices i USING (ettn) WHERE i.delivered_at IS NULL), '0', NULL
    UNION ALL
    SELECT 18, 'Webhook events with more than 6 attempts (RULE-16)',
           (SELECT count(*) FROM (SELECT event_id FROM webhook_deliveries GROUP BY event_id HAVING max(attempt) > 6)), '0', NULL
    UNION ALL
    SELECT 19, 'Accepted submissions without an order',
           (SELECT count(*) FROM order_submissions s
             WHERE s.result_code IN ('ACCEPTED', 'REPLAYED') AND NOT EXISTS (SELECT 1 FROM orders o WHERE o.order_id = s.order_id)),
           '0', NULL
    UNION ALL
    SELECT 20, 'Orders from suspended dealers after the suspension date',
           (SELECT count(*) FROM orders o JOIN dealers d USING (dealer_code)
             WHERE d.suspended_from IS NOT NULL AND CAST(o.received_at AS DATE) >= d.suspended_from), '0', NULL
)
SELECT n, check_name, found, expected, coalesce(passed, found = 0) AS passed
FROM checks
ORDER BY n;
