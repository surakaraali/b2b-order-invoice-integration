-- Step 10: order submissions by result (error scenarios, section 3). Shows which error codes dealers actually meet,
-- and how often idempotency protects against duplicates (REPLAYED: same key and body, original response returned).

SELECT channel,
       result_code,
       http_status,
       coalesce(field_error_code, '')                                              AS field_error_code,
       count(*)                                                                    AS submissions,
       round(100.0 * count(*) / sum(count(*)) OVER (PARTITION BY channel), 2)      AS share_of_channel_pct
FROM order_submissions
GROUP BY channel, result_code, http_status, coalesce(field_error_code, '')
ORDER BY channel, submissions DESC;
