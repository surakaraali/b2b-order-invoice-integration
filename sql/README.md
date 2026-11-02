# Reconciliation and KPI queries

The SQL files in this folder load the [synthetic integration data](../data/README.md) into DuckDB and answer the questions of the case. They produce the daily exception report of UC-09, measure the six BRD goals, and give the operational view the integration team needs. `scripts/run_sql.py` runs them in order and saves every query with its result to `docs/data/results.json` for the report site.

```bash
python3 -m venv .venv
```

```bash
.venv/bin/pip install -r requirements.txt
```

```bash
.venv/bin/python scripts/run_sql.py
```

The CSV files are in the repository. Run `python3 data/generate_data.py` first only to rebuild them.

## Queries

| File | Question | Source |
|---|---|---|
| `00_load.sql` | Load the CSV files into typed tables, with the report time as a parameter | |
| `01_data_quality.sql` | 20 checks on keys, amounts, status sequences, invoices and webhooks; all must pass | |
| `02_daily_exception_report.sql` | What needs action this morning, in five groups | UC-09, BRD 7.6 |
| `03_kpi_channel_adoption.sql` | Share of order lines through the API or the portal, per week | G1 |
| `04_kpi_order_corrections.sql` | Orders corrected after entry, integrated against manual | G2 |
| `05_kpi_decision_time.sql` | Time to the first decision; approvals within 4 business hours | G3, RULE-08 |
| `06_kpi_stock_self_service.sql` | Phone stock questions against API and portal stock queries | G4 |
| `07_kpi_invoice_cycle.sql` | Shipment to the dealer's inbox; webhook within 1 hour | G5 |
| `08_kpi_reconciliation.sql` | Invoices booked with a different total, per month | G6 |
| `09_ops_webhook_delivery.sql` | Delivery at the first attempt, after retries, exhausted | RULE-16 |
| `10_ops_order_submissions.sql` | Order submissions by result and error code | Error scenarios, section 3 |
| `11_ops_invoice_delivery.sql` | How each invoice reached the dealer; legal 7-day limit | UC-06, NFR-COMPL-01 |
| `12_ops_incidents.sql` | Effect of the ERP and integrator incidents; nothing lost | NFR-REL-04, NFR-REL-05 |
| `13_kpi_scorecard.sql` | The six goals over the last four weeks, with status | BRD section 4 |

## Results

All 20 data quality checks pass.

**Scorecard, weeks 10 to 13 (7 June to 3 July 2027)**

| Goal | Result | Status |
|---|---|---|
| G1 Orders through the API or the portal | 74.5% of order lines; 76.3% in week 13, up from 8.5% in week 1 | On the way; the target date is October 2027 |
| G2 Orders corrected after entry | 1.02% overall, 0.28% for integrated orders | Met for integrated orders only |
| G3 Time to first status | 95th percentile 39 seconds; 86.6% of approvals within 4 business hours | Met for automatic decisions; approvals miss the target |
| G4 Stock questions by phone | 29.1 a day, down from about 60 | Not met |
| G5 Invoice in the dealer's inbox | 99.6% on the day of shipment, median 13 minutes | Met |
| G6 Reconciliation mismatches | 1 in June | Met |

**Daily exception report, Monday 5 July 2027, 07:00**

| Group | Items |
|---|---|
| 1 Shipped, invoice not sent | 3 orders without an invoice in the ERP |
| 2 Sent, not delivered within 24 hours | 2 invoices at the integrator |
| 3 Delivered, not acknowledged in 5 working days | 6 invoices |
| 4 Webhook endpoint failing | Dealer D00087, 2 events failed all attempts |
| 5 Shipment confirmation late or missing | 2 carrier pickups not confirmed in the ERP |

**What the results say**

- Integration removes most of the manual work for dealers who are live. The remaining gap in G1 and G4 is the dealers not yet onboarded, mostly small portal dealers, who still order by e-mail and call for stock.
- Corrections fall below the target only for integrated orders; manual entry keeps the overall rate above 0.5%.
- Automatic decisions are fast, but about 15% of approvals miss the 4 business hour due time, credit limit cases more often than stock cases. The escalation works, but the queue needs attention.
- Invoices reach the dealer's inbox within minutes. The three invoices that reached the day-5 legal alert were all late because the warehouse confirmed the shipment days after the carrier pickup, not because of the integration.
- Both incidents delayed work without losing an order or an invoice.

## Interpretations

- **Exception group 1** reads "without an invoice" as "no invoice accepted by the integrator", so held and rejected invoices are listed with their cause.
- **Exception group 3** only covers dealers whose connector acknowledges invoices, because acknowledgement is optional (BR-14).
- **G5 "same day"** is measured from the shipment confirmation to the integrator's delivery report; the status is "met" at 95% or more.
- **G6** counts mismatches reported through acknowledgements. Mismatches of dealers without an acknowledging connector come from finance's reconciliation, which is outside this dataset.
- **The legal 7-day limit** counts from the carrier pickup, when the goods leave Vektör.
