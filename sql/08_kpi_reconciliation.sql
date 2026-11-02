-- Step 8: G6, fewer reconciliation issues. Invoices the dealer's ERP booked with a different total, per month.
-- Baseline about 45 mismatches a month with PDF invoices; target below 5. July covers only the first days.

SELECT strftime(i.delivered_at, '%Y-%m')                                   AS month,
       count(*)                                                            AS invoices_delivered,
       count(a.ettn)                                                       AS acknowledged,
       count(a.ettn) FILTER (WHERE a.match_result = 'MISMATCH')            AS mismatches,
       sum(abs(a.dealer_booked_gross - i.gross_amount))
           FILTER (WHERE a.match_result = 'MISMATCH')                      AS mismatch_amount_try,
       5                                                                   AS target_max_per_month
FROM invoices i
LEFT JOIN acknowledgements a USING (ettn)
WHERE i.delivered_at IS NOT NULL
GROUP BY month
ORDER BY month;
