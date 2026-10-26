# VictorOS scheduler crash-retry hardening (isolated candidate)

Status: PARTIAL RUNTIME MITIGATION (2026-10-26), DRAFT. An in-flight action quarantine is integrated on this branch; the transactional outbox and provider idempotency contract are NOT implemented. Do not merge until exact-head CI and independent review.

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

## 2026-10-26: bounded fail-closed recovery mitigation

The current draft branch now changes only `vos_core/cognitive_scheduler.py` and its targeted regression tests. It introduces `ItemStatus.UNKNOWN` for selected capability claims whose outcome is ambiguous:

- On process restart, stranded `PROCESSING` `ACTION_CANDIDATE` records transition to `UNKNOWN` rather than `PENDING`.
- On an exception after a selected candidate is durably claimed, the claim transitions to `UNKNOWN` rather than becoming immediately retryable.
- Other `PROCESSING` cognition items still resume as `PENDING`; deferred, never-dispatched action candidates remain pending.
- The queue scheduler selects only `PENDING` work, so an `UNKNOWN` action cannot be silently replayed. Operators must inspect/reconcile the local SQLite queue before deciding whether a new action is safe.
- The mitigation deliberately sacrifices automatic liveness for ambiguous effects; a crash before actual dispatch can also quarantine a never-executed action. No automatic `UNKNOWN -> PENDING` transition is provided.

### Verification gates

`python -m pytest tests/test_cognitive_scheduler.py -q` and `python -m pytest tests/ -q` must pass on the exact draft head; GitHub Actions runs the full suite for Python 3.10, 3.11, and 3.12. The isolated SQL transition model passed locally before publication; that model is NOT equivalent to full repository tests.

### Explicitly NOT solved

This does not provide transactional intent/outbox persistence, stable provider idempotency keys, safe multi-worker leases, external receipt reconciliation, or exactly-once side effects. It only prevents one known automatic replay path. The P0 issue remains OPEN. Production promotion and merges remain blocked pending full outbox design, deterministic crash-injection acceptance, and owner approval.

### Rollback

Revert the two 2026-10-26 code/test commits on this draft branch or close PR #18. No production data or schema migration is performed; the new status is a value in the existing SQLite `status` column.
