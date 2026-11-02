-- Step 3: G1, remove manual order entry. Share of order lines received through the API or the dealer portal, per week.
-- Target: at least 80% of order lines, six months after go-live (BRD section 4).

SELECT c.period_week                                                       AS week,
       p.period_start + 7 * (c.period_week - 1)                            AS week_start,
       sum(o.line_count)                                                   AS order_lines,
       sum(o.line_count) FILTER (WHERE o.channel = 'API')                  AS api_lines,
       sum(o.line_count) FILTER (WHERE o.channel = 'PORTAL')               AS portal_lines,
       sum(o.line_count) FILTER (WHERE o.channel = 'MANUAL')               AS manual_lines,
       round(100.0 * sum(o.line_count) FILTER (WHERE o.channel <> 'MANUAL') / sum(o.line_count), 1)
                                                                           AS integrated_share_pct,
       count(DISTINCT o.dealer_code) FILTER (WHERE o.channel <> 'MANUAL')  AS dealers_ordering_integrated,
       80                                                                  AS target_pct
FROM orders o
JOIN calendar c ON c.day = CAST(o.received_at AS DATE)
CROSS JOIN report_params p
GROUP BY c.period_week, p.period_start
ORDER BY week;
