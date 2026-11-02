-- Step 4: G2, reduce order errors. Orders corrected in the ERP after entry, per week and channel.
-- Baseline 4% of orders, target below 0.5%. Integrated orders are validated at the source; manual ones are keyed by hand.

SELECT c.period_week                                                                  AS week,
       count(*)                                                                       AS orders,
       count(*) FILTER (WHERE o.corrected_after_entry)                                AS corrected,
       round(100.0 * count(*) FILTER (WHERE o.corrected_after_entry) / count(*), 2)   AS corrected_pct,
       round(100.0 * count(*) FILTER (WHERE o.corrected_after_entry AND o.channel <> 'MANUAL')
             / nullif(count(*) FILTER (WHERE o.channel <> 'MANUAL'), 0), 2)           AS corrected_pct_integrated,
       round(100.0 * count(*) FILTER (WHERE o.corrected_after_entry AND o.channel = 'MANUAL')
             / nullif(count(*) FILTER (WHERE o.channel = 'MANUAL'), 0), 2)            AS corrected_pct_manual,
       0.5                                                                            AS target_pct
FROM orders o
JOIN calendar c ON c.day = CAST(o.received_at AS DATE)
GROUP BY c.period_week
ORDER BY week;
