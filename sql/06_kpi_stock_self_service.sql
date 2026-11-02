-- Step 6: G4, self-service stock. Stock questions by phone (sales support tally) against stock queries through
-- the API and the portal, per working day. Baseline about 60 phone questions a day, target below 6.

SELECT s.week_start,
       s.working_days,
       round(s.phone_stock_questions / s.working_days, 1)  AS phone_stock_questions_per_day,
       round(sum(t.requests) / s.working_days)             AS stock_queries_per_day,
       round(s.order_status_calls / s.working_days, 1)     AS order_status_calls_per_day,
       6                                                   AS target_phone_per_day
FROM support_tally_weekly s
JOIN api_daily_traffic t
  ON t.endpoint = 'GET /stock' AND t.day >= s.week_start AND t.day < s.week_start + 7
GROUP BY s.week_start, s.working_days, s.phone_stock_questions, s.order_status_calls
ORDER BY s.week_start;
