# e-Invoice SOAP contract and UBL-TR samples

This folder holds the contract between the Vektör integration service and the private e-Invoice integrator Köprü e-Belge, with sample messages for every operation and a complete UBL-TR invoice. It is the SOAP side of the [invoice flow](../../analysis/03_use_cases.md) (UC-06) and implements the UBL-TR mapping in the [field mapping](../../analysis/04_field_mapping.md), section 6.

> Köprü e-Belge, its endpoints, operation names, status codes and fault codes are fictional. They are modelled on how Turkish private integrator services commonly work and must be replaced by the real provider's contract during onboarding. The UBL-TR invoice follows the official GİB format.

## Files

| File | Content |
|---|---|
| `kopru-ebelge-einvoice-v1.wsdl` | WSDL 1.1, SOAP 1.1, document/literal wrapped, inline XML Schema for all messages |
| `samples/CheckUser-request.xml`, `-response.xml` | Is the dealer's tax number a registered e-Invoice user, and which inbox aliases does it have |
| `samples/SendInvoice-request.xml`, `-response.xml` | Sending invoice `VKT2027000001234`: the UBL-TR document zipped, base64-encoded, with its SHA-256 hash |
| `samples/GetInvoiceStatus-request.xml`, `-response-delivered.xml`, `-response-error.xml` | Status polling by ETTN, a delivered and a failed outcome |
| `samples/SoapFault-schema-error.xml` | SOAP 1.1 Fault returned when the document fails the integrator's schema check |
| `samples/ubl-tr/invoice-VKT2027000001234.xml` | The UBL-TR 1.2 invoice for order `VO-2027-000123`, the same order as in the OpenAPI examples |

## Contract summary

| Aspect | Value |
|---|---|
| Protocol | SOAP 1.1 over HTTPS, `text/xml; charset=utf-8`, `SOAPAction` header per operation |
| Style | Document/literal wrapped: one request and one response element per operation |
| Authentication | WS-Security UsernameToken (PasswordText) in the SOAP header, over TLS 1.2 or higher; credentials kept in the secrets vault (NFR-SEC-06) |
| Test endpoint | `https://ws-test.kopru-ebelge.example/einvoice/v1` |
| Timeouts on the Vektör side | 5 seconds to connect, 30 seconds to read (error scenarios, section 6) |
| Document packaging | UBL-TR XML in a zip with one entry named `<ETTN>.xml`, base64-encoded in `content`; `hash` is the SHA-256 of the zip bytes |
| Signature | Vektör sends the document unsigned; the integrator applies the XAdES-BES signature inside `ext:UBLExtensions` before delivery to GİB |

## Operations

| Operation | Purpose | Called when | Idempotency | Retry on the Vektör side | Use case and scenarios |
|---|---|---|---|---|---|
| `CheckUser` | Registered e-Invoice user check for a tax number (VKN); returns the title and the inbox aliases (`PK`) | Before every `SendInvoice` (RULE-14) and at dealer onboarding | Read-only | 3 attempts; if the service is down the invoice waits in `MAPPED` | UC-06, UC-07, UC-10; E2 |
| `SendInvoice` | Hands one invoice to the integrator; returns a receipt id and `QUEUED` | After mapping and local validation | By ETTN: a repeat returns fault 2005 with the original receipt, treated as accepted | Every 5 minutes for 30 minutes on connection errors, never on validation faults; never with a new ETTN | UC-06; E1, E3, E4, E5 |
| `GetInvoiceStatus` | Delivery status by ETTN, with the GİB envelope state | Every 5 minutes after `SendInvoice` until a final status | Read-only | Polling continues; report after 24 hours | UC-06; E6, E7 |

## Status values

The integrator's `status` drives the Vektör invoice state ([use cases](../../analysis/03_use_cases.md), state diagram 8.2). `stateCode` passes through the GİB envelope state reported by the integrator; the codes below are representative and must be confirmed with the provider.

| `status` | Typical `stateCode` | Meaning | Vektör invoice state | Order effect |
|---|---|---|---|---|
| `QUEUED` | None | Received by the integrator, not yet sent to GİB | `AT_INTEGRATOR` | None |
| `SENT` | 1100 to 1220 | Envelope sent to GİB, waiting for the receiver | `AT_INTEGRATOR` | None |
| `DELIVERED` | 1300 | Envelope delivered to the receiver's inbox | `DELIVERED`, then `NOTIFIED` | `INVOICED`, `invoice.issued` webhook |
| `ERROR` | 1150, 1160, 1230 and other error states | Rejected by GİB or delivery failed after the integrator's retries | `ERROR` | Stays `SHIPPED`; alert (scenario E6) |

## Fault codes

Faults are SOAP 1.1 Faults (HTTP 500) with a `ServiceFault` detail carrying `code`, `message` and the integrator's `requestId`. Each code maps to an error code of the [error scenarios](../../analysis/05_error_scenarios.md), section 3.5.

| Code | `faultcode` | Meaning | Vektör error code | Vektör action |
|---|---|---|---|---|
| 1000 | `soapenv:Client` | Authentication failed | `INV_INTEGRATOR_AUTH_FAILED` | Queue all sends, P1 alert (E5) |
| 1100 | `soapenv:Client` | Account not authorised for the sender alias | `INV_INTEGRATOR_AUTH_FAILED` | P1 alert, check the contract with the integrator |
| 2000 | `soapenv:Client` | UBL-TR schema validation failed | `INV_SOAP_FAULT` | `SEND_FAILED`, alert with the message (E3) |
| 2001 | `soapenv:Client` | GİB schematron rule failed | `INV_SOAP_FAULT` | `SEND_FAILED`, alert (E3) |
| 2002 | `soapenv:Client` | Hash does not match the content | `INV_SOAP_FAULT` | Rebuild the package and resend with the same ETTN |
| 2005 | `soapenv:Client` | ETTN already received; message carries the original receipt id | `INV_DUPLICATE_ETTN` | Treat as accepted, continue polling (E4) |
| 3000 | `soapenv:Client` | Receiver is not a registered e-Invoice user | `INV_VKN_NOT_REGISTERED` | `HELD`, task for sales support (E2) |
| 3001 | `soapenv:Client` | Receiver alias not found | `INV_SOAP_FAULT` | Re-run `CheckUser`, update the alias, resend |
| 5000 | `soapenv:Server` | Integrator internal error | `INV_INTEGRATOR_UNREACHABLE` | Retry every 5 minutes, alert after 30 minutes (E4) |

## UBL-TR sample

`samples/ubl-tr/invoice-VKT2027000001234.xml` is the invoice for the order used throughout the case: dealer Marmara Teknoloji, two lines, net 145,380.00 TRY, VAT 29,076.00 TRY at 20%, payable 174,456.00 TRY. It contains every element of the field mapping, section 6, except the line discount block, which is conditional and not used in this order. The dealer order number is in `cac:OrderReference/cbc:ID` and the Vektör order number in `cac:AdditionalDocumentReference`, so the dealer ERP can match the invoice to its purchase order.

Because UBL-TR requires `ext:UBLExtensions`, the unsigned document carries a placeholder element in a Vektör namespace that the integrator replaces with the `ds:Signature`. The XML Schema allows this: extension content is validated laxly, and an element from an undeclared namespace is accepted.

## Validation

| Check | Result |
|---|---|
| All files well-formed XML | Passed (`xmllint`) |
| Every SOAP body against the WSDL's inline schema | Passed for all eight samples |
| UBL-TR invoice against the official GİB UBL-TR 1.2.1 schema (`UBL-Invoice-2.1.xsd`) | Passed (`xmllint --schema`) |
| Every UBL-TR XPath of the field mapping present in the sample | Passed; the three line discount elements are conditional and absent by design |
| Line amounts, VAT per line, totals and line count | Passed |
| `SendInvoice` content decodes to a zip holding exactly the sample invoice, and `hash` is its SHA-256 | Passed |
| Same identifiers and amounts as the OpenAPI invoice example | Passed |
| GİB schematron business rules | Not run in this case; the schematron package is applied by the integrator, and adding it to CI is NFR-COMP-03 |

## SOAP and REST in this project

| Aspect | Dealer API (REST) | Integrator service (SOAP) |
|---|---|---|
| Who defines the contract | Vektör, contract-first in OpenAPI 3.1 | The integrator; Vektör consumes it |
| Payload | JSON | XML; the invoice itself is UBL-TR XML, zipped and base64-encoded inside the SOAP body |
| Contract format | OpenAPI file | WSDL with inline XML Schema |
| Authentication | OAuth2 client credentials, bearer token per request | WS-Security UsernameToken in the SOAP header |
| Errors | HTTP status plus RFC 9457 problem details | HTTP 500 with a SOAP Fault and a typed detail |
| Idempotency | `Idempotency-Key` header chosen by the caller | Business key: the ETTN |
| Asynchronous outcome | Webhooks pushed to the dealer | Status polling by the caller |
| Why this style | Modern, easy for dealer ERP connectors and the portal | Integrator services in Türkiye are typically SOAP, and UBL-TR is an XML standard |

## Open points

| ID | Point | Owner |
|---|---|---|
| S1 | Replace the fictional contract with Köprü e-Belge's real WSDL and confirm operation names, fault codes and state codes. | Integration team |
| S2 | Confirm whether the integrator pushes status changes (callback) so that polling can be reduced. | Integration team |
| S3 | Confirm the resend rule after a GİB rejection: same ETTN or a new document (error scenarios E2). | Integration team, finance |
| S4 | Add the GİB schematron to the CI validation of sample invoices (NFR-COMP-03, NFR-MAIN-07). | Integration team |
