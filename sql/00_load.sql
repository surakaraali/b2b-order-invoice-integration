-- Step 0: load the synthetic integration data (data/raw/*.csv) into typed tables.
-- Every CSV is read as text first, so each type conversion below is explicit. Timestamps are Türkiye local time.
-- The data covers the first 13 weeks after go-live; the daily exception report runs on Monday 5 July 2027 at 07:00.

CREATE OR REPLACE TABLE report_params AS
SELECT TIMESTAMP '2027-07-05 07:00:00' AS as_of,
       DATE '2027-07-05'              AS report_date,
       DATE '2027-04-05'              AS period_start,
       DATE '2027-07-03'              AS period_end;

CREATE OR REPLACE TABLE calendar AS
SELECT CAST(day AS DATE)                               AS day,
       weekday,
       is_working_day = 'true'                         AS is_working_day,
       NULLIF(holiday_name, '')                        AS holiday_name,
       CAST(working_day_index AS INTEGER)              AS working_day_index,
       CAST(NULLIF(period_week, '') AS INTEGER)        AS period_week
FROM read_csv('data/raw/calendar.csv', header = true, all_varchar = true);

CREATE OR REPLACE TABLE dealers AS
SELECT dealer_code, dealer_name, city, profile, erp, integration_channel,
       CAST(NULLIF(integration_live_date, '') AS DATE) AS integration_live_date,
       webhook_registered = 'true'                     AS webhook_registered,
       acknowledges_invoices = 'true'                  AS acknowledges_invoices,
       shipping_warehouse, sales_rep, status,
       CAST(NULLIF(suspended_from, '') AS DATE)        AS suspended_from
FROM read_csv('data/raw/dealers.csv', header = true, all_varchar = true);

CREATE OR REPLACE TABLE products AS
SELECT sku, name, category, unit_code,
       CAST(minimum_order_quantity AS INTEGER)         AS minimum_order_quantity,
       CAST(vat_rate AS INTEGER)                       AS vat_rate,
       CAST(unit_price AS DECIMAL(12, 2))              AS unit_price,
       status
FROM read_csv('data/raw/products.csv', header = true, all_varchar = true);

CREATE OR REPLACE TABLE orders AS
SELECT order_id, dealer_code, dealer_order_no,
       channel,                                                      -- API, PORTAL or MANUAL (keyed by sales support)
       CAST(received_at AS TIMESTAMP)                  AS received_at,
       CAST(line_count AS INTEGER)                     AS line_count,
       CAST(net_amount AS DECIMAL(14, 2))              AS net_amount,
       CAST(vat_amount AS DECIMAL(14, 2))              AS vat_amount,
       CAST(gross_amount AS DECIMAL(14, 2))            AS gross_amount,
       corrected_after_entry = 'true'                  AS corrected_after_entry,   -- from the ERP change log
       current_status
FROM read_csv('data/raw/orders.csv', header = true, all_varchar = true);

CREATE OR REPLACE TABLE order_lines AS
SELECT order_id,
       CAST(line_no AS INTEGER)                        AS line_no,
       sku,
       CAST(requested_qty AS INTEGER)                  AS requested_qty,
       CAST(approved_qty AS INTEGER)                   AS approved_qty,
       CAST(unit_price AS DECIMAL(12, 2))              AS unit_price,
       CAST(line_net AS DECIMAL(14, 2))                AS line_net
FROM read_csv('data/raw/order_lines.csv', header = true, all_varchar = true);

CREATE OR REPLACE TABLE order_status_history AS
SELECT order_id,
       CAST(sequence AS INTEGER)                       AS sequence,
       status,
       NULLIF(reason_code, '')                         AS reason_code,
       NULLIF(decided_by, '')                          AS decided_by,
       CAST(occurred_at AS TIMESTAMP)                  AS occurred_at
FROM read_csv('data/raw/order_status_history.csv', header = true, all_varchar = true);

CREATE OR REPLACE TABLE approval_tasks AS
SELECT task_id, order_id, reason_code, sales_rep,
       CAST(created_at AS TIMESTAMP)                   AS created_at,
       CAST(due_at AS TIMESTAMP)                       AS due_at,         -- created_at + 4 business hours (RULE-08)
       CAST(NULLIF(escalated_at, '') AS TIMESTAMP)     AS escalated_at,
       CAST(NULLIF(decided_at, '') AS TIMESTAMP)       AS decided_at,
       NULLIF(decided_by_role, '')                     AS decided_by_role,
       NULLIF(decision, '')                            AS decision
FROM read_csv('data/raw/approval_tasks.csv', header = true, all_varchar = true);

CREATE OR REPLACE TABLE shipments AS
SELECT order_id, warehouse_code,
       CAST(carrier_pickup_at AS TIMESTAMP)            AS carrier_pickup_at,
       CAST(NULLIF(confirmed_at, '') AS TIMESTAMP)     AS confirmed_at,
       delivery_note_no
FROM read_csv('data/raw/shipments.csv', header = true, all_varchar = true);

CREATE OR REPLACE TABLE invoices AS
SELECT ettn, invoice_no, order_id, dealer_code,
       CAST(invoice_date AS DATE)                      AS invoice_date,
       CAST(created_at AS TIMESTAMP)                   AS created_at,
       CAST(NULLIF(held_at, '') AS TIMESTAMP)          AS held_at,
       CAST(NULLIF(released_at, '') AS TIMESTAMP)      AS released_at,
       CAST(NULLIF(first_send_at, '') AS TIMESTAMP)    AS first_send_at,
       CAST(NULLIF(accepted_at, '') AS TIMESTAMP)      AS accepted_at,      -- SendInvoice returned a receipt
       NULLIF(receipt_id, '')                          AS receipt_id,
       CAST(NULLIF(delivered_at, '') AS TIMESTAMP)     AS delivered_at,     -- integrator reported DELIVERED
       final_state,
       CAST(status_polls AS INTEGER)                   AS status_polls,
       CAST(net_amount AS DECIMAL(14, 2))              AS net_amount,
       CAST(vat_amount AS DECIMAL(14, 2))              AS vat_amount,
       CAST(gross_amount AS DECIMAL(14, 2))            AS gross_amount
FROM read_csv('data/raw/invoices.csv', header = true, all_varchar = true);

CREATE OR REPLACE TABLE integrator_calls AS
SELECT call_id, ettn, operation,
       CAST(called_at AS TIMESTAMP)                    AS called_at,
       result,                                                       -- OK, FAULT or TIMEOUT
       NULLIF(fault_code, '')                          AS fault_code,
       NULLIF(status_returned, '')                     AS status_returned
FROM read_csv('data/raw/integrator_calls.csv', header = true, all_varchar = true);

CREATE OR REPLACE TABLE webhook_deliveries AS
SELECT event_id, dealer_code, order_id, event_type, order_status,
       CAST(event_created_at AS TIMESTAMP)             AS event_created_at,
       CAST(attempt AS INTEGER)                        AS attempt,
       CAST(attempted_at AS TIMESTAMP)                 AS attempted_at,
       result,                                                       -- DELIVERED, TIMEOUT, REJECTED, UNREACHABLE, EXHAUSTED
       CAST(NULLIF(http_status, '') AS INTEGER)        AS http_status
FROM read_csv('data/raw/webhook_deliveries.csv', header = true, all_varchar = true);

CREATE OR REPLACE TABLE acknowledgements AS
SELECT ettn, dealer_code,
       CAST(acknowledged_at AS TIMESTAMP)              AS acknowledged_at,
       match_result,
       CAST(dealer_booked_gross AS DECIMAL(14, 2))     AS dealer_booked_gross
FROM read_csv('data/raw/acknowledgements.csv', header = true, all_varchar = true);

CREATE OR REPLACE TABLE order_submissions AS
SELECT submission_id, dealer_code, channel,
       CAST(submitted_at AS TIMESTAMP)                 AS submitted_at,
       CAST(http_status AS INTEGER)                    AS http_status,
       result_code,
       NULLIF(field_error_code, '')                    AS field_error_code,
       NULLIF(order_id, '')                            AS order_id
FROM read_csv('data/raw/order_submissions.csv', header = true, all_varchar = true);

CREATE OR REPLACE TABLE api_daily_traffic AS
SELECT CAST(day AS DATE) AS day, endpoint,
       CAST(requests AS INTEGER)   AS requests,
       CAST(status_2xx AS INTEGER) AS status_2xx,
       CAST(status_4xx AS INTEGER) AS status_4xx,
       CAST(status_429 AS INTEGER) AS status_429,
       CAST(status_5xx AS INTEGER) AS status_5xx,
       CAST(p95_ms AS INTEGER)     AS p95_ms
FROM read_csv('data/raw/api_daily_traffic.csv', header = true, all_varchar = true);

CREATE OR REPLACE TABLE support_tally_weekly AS
SELECT CAST(week_start AS DATE)               AS week_start,
       CAST(working_days AS INTEGER)          AS working_days,
       CAST(phone_stock_questions AS INTEGER) AS phone_stock_questions,
       CAST(order_status_calls AS INTEGER)    AS order_status_calls,
       CAST(invoice_queries AS INTEGER)       AS invoice_queries
FROM read_csv('data/raw/support_tally_weekly.csv', header = true, all_varchar = true);

CREATE OR REPLACE TABLE incidents AS
SELECT incident_id, system,
       CAST(started_at AS TIMESTAMP) AS started_at,
       CAST(ended_at AS TIMESTAMP)   AS ended_at,
       description
FROM read_csv('data/raw/incidents.csv', header = true, all_varchar = true);

CREATE OR REPLACE TABLE webhook_endpoint_outages AS
SELECT dealer_code,
       CAST(started_at AS TIMESTAMP)               AS started_at,
       CAST(NULLIF(ended_at, '') AS TIMESTAMP)     AS ended_at
FROM read_csv('data/raw/webhook_endpoint_outages.csv', header = true, all_varchar = true);
