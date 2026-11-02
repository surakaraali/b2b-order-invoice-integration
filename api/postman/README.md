# Postman collection and test run

This folder holds the Postman collection for the dealer API and the integrator SOAP service, its environments, a local sandbox simulator to run it against, and the latest test report. The collection turns the [OpenAPI specification](../openapi/vektor-dealer-api.v1.yaml), the [SOAP samples](../soap/) and the negative test list of the [error scenarios](../../analysis/05_error_scenarios.md), section 8, into executable tests.

> All companies, credentials and figures are fictional. The `sim-*` credentials only work against the local simulator.

## Files

| File | Content |
|---|---|
| `vektor-dealer-api.postman_collection.json` | Postman Collection v2.1: 46 requests in four folders, with pre-request and test scripts |
| `environments/local-simulator.postman_environment.json` | Addresses and test credentials of the local simulator |
| `environments/sandbox.postman_environment.json` | Addresses of the Vektör sandbox; credentials left empty, issued at onboarding |
| `simulator/sandbox_simulator.py` | Local test double of the dealer API, the token endpoint and the integrator SOAP service; Python standard library only |
| `reports/test-report.md` | Result of the latest run, one row per request |
| `reports/newman-cli.log` | Raw Newman output of the same run |

## Collection structure

| Folder | Requests | What it covers |
|---|---|---|
| 00 Setup | 1 | OAuth2 client credentials token and a new run id |
| 01 Happy path | 15 | Health, catalogue with paging, stock, order submission, automatic approval and reservation, the two approval paths (credit limit, partial stock), invoice notifications, acknowledgement and the closed case order |
| 02 Negative tests | 22 | The dealer API tests NT-01 to NT-20, NT-27 and NT-28 of the error scenarios, with the same ids |
| 03 Integrator SOAP | 8 | CheckUser, SendInvoice and GetInvoiceStatus with the sample envelopes: integrity fault, duplicate ETTN, status polling and wrong credentials |

Every dealer API request also runs common checks from the collection-level test script: `X-Request-Id` is present, the response time is below the NFR targets (2 seconds for `POST /orders`, 1 second for reads), and every error is `application/problem+json` matching the Problem schema. Successful responses are validated against JSON schemas taken from the OpenAPI components and stored in collection variables.

The collection-level pre-request script sets today's date in Türkiye time, a new `Idempotency-Key` for every request and refreshes the dealer token when it is about to expire. Requests that need another dealer (the suspended dealer, or the second dealer for the rate-limit and isolation tests) fetch their own token in their pre-request script.

## Running it

**With Postman.** Import the collection and the *local simulator* environment, start the simulator, select the environment and run the collection with the Collection Runner. Keep the folder order: later requests use values saved by earlier ones.

**From the command line.** Start the simulator, then run the collection with Newman.

```bash
python3 api/postman/simulator/sandbox_simulator.py --port 8040
```

```bash
npx newman@6 run api/postman/vektor-dealer-api.postman_collection.json -e api/postman/environments/local-simulator.postman_environment.json
```

The simulator keeps its state in memory. Restart it before each run: the SOAP folder sends the case invoice once and expects the integrator to refuse the second attempt.

## Latest result

All 46 requests and 232 assertions passed on 1 November 2026, with Newman 6.2.3 against a freshly started simulator. The run sent 122 HTTP requests, including those sent by scripts, and took about six seconds. Details are in [reports/test-report.md](reports/test-report.md).

## Traceability

| Tests | Use cases | Rules and requirements |
|---|---|---|
| HP-02, HP-03 | UC-02, field mapping rule T6 | BR-07 |
| HP-04, HP-07, NT-16 to NT-18 | UC-02 | RULE-07, RULE-11, RULE-12, BR-13 |
| HP-05, HP-06, HP-08, NT-01, NT-04 to NT-15, NT-28 | UC-01 | RULE-01 to RULE-07, RULE-10, BR-01 to BR-05 |
| HP-09, HP-10 | UC-01 A1, UC-04 | RULE-05, RULE-06 |
| HP-11 to HP-15, NT-27 | UC-08 | BR-09, BR-14 |
| NT-02, NT-03, NT-19, NT-20 | UC-10 | RULE-01, NFR-SEC-01, NFR-SEC-04 |
| S-01 to S-08 | UC-06, UC-07 | RULE-13 to RULE-15, error scenarios E2 to E5 |

## Integration-side tests outside the collection

NT-21 to NT-26 cannot be triggered through the dealer API. The integration team runs them in the sandbox with access to the ERP test data, the integrator test environment and the logs.

| Test | Scenario | How it is run | Pass criteria |
|---|---|---|---|
| NT-21 | D1 webhook endpoint fails | Point the test dealer's webhook URL at an endpoint that answers 500, trigger a status change | Log shows `WEBHOOK_REJECTED` and retries at 1, 5, 15, 60 and 240 minutes |
| NT-22 | D3 slow webhook endpoint | Endpoint delays 12 seconds, then answers 200 | Event is redelivered with the same `eventId` |
| NT-23 | E2 dealer tax number not registered | Test dealer with an unregistered VKN, ship a test order | Invoice `HELD`, task for sales support |
| NT-24 | E1 invalid invoice data | Product with an empty name in the test ERP, ship a test order | Invoice `SEND_FAILED`, alert with `INV_VALIDATION_FAILED` |
| NT-25 | E4 integrator unreachable | Block the integrator test endpoint, ship a test order | Invoice stays `MAPPED`, resend every 5 minutes, alert after 30 minutes |
| NT-26 | C4 double approval | Approve the same pending order twice through the internal task API | Second call returns the current state without change |

## The simulator

`simulator/sandbox_simulator.py` is a test double written for this case, not the product. It implements what the tests need: OAuth2 client credentials, validation with the error catalogue in Turkish and English, idempotency keys with body comparison and an in-progress state, per-dealer rate limits with a sliding one-minute window, dealer isolation, paging, the business rules (catalogue, minimum quantity, credit limit, stock, reservation), invoices and acknowledgement, and the three integrator operations with WS-Security, hash and zip checks and duplicate ETTN detection.

It does not deliver webhooks, has no approval task API and no ERP behind it; its master data is a small fictional catalogue and three dealers. Business rules run right after an order is accepted, so the result is visible on the next read; the real system runs them asynchronously within a minute. Each order submission takes about 250 milliseconds to simulate storage, which makes the concurrent duplicate in NT-08 observable.

| Test dealer | Client id | Profile |
|---|---|---|
| D00042 Marmara Teknoloji | `sim-d00042` | Active, ships from IST, credit limit 500,000 TRY with 120,000 open |
| D00077 Ege Bilişim | `sim-d00077` | Active, ships from IZM; used for the rate-limit and isolation tests |
| D00099 Çınar Elektronik | `sim-d00099` | Suspended |

## Notes

- JSON schema validation leaves out `multipleOf`, because binary floating point makes checks such as 0.01 steps unreliable in JavaScript; amounts are checked with exact values in the tests instead.
- NT-07 asks for a rejected order in the test ERP. The collection produces it through the business rules with an inactive SKU, which gives the same state without manual preparation.
- NT-08 sends the same submission twice in parallel from its pre-request script; the test then confirms that exactly one order exists.
- The local environment uses `127.0.0.1` rather than `localhost`, because Newman on Node 22 fails to resolve `localhost` in this setup.
- The report is generated from Newman's command-line output. Newman's HTML reporter lists every request a script sends as a copy of the item, which makes items such as the rate-limit test unreadable.
