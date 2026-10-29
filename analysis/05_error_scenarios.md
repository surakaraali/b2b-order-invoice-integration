# Error, Retry and Idempotency Scenarios

## B2B Order, Stock and Invoice Integration

| | |
|---|---|
| **Project** | B2B Order, Stock and Invoice Integration |
| **Document** | Error, retry and idempotency scenarios, version 1.0 |
| **Status** | Approved |
| **Author** | Sura Karaali, Business Analyst |
| **Date** | 29 October 2026 |
| **Related documents** | [01 BRD](01_brd.md), [03 Use cases](03_use_cases.md), [04 Field mapping](04_field_mapping.md), [06 Non-functional requirements](06_nfr.md), API specification in `api/openapi/`, Postman collection in `api/postman/` |

> All companies, people and figures in this document are fictional. They were created for this portfolio case and are consistent with the [BRD](01_brd.md).

---

## 1. Purpose and principles

This document lists what can go wrong in the three flows and what the systems and the people do about it. It consolidates the exception flows of the [use cases](03_use_cases.md), the validation rules of the [field mapping](04_field_mapping.md) and the business rules of the [BRD](01_brd.md) into one error code catalogue, one scenario catalogue and one list of negative tests. The OpenAPI error responses and the Postman tests are written from these tables.

**Principles**

| # | Principle | What it means in practice |
|---|---|---|
| P1 | Fail fast at the boundary | Schema and format problems are answered immediately with `400` and a list of field errors; nothing is stored |
| P2 | Every write is idempotent | Repeating a request never creates a second order, a second invoice or a second event; the caller can always retry safely |
| P3 | No silent loss | An event or an invoice that cannot be delivered is kept, retried on a schedule and, when retries are exhausted, listed in the daily report with an owner |
| P4 | Every failure has a human owner | Each error code names who fixes it: the dealer, sales support, the integration team or finance |
| P5 | The dealer always gets a code | Errors are machine-readable codes plus a message; the dealer connector decides on the code, never on the text |
| P6 | Retries back off | Retries use increasing delays and a fixed maximum; after that a person takes over |
| P7 | Legal deadlines are hard stops | An invoice must be issued within 7 days of delivery under Turkish tax rules; a held invoice is escalated before that limit |

## 2. Error response format

API errors use RFC 9457 Problem Details, media type `application/problem+json`, with three extension members: `code`, `requestId` and `errors`. `title` is always English; `detail` and `errors[].message` follow the `Accept-Language` header (`tr` by default, `en` on request).

```json
{
  "type": "https://api.vektor-elektronik.example/problems/validation-failed",
  "title": "Validation failed",
  "status": 400,
  "detail": "İstek 2 alanda doğrulamadan geçemedi.",
  "instance": "/orders",
  "code": "VALIDATION_FAILED",
  "requestId": "req_01J9X4M3Q8",
  "timestamp": "2027-03-05T14:21:07+03:00",
  "errors": [
    { "code": "FIELD_REQUIRED", "field": "deliveryAddress.city", "message": "city alanı zorunludur." },
    { "code": "QUANTITY_NOT_INTEGER", "field": "lines[2].quantity", "message": "Adet birimi için miktar tam sayı olmalıdır." }
  ]
}
```

| Member | Rule |
|---|---|
| `type` | Stable URI per code; the URI documents the code and does not have to resolve |
| `title` | Short English summary, fixed per code |
| `status` | Same as the HTTP status |
| `detail` | Human-readable explanation in the requested language |
| `instance` | Request path |
| `code` | Catalogue code from section 3, upper case |
| `requestId` | Correlation id, also returned in the `X-Request-Id` header on every response; quote it in support tickets |
| `timestamp` | Server time with offset |
| `errors[]` | Only for `VALIDATION_FAILED`; one entry per field problem with the field path in JSON Pointer-like notation |
| `Retry-After` | Header on `429` and `503`, seconds |

## 3. Error code catalogue

### 3.1 API errors

| Code | HTTP | Title (EN) | Message (TR) | When | Fixed by | Retry |
|---|---|---|---|---|---|---|
| `UNAUTHORIZED` | 401 | Unauthorized | Erişim belirteci eksik, geçersiz veya süresi dolmuş. | Missing or expired OAuth2 token | Dealer system, refresh the token | After a new token |
| `DEALER_SUSPENDED` | 403 | Dealer suspended | Bayi hesabı askıya alınmış; satış destek ile iletişime geçin. | Dealer not active (RULE-01) | Sales support | No |
| `DEALER_MISMATCH` | 403 | Dealer mismatch | dealerCode, kimlik bilgilerinizle eşleşmiyor. | Body `dealerCode` differs from the token's dealer | Dealer connector configuration | No |
| `FORBIDDEN_RESOURCE` | 403 | Access denied | Bu kayda erişim yetkiniz yok. | Order or invoice belongs to another dealer | None, expected | No |
| `NOT_FOUND` | 404 | Not found | Kayıt bulunamadı. | Unknown `orderId` or `ettn` | Dealer, check the id | No |
| `VALIDATION_FAILED` | 400 | Validation failed | İstek doğrulamadan geçemedi. | Any field error; details in `errors[]` (section 3.2) | Dealer | After correction |
| `MISSING_IDEMPOTENCY_KEY` | 400 | Idempotency key missing | Idempotency-Key başlığı zorunludur. | Header absent on `POST /orders` | Dealer connector | After correction |
| `INVALID_IDEMPOTENCY_KEY` | 400 | Idempotency key invalid | Idempotency-Key geçerli bir UUID değil. | Not a UUID (rule T10) | Dealer connector | After correction |
| `IDEMPOTENCY_KEY_REUSED` | 422 | Idempotency key reused | Idempotency-Key daha önce farklı bir istekle kullanılmış. | Same key, different body hash within 7 days | Dealer connector, new key | With a new key |
| `REQUEST_IN_PROGRESS` | 409 | Request in progress | Aynı istek işlenmekte; Retry-After süresi sonra tekrar deneyin. | Same key while the first request is still being processed | None | After `Retry-After` (2 s) |
| `DUPLICATE_DEALER_ORDER_NO` | 409 | Dealer order number already used | Bu bayi sipariş numarası daha önce gönderilmiş. | Existing order with the same `dealerOrderNo` that is not `REJECTED` | Dealer, check the earlier order | No |
| `INVALID_STATE` | 409 | Invalid state | İşlem, kaydın mevcut durumunda yapılamaz. | For example acknowledge on an order that is not `INVOICED` | Dealer | No |
| `PAYLOAD_TOO_LARGE` | 413 | Payload too large | İstek gövdesi 256 KB sınırını aşıyor. | Body over the limit | Dealer, split the order | After correction |
| `UNSUPPORTED_MEDIA_TYPE` | 415 | Unsupported media type | Content-Type application/json olmalıdır. | Wrong content type | Dealer connector | After correction |
| `RATE_LIMIT_EXCEEDED` | 429 | Rate limit exceeded | İstek limiti aşıldı; Retry-After süresi sonra tekrar deneyin. | Per-dealer limit reached (RULE-11, section 6) | None | After `Retry-After` |
| `INTERNAL_ERROR` | 500 | Internal error | Beklenmeyen bir hata oluştu; requestId ile destek ekibine başvurun. | Unhandled failure; logged with `requestId` and alerted | Integration team | Once, then report |
| `SERVICE_UNAVAILABLE` | 503 | Service unavailable | Servis geçici olarak kullanılamıyor; Retry-After süresi sonra tekrar deneyin. | ERP or integration database unreachable, or maintenance | Integration team | After `Retry-After` |

### 3.2 Field validation errors (inside `VALIDATION_FAILED`)

| Code | Message (TR) | Rule |
|---|---|---|
| `FIELD_REQUIRED` | {field} alanı zorunludur. | Mandatory field missing or empty |
| `FIELD_TOO_LONG` | {field} alanı en fazla {max} karakter olabilir. | Length over the maximum (rule T4) |
| `INVALID_FORMAT` | {field} alanı beklenen biçimde değil. | Pattern or type mismatch, for example postal code, phone, country code |
| `INVALID_DATE` | {field} geçerli bir tarih değil. | Not `YYYY-MM-DD` or not a real date |
| `DATE_OUT_OF_RANGE` | {field} izin verilen aralığın dışında. | `orderDate` in the future or older than 30 days; delivery date before order date |
| `NO_LINES` | Sipariş en az bir satır içermelidir. | Empty `lines` |
| `TOO_MANY_LINES` | Sipariş en fazla 200 satır içerebilir. | Over the limit |
| `DUPLICATE_LINE_SKU` | {sku} birden fazla satırda tekrar ediyor. | Same SKU twice |
| `QUANTITY_NOT_POSITIVE` | Miktar sıfırdan büyük olmalıdır. | Zero or negative |
| `QUANTITY_NOT_INTEGER` | Adet birimi için miktar tam sayı olmalıdır. | Fractional quantity for `C62` or `SET` (rule T2) |
| `INVALID_UNIT` | {unit} birimi tanınmıyor veya ürünün satış birimiyle uyuşmuyor. | Unit not in the code list or not the SKU's unit (rule T11) |
| `INVALID_CITY` | {city} geçerli bir il değil. | Not one of the 81 provinces |
| `INVALID_COUNTRY` | Bu sürümde yalnızca TR desteklenir. | Country other than `TR` |
| `INVALID_ADDRESS_CODE` | {addressCode} bu bayi için tanımlı değil. | Unknown saved address |
| `TOO_MANY_SKUS` | Stok sorgusu en fazla 50 SKU içerebilir. | `GET /stock` over the limit |
| `UNKNOWN_FIELD` | {field} tanınmayan bir alan. | Field not in the schema; rejected to catch connector mistakes early |

### 3.3 Order reason codes delivered in events

These are not HTTP errors. The order was accepted with `202` and the outcome arrives in the `order.status.changed` event (field mapping section 8.2): `INVALID_SKU`, `BELOW_MOQ`, `CREDIT_LIMIT`, `PARTIAL_STOCK`, `CREDIT_LIMIT_REJECTED`, `STOCK_UNAVAILABLE`, `REMOVED_BY_REPRESENTATIVE`, `OTHER`.

### 3.4 Webhook delivery results (integration log)

| Code | Meaning | Effect |
|---|---|---|
| `DELIVERED` | Dealer answered `2xx` within 10 seconds | Done |
| `WEBHOOK_TIMEOUT` | No answer within 10 seconds | Next attempt scheduled |
| `WEBHOOK_REJECTED` | Dealer answered `4xx` or `5xx` | Next attempt scheduled; `410 Gone` stops retries and flags the dealer immediately |
| `WEBHOOK_UNREACHABLE` | DNS, connection or TLS failure | Next attempt scheduled |
| `WEBHOOK_EXHAUSTED` | Fifth attempt failed | Dealer flagged as webhook failing; daily report; event stays available by query |

### 3.5 Invoice flow errors (integration log and alerts)

| Code | Meaning | Invoice state | Owner |
|---|---|---|---|
| `INV_VALIDATION_FAILED` | UBL-TR schema or business rule check failed locally | `SEND_FAILED` | Integration team |
| `INV_VKN_NOT_REGISTERED` | Dealer tax number not on the GİB registered-user list | `HELD` | Sales support |
| `INV_SOAP_FAULT` | Integrator returned a SOAP fault or an application error on `SendInvoice` | `SEND_FAILED` | Integration team |
| `INV_INTEGRATOR_UNREACHABLE` | Connection or timeout to the integrator | `MAPPED` (queued) | Integration team if it persists |
| `INV_INTEGRATOR_AUTH_FAILED` | Integrator rejected Vektör's credentials | `MAPPED` (queued) | Integration team, priority 1 |
| `INV_DUPLICATE_ETTN` | Integrator already holds this ETTN | Treated as accepted; polling continues | None |
| `INV_STATUS_ERROR` | Integrator or GİB reported `ERROR`, with the integrator's reason text | `ERROR` | Integration team, finance for content errors |
| `INV_STATUS_TIMEOUT` | No final status 24 hours after sending | `AT_INTEGRATOR` | Integration team |
| `INV_LEGAL_DEADLINE_RISK` | Invoice not delivered 5 days after shipment | Any non-final | Finance, escalation |

## 4. Scenario catalogue

Columns: trigger, how it is detected, what the system does, who is told, retry and idempotency behaviour, how it is recovered, and the state afterwards. Scenario ids are reused in the test list (section 8).

### 4.1 Order submission

| ID | Scenario | Detection | System response | Notified | Retry and idempotency | Recovery | State afterwards |
|---|---|---|---|---|---|---|---|
| A1 | Request fails schema validation | API validation | `400 VALIDATION_FAILED` with `errors[]`; nothing stored | Dealer, in the response | Dealer corrects and resubmits with a new key | None needed | No order |
| A2 | Access token expired | Token check | `401 UNAUTHORIZED` | Dealer connector | Connector refreshes the token and retries the same request with the same key | None | No order |
| A3 | Dealer suspended | Dealer master | `403 DEALER_SUSPENDED` | Dealer; sales support sees the attempt in the log | No retry | Sales support reactivates the dealer | No order |
| A4 | Connector retries after a network timeout: same key, same body | Key store | Original response returned, no second order (RULE-10) | Dealer | Safe to retry up to 3 times | None | One order |
| A5 | Same key, different body | Body hash differs | `422 IDEMPOTENCY_KEY_REUSED` | Dealer | New key required | Connector bug: keys must be generated per submission | No new order |
| A6 | Same `dealerOrderNo` with a new key | Open order with that number exists | `409 DUPLICATE_DEALER_ORDER_NO` | Dealer | No retry | Dealer checks the earlier order; a `REJECTED` order may be resubmitted with the same number | No new order |
| A7 | Two identical requests at the same time | Key locked by the first | `409 REQUEST_IN_PROGRESS`, `Retry-After: 2` | Dealer | Retry after 2 seconds receives the original response | None | One order |
| A8 | SKU invalid or quantity below the minimum | Business rules after `202` | Order `REJECTED` with `INVALID_SKU` or `BELOW_MOQ`; status event | Dealer by webhook | New submission with a new key; same `dealerOrderNo` allowed | Dealer corrects the line | Order `REJECTED` |
| A9 | ERP unreachable while the rules run | ERP call timeout | Order stays `RECEIVED`; rules retried every minute for 15 minutes, then hourly; alert after 15 minutes | Integration team | Rules are idempotent; no duplicate reservation | ERP back, rules run; dealer sees the normal status event | `RECEIVED` until the ERP answers |
| A10 | Stock gone between approval and reservation | ERP rejects the reservation | Order back to `PENDING_APPROVAL` with `PARTIAL_STOCK`; task reopened | Representative, dealer by webhook | Reservation retried 3 times 30 seconds apart before giving up | Representative decides again | `PENDING_APPROVAL` |
| A11 | Body over 256 KB or over 200 lines | Size and count checks | `413 PAYLOAD_TOO_LARGE` or `400 TOO_MANY_LINES` | Dealer | Split into several orders | None | No order |
| A12 | Integration database unavailable | Health check | `503 SERVICE_UNAVAILABLE`, `Retry-After: 60`; no `202` is given without storage | Integration team, priority 1 | Dealer retries with the same key | Database restored | No order until accepted |

### 4.2 Stock inquiry

| ID | Scenario | Detection | System response | Notified | Retry and idempotency | Recovery | State afterwards |
|---|---|---|---|---|---|---|---|
| B1 | Rate limit exceeded | Counter per dealer | `429 RATE_LIMIT_EXCEEDED`, `Retry-After` | Dealer | Connector backs off | Connector caches stock answers | None |
| B2 | ERP unreachable and no cached entry | ERP call timeout | `503 SERVICE_UNAVAILABLE`, `Retry-After: 60`; never a partial answer | Dealer; integration team after 5 minutes | Read-only, safe to retry | ERP back | None |
| B3 | Unknown or inactive SKU in the request | Catalogue lookup | `200` with the item flagged `UNKNOWN` or `INACTIVE` (RULE-12) | Dealer | Not an error | Dealer fixes its cross-reference | None |
| B4 | Cache older than 5 minutes and ERP slow | Cache age | Fresh read attempted; if the ERP does not answer in 5 seconds the stale entry is returned with its `asOf` | Dealer sees `asOf` | None | None | None |

### 4.3 Approval

| ID | Scenario | Detection | System response | Notified | Retry and idempotency | Recovery | State afterwards |
|---|---|---|---|---|---|---|---|
| C1 | Representative does not decide within 4 business hours | Timer | Task escalated to the sales manager (RULE-08) | Manager, representative | None | Manager decides | `PENDING_APPROVAL` |
| C2 | Task system unavailable | Task API error | Tasks queued in the integration layer and replayed; alert after 30 minutes | Integration team | Task creation keyed by `orderId`, no duplicates | Task system back | `PENDING_APPROVAL` |
| C3 | Credit data changed while pending | Re-check at decision time | Checks re-run before approval; if they now fail, the task is updated with the new reason | Representative | None | Representative decides on current data | `PENDING_APPROVAL` or `APPROVED` |
| C4 | Representative approves twice (double click or retry) | Decision already recorded | Second decision ignored, `200` with the current state | None | Decision keyed by `orderId` and task id | None | Unchanged |

### 4.4 Webhook delivery

| ID | Scenario | Detection | System response | Notified | Retry and idempotency | Recovery | State afterwards |
|---|---|---|---|---|---|---|---|
| D1 | Dealer endpoint down or slow | Timeout or connection error | Attempts at 1, 5, 15, 60 and 240 minutes (RULE-16); after the fifth, dealer flagged | Sales support after exhaustion; daily report | Each attempt carries the same `eventId` | Dealer fixes the endpoint; events fetched by query | Event `WEBHOOK_EXHAUSTED` |
| D2 | Dealer endpoint rejects with `401` after rotating its secret | `4xx` answer | Same schedule; `410 Gone` stops retries at once | Sales support after exhaustion | Same `eventId` | Dealer re-registers the secret (UC-10) | Event exhausted |
| D3 | Dealer processed the event but answered after 10 seconds | Timeout on Vektör side | Event redelivered | None | Dealer deduplicates by `eventId` | None | Delivered once from the dealer's view |
| D4 | Two status changes seconds apart arrive out of order | Dealer compares `occurredAt` | Dealer applies the newer event only | None | Events are immutable; `GET /orders/{orderId}` gives the truth | None | Correct status at the dealer |
| D5 | Webhook URL has an invalid TLS certificate | TLS failure | Treated as unreachable (D1) | Sales support | Same | Dealer renews the certificate | Event exhausted |

### 4.5 Invoice

| ID | Scenario | Detection | System response | Notified | Retry and idempotency | Recovery | State afterwards |
|---|---|---|---|---|---|---|---|
| E1 | UBL-TR document fails local validation | Schema and rule check | `SEND_FAILED`, alert with the validation messages | Integration team, priority 2 | No automatic retry | Mapping or master data fixed, document rebuilt from the same invoice and ETTN | `SEND_FAILED` until fixed |
| E2 | Dealer tax number not registered at GİB | `CheckUser` | `HELD`, task for sales support (RULE-14); escalated to finance on day 5 (P7) | Sales support, finance | Re-check when the task is resolved | Dealer data corrected (UC-07) | `HELD` until fixed |
| E3 | `SendInvoice` returns a SOAP fault | Fault in the response | `SEND_FAILED`, alert with the fault code | Integration team | No automatic retry for validation faults | Fix and resend with the same ETTN | `SEND_FAILED` |
| E4 | Integrator unreachable or times out on `SendInvoice` | Connection error or timeout | Outcome unknown: resend every 5 minutes with the same ETTN; the integrator deduplicates by ETTN (`INV_DUPLICATE_ETTN` counts as accepted) | Integration team after 30 minutes | Never a new ETTN for a retry | Connectivity restored | `MAPPED` then `AT_INTEGRATOR` |
| E5 | Integrator credentials expired | Authentication error | All sends queued; alert at once | Integration team, priority 1 | Queue replayed after the fix | Credentials renewed with Köprü e-Belge | `MAPPED`, nothing lost |
| E6 | Integrator or GİB reports `ERROR` (for example recipient inbox not found) | Status poll | `ERROR`, alert with the reason text | Integration team; finance for content errors | None automatic | If the document never reached GİB: resend with the same ETTN. If GİB rejected it: cancel in the ERP, issue a new invoice with a new number and ETTN (open point E2) | `ERROR` then a new document |
| E7 | No final status 24 hours after sending | Poll timer | `INV_STATUS_TIMEOUT` in the daily report | Integration team | Polling continues | Integrator support contacted | `AT_INTEGRATOR` |
| E8 | Shipment confirmed days after the goods left | Carrier pickup date versus confirmation date | Daily report line; invoice date is the actual shipment date; `INV_LEGAL_DEADLINE_RISK` at day 5 | Warehouse supervisor, finance | None | Warehouse confirms at once; finance checks the 7-day rule | Invoice issued late but inside the limit |
| E9 | Dealer reports a totals mismatch between the event and the UBL document | Dealer ticket | Integration team compares the event, the UBL and the ERP invoice | Finance | None | Rounding or mapping fix; corrected invoice by the manual return process | Depends on the cause |
| E10 | Same invoice created twice in the ERP for one shipment | ETTN and shipment check | Second invoice blocked before mapping; alert | Finance, integration team | Keyed by shipment id | ERP duplicate cancelled | One invoice |

### 4.6 Cross-cutting

| ID | Scenario | Detection | System response | Notified | Retry and idempotency | Recovery | State afterwards |
|---|---|---|---|---|---|---|---|
| F1 | Clock skew between the dealer system and Vektör | Token or timestamp outside tolerance | Tolerance of 5 minutes; beyond that `401` | Dealer | None | NTP fixed on the dealer side | None |
| F2 | API TLS certificate close to expiry | Monitoring 30 days ahead | Alert | Integration team | None | Certificate renewed | None |
| F3 | Two dealer records with the same tax number | Onboarding check | Onboarding blocked | Sales support | None | Master data corrected | None |
| F4 | Unexpected exception in the API | Exception handler | `500 INTERNAL_ERROR` with `requestId`; alert when the rate exceeds 1% of requests in 5 minutes | Integration team | Dealer may retry once with the same key | Root cause fixed | Depends |
| F5 | Dealer sends a field the schema does not know | Schema check | `400 UNKNOWN_FIELD` | Dealer | After correction | Connector fixed | No order |

## 5. Retry and idempotency policies

| Operation | Idempotency mechanism | Retry policy | Who retries |
|---|---|---|---|
| `POST /orders` | `Idempotency-Key` per dealer, 7 days, body hash compared | Up to 3 retries with the same key at 2, 10 and 60 seconds on timeouts and `503`; on `409 REQUEST_IN_PROGRESS` wait `Retry-After` | Dealer connector |
| `GET /stock`, `GET /orders`, `GET /invoices` | Read-only | Honour `Retry-After` on `429` and `503`; at most 3 retries | Dealer connector |
| `POST /invoices/{ettn}/acknowledge` | ETTN; a repeat is a no-op `200` | Up to 3 retries | Dealer connector |
| Business rules evaluation | Keyed by `orderId`; a re-run produces the same outcome | Every minute for 15 minutes, then hourly; alert at 15 minutes | Vektör |
| Stock reservation in the ERP | Keyed by `orderId` and line; the ERP ignores a repeated reservation | 3 attempts 30 seconds apart, then back to `PENDING_APPROVAL` | Vektör |
| Task creation for representatives | Keyed by `orderId` | Queued and replayed; alert at 30 minutes | Vektör |
| Webhook delivery | `eventId`; dealer deduplicates | 5 attempts at 1, 5, 15, 60 and 240 minutes; `410 Gone` stops early | Vektör |
| `SendInvoice` | ETTN; integrator deduplicates | Every 5 minutes for 30 minutes on connectivity errors, then alert; no retry on validation faults | Vektör |
| `GetInvoiceStatus` | Read-only | Every 5 minutes until final; report at 24 hours | Vektör |
| `CheckUser` (tax number) | Read-only | 3 attempts; if the service is down the invoice waits in `MAPPED` rather than being held | Vektör |

## 6. Timeouts and limits

| Item | Value | Where defined |
|---|---|---|
| `POST /orders` response time target | Under 2 seconds; hard timeout 10 seconds | NFR |
| `GET /stock` response time target | Under 1 second; hard timeout 5 seconds | NFR |
| ERP call timeout | 5 seconds | Integration layer |
| Integrator SOAP timeouts | 5 seconds to connect, 30 seconds to read | Integration service |
| Webhook delivery timeout | 10 seconds | RULE-16 |
| Request body limit | 256 KB | API gateway |
| Order lines per request | 200 | Field mapping |
| SKUs per stock request | 50 | Field mapping |
| Rate limit, `GET /stock` | 60 requests per minute per dealer | RULE-11 |
| Rate limit, `POST /orders` | 30 requests per minute per dealer | This document |
| Rate limit, other `GET` endpoints | 120 requests per minute per dealer | This document |
| Idempotency key retention | 7 days | RULE-10 |
| Access token lifetime | 60 minutes | Field mapping |
| Clock skew tolerance | 5 minutes | This document |

## 7. Monitoring and alerting

| Alert | Condition | Severity | Who | Response target |
|---|---|---|---|---|
| API down | Health check fails 3 times in a row | P1 | Integration team on call | 15 minutes |
| Integration database down | Connection failures | P1 | Integration team on call | 15 minutes |
| Integrator authentication failed | Any `INV_INTEGRATOR_AUTH_FAILED` | P1 | Integration team | 30 minutes |
| ERP unreachable | Failures for more than 15 minutes | P2 | Integration team | 1 hour |
| Invoice send failed | Any `SEND_FAILED` | P2 | Integration team | 4 business hours |
| Invoice in error | Any `INV_STATUS_ERROR` | P2 | Integration team, finance | 4 business hours |
| Invoice held | `HELD` for more than 2 business days | P2 | Sales support lead | 1 business day |
| Legal deadline risk | Any `INV_LEGAL_DEADLINE_RISK` | P2 | Finance | Same day |
| Error rate | `500` responses above 1% of requests in 5 minutes | P2 | Integration team | 1 hour |
| Webhook failing dealer | Any `WEBHOOK_EXHAUSTED` | P3 | Sales support | Daily report |
| Stalled orders and invoices | Daily report groups (UC-09) | P3 | Integration team, finance | Daily report |
| Certificate expiry | Less than 30 days | P3 | Integration team | Before expiry |

The daily report (UC-09) collects the P3 items; P1 and P2 alerts go to the on-call channel immediately. Thresholds and availability targets are in [06 Non-functional requirements](06_nfr.md).

## 8. Negative test list

Each test runs against the test environment with a dedicated test dealer. The ids become folder and request names in the Postman collection.

| Test | Scenario | Preparation | Request | Expected status | Expected code or outcome |
|---|---|---|---|---|---|
| NT-01 | A1 | Omit `deliveryAddress.city`, send `lines[2].quantity = 1.5` for a piece item | `POST /orders` | 400 | `VALIDATION_FAILED` with `FIELD_REQUIRED` and `QUANTITY_NOT_INTEGER` |
| NT-02 | A2 | Use an expired token | `POST /orders` | 401 | `UNAUTHORIZED` |
| NT-03 | A3 | Test dealer set to suspended | `POST /orders` | 403 | `DEALER_SUSPENDED` |
| NT-04 | A4 | Send a valid order, then resend the identical request with the same key | `POST /orders` twice | 202 then 202 | Same `orderId` in both responses |
| NT-05 | A5 | Resend with the same key and a changed quantity | `POST /orders` | 422 | `IDEMPOTENCY_KEY_REUSED` |
| NT-06 | A6 | Send a second order with the same `dealerOrderNo` and a new key | `POST /orders` | 409 | `DUPLICATE_DEALER_ORDER_NO` |
| NT-07 | A6 | Reject the first order in the test ERP, then resend with the same `dealerOrderNo` | `POST /orders` | 202 | New `orderId` |
| NT-08 | A7 | Fire two identical requests in parallel | `POST /orders` | 202 and 409 | One `REQUEST_IN_PROGRESS` with `Retry-After` |
| NT-09 | A8 | Use an inactive SKU | `POST /orders`, then poll | 202, then event | Status `REJECTED`, reason `INVALID_SKU` |
| NT-10 | A8 | Quantity below the minimum | `POST /orders`, then poll | 202, then event | Status `REJECTED`, reason `BELOW_MOQ` |
| NT-11 | A11 | 201 lines | `POST /orders` | 400 | `TOO_MANY_LINES` |
| NT-12 | A11 | Body over 256 KB | `POST /orders` | 413 | `PAYLOAD_TOO_LARGE` |
| NT-13 | F5 | Add an unknown field `price` on a line | `POST /orders` | 400 | `UNKNOWN_FIELD` |
| NT-14 | A1 | Missing `Idempotency-Key` header | `POST /orders` | 400 | `MISSING_IDEMPOTENCY_KEY` |
| NT-15 | A1 | `Idempotency-Key: not-a-uuid` | `POST /orders` | 400 | `INVALID_IDEMPOTENCY_KEY` |
| NT-16 | B1 | 61 stock requests within a minute | `GET /stock` | 429 | `RATE_LIMIT_EXCEEDED`, `Retry-After` present |
| NT-17 | B3 | One unknown SKU among two valid ones | `GET /stock` | 200 | Item flagged `UNKNOWN`, others `OK` |
| NT-18 | B1 | 51 SKUs in one request | `GET /stock` | 400 | `TOO_MANY_SKUS` |
| NT-19 | A6 | Query another dealer's order id | `GET /orders/{orderId}` | 403 | `FORBIDDEN_RESOURCE` |
| NT-20 | A6 | Query a random order id | `GET /orders/{orderId}` | 404 | `NOT_FOUND` |
| NT-21 | D1 | Test dealer webhook endpoint returns 500 | Trigger a status change | Event retried | Log shows `WEBHOOK_REJECTED` and a scheduled retry |
| NT-22 | D3 | Test endpoint delays 12 seconds then answers 200 | Trigger a status change | Event redelivered | Second delivery carries the same `eventId` |
| NT-23 | E2 | Test dealer with an unregistered tax number | Ship a test order | Invoice `HELD` | Task for sales support exists |
| NT-24 | E1 | Product with an empty name in the test ERP | Ship a test order | Invoice `SEND_FAILED` | Alert with `INV_VALIDATION_FAILED` |
| NT-25 | E4 | Integrator sandbox unreachable (blocked by firewall rule) | Ship a test order | Invoice stays `MAPPED` | Resend attempts logged every 5 minutes, alert after 30 minutes |
| NT-26 | C4 | Approve the same pending order twice | Internal task API | 200 | Second call returns the current state without change |
| NT-27 | INVALID_STATE | Acknowledge an order that is `SHIPPED`, not `INVOICED` | `POST /invoices/{ettn}/acknowledge` | 409 | `INVALID_STATE` |
| NT-28 | Language | Send `Accept-Language: en` with an invalid request | `POST /orders` | 400 | `detail` and `errors[].message` in English |

## 9. Open points

| ID | Point | Owner | Needed by |
|---|---|---|---|
| E1 | Add a per-order `sequence` number to the status event so that dealers can order events without comparing timestamps (change request to the field mapping). | Integration team | API design |
| E2 | Confirm with Köprü e-Belge when a failed invoice may be resent with the same ETTN and when a new document is required. | Integration team | Before pilot |
| E3 | Confirm with finance the manual correction process for a delivered invoice with wrong totals (return invoice is out of scope in this version). | Finance | Before pilot |
| E4 | Decide whether `410 Gone` from a dealer endpoint should also pause all further events for that dealer until re-registration. | Sales Operations | API design |
| E5 | Agree the on-call rota and channels for P1 and P2 alerts (operations model, NFR). | IT | Go-live |
