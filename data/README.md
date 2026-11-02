# Synthetic integration data

`generate_data.py` creates the data that the SQL in `sql/` analyses: thirteen weeks of orders, invoices and integration logs after the go-live of the dealer integration. The data is synthetic and fictional. Problems are planted at known rates, so the query results can be checked against what was put in.

```bash
python3 data/generate_data.py
```

The script uses only the Python standard library and a fixed seed. Running it again produces byte-identical CSV files in `data/raw/`.

## The story

| Item | Value |
|---|---|
| Period | Monday 5 April to Saturday 3 July 2027, the first 13 weeks after go-live |
| Working days | 73: Monday to Saturday, 08:00 to 20:00, without public holidays |
| Public holidays | 23 April, 1 May, 17 to 19 May. The Kurban Bayramı dates are an assumption for 2027 |
| Report time | The daily exception report runs on Monday 5 July 2027 at 07:00 |
| Dealers | 120: 15 large, 45 mid-size, 60 small. Two pilot dealers were live before go-live |
| Adoption | Dealers move from e-mail orders, keyed by sales support, to the API or the portal on their own go-live date; 79 of 120 are live by the end of week 13 |
| Volume | About 45 orders and 380 order lines per working day; 3,306 orders in total |
| Timestamps | Türkiye local time, UTC+3, written as `YYYY-MM-DD HH:MM:SS` |

Two incidents happen in the period:

- **INC-2027-014, ERP, 11 May, 10:05 to 11:50.** The business rules cannot read credit and stock data. Orders stay `RECEIVED` and are decided after the recovery.
- **INC-2027-022, integrator, 8 June, 14:00 to 16:10.** The Köprü e-Belge service is unreachable. Invoices queue and are sent after the recovery.

Two dealer webhook endpoints fail. D00031 is down from 14 to 16 June, and D00087 has been down since 2 July 08:00, still failing at report time.

## Files

| File | Rows | Grain and content |
|---|---|---|
| `calendar.csv` | 111 | One row per day: working day flag, holiday, working-day index, period week |
| `dealers.csv` | 120 | Profile, ERP, integration channel and go-live date, webhook and acknowledgement capability, warehouse, sales representative, status |
| `products.csv` | 28 | Catalogue with minimum order quantities and prices; one inactive SKU |
| `orders.csv` | 3,306 | One row per order: channel (`API`, `PORTAL`, `MANUAL`), amounts, ERP correction flag, current status |
| `order_lines.csv` | 27,872 | Requested and approved quantities, unit price, line net |
| `order_status_history.csv` | 19,143 | Every status change with sequence, reason code and decider |
| `approval_tasks.csv` | 383 | Credit limit and partial stock exceptions with due time (4 business hours), escalation and decision |
| `shipments.csv` | 3,199 | Carrier pickup and shipment confirmation in the ERP |
| `invoices.csv` | 3,192 | e-Invoice lifecycle: created, held, sent, accepted, delivered, final state |
| `integrator_calls.csv` | 10,009 | SOAP calls to Köprü e-Belge with result, fault code and returned status |
| `webhook_deliveries.csv` | 5,993 | One row per delivery attempt of each webhook event |
| `acknowledgements.csv` | 861 | Dealer acknowledgements with the match result and the total the dealer booked |
| `order_submissions.csv` | 1,472 | `POST /orders` attempts through the API and the portal, with result and error codes |
| `api_daily_traffic.csv` | 438 | Requests per day and endpoint, by status class, with the 95th percentile response time |
| `support_tally_weekly.csv` | 13 | Phone questions counted by sales support per week |
| `incidents.csv`, `webhook_endpoint_outages.csv` | 2, 2 | The incidents and endpoint outages above |

## Planted problems and where the SQL finds them

| Planted | Rate | Count | Found by |
|---|---|---|---|
| Rejected by the rules: inactive SKU, quantity below the minimum | 0.5%, 0.3% | 12, 9 | Order status history |
| Sent to approval: credit limit, partial stock | 5%, 6% | 184, 199 | `05_kpi_decision_time`: 383 orders sent to approval |
| Approval decided after the 4 business hour due time, escalated | 13% of tasks (14.9% realised) | 57 | `05_kpi_decision_time`: 85.1% on time, 57 escalated |
| Orders waiting during the ERP incident | Incident | 12 | `12_ops_incidents`: 12 orders, longest wait 91 minutes |
| Shipment confirmed late in the ERP | 2.5% | 74 | `11_ops_invoice_delivery`: 54 of them already invoiced; 3 reached the day-5 alert |
| Invoice stuck in the ERP | 0.2% plus 5 open | 8 | 3 delivered late; 3 open in the exception report; 2 confirmed on 3 July, not yet overdue |
| Invoice held: dealer tax number not registered | 0.25% | 5 | `11_ops_invoice_delivery`: delivered after a hold |
| SendInvoice rejected, fixed and resent | 0.35% | 14 | `11_ops_invoice_delivery` |
| Delivery error at GİB, resent | 0.2% | 9 | `11_ops_invoice_delivery` |
| More than 24 hours at the integrator | 0.15% plus 2 open | 2 delivered, 2 open | `11_ops_invoice_delivery`; the open two in the exception report |
| Invoices delayed by the integrator incident | Incident | 30 | `12_ops_incidents`: 30 invoices, none lost |
| Webhook events failing all 6 attempts | Outages | 23 | `09_ops_webhook_delivery`: 21 for D00031, 2 for D00087 |
| Acknowledged late, never acknowledged | 6%, 1% | 55, 10 | Exception report group 3 lists the 6 still open |
| Acknowledged with a different total | 0.4% | 2 | `08_kpi_reconciliation`: 1 in May, 1 in June |
| Failed order submissions, replays of the same request | 5% API, 1.5% portal; 1.5% | 75, 14 | `10_ops_order_submissions` |
| Orders corrected after entry | 3.5% manual, 0.6% portal, 0.2% API | | `04_kpi_order_corrections` |

Every count in the "Count" column is printed by the generator and matches the query results in `docs/data/results.json`.
