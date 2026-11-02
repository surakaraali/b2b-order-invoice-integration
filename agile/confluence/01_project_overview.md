# B2B Order, Stock and Invoice Integration

> Fictional portfolio case. All companies, people and figures are invented.

## Summary

Vektör Elektronik Dağıtım A.Ş. connects about 120 dealers system to system. Dealers' ERPs, or a dealer portal for small dealers, submit orders and query stock through a REST API. Invoices are issued as e-Fatura through the private integrator Köprü e-Belge, and the dealer is notified with the ETTN so it can match the invoice automatically.

## Goals

| Goal | Measure | Baseline | Target |
|---|---|---|---|
| G1 | Order lines through the API or the portal | 0% | At least 80% six months after go-live |
| G2 | Orders corrected after entry | 4% | Below 0.5% |
| G3 | Time to the first order status | About 1 working day | Under 2 minutes; approvals within 4 business hours |
| G4 | Stock questions by phone | About 60 a day | Below 6 a day |
| G5 | Shipment to the dealer booking the invoice | 1.5 working days | Same day |
| G6 | Reconciliation mismatches | About 45 a month | Below 5 a month |

## Scope

In scope: order submission and approval, stock and catalogue queries, e-Fatura issuing and delivery notification, the dealer portal, dealer onboarding and the daily exception report. Out of scope for this version: returns, cancellations after approval and the Ticari invoice profile.

## Timeline

| Milestone | Date |
|---|---|
| Sprint 1 starts | 16 November 2026 |
| End-to-end order to invoice in the sandbox | 8 January 2027 |
| Pilot go/no-go | 8 February 2027 |
| Pilot with Marmara Teknoloji and Ege Bilişim | 15 February to 2 April 2027 |
| Go-live for all dealers | 5 April 2027 |

## Team

Product owner: Sales Operations Manager. Business analyst: Sura Karaali. Scrum master: IT project lead. Development team: three backend developers, one frontend developer, one test engineer, one integration engineer.

## Documents

| Document | Link |
|---|---|
| Business requirements | [01 BRD](https://github.com/surakaraali/b2b-order-invoice-integration/blob/main/analysis/01_brd.md) |
| Process analysis and BPMN | [02 Process analysis](https://github.com/surakaraali/b2b-order-invoice-integration/blob/main/analysis/02_process_as_is_to_be.md) |
| Use cases and UML | [03 Use cases](https://github.com/surakaraali/b2b-order-invoice-integration/blob/main/analysis/03_use_cases.md) |
| Field mapping | [04 Field mapping](https://github.com/surakaraali/b2b-order-invoice-integration/blob/main/analysis/04_field_mapping.md) |
| Error scenarios | [05 Error scenarios](https://github.com/surakaraali/b2b-order-invoice-integration/blob/main/analysis/05_error_scenarios.md) |
| Non-functional requirements | [06 NFR](https://github.com/surakaraali/b2b-order-invoice-integration/blob/main/analysis/06_nfr.md) |
| Dealer API | [OpenAPI specification](https://github.com/surakaraali/b2b-order-invoice-integration/blob/main/api/openapi/vektor-dealer-api.v1.yaml) |
| Integrator contract | [SOAP contract and UBL-TR samples](https://github.com/surakaraali/b2b-order-invoice-integration/blob/main/api/soap/README.md) |
| Tests | [Postman collection and test report](https://github.com/surakaraali/b2b-order-invoice-integration/blob/main/api/postman/README.md) |
| Backlog and plan | [Product backlog](https://github.com/surakaraali/b2b-order-invoice-integration/blob/main/agile/backlog.md), [Sprint plan](https://github.com/surakaraali/b2b-order-invoice-integration/blob/main/agile/sprint_plan.md) |
