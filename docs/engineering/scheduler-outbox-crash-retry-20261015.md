# VictorOS scheduler crash-retry hardening (isolated candidate)

Status: RESEARCH_CANON / BUILD_CANON candidate. Not integrated with vos_core/cognitive_scheduler.py. Do not merge until tests and integration review.

## Confirmed failure window
The current scheduler persists ACTION_CANDIDATE, calls physiology.execute(), then records capability_results. A process exit after the capability side effect but before result storage strands a PROCESSING item, which startup resets to PENDING, risking duplicate side effects.

## Required contract
- Persist stable action_id/idempotency_key and canonical payload hash, reject collisions with different payloads.
- Claim READY atomically as RUNNING; on restart move abandoned RUNNING to UNKNOWN, *never* automatically retry unknown external outcomes.
- When provider supports idempotency, pass stable key to external call and reconcile with provider receipt before retry.
- For local SQLite effects, co-commit side effect and completion in one transaction when they share the database.
- For remote non-idempotent calls, require human/provider reconciliation; exactly-once cannot be promised.
- Preserve physiology governance and human approval gates.

## Regression gates
1. Duplicate action_id + same payload does not execute twice.
2. Duplicate action_id + different payload is rejected.
3. Kill process after external effect but before result commit: recovery state UNKNOWN; no second execution.
4. Provider receipt reconciliation transitions UNKNOWN to DONE.
5. Proven non-execution transitions UNKNOWN to READY with recorded evidence.
6. Fail-closed gating and existing scheduler regression suite remain green.

A runnable isolated SQLite proof of this journal has been created and passed 5 local unit tests, but it has not been integrated into the scheduler. Next: wire execution via action IDs and supply integration crash-injection tests on this branch before PR review.
