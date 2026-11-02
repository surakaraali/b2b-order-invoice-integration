# Requirements index

> Fictional portfolio case.

Every business requirement of the [BRD](https://github.com/surakaraali/b2b-order-invoice-integration/blob/main/analysis/01_brd.md) with the stories that deliver it and the checks that verify it. Story keys are the backlog ids; after the JIRA import, link them to the JIRA issues.

| Requirement | Summary | Priority | Stories | Use cases | Verified by |
|---|---|---|---|---|---|
| BR-01 | Orders from the dealer's ERP or the portal without re-keying | Must | US-01 | UC-01 | HP-05, NT-02, NT-03 |
| BR-02 | Immediate acknowledgement with an order number | Must | US-01 | UC-01 | HP-05 |
| BR-03 | A duplicate submission never creates a second order | Must | US-03 | UC-01 | NT-04 to NT-08 |
| BR-04 | Automatic validation against catalogue, price list, minimum quantity, credit and stock | Must | US-02, US-04 | UC-01 | NT-01, NT-09, NT-10 |
| BR-05 | Clean orders approved automatically, exceptions to the representative | Must | US-04, US-11, US-12 | UC-01, UC-04 | HP-06, HP-09, HP-10 |
| BR-06 | Dealers informed of every status change | Must | US-20, US-21 | UC-03 | HP-08 |
| BR-07 | Sellable stock per SKU and warehouse | Must | US-07, US-09 | UC-02 | HP-04, NT-17 |
| BR-08 | e-Fatura issued automatically on shipment | Must | US-15, US-17 | UC-05, UC-06 | S-03 to S-07 |
| BR-09 | Invoice notification with the ETTN for automatic matching | Must | US-18 | UC-08 | HP-11, HP-12 |
| BR-10 | Daily reconciliation report | Must | US-25 | UC-09 | sql/02_daily_exception_report.sql |
| BR-11 | Everything available in a portal for dealers without an ERP | Should | US-22, US-23 | UC-01, UC-03 | Sprint review |
| BR-12 | Approval with reduced quantities | Should | US-13 | UC-04 | Sprint review |
| BR-13 | Expected receipt date for unavailable items | Could | US-08 | UC-02 | HP-04 |
| BR-14 | Dealer acknowledgement closes the order | Could | US-19 | UC-08 | HP-13 to HP-15, NT-27 |
| BR-15 | Returns, cancellations, Ticari profile | Won't (this version) | None | None | None |
