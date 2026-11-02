# Sprint Plan

## B2B Order, Stock and Invoice Integration

| | |
|---|---|
| **Project** | B2B Order, Stock and Invoice Integration |
| **Document** | Release and sprint plan, version 1.0 |
| **Status** | Draft for review |
| **Author** | Sura Karaali, Business Analyst |
| **Date** | 2 November 2026 |
| **Related documents** | [Product backlog](backlog.md), [01 BRD](../analysis/01_brd.md), [06 NFR](../analysis/06_nfr.md) |

> All companies, people and figures in this document are fictional.

---

## 1. Team and way of working

| Role | Who | Responsibility |
|---|---|---|
| Product owner | Sales Operations Manager | Owns the backlog order, accepts stories, decides scope |
| Business analyst | Sura Karaali | Refines stories and acceptance criteria, keeps the analysis documents current, prepares sprint reviews with the business |
| Scrum master | IT project lead | Runs the events, removes impediments |
| Development team | 3 backend developers, 1 frontend developer, 1 test engineer, 1 integration engineer | Builds, tests and deploys the increment |
| Stakeholders in reviews | Sales support, a sales representative, finance, warehouse, pilot dealers from sprint 4 | Give feedback on the increment |

Sprints last two weeks, Monday to Friday. The team works Monday to Friday; business hours of the service itself are Monday to Saturday (NFR section 2).

| Event | When | Length | Output |
|---|---|---|---|
| Sprint planning | First Monday, 10:00 | 2 hours | Sprint goal, committed stories, task breakdown |
| Daily scrum | Every day, 09:30 | 15 minutes | Plan for the day, impediments |
| Backlog refinement | Every Wednesday, 14:00 | 1 hour | Stories for the next two sprints meet the Definition of Ready |
| Sprint review | Last Friday, 14:00 | 1 hour | Live demo with the Postman collection and the portal, feedback |
| Retrospective | Last Friday, 15:30 | 45 minutes | One or two improvement actions |

## 2. Release plan

The plan runs from the first sprint to the pilot with two dealers, then to go-live for all dealers. It uses a forecast velocity of 25 points for the first sprint, while the team settles, and 28 points after that. The backlog totals 141 points; the plan loads sprints 1 to 5 at 25 to 28 points and keeps sprint 6 light for pilot readiness.

| Sprint | Dates | Goal | Stories | Points | Milestone |
|---|---|---|---|---|---|
| 1 | 16 to 27 November 2026 | A dealer connector can submit a valid order in the sandbox, read it back, and get clear errors for invalid ones | US-01, US-02, US-21, US-27, SP-01, SP-02 | 25 | Sandbox open to the integration team |
| 2 | 30 November to 11 December | Orders are checked by the business rules, approved or routed, stock is reserved; dealers query stock and the catalogue | US-03, US-04, US-05, US-07, US-09, US-10 | 27 | Order and stock API complete in the sandbox |
| 3 | 14 to 25 December | Exceptions reach the representatives and are decided on time; dealers are notified by webhook; orders survive ERP outages | US-06, US-08, US-11, US-12, US-14, US-20 | 28 | Pilot dealers' partners start connector work |
| 4 | 28 December to 8 January 2027 | Shipments are invoiced as e-Fatura through Köprü e-Belge and dealers are told when the invoice arrives | US-13, US-15, US-16, US-17, US-18 | 27 | End-to-end order to invoice in the sandbox |
| 5 | 11 to 22 January | Small dealers can order and follow orders in the portal; dealers can be onboarded; the daily exception report runs | US-19, US-22, US-23, US-24, US-25 | 26 | Portal ready for user testing |
| 6 | 25 January to 5 February | The service is ready for the pilot: monitored, security tested, accepted by the pilot dealers | US-26, US-28, plus pilot acceptance testing and fixes | 8 | Go/no-go for the pilot on 8 February |
| Pilot | 15 February to 2 April | Marmara Teknoloji and Ege Bilişim order through their ERPs; first portal dealers onboarded; fixes from the pilot | Pilot findings, onboarding | | Go-live decision on 26 March |
| Go-live | 5 April 2027 | All dealers can connect; onboarding in waves | | | Start of the 13 weeks analysed in `sql/` |

Sprint 4 has nine working days because of the 1 January holiday. Sprint 6 is deliberately light: pilot acceptance testing with the two dealers, connector support for their partners and fixing what they find will take the rest of the capacity.

## 3. Sprint 1 in detail

**Goal.** A dealer connector can submit a valid order in the sandbox, read it back, and get clear errors for invalid ones.

**Capacity.** Six team members for ten days is 60 person-days; one developer is on leave for two days, so 58 person-days. The first sprint of a new team is forecast at 25 points.

| Story | Points | Tasks |
|---|---|---|
| US-27 Sandbox for dealer connectors | 5 | Provision the sandbox environment; OAuth2 token endpoint with test clients; nightly data reset; publish the OpenAPI file and the Postman collection; run the collection in CI |
| US-01 Submit an order through the API | 5 | `POST /orders` with storage before the `202`; Location header and order number format; token validation; Postman HP-05 and NT-02 green in CI |
| US-02 Validate order requests at the boundary | 8 | Schema validation from the OpenAPI file; field error codes and paths; problem+json responses with Turkish and English messages; size and line limits; NT-01, NT-11 to NT-13 and NT-28 green |
| US-21 Query order status and history | 3 | `GET /orders/{orderId}` and `GET /orders` with filters and paging; dealer isolation; NT-19 and NT-20 green |
| SP-01 Confirm the integrator's real contract | 2 | Request the Köprü e-Belge test account; compare the real WSDL with `api/soap`; list changes for sprint 4 |
| SP-02 Reference connector for Logo and SAP Business One | 2 | Two workshops with the pilot dealers' ERP partners; effort and options; recommendation to the product owner |

**Dependencies.**

- IT provides the sandbox infrastructure and the token service by the first Wednesday.
- Köprü e-Belge issues a test account for SP-01; requested on 9 November.

**Risks.**

| Risk | Effect | Response |
|---|---|---|
| The ERP test environment is not ready for sprint 2 | The business rules in US-04 cannot be tested against real data | IT confirms the read interfaces for products, prices, credit and stock by 27 November; otherwise sprint 2 uses a stubbed ERP and the order changes |
| The pilot dealers' partners are not available for SP-02 | Q1 stays open and connector work starts late | The product owner books the workshops in the first week |

**Review demo.** Submit an order from Postman, read it back, show three validation errors in Turkish and English, show the Swagger page of the sandbox.

## 4. Sprint 2 in detail

**Goal.** Orders are checked by the business rules, approved or routed, stock is reserved; dealers query stock and the catalogue.

**Capacity.** 60 person-days, minus one day of ERP interface training for two developers, so 58 person-days. Forecast 28 points; committed 27.

| Story | Points | Tasks |
|---|---|---|
| US-03 Protect against duplicate submissions | 5 | Idempotency key store with body hash and 7-day retention; in-progress state; duplicate dealer order number check; NT-04 to NT-08, NT-14 and NT-15 green |
| US-04 Run the business rules on accepted orders | 8 | Read catalogue, price list, credit and stock from the ERP; rule evaluation with reason codes; status history with sequence numbers; HP-06, HP-09, HP-10, NT-09 and NT-10 green |
| US-05 Reserve stock on approval | 3 | Reservation call to the ERP with retries; return to PENDING_APPROVAL on failure; HP-07 green |
| US-07 Query sellable stock per warehouse | 5 | `GET /stock` with a 5-minute cache; shipping warehouse flag; unknown and inactive SKUs; HP-04, NT-17 and NT-18 green |
| US-09 Publish the product catalogue with dealer prices | 3 | `GET /products` with paging and `updatedSince`; dealer price list; HP-02 and HP-03 green |
| US-10 Rate limits per dealer | 3 | Sliding one-minute window per dealer and endpoint; rate limit headers; NT-16 green |

**Dependencies.** ERP read interfaces for products, prices, credit and stock, and a reservation call, in the ERP test environment.

**Risks.**

| Risk | Effect | Response |
|---|---|---|
| Credit data in the ERP lags payments (BRD R3) | Good dealers end up in approval | Show the open balance date in the task in sprint 3; finance confirms the refresh frequency (BRD Q4) |
| Rule evaluation is slower than 60 seconds at peak | NFR-PERF-04 missed | Load test with 60 orders a minute at the end of the sprint |

**Review demo.** A clean order becomes ALLOCATED; one order goes to approval for credit and one for stock; a stock query before and after shows the reservation; the rate limit answers 429 on the 61st query.

## 5. Definition of Ready

A story can enter a sprint when:

- It is written as "As a ... I want ... so that ..." and traces to a business requirement or an NFR.
- Its acceptance criteria are Gherkin scenarios that the product owner has read.
- It is estimated by the team and is 8 points or less; larger stories are split.
- Its dependencies are known and either resolved or planned.
- Test data and the Postman or SQL checks that will verify it are named.
- Portal stories have an agreed wireframe.

## 6. Definition of Done

A story is done when:

- The code is reviewed and merged, and unit tests pass.
- The implementation matches the OpenAPI file and the contract tests pass.
- The Postman collection is updated and all of it passes in CI, including the negative tests.
- Response times meet the NFR targets in the sandbox.
- The OpenAPI file, the field mapping and any affected analysis document are updated.
- It is deployed to the sandbox and shown in the sprint review.
- The product owner accepted it, and no critical or major defect is open against it.

## 7. Measures the team tracks

| Measure | Why |
|---|---|
| Velocity per sprint | Re-forecast the release plan after each sprint |
| Sprint burndown | See early when the sprint goal is at risk |
| Postman suite pass rate in CI | Every acceptance criterion with a test stays green |
| Escaped defects found in the pilot | Quality of the Definition of Done |
| Open questions from the analysis documents | Decisions the product owner still owes the team |
