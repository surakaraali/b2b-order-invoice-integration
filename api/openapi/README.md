# OpenAPI specification

`vektor-dealer-api.v1.yaml` is the dealer-facing contract of the Vektör integration layer (OpenAPI 3.1, version 1.0.0). It is derived from the analysis documents: field names and limits from the [field mapping](../../analysis/04_field_mapping.md), error codes and the RFC 9457 format from the [error scenarios](../../analysis/05_error_scenarios.md), versioning and rate limits from the [non-functional requirements](../../analysis/06_nfr.md).

| Area | Content |
|---|---|
| Endpoints | `POST /orders`, `GET /orders`, `GET /orders/{orderId}`, `GET /stock`, `GET /products`, `GET /invoices`, `GET /invoices/{ettn}`, `POST /invoices/{ettn}/acknowledge`, `GET /health` |
| Webhooks | `orderStatusChanged`, `invoiceIssued`, with `X-Event-Id`, `X-Signature` and `X-Timestamp` headers |
| Security | OAuth2 client credentials, one client per dealer, scoped |
| Errors | `application/problem+json`, codes as enumerations |

To view it, open the file in [Swagger Editor](https://editor.swagger.io/) or import it into Postman. The Postman collection in `../postman/` is generated from this file and adds the negative tests of the error scenarios.
