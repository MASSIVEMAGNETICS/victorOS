# Empire Execution Gate — 2026-10-16
Status: ENGINEERING_CANDIDATE; not proof of autonomous or commercial operation.
Authority: Founder directive "Execute 1 through 5"; no merge or production deployment.

## WIP freeze
Only TWO active delivery lanes until both have verified terminal outcomes:
- P0 VictorOS crash/retry idempotency and outbox (issue #19).
- P0 B Heard Network $9.99 creator submission checkout → persisted order → fulfillment → buyer receipt.
Other initiatives are INVENTORY or RESEARCH, not abandoned. Exceptions only for actual security incidents.

## Evidence semantics
REALITY_VERIFIED = independently inspectable production event or reproducible external observation.
ENGINEERING_INSPECTED = source examined, NOT tested.
TESTED_LOCAL = recorded commands + exact SHA + logs.
REPORTED = historical statement without current independent proof.
UNKNOWN = missing evidence.
Do not promote a build, a price, a marketing page, or a payment-link draft to REVENUE_VERIFIED.

## Commercial invariants
A unique order ID maps one signed, verified processor payment event to at most one fulfillment record and one logically unique customer receipt. Verify signature against raw body; dedupe provider event IDs; use monotonic state machine PENDING→PAID→FULFILLED (REFUNDED and DISPUTED are distinct terminal/exception states). Persist processing intent and fulfillment outbox atomically; bound retries; quarantine unknowns for manual reconciliation. Never store full card details. A screenshot or self-issued receipt is not transaction proof.

## Four tracked metrics (rolling 7 and 30 days)
1. PRODUCTS_VERIFIED: tested end-to-end reproducible releases, with URL, SHA and independent test evidence.
2. PAID_CUSTOMERS: distinct customers with settled, nonrefunded payments (processor export/source of truth).
3. AUTONOMOUS_SUCCESS_RATE: verified successful unattended jobs / all attempted unattended jobs, with separately counted retries, failures, human interventions, and unmeasured intervals.
4. NET_OPERATING_CASH: collected revenue less refunds, processor fees, hosting, compute, tools, fulfillment and other cash operating costs (before tax; use a separately reconciled accounting view for accrual profit).
Unknown numerator/denominator => UNKNOWN, not zero or 100%.

## Infrastructure sovereignty acceptance
Code, data, credentials, backup and signing keys must remain exportable and under owner control. Map registrar, DNS, CI, source hosting, model/API, payments, email and database dependencies with a recovery playbook and feasible alternatives. No "zero dependency" assertion: global DNS and payment rails remain external dependencies. GitHub Pages is not a secure payments/webhook backend.

## Release freeze criteria
No code promotion without exact-head automated tests, crash-injection tests, independent review, migration/backup/restore drill, observable rollback, and Founder authorization. No real checkout without live end-to-end receipt audit, terms/refund disclosure and operational fulfillment.
