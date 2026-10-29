# B2B Order, Stock and Invoice Integration Analysis

**Live site: coming soon** (GitHub Pages, served from `docs/`)

By **Sura Karaali**, [LinkedIn](https://www.linkedin.com/in/surakaraali/)

A business and technical analysis of a B2B integration between an electronics distributor and the ERP systems of its dealers. It answers the question an integration team asks before building anything: **what has to flow between the systems, in which format, under which rules, and how do we know it worked?**

The project is a complete analysis package, not an implementation: requirements, process models, UML, an API specification, a Postman test collection, field mappings, error handling rules, reconciliation SQL and an Agile backlog. Everything is presented on a one-page report site, available in **English and Turkish**.

---

## Scope

Three flows are in scope for this version:

| Flow | Direction | Protocol | Standard |
|---|---|---|---|
| Order | Dealer ERP → Distributor | REST | OpenAPI 3 |
| Stock inquiry | Dealer ERP → Distributor | REST | OpenAPI 3 |
| Invoice | Distributor → e-Invoice integrator → Dealer | SOAP | UBL-TR (GİB e-Fatura) |

Returns and cancellations are out of scope for this version.

## Deliverables

| Deliverable | Where | Status |
|---|---|---|
| Business requirements document (BRD) | `analysis/01_brd.md` | Done |
| As-is / to-be process analysis with BPMN | `analysis/02_process_as_is_to_be.md`, `diagrams/bpmn/` | Done |
| Use cases and UML (use case, sequence, state) | `analysis/03_use_cases.md`, `diagrams/uml/` | Done |
| Field mapping: dealer ERP ↔ distributor API ↔ UBL-TR | `analysis/04_field_mapping.md`, `analysis/04_field_mapping.xlsx` | Done |
| Error, retry and idempotency scenarios | `analysis/05_error_scenarios.md` | Done |
| Non-functional requirements (SLA, security, performance) | `analysis/06_nfr.md` | Done |
| OpenAPI specification for the dealer API (orders, stock, products, invoices, webhooks) | `api/openapi/vektor-dealer-api.v1.yaml` | Done |
| e-Invoice SOAP contract and sample UBL-TR messages | `api/soap/` | Planned |
| Postman collection with tests | `api/postman/` | Planned |
| Reconciliation SQL on synthetic integration data (DuckDB) | `sql/`, `scripts/` | Planned |
| Product backlog, sprint plan, JIRA and Confluence screenshots | `agile/` | Planned |
| Dealer portal wireframes (Figma) | `design/wireframes/` | Planned |
| One-page report site (EN/TR) | `docs/` | Planned |

## How it works

- **Documents** are Markdown files under `analysis/`, written in the order a real project would produce them.
- **Diagrams**: UML diagrams are Mermaid text files under `diagrams/uml/`, rendered directly by GitHub. BPMN diagrams are draw.io files under `diagrams/bpmn/` with PNG exports.
- **API contracts**: the REST side is an OpenAPI 3 file under `api/openapi/`; the SOAP side is a WSDL with sample UBL-TR XML under `api/soap/`. The Postman collection under `api/postman/` exercises both.
- **SQL**: `sql/` builds a small synthetic dataset of orders, invoices and integration logs, then runs reconciliation queries. `scripts/run_sql.py` executes them with DuckDB and writes the results as JSON into `docs/data/` for the site. No build step.
- **Site**: `docs/` is plain HTML, CSS and JavaScript with Chart.js, the same approach as the [Telco Customer Churn Analysis](https://github.com/surakaraali/telco-churn-analysis) project.

## Repository layout

```
b2b-order-invoice-integration/
├── README.md
├── docs/                 # report site (GitHub Pages)
│   ├── assets/           # diagram exports, screenshots
│   └── data/             # JSON written by scripts/run_sql.py
├── analysis/             # BRD, process, use cases, mapping, errors, NFR
├── diagrams/
│   ├── bpmn/             # .drawio + .png
│   └── uml/              # .mmd (Mermaid)
├── api/
│   ├── openapi/          # order and stock API (OpenAPI 3)
│   ├── soap/             # e-Invoice WSDL + sample UBL-TR XML
│   └── postman/          # collection + environment
├── sql/                  # schema, seed, reconciliation queries
├── scripts/              # run_sql.py (DuckDB → docs/data)
├── agile/                # backlog, sprint plan, screenshots
└── design/
    └── wireframes/       # Figma exports + link
```

## Status

Started October 2026. Work in progress. The deliverables table above is updated as each piece is completed.
