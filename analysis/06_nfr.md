# Non-Functional Requirements

## B2B Order, Stock and Invoice Integration

| | |
|---|---|
| **Project** | B2B Order, Stock and Invoice Integration |
| **Document** | Non-functional requirements, version 1.0 |
| **Status** | Approved |
| **Author** | Sura Karaali, Business Analyst |
| **Date** | 29 October 2026 |
| **Related documents** | [01 BRD](01_brd.md), [02 Process analysis](02_process_as_is_to_be.md), [04 Field mapping](04_field_mapping.md), [05 Error scenarios](05_error_scenarios.md) |

> All companies, people and figures in this document are fictional. They were created for this portfolio case and are consistent with the [BRD](01_brd.md). Legal references are to Turkish legislation as commonly applied to e-Invoice and record keeping; they describe the project's assumptions and are not legal advice.

---

## 1. Purpose and how to read

This document states the quality requirements of the integration layer: how available, fast, secure, observable and maintainable it has to be, and what the law requires of it. Every requirement has an id, a measurable target and a verification method, so that it can be tested before go-live and monitored afterwards.

The requirements are grouped by the characteristics of the ISO/IEC 25010 quality model (reliability, performance efficiency, compatibility, usability, security, maintainability, portability), with two added groups that the model does not cover as such: observability, and legal compliance with privacy.

| Column | Meaning |
|---|---|
| ID | `NFR-<group>-<nn>` |
| Requirement | What must hold, as a testable statement |
| Metric and target | How it is measured and the value that passes |
| Verification | How and when it is checked (section 13) |
| Priority | Must, Should, Could |

Targets are set for a mid-size distributor: business hours availability with a staffed support window, not a 24/7 enterprise platform. Section 14 lists where the targets would change if the company or the dealer base grows.

## 2. Context and capacity model

Volumes are derived from the BRD and the process analysis. Year 3 assumes the dealer base grows from 120 to 200 and order volume doubles.

| Measure | Today (as-is) | Go-live, year 1 | Year 3 | Basis |
|---|---|---|---|---|
| Active dealers | 120 | 120 | 200 | BRD section 2.1; growth assumption |
| Orders per working day | 45 | 45 | 90 | BRD |
| Order lines per working day | 350 | 350 | 700 | BRD |
| Stock queries per day | 60 phone calls | About 1,500 API calls | About 4,000 | Connected dealers query before each order and on schedules |
| Order status queries per day | None | About 500 | About 1,500 | Polling by dealers without webhooks, portal views |
| Webhook events per day | None | About 350 | About 700 | About 6 status events per order plus invoice events |
| Invoices per day | 45 | 45 | 90 | One invoice per shipment |
| Integrator calls per day | None | About 600 | About 1,200 | Send, status polls, tax number checks |
| Peak API requests per minute | Not applicable | 30 | 60 | BRD section 11; morning order burst |
| Integration log rows per year | Not applicable | About 1.2 million, about 1.5 GB | About 3 million, about 4 GB | 1 KB per row with masked payload |
| Portal users | None | About 60 | About 80 | Small dealers, 1 to 2 users each |

Business hours are Monday to Saturday, 08:00 to 20:00, Türkiye time (Europe/Istanbul). A month has about 312 business hours.

## 3. Reliability

| ID | Requirement | Metric and target | Verification | Priority |
|---|---|---|---|---|
| NFR-REL-01 | The API and the portal are available during business hours. | Monthly availability of at least 99.5% in business hours, measured by a synthetic check every minute; at most 1.5 hours of unplanned downtime per month. Announced maintenance is excluded. | Monitoring report, monthly | Must |
| NFR-REL-02 | Outside business hours the service runs on a best-effort basis with a maintenance window. | Availability of at least 98% outside business hours. Maintenance window Sunday 02:00 to 06:00, announced 3 business days ahead. | Monitoring report | Should |
| NFR-REL-03 | An accepted order is never lost. | An order is written to the integration database before the `202` response is sent; no `202` is given when the database is unavailable (error scenario A12). | Code review, failover test | Must |
| NFR-REL-04 | ERP outages do not stop order intake or stock answers. | Orders stay `RECEIVED` and are evaluated when the ERP returns (A9); stock is answered from cache for up to 5 minutes (B4). | Failover test with the ERP connection cut | Must |
| NFR-REL-05 | Integrator outages do not lose invoices. | Invoices queue in `MAPPED` for at least 72 hours and are sent when the integrator returns (E4, E5); the legal deadline guard raises an alert at day 5 (NFR-COMPL-01). | Failover test with the integrator sandbox unreachable | Must |
| NFR-REL-06 | Data can be recovered after a failure of the integration database. | Recovery point objective 1 hour (hourly incremental backups, daily full backup); recovery time objective 4 hours in business hours. | Restore drill twice a year | Must |
| NFR-REL-07 | Webhook events survive restarts and are delivered at least once. | Events are persisted before the first delivery attempt; after a restart pending attempts resume on schedule. | Restart test | Must |

## 4. Performance efficiency

| ID | Requirement | Metric and target | Verification | Priority |
|---|---|---|---|---|
| NFR-PERF-01 | Order submission answers quickly. | `POST /orders` p95 under 2 seconds and p99 under 4 seconds at 30 requests per minute, measured from the API gateway; hard timeout 10 seconds. | Load test before go-live, monitoring | Must |
| NFR-PERF-02 | Stock queries answer quickly. | `GET /stock` p95 under 1 second; under 300 milliseconds on a cache hit; hard timeout 5 seconds. | Load test, monitoring | Must |
| NFR-PERF-03 | Read endpoints answer quickly. | `GET /orders`, `GET /orders/{orderId}`, `GET /invoices` p95 under 1 second. | Load test, monitoring | Must |
| NFR-PERF-04 | Business rules complete soon after acceptance. | 95% of orders leave `RECEIVED` within 60 seconds; 100% within 5 minutes when the ERP answers normally. | Monitoring of status timestamps | Must |
| NFR-PERF-05 | Status events reach dealers promptly. | First webhook attempt within 10 seconds of the status change for 95% of events. | Monitoring | Must |
| NFR-PERF-06 | Invoices move without manual delay. | `SendInvoice` called within 15 minutes of shipment confirmation for 95% of invoices; `invoice.issued` sent within 1 hour of `DELIVERED` (BRD goal G5). | Monitoring | Must |
| NFR-PERF-07 | Peaks degrade gracefully. | The platform sustains 60 requests per minute with the targets above and absorbs bursts of 120 requests per minute for 5 minutes by answering `429` with `Retry-After`, never `5xx`. | Load test at 2 times peak | Must |
| NFR-PERF-08 | The portal is responsive. | Portal pages load in under 3 seconds p95 on a 20 Mbit connection; order form validation under 1 second. | Front-end performance test | Should |
| NFR-PERF-09 | The daily report is ready before the working day. | Report for the previous day generated by 07:00; the SQL runs in under 5 minutes. | Monitoring | Should |

## 5. Compatibility

| ID | Requirement | Metric and target | Verification | Priority |
|---|---|---|---|---|
| NFR-COMP-01 | The API is usable from any platform without special libraries. | HTTPS, JSON in UTF-8, OpenAPI 3.1 contract; no proprietary headers beyond `Idempotency-Key`, `X-Request-Id` and the webhook signature headers. | Contract review, Postman run from a clean machine | Must |
| NFR-COMP-02 | Dealer connectors can be built on SAP Business One and Logo with their standard integration tools. | A reference flow is documented for each: SAP Business One Service Layer or the Integration Framework, Logo Objects or the Logo REST service; the Postman collection runs the same calls. | Pilot with Marmara Teknoloji and Ege Bilişim | Should |
| NFR-COMP-03 | Invoices conform to the e-Invoice standard. | UBL-TR 1.2 schema and the current GİB schematron pass locally before sending; the integrator's WSDL version is pinned and changes are tracked. | Validation in CI with sample documents | Must |
| NFR-COMP-04 | The portal works in common browsers. | Latest two major versions of Chrome, Edge, Safari and Firefox; usable at widths down to 1024 pixels. | Browser test matrix | Should |
| NFR-COMP-05 | Time handling is unambiguous. | All timestamps carry an explicit offset; business rules use Europe/Istanbul; dates are calendar dates (field mapping rule T1). | Code review, tests around midnight and daylight time changes | Must |

## 6. Usability (dealer portal)

| ID | Requirement | Metric and target | Verification | Priority |
|---|---|---|---|---|
| NFR-USE-01 | The portal speaks the dealers' language. | All portal text, validation messages and e-mails in Turkish; English can be added later. | Review | Must |
| NFR-USE-02 | Order entry is fast for a trained user. | A 10-line order is entered in under 5 minutes; field errors are shown inline next to the field, with the messages of the error catalogue. | Usability test with 3 small dealers | Should |
| NFR-USE-03 | The portal is accessible. | WCAG 2.1 level AA for forms, tables and navigation: keyboard operation, contrast, labels. | Accessibility audit before go-live | Should |
| NFR-USE-04 | Dealers can connect without hand-holding. | A dealer with the integration guide and the Postman collection completes a successful sandbox order within 1 working day of receiving credentials. | Measured during the pilot | Should |

## 7. Security

| ID | Requirement | Metric and target | Verification | Priority |
|---|---|---|---|---|
| NFR-SEC-01 | Every API call is authenticated with OAuth2 client credentials. | Access tokens valid 60 minutes; one client per dealer; client secrets rotated at least yearly and on demand; secrets never appear in URLs or logs. | Pen test, log review | Must |
| NFR-SEC-02 | Traffic is encrypted in transit. | TLS 1.2 or higher, TLS 1.3 preferred, HSTS on the API and the portal; webhooks are sent only to HTTPS URLs with valid certificates. | TLS scan | Must |
| NFR-SEC-03 | Webhooks are authentic and cannot be replayed. | Each delivery carries `X-Signature` (HMAC-SHA256 of the body with a per-dealer secret) and `X-Timestamp`; dealers are instructed to reject deliveries older than 5 minutes; secrets rotatable from the onboarding screen. | Contract test, dealer guide | Must |
| NFR-SEC-04 | A dealer sees only its own data. | Every query is filtered by the dealer of the token; cross-dealer access returns `403 FORBIDDEN_RESOURCE` (negative test NT-19). | Automated test, pen test | Must |
| NFR-SEC-05 | Input is validated and bounded. | Field validation per the field mapping, unknown fields rejected, body limit 256 KB, rate limits per the error scenarios; SQL access parameterised; XML external entities disabled when parsing integrator responses. | Code review, pen test | Must |
| NFR-SEC-06 | Secrets are managed centrally. | Integrator credentials, signing material and dealer secrets live in a secrets vault; none in source code, configuration files or tickets. | Repository scan, review | Must |
| NFR-SEC-07 | Writes are attributable. | Every status change, approval decision, invoice send and configuration change records the actor (system, user id or dealer client), the time and the before and after values. | Audit log review | Must |
| NFR-SEC-08 | The platform is tested against common API weaknesses. | OWASP API Security Top 10 review and an external penetration test before go-live and yearly; high and critical findings closed before go-live. | Pen test report | Must |
| NFR-SEC-09 | The integration service has the least ERP privilege it needs. | A dedicated ERP account with read access to products, prices, stock and credit data and write access only to reservations and invoice creation. | ERP role review | Must |
| NFR-SEC-10 | Dealers can restrict traffic sources. | Vektör publishes the source IP range of webhooks; dealers may register an IP allowlist for their API client. | Onboarding checklist | Could |
| NFR-SEC-11 | Portal accounts are protected. | Password policy, session timeout of 30 minutes, account lock after 5 failed attempts, one-time code by e-mail as a second factor. | Review | Should |

## 8. Maintainability and API versioning

| ID | Requirement | Metric and target | Verification | Priority |
|---|---|---|---|---|
| NFR-MAIN-01 | The API is contract-first. | The OpenAPI file is the source of truth; the implementation is validated against it in CI; the Postman collection, including the 28 negative tests, runs on every change. | CI pipeline | Must |
| NFR-MAIN-02 | The API is versioned in the path. | Version `v1` in the path (`/v1/orders`); the version changes only for breaking changes. | Contract review | Must |
| NFR-MAIN-03 | Compatible changes do not break dealers. | Adding optional request fields, response fields, new endpoints and new enumeration values are compatible changes; dealers are required by the integration guide to ignore unknown response fields and to handle unknown enumeration values as "other". | Dealer guide, contract tests | Must |
| NFR-MAIN-04 | Breaking changes are announced and overlapped. | A new major version runs in parallel with the old one for at least 6 months; the old version answers with a `Sunset` header and a `Deprecation` header; dealers are notified by e-mail and in the changelog at least 6 months before shutdown. | Release checklist | Must |
| NFR-MAIN-05 | Operational parameters change without a release. | Rate limits, retry schedules, timeouts and alert thresholds are configuration, changeable by the integration team with an audit record. | Review | Should |
| NFR-MAIN-06 | Documentation stays with the code. | Changelog, runbooks and the dealer integration guide are versioned with the OpenAPI file; every release updates them. | Release checklist | Should |
| NFR-MAIN-07 | UBL samples are regression tested. | Sample invoices for each VAT rate and for discounts are validated against the schema and schematron in CI. | CI pipeline | Should |

## 9. Portability and environments

| ID | Requirement | Metric and target | Verification | Priority |
|---|---|---|---|---|
| NFR-PORT-01 | Three environments with the same contract. | Sandbox (dealer-facing, test ERP data, integrator test environment), staging (pre-production copy), production. | Environment review | Must |
| NFR-PORT-02 | The sandbox is safe and self-service. | Test dealer accounts and test SKUs; data reset nightly; sandbox invoices go only to the integrator's test environment, never to GİB production; `202` responses and webhooks behave as in production. | Sandbox test | Must |
| NFR-PORT-03 | Deployments do not interrupt dealers. | Deployments in business hours are zero-downtime; otherwise in the maintenance window; rollback within 30 minutes. | Deployment drill | Should |
| NFR-PORT-04 | The platform is not tied to one host. | The integration layer runs in containers with externalised configuration; moving between on-premise and cloud hosting needs no code change (open point N1). | Architecture review | Could |

## 10. Observability and logging

| ID | Requirement | Metric and target | Verification | Priority |
|---|---|---|---|---|
| NFR-OBS-01 | Every request can be traced end to end. | `X-Request-Id` on every request and response, generated if absent, propagated to ERP calls, integrator calls and the related webhook `eventId`. | Log review | Must |
| NFR-OBS-02 | The integration log captures what support needs. | Per call: timestamp, flow, direction, dealer, request id, endpoint or operation, result code, latency, payload size; request and response payloads kept 90 days with personal data masked. | Schema review | Must |
| NFR-OBS-03 | Dashboards show the health of each flow. | Request rate, error rate and p95 latency per endpoint; orders by status and age; invoices by state and age; webhook delivery success; integrator response time. | Dashboard review (Kibana or equivalent) | Must |
| NFR-OBS-04 | Problems are detected before dealers call. | Alerts as defined in the error scenarios, section 7; a health endpoint checked every minute from outside the network. | Alert test | Must |
| NFR-OBS-05 | Logs are kept long enough to investigate. | Application and integration logs searchable for 12 months, archived for 24 months; events linked to an invoice are kept with the invoice record for the invoice retention period (NFR-COMPL-02). | Retention configuration review | Must |
| NFR-OBS-06 | Personal data is masked in logs. | Contact names and phone numbers masked; tax numbers and company names are business identifiers and are kept. | Log review | Must |

## 11. Legal compliance and privacy

| ID | Requirement | Metric and target | Verification | Priority |
|---|---|---|---|---|
| NFR-COMPL-01 | Invoices are issued within the legal deadline. | Under the Tax Procedure Law (VUK, article 231/5) an invoice must be issued within 7 days of delivery; the integration raises `INV_LEGAL_DEADLINE_RISK` on day 5 after shipment for any invoice not yet `DELIVERED` (error scenario E8). | Alert test, finance review | Must |
| NFR-COMPL-02 | Invoices and related records are retained as required. | e-Invoice documents, their delivery receipts and the related integration events are retained for 10 years, the longer of the Turkish Commercial Code (TTK, article 82) and the Tax Procedure Law (VUK, article 253) periods, in the integrator's archive and in Vektör's own archive. | Retention configuration, archive test | Must |
| NFR-COMPL-03 | e-Invoice format and delivery follow GİB rules. | UBL-TR 1.2, GİB schematron, delivery only through a GİB-certified private integrator; the "Temel" profile in this version. | Validation in CI, integrator contract | Must |
| NFR-COMPL-04 | Personal data is minimised and lawfully processed (KVKK, Law 6698). | Only contact name and phone for deliveries are processed; purpose and retention are stated in the dealer agreement and the portal privacy notice; the integrator and the hosting provider are bound as data processors; access to personal data is logged. | Privacy review, agreements | Must |
| NFR-COMPL-05 | Portal users are informed. | A privacy notice (aydınlatma metni) is shown at first login; cookie use limited to session cookies. | Review | Must |
| NFR-COMPL-06 | Scope limits are explicit. | Only registered e-Invoice taxpayers are served; e-Arşiv invoices and individual customers (TCKN) are out of scope and rejected at onboarding. | Onboarding checklist | Must |

## 12. Operations and support

| ID | Requirement | Metric and target | Verification | Priority |
|---|---|---|---|---|
| NFR-OPS-01 | Support is staffed in business hours. | Monday to Saturday 08:00 to 20:00; response targets P1 15 minutes, P2 1 hour, P3 next business day; outside hours a P1 phone line with best-effort 1 hour response. | Support rota | Must |
| NFR-OPS-02 | Dealers are kept informed. | Incident acknowledgement to affected dealers within 1 business hour; maintenance announced 3 business days ahead; contract changes 10 business days ahead. | Communication log | Must |
| NFR-OPS-03 | Every alert has a runbook. | A runbook per alert in the error scenarios, section 7, reviewed quarterly. | Runbook review | Must |
| NFR-OPS-04 | Capacity is reviewed. | Quarterly review of volumes against the capacity model; thresholds raised before 70% of capacity is reached. | Review record | Should |
| NFR-OPS-05 | Onboarding is repeatable. | A checklist per dealer: credentials, price list, warehouse, credit limit, tax data, webhook URL, sandbox test, go-live; target 5 working days from agreement to production. | Checklist, pilot measurement | Should |

## 13. Verification matrix

| Verification | What it covers | When | Owner |
|---|---|---|---|
| Load test at 2 times peak | NFR-PERF-01 to 07 | Before go-live, after major changes | Integration team |
| Failover tests (database, ERP, integrator cut) | NFR-REL-03 to 05, 07 | Before go-live, yearly | Integration team |
| Restore drill | NFR-REL-06 | Twice a year | IT operations |
| External penetration test and OWASP review | NFR-SEC-01 to 09 | Before go-live, yearly | External tester, IT |
| Contract tests and Postman regression in CI | NFR-MAIN-01 to 03, 07, NFR-COMP-01, 03 | Every change | Integration team |
| Pilot with two dealers | NFR-COMP-02, NFR-USE-04, NFR-OPS-05 | Pilot phase | Sales support, IT |
| Usability test and accessibility audit | NFR-USE-02, 03 | Before go-live | Product owner, external auditor |
| Monitoring and alert tests | NFR-OBS-01 to 06, NFR-COMPL-01 | Before go-live, after changes | Integration team |
| Compliance and privacy review | NFR-COMPL-02 to 06 | Before go-live, yearly | Finance, legal advisor |
| Environment and deployment review | NFR-PORT-01 to 04 | Before go-live | IT operations |

## 14. Where the targets would change

| Trigger | Change |
|---|---|
| Dealers ordering outside business hours become common (for example e-commerce dealers) | Availability target extended to 24/7 with 99.9% and an on-call rota; RTO reduced to 1 hour |
| Dealer count above 300 or order volume above 200 per day | Capacity model revised; rate limits per dealer reviewed; database sizing and archiving plan updated |
| "Ticari" invoice profile adopted | Response handling (accept or reject within 8 days) added to the invoice flow, retention and alerting updated |
| Cloud hosting chosen (open point N1) | Backup, DR and data residency requirements restated for the provider |

## 15. Open points

| ID | Point | Owner | Needed by |
|---|---|---|---|
| N1 | Hosting: on-premise next to the ERP, or cloud? Decides backup, DR and network design. | IT | Architecture |
| N2 | Does Köprü e-Belge provide a test environment that dealers can also use, so that the sandbox covers the invoice flow end to end? | Integration team | Sandbox design |
| N3 | Is a second factor for portal users acceptable to small dealers, or does it hurt adoption? | Sales Operations | Portal design |
| N4 | Who signs off the KVKK texts and the data processing agreements? | Legal advisor, finance | Before pilot |
| N5 | Is a status page for dealers wanted, or is e-mail notification enough? | Sales Operations | Go-live |
