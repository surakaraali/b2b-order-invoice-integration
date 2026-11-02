# Postman test report

Collection **Vektör Dealer Integration API** run with Newman 6.2.3 against the local sandbox simulator (`simulator/sandbox_simulator.py`, fresh start), environment *Vektör local simulator*. Run on 01 November 2026, 22:34 Türkiye time.

| Measure | Total | Failed |
|---|---|---|
| Test items | 46 | 0 |
| HTTP requests, including those sent by scripts | 122 | 0 |
| Assertions | 232 | 0 |
| Test scripts | 92 | 0 |
| Pre-request scripts | 57 | 0 |
| Run duration | 5.6s | |

Each row is one request of the collection. *Main request* is the request the item itself sends; *extra* counts the requests its scripts send to set up or verify the case, for example the 60 queries before the rate-limit test.

## 00 Setup

| Test | Main request | Status | Time | Assertions | Extra requests |
|---|---|---|---|---|---|
| Setup · Get dealer access token | `POST /oauth2/token` | 200 OK | 20 ms | 2 of 2 passed | 0 |

## 01 Happy path

| Test | Main request | Status | Time | Assertions | Extra requests |
|---|---|---|---|---|---|
| HP-01 · Service health | `GET /v1/health` | 200 OK | 2 ms | 5 of 5 passed | 0 |
| HP-02 · Product catalogue, first page | `GET /v1/products?pageSize=5` | 200 OK | 5 ms | 6 of 6 passed | 0 |
| HP-03 · Product catalogue, last page | `GET /v1/products?pageSize=5&pageToken=eyJvZmZzZXQiOiA1fQ` | 200 OK | 2 ms | 7 of 7 passed | 0 |
| HP-04 · Query sellable stock | `GET /v1/stock?sku=100234,200117` | 200 OK | 1 ms | 7 of 7 passed | 0 |
| HP-05 · Submit an order | `POST /v1/orders` | 202 Accepted | 258 ms | 7 of 7 passed | 0 |
| HP-06 · Read the order | `GET /v1/orders/VO-2026-000201` | 200 OK | 2 ms | 9 of 9 passed | 0 |
| HP-07 · Stock after the reservation | `GET /v1/stock?sku=100234` | 200 OK | 2 ms | 4 of 4 passed | 0 |
| HP-08 · Find the order by dealer order number | `GET /v1/orders?dealerOrderNo=PO-MVY8AJ1Z-HP05` | 200 OK | 3 ms | 5 of 5 passed | 0 |
| HP-09 · Order above the credit limit goes to approval | `POST /v1/orders` | 202 Accepted | 259 ms | 5 of 5 passed | 1 |
| HP-10 · Order with partial stock goes to approval | `POST /v1/orders` | 202 Accepted | 259 ms | 5 of 5 passed | 1 |
| HP-11 · Invoices of the case order | `GET /v1/invoices?orderId=VO-2027-000123` | 200 OK | 2 ms | 5 of 5 passed | 0 |
| HP-12 · Read the invoice notification | `GET /v1/invoices/8f7a9c2e-1b3d-4e5f-9a6b-7c8d9e0f1a2b` | 200 OK | 1 ms | 7 of 7 passed | 0 |
| HP-13 · Acknowledge the invoice match | `POST /v1/invoices/8f7a9c2e-1b3d-4e5f-9a6b-7c8d9e0f1a2b/acknowledge` | 200 OK | 2 ms | 5 of 5 passed | 0 |
| HP-14 · Acknowledge again | `POST /v1/invoices/8f7a9c2e-1b3d-4e5f-9a6b-7c8d9e0f1a2b/acknowledge` | 200 OK | 1 ms | 4 of 4 passed | 0 |
| HP-15 · The case order is closed | `GET /v1/orders/VO-2027-000123` | 200 OK | 1 ms | 6 of 6 passed | 0 |

## 02 Negative tests

| Test | Main request | Status | Time | Assertions | Extra requests |
|---|---|---|---|---|---|
| NT-01 · A1 Request fails validation on two fields | `POST /v1/orders` | 400 Bad Request | 257 ms | 9 of 9 passed | 1 |
| NT-02 · A2 Expired access token | `POST /v1/orders` | 401 Unauthorized | 1 ms | 5 of 5 passed | 0 |
| NT-03 · A3 Suspended dealer | `POST /v1/orders` | 403 Forbidden | 2 ms | 5 of 5 passed | 1 |
| NT-04 · A4 Retry with the same key and body returns the original response | `POST /v1/orders` | 202 Accepted | 2 ms | 5 of 5 passed | 2 |
| NT-05 · A5 Same key with a different body | `POST /v1/orders` | 422 Unprocessable Content | 3 ms | 5 of 5 passed | 1 |
| NT-06 · A6 Dealer order number already used | `POST /v1/orders` | 409 Conflict | 259 ms | 5 of 5 passed | 1 |
| NT-07 · A6 A rejected dealer order number may be reused | `POST /v1/orders` | 202 Accepted | 258 ms | 5 of 5 passed | 2 |
| NT-08 · A7 Two identical requests at the same time | `GET /v1/orders?dealerOrderNo=PO-MVY8AJ1Z-NT08` | 200 OK | 2 ms | 5 of 5 passed | 2 |
| NT-09 · A8 Inactive SKU is rejected by the business rules | `POST /v1/orders` | 202 Accepted | 256 ms | 5 of 5 passed | 1 |
| NT-10 · A8 Quantity below the minimum order quantity | `POST /v1/orders` | 202 Accepted | 259 ms | 4 of 4 passed | 1 |
| NT-11 · A11 More than 200 lines | `POST /v1/orders` | 400 Bad Request | 260 ms | 6 of 6 passed | 0 |
| NT-12 · A11 Body over 256 KB | `POST /v1/orders` | 413 Content Too Large | 2 ms | 5 of 5 passed | 0 |
| NT-13 · F5 Unknown field on a line | `POST /v1/orders` | 400 Bad Request | 258 ms | 6 of 6 passed | 0 |
| NT-14 · A1 Missing Idempotency-Key | `POST /v1/orders` | 400 Bad Request | 2 ms | 5 of 5 passed | 0 |
| NT-15 · A1 Idempotency-Key is not a UUID | `POST /v1/orders` | 400 Bad Request | 1 ms | 5 of 5 passed | 0 |
| NT-16 · B1 Stock rate limit | `GET /v1/stock?sku=200117` | 429 Too Many Requests | 1 ms | 7 of 7 passed | 61 |
| NT-17 · B3 Unknown SKU in a stock query | `GET /v1/stock?sku=100234,999999,200117` | 200 OK | 1 ms | 5 of 5 passed | 0 |
| NT-18 · B1 More than 50 SKUs | `GET /v1/stock?sku=800000,800001,800002,800003,800004,800005,800006,800007,800008,800009,800010,800011,800012,800013,800014,800015,800016,800017,800018,800019,800020,800021,800022,800023,800024,800025,800026,800027,800028,800029,800030,800031,800032,800033,800034,800035,800036,800037,800038,800039,800040,800041,800042,800043,800044,800045,800046,800047,800048,800049,800050` | 400 Bad Request | 1 ms | 6 of 6 passed | 0 |
| NT-19 · Another dealer's order is not visible | `GET /v1/orders/VO-2027-000123` | 403 Forbidden | under 1 ms | 5 of 5 passed | 1 |
| NT-20 · Unknown order id | `GET /v1/orders/VO-2026-999999` | 404 Not Found | 1 ms | 5 of 5 passed | 0 |
| NT-27 · Acknowledge before the invoice is delivered | `POST /v1/invoices/2b6e1f0a-5c3d-4e7f-8a9b-0c1d2e3f4a5b/acknowledge` | 409 Conflict | 1 ms | 5 of 5 passed | 0 |
| NT-28 · Error messages follow Accept-Language | `POST /v1/orders` | 400 Bad Request | 258 ms | 6 of 6 passed | 0 |

## 03 Integrator SOAP

| Test | Main request | Status | Time | Assertions | Extra requests |
|---|---|---|---|---|---|
| S-01 · CheckUser, registered dealer | `POST /kopru/einvoice/v1` | 200 OK | 4 ms | 3 of 3 passed | 0 |
| S-02 · CheckUser, unregistered tax number | `POST /kopru/einvoice/v1` | 200 OK | 2 ms | 3 of 3 passed | 0 |
| S-03 · SendInvoice with a hash that does not match | `POST /kopru/einvoice/v1` | 500 Internal Server Error | 1 ms | 3 of 3 passed | 0 |
| S-04 · SendInvoice | `POST /kopru/einvoice/v1` | 200 OK | 2 ms | 3 of 3 passed | 0 |
| S-05 · SendInvoice again with the same ETTN | `POST /kopru/einvoice/v1` | 500 Internal Server Error | 2 ms | 3 of 3 passed | 0 |
| S-06 · GetInvoiceStatus, first poll | `POST /kopru/einvoice/v1` | 200 OK | 1 ms | 3 of 3 passed | 0 |
| S-07 · GetInvoiceStatus, second poll | `POST /kopru/einvoice/v1` | 200 OK | 1 ms | 3 of 3 passed | 0 |
| S-08 · Wrong integrator credentials | `POST /kopru/einvoice/v1` | 500 Internal Server Error | 1 ms | 3 of 3 passed | 0 |

## Failures

None.
