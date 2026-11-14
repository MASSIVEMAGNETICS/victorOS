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

## 2026-11-12: live-worker startup conflict — acceptance contract (draft, unimplemented)

**Evidence:** PR #22 head `427c30fbec48801e58ba87af48d93d45fe9a6b19`,
[Python Core Tests #43171755654](https://github.com/MASSIVEMAGNETICS/victorOS/actions/runs/43171755654)
failed on Python 3.10; Python 3.11/3.12 jobs were cancelled. The two
new live-second-instance tests fail against current startup recovery.
No passing exact-head CI is claimed.

### Root cause and forbidden shortcut

`PersistentCognitiveQueue.__init__` resets all PROCESSING cognition
(unknown action candidates, pending other items) and invokes
`EffectOutbox.recover_claimed_to_unknown()` for **every** CLAIMED effect.
A second *live* scheduler opening the same SQLite database can therefore
invalidate work owned by the first. Earlier crash-injection tests assume
that opening another scheduler proves the first died; it does not.
**Do not** fix by disabling all recovery, relaxing either regression,
trusting lease expiration as proof of death, or automatically replaying
ambiguous provider calls.

### Proposed bounded implementation contract (not yet code)

1. Record a unique owner incarnation token at scheduler startup, plus a
   durable claim generation and owner identity on each PROCESSING queue item
   and CLAIMED outbox effect. Add schema columns via additive migration,
   preserving existing records and indexes.
2. Make claim acquisition, completion, release, transient failure, and
   UNKNOWN transitions conditional on the exact owner **and generation**.
   A stale callback must change zero rows and must not write a result,
   observation, or provider receipt. Use one SQLite transaction for
   completion and all its local consequences.
3. Treat another scheduler's startup as **observation**, not a recovery
   authority. An unexpired heartbeat is advisory, and an expired lease is
   not proof of death. A confirmed-death or explicit operator recovery
   operation may quarantine ambiguous effects to UNKNOWN, but never
   re-dispatch them. If death cannot be proven, retain CLAIMED/PROCESSING
   and surface a blocked-recovery diagnostic.
4. Keep provider-authoritative reconciliation separate from worker
   recovery. Caller-supplied outcome strings are not authenticated
   provider evidence. Preserve the human STOP/approval and EUSS gates.
5. Legacy rows with missing owner/generation must fail closed. Document
   any operator recovery workflow before enabling migration or deployment.

### Required deterministic acceptance matrix

| Scenario | Required outcome |
| --- | --- |
| Worker A owns live CLAIMED effect; worker B initializes | A claim unchanged; B cannot dispatch |
| Worker A owns live PROCESSING cognition; B initializes | A item unchanged; B cannot pop it |
| A lease expires while A still runs | B cannot steal, quarantine, or replay |
| A completes with current owner/generation | One atomic result, observation and completion |
| A stale completion/release/failure arrives after generation changes | Zero mutation; explicit conflict |
| A is confirmed dead before provider ACK | Quarantine ambiguous effect; no replay |
| Provider execution outcome remains unknown | UNKNOWN persists until authoritative reconciliation |
| Provider confirms non-execution with auditable evidence | Controlled retry permitted, subject to governance |
| Old schema or unknown owner | Additive migration; fail closed until reconciled |

### Verification and rollback gate

Run `python -m pytest tests/test_issue19_outbox.py -q`,
`python -m pytest tests/test_cognitive_scheduler.py -q`, and
`python -m pytest tests/ -q`; require passing exact-head Python 3.10,
3.11, and 3.12 CI. Record commands and actual results. The existing
crash tests must be adjusted only to model **confirmed death explicitly**,
not to lower their no-replay assertions. Keep PR #22 draft and unmerged
until independent review and founder approval. Roll back a future code
change by reverting its draft-branch commit; do not reverse an applied
schema migration or alter production data without a separate approved plan.

**This appendix is a design/acceptance artifact only. It does not repair
the failing tests or establish production safety.**

## 2026-11-14: implementation-status reconciliation and remaining gate

**Evidence scope:** Inspected the exact draft branch source and PR #22 metadata on
2026-11-14. This corrects the historical 2026-11-12 heading above: the
startup-recovery mitigation is **implemented**, but the full ownership-fencing
acceptance contract is **not**. Historical failed-CI evidence remains historical.

- `PersistentCognitiveQueue.__init__` now only initializes the schema and
  outbox; it does **not** implicitly reset another live scheduler's
  PROCESSING/CLAIMED rows. This is a partial fix, not worker fencing.
- `recover_after_confirmed_shutdown(confirmed_terminated=True)` is an
  explicit operator-gated path. Its Boolean argument is a caller assertion,
  **not proof** that all old workers are dead. Its queue updates and the
  subsequent outbox-wide quarantine are separate transactions; do not
  advertise this as a single atomic recovery operation.
- `EffectOutbox.claim` still transitions only READY to CLAIMED atomically.
  `release_claim`, `mark_unknown`, `record_transient_failure`, and ordinary
  `_complete_with_conn` do not require a matching worker incarnation and
  claim generation. `_execute` derives worker_id from process-local
  `id(self)` and tick, which is not a durable fencing token.
- PR #22 head inspected: `b27ebba497fb710dab107b57f5c3cbc078fb2b3d`.
  Existing Python Core Tests workflow #43542729852 is recorded successful
  for that head; this addendum did **not** execute new tests or prove
  distributed worker safety.

**Next bounded code objective (not implemented by this documentation commit):**
add an incrementing durable claim generation and owner-incarnation field with
additive SQLite migration; return the claim token on acquisition; pass it
through all dispatch callback paths; enforce owner+generation in conditional
UPDATE predicates; require completion result/observation and outbox transition
to share one transaction; fail closed on missing legacy tokens. Add tests for
stale completion, release, transient failure, quarantine, live second worker,
expired lease, and legacy rows. Keep operator recovery and authenticated
provider reconciliation as separate review gates. Require targeted pytest,
full-suite checks and exact-head Python 3.10–3.12 CI before any merge.

**Approval:** draft only. Do not merge, deploy, change production schema, or
claim exactly-once external effects without independent review and explicit
founder approval. Documentation rollback: revert this addendum commit on the
draft branch; no production migration is involved.
