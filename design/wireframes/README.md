# Dealer portal wireframes

Low-fidelity wireframes for the dealer portal and for the sales representative's approval screen. They support the portal stories US-22 and US-23 and the approval stories US-11 and US-12 of the [product backlog](../../agile/backlog.md), and satisfy the Definition of Ready rule that portal stories have an agreed wireframe.

The portal is for small dealers without an ERP, and its text is Turkish (NFR-USE-01), so the screens are in Turkish. Data on the screens is fictional and consistent with the rest of the case: prices from the catalogue, the 20% VAT rate, the order statuses and the reason codes of the API.

| Screen | What it shows | Stories and rules |
|---|---|---|
| `01_order_entry` | Product search with sellable stock and expected receipts, a cart with an inline validation error, totals from the price list | US-22, US-07, RULE-03, RULE-04, error code QUANTITY_NOT_INTEGER |
| `02_order_list` | Orders with status badges and reasons, filters by status, date and dealer order number | US-23, US-21 |
| `03_order_detail` | Lines with requested and approved quantities, totals, status history with sequence numbers, shipment data | US-23, US-21, US-05 |
| `04_invoices` | Delivered invoices with ETTN and order numbers, invoice detail, acknowledge and report-a-difference actions | US-23, US-18, US-19 |
| `05_approval_task` | The representative's queue with due times and an escalated task, credit and stock facts, decision buttons and reason codes | US-11, US-12, US-13, US-14, RULE-08 |

## Files

Each screen is available in three formats:

| Format | Use |
|---|---|
| `.drawio` | Source; open and edit in draw.io or at app.diagrams.net |
| `.png` | For documents and the report site |
| `.svg` | With plain text layers, so it can be imported into Figma and edited there |

To continue in Figma, create a file, drag the SVG files onto the canvas, and turn the repeated elements (top bar, buttons, badges, table rows) into components.
