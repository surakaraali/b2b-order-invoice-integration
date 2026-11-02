# Decision log

> Fictional portfolio case.

Decisions that shape the solution, with the alternatives that were considered. New decisions are added at the top.

| ID | Date | Decision | Alternatives considered | Rationale | Owner |
|---|---|---|---|---|---|
| D-12 | 2 November 2026 | The legal 7-day invoice limit is counted from the carrier pickup | From the shipment confirmation in the ERP | VUK counts from the delivery of the goods; a late confirmation must not hide a legal risk | Finance, BA |
| D-11 | 29 October 2026 | Integrator calls use WS-Security UsernameToken; invoices travel zipped, base64-encoded, with a SHA-256 hash | Login operation with a session; raw XML in the body | Common pattern of Turkish integrators; the hash proves integrity. To be confirmed by spike SP-01 | Integration team |
| D-10 | 29 October 2026 | Service targets: 99.5% availability in business hours, RPO 1 hour, RTO 4 hours | 99.9% with 24/7 on-call | Fits a mid-size distributor whose dealers order in business hours; revisited if 24/7 ordering appears | IT, product owner |
| D-09 | 29 October 2026 | API version in the path (`/v1`); breaking changes run in parallel for 6 months | Version in a header; no overlap | Easiest for dealer connectors; gives partners time to migrate | Integration team |
| D-08 | 29 October 2026 | Dealers keep the SKU cross-reference; Vektör publishes the catalogue with `GET /products` | Vektör stores every dealer's item codes | Dealers' ERPs already support supplier catalogue numbers; Vektör stays out of their master data | BA, product owner |
| D-07 | 29 October 2026 | Status events carry a per-order `sequence` number | Dealers order events by timestamp | Webhooks can arrive out of order; a sequence makes the rule simple and testable | BA |
| D-06 | 29 October 2026 | `Idempotency-Key` is mandatory on `POST /orders` and kept 7 days | Optional key; duplicate check on the dealer order number only | Retries after timeouts are normal for connectors; duplicates were a known pain in the manual process | Integration team |
| D-05 | 29 October 2026 | Errors follow RFC 9457 problem details with codes, English titles and Turkish messages | A custom error envelope | Standard format, machine-readable codes, readable for dealer staff | BA |
| D-04 | 29 October 2026 | e-Fatura through a private integrator over SOAP, profile Temel in this version | Direct GİB connection; Ticari profile | Standard route for a mid-size company; Ticari adds an accept or reject step, planned for the next version (BRD Q3) | Finance |
| D-03 | 29 October 2026 | Hybrid approval: automatic when credit and stock allow, sales representative otherwise | Fully automatic; always manual | Removes waiting for clean orders while keeping people in charge of exceptions | Product owner |
| D-02 | 28 October 2026 | Version 1 covers order, stock and invoice; returns and cancellations are out | Include returns and cancellations | Delivers the main value first; returns need their own process work | Product owner |
| D-01 | 28 October 2026 | Dealer integration by REST API, with a portal on the same API for dealers without an ERP | Separate portal backend; EDI files | One contract for all channels; modern and simple for connectors | BA, IT |
