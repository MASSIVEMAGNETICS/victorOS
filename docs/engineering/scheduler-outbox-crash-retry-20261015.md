# VictorOS scheduler crash-retry hardening (isolated candidate)

Status: PARTIAL RUNTIME MITIGATION (2026-10-26), DRAFT — see the 2026-11-05 addendum at the end: the transactional outbox is now integrated in the scheduler path as a draft for Issue #19. Do not merge until exact-head CI and independent review.

## Confirmed failure window
The current scheduler persists ACTION_CANDIDATE, calls physiology.execute(), then records capability_results. A process exit after the capability side effect but before result storage strands a PROCESSING item, which the default-branch startup logic resets to PENDING, risking duplicate side effects.

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

The earlier isolated SQLite journal proof passed five local tests, but its transactional outbox has NOT been integrated into the scheduler. The 2026-10-26 runtime change below is a narrower UNKNOWN-state quarantine, not that journal. Next: integrate stable action IDs, provider reconciliation, and deterministic crash-injection tests before PR promotion.

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

## 2026-11-05: transactional outbox integrated (draft, Issue #19)

`vos_core/cognitive_scheduler.py` now carries the outbox this doc required,
in the scheduler path only (no Chronos changes):

- Stable effect ID (`eff_` + hash of capability + source item) and canonical
  payload digest, recorded atomically with the action candidate; the same
  effect ID with a different payload is rejected, never re-dispatched.
- Concurrency-safe claim (one READY worker wins; expired CLAIMED leases are **not** re-claimed automatically),
  the effect ID passed to the provider as the idempotency key.
- Result + observation + outbox completion co-committed in one SQLite
  transaction; a provider timeout is treated as ambiguous (UNKNOWN), not
  terminal. Bounded transient-failure retries (3 attempts) then DLQ.
- `CognitiveScheduler.reconcile_effect()` is the only path out of UNKNOWN:
  provider-confirmed "executed" commits the outcome exactly once;
  "not_executed" returns the claim to PENDING for one safe retry.
- Crash-injection acceptance: `tests/test_issue19_outbox.py` (14 tests,
  deterministic, no real process kill) plus the 22 pre-existing scheduler
  tests, all green locally. Full suite: 127 passed, 2 pre-existing failures
  (`test_vos_apps.py`, missing `streamlit` in the test env, unrelated).

Honest limit, unchanged: without provider-supported idempotency or a
provider receipt, exactly-once external execution cannot be promised.
Production promotion still requires owner review of the draft PR.

### Rollback

Revert the two 2026-10-26 code/test commits on this draft branch or close PR #18. No production data or schema migration is performed; the new status is a value in the existing SQLite `status` column.

## 2026-11-08: expired-lease replay gate (draft)

The outbox claim transition now permits **READY -> CLAIMED only**. A lease expiry
alone cannot prove that the previous worker stopped a provider call; therefore
an expired CLAIMED record cannot be reclaimed or dispatched by a second worker.
Restart recovery moves unresolved CLAIMED records to UNKNOWN for explicit
reconciliation. The existing two-worker regression now checks this fail-closed
behavior after forcing lease expiry, including restart quarantine.

This is a bounded replay-risk mitigation, **not** complete worker-generation
fencing or provider-authenticated reconciliation. Live stale-worker completion,
lease-expiry reconciliation without restart, and externally authenticated
receipts remain outstanding. The draft must not merge or deploy without
exact-head CI, independent review, and founder approval.
