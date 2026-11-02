-- Step 9: webhook delivery (RULE-16). Per week: events created, delivered at the first attempt, delivered after
-- retries, and events that failed all 6 attempts (first attempt plus retries at 1, 5, 15, 60 and 240 minutes).

WITH events AS (
    SELECT event_id, dealer_code,
           min(event_created_at)                AS created_at,
           max(attempt)                         AS attempts,
           bool_or(result = 'DELIVERED')        AS delivered,
           bool_or(result = 'EXHAUSTED')        AS exhausted
    FROM webhook_deliveries
    GROUP BY event_id, dealer_code
)
SELECT c.period_week                                                          AS week,
       count(*)                                                               AS events,
       round(100.0 * avg((e.delivered AND e.attempts = 1)::INTEGER), 2)       AS first_attempt_pct,
       count(*) FILTER (WHERE e.delivered AND e.attempts > 1)                 AS delivered_after_retry,
       count(*) FILTER (WHERE e.exhausted)                                    AS exhausted,
       string_agg(DISTINCT e.dealer_code, ', ') FILTER (WHERE e.exhausted)    AS dealers_exhausted,
       count(*) FILTER (WHERE NOT e.delivered AND NOT e.exhausted)            AS still_retrying
FROM events e
JOIN calendar c ON c.day = CAST(e.created_at AS DATE)
GROUP BY c.period_week
ORDER BY week;
