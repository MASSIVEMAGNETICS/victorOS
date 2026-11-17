"""Issue #19 crash-injection acceptance tests (deterministic, no real kill).

Every test here simulates a crash window without killing the process:
- crash before dispatch: an outbox claim is left held, then the queue is
  reopened (restart recovery) with no dispatch ever having run.
- crash after effect before ACK: ``scheduler.crash_hook`` raises
  BaseException after the provider dispatch and before the result commit.
- provider timeout: the registry raises TimeoutError, which physiology
  reports as a FAILED decision with that error type.

Fail-closed rule under test throughout: an UNKNOWN effect is never
auto-replayed. Only ``reconcile_effect()`` with a provider outcome moves
it, and a second dispatch after a confirmed execution must not happen.
"""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import mock

import pytest

from vos_core.cognitive_scheduler import (
    CognitiveItem,
    CognitiveScheduler,
    EffectOutbox,
    ItemKind,
    ItemStatus,
    PersistentCognitiveQueue,
    effect_id_for_candidate,
    stable_effect_id,
)
from vos_core.physiology import PhysiologyReceiptLedger, VictorPhysiologyRuntime
from vos_core.victor_cognition_stack import VictorCognitionStack


def runtime(tmp_path):
    stack = VictorCognitionStack(str(tmp_path / "victor_stack.db"))
    phys = VictorPhysiologyRuntime(
        receipt_ledger=PhysiologyReceiptLedger(str(tmp_path / "physiology.jsonl")),
        granted_authorities=("local_owner",),
    )
    return stack, phys, CognitiveScheduler(stack, phys, tmp_path / "victor_stack.db")


def restart(tmp_path, name="physiology2.jsonl"):
    stack = VictorCognitionStack(str(tmp_path / "victor_stack.db"))
    phys = VictorPhysiologyRuntime(
        receipt_ledger=PhysiologyReceiptLedger(str(tmp_path / name)),
        granted_authorities=("local_owner",),
    )
    scheduler = CognitiveScheduler(stack, phys, tmp_path / "victor_stack.db")
    # Test harness explicitly simulates a terminated prior process. Merely
    # opening a second instance must never trigger this recovery in production.
    scheduler.queue.recover_after_confirmed_shutdown(confirmed_terminated=True)
    return stack, phys, scheduler


def queue_claim_args(queue, item_id, worker_id=None):
    """Acquire a durable cognitive-queue claim token for a regression fixture."""
    claimed = queue.claim_item(item_id, worker_id=worker_id)
    assert claimed is not None
    return {
        "worker_id": claimed.worker_id,
        "claim_generation": claimed.claim_generation,
    }


def quarantine_queue_item(queue, item_id, worker_id=None):
    token = queue_claim_args(queue, item_id, worker_id=worker_id)
    assert queue.mark_claimed(item_id, ItemStatus.UNKNOWN, **token)
    return token


def candidate(text="outbox memory", source="source-1"):
    return {
        "capability": "memory.commit_reflection",
        "payload": {"text": text, "item_id": source},
        "score": 0.7,
        "source_item_id": source,
        "source_depth": 1,
    }


def counting_registry(scheduler):
    calls = []
    orig = scheduler.registry.execute

    def counting(capability, payload, idempotency_key=None):
        calls.append(idempotency_key)
        return orig(capability, payload, idempotency_key=idempotency_key)

    scheduler.registry.execute = counting
    return calls

def claim_args(outbox, effect_id, worker_id, lease_seconds=30, queue_claim_generation=None):
    """Acquire the exact outbox token, optionally bound to a queue claim."""
    token = outbox.claim_with_token(
        effect_id, worker_id, lease_seconds=lease_seconds,
        queue_claim_generation=queue_claim_generation,
    )
    assert token is not None
    return token


def _prepare_claimed_linked_effect(scheduler, item_id, worker_id="linked-worker"):
    """Create a PROCESSING action projection and its matching CLAIMED outbox row."""
    item = CognitiveItem(
        id=item_id,
        kind=ItemKind.ACTION_CANDIDATE,
        content={"candidate": candidate(source=item_id)},
        priority=0.8,
        depth=1,
        parent_id="source",
        created_tick=0,
    )
    assert scheduler.queue.push(item)
    queue_claim = scheduler.queue.claim_item(item_id, worker_id=worker_id)
    assert queue_claim is not None
    effect_id = stable_effect_id("memory.commit_reflection", item_id)
    scheduler.outbox.record_intent(
        effect_id,
        "memory.commit_reflection",
        item_id,
        "linked-test-digest",
        queue_item_id=item_id,
    )
    outbox_claim = claim_args(
        scheduler.outbox,
        effect_id,
        worker_id,
        queue_claim_generation=queue_claim.claim_generation,
    )
    return effect_id, queue_claim, outbox_claim


def test_stable_effect_id_and_payload_digest_conflict(tmp_path):
    _, _, s = runtime(tmp_path)
    cand = candidate()
    effect_id = effect_id_for_candidate(cand)
    assert effect_id == stable_effect_id("memory.commit_reflection", "source-1")
    assert effect_id == effect_id_for_candidate(candidate(text="different text"))

    # Same effect ID, different payload: the intent is rejected, nothing runs.
    s.outbox.record_intent(effect_id, cand["capability"], "source-1",
                           "digest-one", queue_item_id="q1")
    with pytest.raises(ValueError, match="different payload digest"):
        s.outbox.record_intent(effect_id, cand["capability"], "source-1",
                               "digest-two", queue_item_id="q1")
    # Same effect ID, same payload: idempotent, no duplicate record.
    again = s.outbox.record_intent(effect_id, cand["capability"], "source-1",
                                   "digest-one", queue_item_id="q1")
    assert again["effect_id"] == effect_id
    assert again["status"] == "READY"


def test_same_effect_executes_once_no_duplicate_external_effect(tmp_path):
    _, _, s = runtime(tmp_path)
    calls = counting_registry(s)
    cand = candidate()
    effect_id = effect_id_for_candidate(cand)

    first = s._execute([cand])
    assert first["status"] == "EXECUTED"
    assert first["executed"]["effect_id"] == effect_id
    assert first["executed"]["idempotency_key"] == effect_id
    assert calls == [effect_id]

    second = s._execute([cand])
    assert second == first
    assert calls == [effect_id]
    with s._conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM capability_results").fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM cognitive_queue WHERE kind=?",
            (ItemKind.OBSERVATION.value,)).fetchone()[0] == 1


def test_execute_with_conflicting_payload_is_rejected_without_dispatch(tmp_path):
    _, _, s = runtime(tmp_path)
    calls = counting_registry(s)
    assert s._execute([candidate()])["status"] == "EXECUTED"
    assert len(calls) == 1
    with pytest.raises(ValueError, match="different payload digest"):
        s._execute([candidate(text="a different reflection")])
    assert len(calls) == 1


def test_idempotency_key_is_passed_to_provider(tmp_path):
    _, _, s = runtime(tmp_path)
    calls = counting_registry(s)
    cand = candidate()
    s._execute([cand])
    assert calls == [effect_id_for_candidate(cand)]


def test_crash_before_dispatch_leaves_no_effect_and_safe_retry(tmp_path):
    _, _, s = runtime(tmp_path)
    calls = counting_registry(s)
    cand = candidate()
    effect_id = effect_id_for_candidate(cand)
    from vos_core.cognitive_scheduler import _payload_digest
    s.outbox.record_intent(effect_id, cand["capability"], "source-1",
                           _payload_digest(cand["payload"]))
    assert s.outbox.claim(effect_id, "worker-a", lease_seconds=30) is True
    # Simulated process kill before any dispatch: reopen the queue.
    _, _, restarted = restart(tmp_path)
    assert restarted.outbox.get(effect_id)["status"] == "UNKNOWN"
    assert calls == []
    # Still quarantined across another restart and across ticks.
    _, _, restarted2 = restart(tmp_path, "physiology3.jsonl")
    assert restarted2.outbox.get(effect_id)["status"] == "UNKNOWN"
    assert restarted2.run_until_quiescent(max_ticks=2)["ticks"] == 0
    assert calls == []
    # Provider confirms non-execution: safe retry executes exactly once.
    reconciled = restarted2.reconcile_effect(effect_id, "not_executed",
                                             provider_receipt="prov-none")
    assert reconciled["status"] == "READY"
    calls2 = counting_registry(restarted2)
    result = restarted2._execute([cand])
    assert result["status"] == "EXECUTED"
    assert calls2 == [effect_id]


def test_crash_after_effect_before_ack_quarantines_and_reconciles(tmp_path):
    _, _, s = runtime(tmp_path)
    calls = counting_registry(s)
    cand = candidate(text="crash after effect memory")
    effect_id = effect_id_for_candidate(cand)

    def crash(_effect_id):
        raise KeyboardInterrupt("simulated process kill after effect")

    s.crash_hook = crash
    with pytest.raises(KeyboardInterrupt):
        s._execute([cand])
    # The external effect happened exactly once, but no outcome was committed.
    assert calls == [effect_id]
    with s._conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM capability_results").fetchone()[0] == 0
    assert s.outbox.get(effect_id)["status"] == "CLAIMED"

    # Restart recovery quarantines the ambiguous effect; ticks never replay it.
    _, _, restarted = restart(tmp_path)
    assert restarted.outbox.get(effect_id)["status"] == "UNKNOWN"
    assert restarted.run_until_quiescent(max_ticks=2)["ticks"] == 0
    assert calls == [effect_id]
    with pytest.raises(RuntimeError, match="requires reconciliation"):
        restarted._execute([cand])
    assert calls == [effect_id]

    # Provider confirms execution: outcome recorded exactly once, idempotently.
    reconciled = restarted.reconcile_effect(effect_id, "executed",
                                            provider_receipt="prov-receipt-1")
    assert reconciled["status"] == "COMPLETED"
    assert reconciled["changed"] is True
    with restarted._conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM capability_results").fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM cognitive_queue WHERE kind=?",
            (ItemKind.OBSERVATION.value,)).fetchone()[0] == 1
    again = restarted.reconcile_effect(effect_id, "executed",
                                       provider_receipt="prov-receipt-1")
    assert again["changed"] is False
    stored = restarted._execute([cand])
    assert stored["status"] == "EXECUTED"
    assert calls == [effect_id]
    with restarted._conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM capability_results").fetchone()[0] == 1


def test_tick_crash_after_effect_reconciles_through_queue_claim(tmp_path):
    stack, phys, s = runtime(tmp_path)
    calls = counting_registry(s)
    s.publish_query("Victor tick crash recovery test.")
    s.tick(max_items=1)  # generates the follow-up thought
    s.crash_hook = lambda _eid: (_ for _ in ()).throw(
        KeyboardInterrupt("simulated kill in tick"))
    with pytest.raises(KeyboardInterrupt):
        s.tick(max_items=1)
    assert len(calls) == 1
    assert s.queue.unknown_count() == 1

    _, _, restarted = restart(tmp_path)
    assert restarted.queue.unknown_count() == 1
    report = restarted.run_until_quiescent(max_ticks=2)
    assert report["blocked_on_reconciliation"] is True
    assert len(calls) == 1

    effect_id = restarted.queue.unknown_effects()[0]["id"]
    # The unknown-effects inventory reports the queue item id, not the
    # effect id; resolve the outbox record through the queue linkage.
    with restarted._conn() as conn:
        row = conn.execute(
            "SELECT effect_id FROM effect_outbox WHERE queue_item_id=?",
            (effect_id,)).fetchone()
    assert row is not None
    reconciled = restarted.reconcile_effect(row["effect_id"], "executed",
                                            provider_receipt="prov-tick-1")
    assert reconciled["status"] == "COMPLETED"
    assert restarted.queue.unknown_count() == 0
    closed = restarted.run_until_quiescent(max_ticks=6, max_items=1)
    assert closed["quiescent"] is True
    assert len(calls) == 1


def test_two_worker_claim_race_only_one_dispatches(tmp_path):
    _, _, s = runtime(tmp_path)
    calls = counting_registry(s)
    cand = candidate()
    effect_id = effect_id_for_candidate(cand)
    from vos_core.cognitive_scheduler import _payload_digest
    s.outbox.record_intent(effect_id, cand["capability"], "source-1",
                           _payload_digest(cand["payload"]))
    assert s.outbox.claim(effect_id, "worker-a") is True
    assert s.outbox.claim(effect_id, "worker-b") is False
    blocked = s._execute([cand])
    assert blocked["status"] == "BLOCKED_CLAIMED"
    assert calls == []
    # Lease expiry is not proof that worker A's provider call stopped.
    # A second worker must not reclaim or dispatch an ambiguous effect.
    assert s.outbox.claim(effect_id, "worker-b", lease_seconds=0) is False
    with s._conn() as conn:
        conn.execute("UPDATE effect_outbox SET lease_expires_at='2000-01-01T00:00:00+00:00' "
                     "WHERE effect_id=?", (effect_id,))
    assert s.outbox.claim(effect_id, "worker-b") is False
    assert s._execute([cand])["status"] == "BLOCKED_CLAIMED"
    assert calls == []
    assert s.outbox.get(effect_id)["worker_id"] == "worker-a"

    # Restart quarantines the abandoned claim; no worker may replay it
    # without explicit reconciliation of the provider outcome.
    _, _, recovered = restart(tmp_path)
    assert recovered.outbox.get(effect_id)["status"] == "UNKNOWN"
    assert recovered.outbox.claim(effect_id, "worker-b") is False
    with pytest.raises(RuntimeError, match="requires reconciliation"):
        recovered._execute([cand])
    assert calls == []


def test_concurrent_workers_only_one_atomic_claim_succeeds(tmp_path):
    """Two independently opened workers race; SQLite grants exactly one claim."""
    db_path = tmp_path / "concurrent-claims.db"
    worker_a = EffectOutbox(db_path)
    worker_b = EffectOutbox(db_path)
    effect_id = stable_effect_id("memory.commit_reflection", "concurrent-claim")
    worker_a.record_intent(
        effect_id, "memory.commit_reflection", "concurrent-claim", "digest"
    )

    start = Barrier(3)

    def claim(outbox, worker_id):
        start.wait(timeout=10)
        return outbox.claim_with_token(effect_id, worker_id)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            "worker-a": executor.submit(claim, worker_a, "worker-a"),
            "worker-b": executor.submit(claim, worker_b, "worker-b"),
        }
        # Release both workers only after both have reached the same barrier.
        start.wait(timeout=10)
        results = {worker_id: future.result(timeout=15)
                   for worker_id, future in futures.items()}

    winners = [(worker_id, token) for worker_id, token in results.items()
               if token is not None]
    assert len(winners) == 1
    winner_id, token = winners[0]
    assert token == {"worker_id": winner_id, "claim_generation": 1}
    assert results["worker-b" if winner_id == "worker-a" else "worker-a"] is None

    stored = worker_a.get(effect_id)
    assert stored["status"] == "CLAIMED"
    assert stored["worker_id"] == winner_id
    assert stored["attempts"] == 1
    assert stored["claim_generation"] == 1


def test_provider_timeout_is_ambiguous_not_terminal(tmp_path):
    _, _, s = runtime(tmp_path)
    calls = counting_registry(s)
    cand = candidate()
    effect_id = effect_id_for_candidate(cand)

    def timeout_provider(capability, payload, idempotency_key=None):
        calls.append(idempotency_key)
        raise TimeoutError("provider did not answer")

    real_execute = s.registry.execute
    s.registry.execute = timeout_provider
    with pytest.raises(RuntimeError, match="ambiguous provider failure"):
        s._execute([cand])
    assert s.outbox.get(effect_id)["status"] == "UNKNOWN"
    with s._conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM capability_results").fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM cognitive_queue WHERE kind=?",
            (ItemKind.OBSERVATION.value,)).fetchone()[0] == 0
    # Provider confirms non-execution; a safe retry with the real provider
    # executes exactly once.
    calls.clear()
    s.registry.execute = real_execute
    calls2 = counting_registry(s)
    reconciled = s.reconcile_effect(effect_id, "not_executed",
                                    provider_receipt="prov-timeout-none")
    assert reconciled["status"] == "READY"
    assert s._execute([cand])["status"] == "EXECUTED"
    assert calls2 == [effect_id]


def test_result_observation_and_outbox_rollback_together(tmp_path):
    _, _, s = runtime(tmp_path)
    cand = candidate(text="atomic observation test", source="source")
    effect_id = effect_id_for_candidate(cand)
    with mock.patch.object(
        s.queue, "_insert_with_conn", side_effect=RuntimeError("forced observation failure")
    ):
        with pytest.raises(RuntimeError, match="forced observation failure"):
            s._execute([cand])
    with s._conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM capability_results").fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM cognitive_queue WHERE kind=?",
            (ItemKind.OBSERVATION.value,)).fetchone()[0] == 0
    # The outbox completion rolled back with the result: still CLAIMED,
    # so restart recovery quarantines it instead of claiming success.
    assert s.outbox.get(effect_id)["status"] == "CLAIMED"
    _, _, restarted = restart(tmp_path)
    assert restarted.outbox.get(effect_id)["status"] == "UNKNOWN"


def test_retry_budget_reaches_dlq_and_stops_claims(tmp_path):
    _, _, s = runtime(tmp_path)
    cand = candidate()
    effect_id = effect_id_for_candidate(cand)
    from vos_core.cognitive_scheduler import _payload_digest
    s.outbox.record_intent(effect_id, cand["capability"], "source-1",
                           _payload_digest(cand["payload"]))
    token = claim_args(s.outbox, effect_id, "worker-a")
    first = s.outbox.record_transient_failure(effect_id, "provider 503", **token)
    assert first["status"] == "READY"
    assert first["attempts"] == 1
    token = claim_args(s.outbox, effect_id, "worker-a")
    second = s.outbox.record_transient_failure(effect_id, "provider 503", **token)
    assert second["status"] == "READY"
    assert second["attempts"] == 2
    token = claim_args(s.outbox, effect_id, "worker-a")
    last = s.outbox.record_transient_failure(effect_id, "provider 503", **token)
    assert last["status"] == "FAILED"
    assert last["attempts"] == 3
    assert s.outbox.claim(effect_id, "worker-a") is False
    assert s._execute([cand])["status"] == "BLOCKED_DLQ"
    with pytest.raises(KeyError):
        s.outbox.record_transient_failure("eff_does-not-exist", "x")


def test_reconcile_unknown_outcome_changes_nothing(tmp_path):
    _, _, s = runtime(tmp_path)
    cand = candidate()
    effect_id = effect_id_for_candidate(cand)
    from vos_core.cognitive_scheduler import _payload_digest
    s.outbox.record_intent(effect_id, cand["capability"], "source-1",
                           _payload_digest(cand["payload"]))
    s.outbox.claim(effect_id, "worker-a")
    _, _, restarted = restart(tmp_path)
    result = restarted.reconcile_effect(effect_id, "unknown")
    assert result["changed"] is False
    assert result["status"] == "UNKNOWN"
    with pytest.raises(ValueError):
        restarted.reconcile_effect(effect_id, "maybe")
    with pytest.raises(KeyError):
        restarted.reconcile_effect("eff_does-not-exist", "executed")


def test_completed_effect_cannot_be_contradicted(tmp_path):
    _, _, s = runtime(tmp_path)
    cand = candidate()
    effect_id = effect_id_for_candidate(cand)
    assert s._execute([cand])["status"] == "EXECUTED"
    with pytest.raises(ValueError, match="already recorded COMPLETED"):
        s.reconcile_effect(effect_id, "not_executed")


def test_generic_mark_still_cannot_clear_quarantine(tmp_path):
    _, _, s = runtime(tmp_path)
    queue = PersistentCognitiveQueue(tmp_path / "queue.db")
    assert queue.push(CognitiveItem(
        id="quarantined-effect", kind=ItemKind.ACTION_CANDIDATE,
        content={"candidate": {"capability": "memory.commit_reflection"}},
        priority=0.8, depth=1, parent_id="source", created_tick=0,
    ))
    quarantine_queue_item(queue, "quarantined-effect")
    for unsafe in (ItemStatus.PENDING, ItemStatus.COMPLETED):
        with pytest.raises(ValueError, match="requires explicit reconciliation"):
            queue.mark("quarantined-effect", unsafe)
    # Only the explicit reconciliation path may resolve it.
    queue.reconcile_mark("quarantined-effect", ItemStatus.PENDING)
    assert queue.pending_count() == 1


@pytest.mark.parametrize("state", ["READY", "CLAIMED", "FAILED"])
@pytest.mark.parametrize("outcome", ["executed", "not_executed"])
def test_reconciliation_cannot_override_non_unknown_state(tmp_path, state, outcome):
    """Only quarantined effects may be reconciled, even with a supplied receipt."""
    _, _, scheduler = runtime(tmp_path)
    effect_id = stable_effect_id("memory.commit_reflection", f"state-{state}")
    scheduler.outbox.record_intent(
        effect_id, "memory.commit_reflection", f"state-{state}", "digest")
    if state in ("CLAIMED", "FAILED"):
        assert scheduler.outbox.claim(effect_id, "worker-a")
    if state == "FAILED":
        with scheduler.outbox._conn() as conn:
            conn.execute(
                "UPDATE effect_outbox SET status='FAILED' WHERE effect_id=?",
                (effect_id,))
    before = scheduler.outbox.get(effect_id)
    with pytest.raises(ValueError, match="only UNKNOWN effects may transition"):
        scheduler.outbox.reconcile(
            effect_id, outcome, provider_receipt="unverified-receipt")
    assert scheduler.outbox.get(effect_id) == before


def test_unknown_reconciliation_transitions_once(tmp_path):
    _, _, scheduler = runtime(tmp_path)
    effect_id = stable_effect_id("memory.commit_reflection", "once")
    scheduler.outbox.record_intent(
        effect_id, "memory.commit_reflection", "once", "digest")
    token = claim_args(scheduler.outbox, effect_id, "worker-a")
    assert scheduler.outbox.mark_unknown(effect_id, "timeout", **token)
    result = scheduler.outbox.reconcile(
        effect_id, "not_executed", provider_receipt="provider-confirmed-none")
    assert result["status"] == "READY"
    assert result["changed"] is True
    with pytest.raises(ValueError, match="only UNKNOWN effects may transition"):
        scheduler.outbox.reconcile(
            effect_id, "not_executed", provider_receipt="duplicate")
    assert scheduler.outbox.get(effect_id)["status"] == "READY"


@pytest.mark.parametrize("terminal_state", ["READY", "UNKNOWN", "FAILED", "COMPLETED"])
def test_transient_failure_cannot_resurrect_non_claimed_effect(tmp_path, terminal_state):
    """Late failure callbacks cannot mutate a released or terminal generation."""
    _, _, scheduler = runtime(tmp_path)
    effect_id = stable_effect_id("memory.commit_reflection", terminal_state)
    scheduler.outbox.record_intent(
        effect_id, "memory.commit_reflection", terminal_state, "digest")
    token = claim_args(scheduler.outbox, effect_id, "worker-a")
    if terminal_state == "READY":
        assert scheduler.outbox.release_claim(effect_id, **token)
    elif terminal_state == "UNKNOWN":
        assert scheduler.outbox.mark_unknown(effect_id, "ambiguous", **token)
    elif terminal_state == "FAILED":
        with scheduler.outbox._conn() as conn:
            conn.execute("UPDATE effect_outbox SET status='FAILED' WHERE effect_id=?",
                         (effect_id,))
    else:
        assert scheduler.outbox.complete(
            effect_id, {"ok": True}, "obs-terminal", **token)
    before = scheduler.outbox.get(effect_id)
    with pytest.raises(ValueError, match="stale or no longer CLAIMED"):
        scheduler.outbox.record_transient_failure(
            effect_id, "late failure", **token)
    assert scheduler.outbox.get(effect_id) == before


def test_live_second_instance_does_not_quarantine_first_worker_claim(tmp_path):
    """A new queue object is not evidence that an existing worker died.

    Regression for multi-instance startup: the first worker retains its live
    outbox claim until an explicit, ownership-aware recovery decision.
    """
    _, _, first = runtime(tmp_path)
    effect_id = stable_effect_id("memory.commit_reflection", "live-instance")
    first.outbox.record_intent(
        effect_id, "memory.commit_reflection", "live-instance", "digest")
    assert first.outbox.claim(effect_id, "worker-a", lease_seconds=300)
    before = first.outbox.get(effect_id)
    assert before["status"] == "CLAIMED"
    assert before["worker_id"] == "worker-a"

    # This is a concurrent instance, not a simulated process crash.
    second = PersistentCognitiveQueue(tmp_path / "victor_stack.db")
    after = second.outbox.get(effect_id)
    assert after["status"] == "CLAIMED"
    assert after["worker_id"] == "worker-a"
    assert second.outbox.claim(effect_id, "worker-b") is False


def test_live_second_instance_does_not_reset_processing_cognition(tmp_path):
    """Initialization must not hand live PROCESSING cognition to worker B."""
    first = PersistentCognitiveQueue(tmp_path / "queue-live.db")
    assert first.push(CognitiveItem(
        id="live-thought", kind=ItemKind.THOUGHT,
        content={"text": "in progress"}, priority=0.8,
        depth=0, parent_id=None, created_tick=0))
    claimed = first.pop_budgeted(current_tick=0, max_items=1)
    assert len(claimed) == 1
    assert claimed[0].id == "live-thought"
    assert claimed[0].status == ItemStatus.PROCESSING

    # A separate instance cannot infer worker death merely by starting.
    second = PersistentCognitiveQueue(tmp_path / "queue-live.db")
    assert second.pop_budgeted(current_tick=0, max_items=1) == []
    with first._conn() as conn:
        status = conn.execute(
            "SELECT status FROM cognitive_queue WHERE id=?",
            ("live-thought",)).fetchone()["status"]
    assert status == ItemStatus.PROCESSING.value


def test_recovery_requires_explicit_termination_authority(tmp_path):
    queue = PersistentCognitiveQueue(tmp_path / "recovery-guard.db")
    with pytest.raises(PermissionError, match="confirmed termination"):
        queue.recover_after_confirmed_shutdown()
    with pytest.raises(PermissionError, match="confirmed termination"):
        queue.recover_after_confirmed_shutdown(confirmed_terminated=False)


def test_outbox_recovery_requires_explicit_termination_authority(tmp_path):
    outbox = EffectOutbox(tmp_path / "outbox-recovery-guard.db")
    effect_id = stable_effect_id("memory.commit_reflection", "outbox-recovery-guard")
    outbox.record_intent(
        effect_id, "memory.commit_reflection", "outbox-recovery-guard", "digest"
    )
    assert outbox.claim(effect_id, "worker-a")
    before = outbox.get(effect_id)

    with pytest.raises(PermissionError, match="confirmed termination"):
        outbox.recover_claimed_to_unknown()
    with pytest.raises(PermissionError, match="confirmed termination"):
        outbox.recover_claimed_to_unknown(confirmed_terminated=False)

    assert outbox.get(effect_id) == before


def test_standalone_outbox_recovery_quarantines_only_after_confirmation(tmp_path):
    outbox = EffectOutbox(tmp_path / "standalone-outbox-recovery.db")
    effect_id = stable_effect_id("memory.commit_reflection", "standalone-recovery")
    outbox.record_intent(
        effect_id, "memory.commit_reflection", "standalone-recovery", "digest"
    )
    assert outbox.claim(effect_id, "terminated-worker")

    assert outbox.recover_claimed_to_unknown(confirmed_terminated=True) == 1
    recovered = outbox.get(effect_id)
    assert recovered["status"] == "UNKNOWN"
    assert recovered["worker_id"] is None


def test_outbox_recovery_refuses_linked_claims_outside_queue_transaction(tmp_path):
    path = tmp_path / "linked-outbox-recovery.db"
    queue = PersistentCognitiveQueue(path)
    item_id = "linked-outbox-recovery"
    assert queue.push(CognitiveItem(
        id=item_id,
        kind=ItemKind.ACTION_CANDIDATE,
        content={"candidate": candidate(source=item_id)},
        priority=0.8,
        depth=1,
        parent_id="source",
        created_tick=0,
    ))
    queue_claim = queue.claim_item(item_id, worker_id="worker-a")
    assert queue_claim is not None

    effect_id = stable_effect_id("memory.commit_reflection", item_id)
    queue.outbox.record_intent(
        effect_id,
        "memory.commit_reflection",
        item_id,
        "digest",
        queue_item_id=item_id,
    )
    assert queue.outbox.claim(
        effect_id, "worker-a",
        queue_claim_generation=queue_claim.claim_generation,
    )

    with pytest.raises(RuntimeError, match="recover_after_confirmed_shutdown"):
        queue.outbox.recover_claimed_to_unknown(confirmed_terminated=True)

    assert queue.outbox.get(effect_id)["status"] == "CLAIMED"
    with queue._conn() as conn:
        queue_row = conn.execute(
            "SELECT status,worker_id,claim_generation FROM cognitive_queue WHERE id=?",
            (item_id,),
        ).fetchone()
    assert queue_row["status"] == ItemStatus.PROCESSING.value
    assert queue_row["worker_id"] == queue_claim.worker_id
    assert queue_row["claim_generation"] == queue_claim.claim_generation


def test_explicit_recovery_quarantines_claims_and_requeues_cognition(tmp_path):
    path = tmp_path / "recovery-guard.db"
    first = PersistentCognitiveQueue(path)
    assert first.push(CognitiveItem(
        id="recover-thought", kind=ItemKind.THOUGHT,
        content={"text": "recover"}, priority=0.7, depth=0,
        parent_id=None, created_tick=0))
    assert len(first.pop_budgeted(current_tick=0, max_items=1)) == 1
    effect_id = stable_effect_id("memory.commit_reflection", "recover")
    first.outbox.record_intent(effect_id, "memory.commit_reflection", "recover", "digest")
    assert first.outbox.claim(effect_id, "terminated-worker")
    second = PersistentCognitiveQueue(path)
    assert second.outbox.get(effect_id)["status"] == "CLAIMED"
    assert second.pending_count() == 0
    receipt = second.recover_after_confirmed_shutdown(confirmed_terminated=True)
    assert receipt == {"quarantined_actions": 0, "requeued_cognition": 1,
                       "quarantined_effects": 1}
    assert second.outbox.get(effect_id)["status"] == "UNKNOWN"
    assert second.pending_count() == 1
    assert second.outbox.claim(effect_id, "replacement-worker") is False


def test_expired_lease_does_not_authorize_another_worker_claim(tmp_path):
    """A timeout is not proof that the first provider dispatch stopped."""
    outbox = EffectOutbox(tmp_path / "lease-safety.db")
    effect_id = stable_effect_id("memory.commit_reflection", "expired-lease")
    outbox.record_intent(effect_id, "memory.commit_reflection", "expired-lease", "digest")
    assert outbox.claim(effect_id, "worker-original", lease_seconds=1)
    with outbox._conn() as conn:
        conn.execute(
            "UPDATE effect_outbox SET lease_expires_at=? WHERE effect_id=?",
            ("2000-01-01T00:00:00+00:00", effect_id),
        )
    before = outbox.get(effect_id)
    assert before["status"] == "CLAIMED"
    assert outbox.claim(effect_id, "worker-replacement") is False
    assert outbox.get(effect_id) == before


def test_expired_claim_recovery_quarantines_before_any_retry(tmp_path):
    """Even an expired claim must pass explicit shutdown and reconciliation."""
    path = tmp_path / "expired-recovery.db"
    original = PersistentCognitiveQueue(path)
    effect_id = stable_effect_id("memory.commit_reflection", "expired-recovery")
    original.outbox.record_intent(
        effect_id, "memory.commit_reflection", "expired-recovery", "digest"
    )
    assert original.outbox.claim(effect_id, "worker-original", lease_seconds=1)
    with original.outbox._conn() as conn:
        conn.execute(
            "UPDATE effect_outbox SET lease_expires_at=? WHERE effect_id=?",
            ("2000-01-01T00:00:00+00:00", effect_id),
        )
    replacement = PersistentCognitiveQueue(path)
    assert replacement.outbox.get(effect_id)["status"] == "CLAIMED"
    assert replacement.outbox.claim(effect_id, "worker-replacement") is False
    recovery = replacement.recover_after_confirmed_shutdown(
        confirmed_terminated=True
    )
    assert recovery["quarantined_effects"] == 1
    assert replacement.outbox.get(effect_id)["status"] == "UNKNOWN"
    assert replacement.outbox.claim(effect_id, "worker-replacement") is False


def test_direct_completion_requires_active_claim_and_preserves_quarantine(tmp_path):
    """Completion requires a fencing token and cannot clear UNKNOWN."""
    outbox = EffectOutbox(tmp_path / "completion-guard.db")
    effect_id = stable_effect_id("memory.commit_reflection", "completion-guard")
    outbox.record_intent(
        effect_id, "memory.commit_reflection", "completion-guard", "digest"
    )
    before = outbox.get(effect_id)
    with pytest.raises(ValueError, match="worker_id is required"):
        outbox.complete(effect_id, {"ok": True}, "obs-unclaimed")
    assert outbox.get(effect_id) == before

    token = claim_args(outbox, effect_id, "worker-original")
    assert outbox.mark_unknown(effect_id, "provider timeout", **token)
    quarantined = outbox.get(effect_id)
    assert outbox.complete(effect_id, {"ok": True}, "obs-stale", **token) is False
    assert outbox.get(effect_id) == quarantined

    reconciled = outbox.reconcile(
        effect_id, "executed", provider_receipt="operator-supplied-receipt"
    )
    assert reconciled["status"] == "COMPLETED"
    assert outbox.complete(effect_id, {"ok": True}, "obs-duplicate", **token) is False


def test_dispatch_completion_state_change_rolls_back_result_and_observation(tmp_path):
    """A callback cannot report success if its claim was quarantined mid-flight."""
    _, _, scheduler = runtime(tmp_path)
    cand = candidate(source="completion-race")
    effect_id = effect_id_for_candidate(cand)

    def quarantine_before_commit(dispatched_effect_id):
        assert dispatched_effect_id == effect_id
        row = scheduler.outbox.get(effect_id)
        assert scheduler.outbox.mark_unknown(
            effect_id, "simulated concurrent recovery",
            worker_id=row["worker_id"], claim_generation=row["claim_generation"])

    scheduler.crash_hook = quarantine_before_commit
    with pytest.raises(RuntimeError, match="claim changed before completion"):
        scheduler._execute([cand])
    assert scheduler.outbox.get(effect_id)["status"] == "UNKNOWN"
    with scheduler._conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM capability_results").fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM cognitive_queue WHERE kind=?",
            (ItemKind.OBSERVATION.value,),
        ).fetchone()[0] == 0


def test_unclaimed_intent_cannot_be_quarantined_by_stale_callback(tmp_path):
    """A callback without the current owner/generation cannot quarantine an intent."""
    outbox = EffectOutbox(tmp_path / "unknown-guard.db")
    effect_id = stable_effect_id("memory.commit_reflection", "unknown-guard")
    outbox.record_intent(
        effect_id, "memory.commit_reflection", "unknown-guard", "digest"
    )
    before = outbox.get(effect_id)
    assert outbox.mark_unknown(
        effect_id, "stale callback", worker_id="worker-current",
        claim_generation=1) is False
    assert outbox.get(effect_id) == before
    token = claim_args(outbox, effect_id, "worker-current")
    assert outbox.mark_unknown(effect_id, "provider timeout", **token) is True
    assert outbox.get(effect_id)["status"] == "UNKNOWN"


def test_stale_claim_generation_cannot_mutate_reacquired_claim(tmp_path):
    """The same owner cannot use an earlier generation after release/reclaim."""
    outbox = EffectOutbox(tmp_path / "generation-fence.db")
    effect_id = stable_effect_id("memory.commit_reflection", "generation-fence")
    outbox.record_intent(
        effect_id, "memory.commit_reflection", "generation-fence", "digest"
    )
    first = claim_args(outbox, effect_id, "same-worker")
    assert outbox.release_claim(effect_id, **first) is True

    second = claim_args(outbox, effect_id, "same-worker")
    assert second["claim_generation"] == first["claim_generation"] + 1
    before = outbox.get(effect_id)

    assert outbox.release_claim(effect_id, **first) is False
    assert outbox.mark_unknown(effect_id, "late timeout", **first) is False
    assert outbox.complete(effect_id, {"ok": True}, "obs-stale", **first) is False
    with pytest.raises(ValueError, match="stale or no longer CLAIMED"):
        outbox.record_transient_failure(effect_id, "late failure", **first)
    assert outbox.get(effect_id) == before

    assert outbox.mark_unknown(effect_id, "current timeout", **second) is True
    assert outbox.get(effect_id)["status"] == "UNKNOWN"


def test_legacy_outbox_schema_adds_claim_generation_without_losing_rows(tmp_path):
    """Existing databases gain the fencing column additively and fail closed."""
    path = tmp_path / "legacy-outbox.db"
    effect_id = stable_effect_id("memory.commit_reflection", "legacy-row")
    with sqlite3.connect(path) as conn:
        conn.execute("""
            CREATE TABLE effect_outbox(
                effect_id TEXT PRIMARY KEY,
                capability TEXT NOT NULL,
                source_item_id TEXT,
                queue_item_id TEXT,
                payload_digest TEXT NOT NULL,
                idempotency_key TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 3,
                worker_id TEXT,
                lease_expires_at TEXT,
                result_json TEXT,
                observation_event_id TEXT UNIQUE,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute(
            "CREATE INDEX idx_outbox_status ON effect_outbox(status, created_at ASC)"
        )
        conn.execute("""
            INSERT INTO effect_outbox(
                effect_id, capability, source_item_id, queue_item_id,
                payload_digest, idempotency_key, status, attempts,
                max_attempts, created_at, updated_at
            ) VALUES(?,?,?,?,?,?,'READY',0,3,?,?)
        """, (effect_id, "memory.commit_reflection", "legacy-row", None,
              "digest", effect_id, "2026-11-14T00:00:00+00:00",
              "2026-11-14T00:00:00+00:00"))

    outbox = EffectOutbox(path)
    legacy = outbox.get(effect_id)
    assert legacy is not None
    assert legacy["claim_generation"] == 0
    token = outbox.claim_with_token(effect_id, "legacy-worker")
    assert token == {"worker_id": "legacy-worker", "claim_generation": 1}
    with outbox._conn() as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(effect_outbox)")}
    assert "claim_generation" in columns


@pytest.mark.parametrize("replacement_worker", ["worker-a", "worker-b"])
def test_cognitive_queue_claim_generation_fences_stale_callback_after_recovery(
    tmp_path, replacement_worker
):
    path = tmp_path / "queue-generation.db"
    first = PersistentCognitiveQueue(path)
    assert first.push(CognitiveItem(
        id="queue-generation-item", kind=ItemKind.THOUGHT,
        content={"text": "generation fence"}, priority=0.8,
        depth=0, parent_id=None, created_tick=0,
    ))
    old = first.claim_item("queue-generation-item", worker_id="worker-a")
    assert old is not None
    assert old.claim_generation == 1

    second = PersistentCognitiveQueue(path)
    recovery = second.recover_after_confirmed_shutdown(confirmed_terminated=True)
    assert recovery["requeued_cognition"] == 1
    current = second.claim_item("queue-generation-item", worker_id=replacement_worker)
    assert current is not None
    assert current.claim_generation == old.claim_generation + 1

    old_token = {"worker_id": old.worker_id, "claim_generation": old.claim_generation}
    current_token = {
        "worker_id": current.worker_id,
        "claim_generation": current.claim_generation,
    }
    assert first.mark_claimed(
        "queue-generation-item", ItemStatus.COMPLETED, **old_token
    ) is False
    with second._conn() as conn:
        row = conn.execute(
            "SELECT status,worker_id,claim_generation FROM cognitive_queue WHERE id=?",
            ("queue-generation-item",),
        ).fetchone()
    assert row["status"] == ItemStatus.PROCESSING.value
    assert row["worker_id"] == replacement_worker
    assert row["claim_generation"] == current.claim_generation
    assert second.mark_claimed(
        "queue-generation-item", ItemStatus.COMPLETED, **current_token
    ) is True


def test_cognitive_queue_legacy_schema_adds_fencing_columns_without_losing_rows(tmp_path):
    path = tmp_path / "legacy-queue.db"
    with sqlite3.connect(path) as conn:
        conn.execute("""
            CREATE TABLE cognitive_queue(
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                content_json TEXT NOT NULL,
                priority REAL NOT NULL,
                depth INTEGER NOT NULL,
                parent_id TEXT,
                created_tick INTEGER NOT NULL,
                ttl INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            INSERT INTO cognitive_queue(
                id,kind,content_json,priority,depth,parent_id,created_tick,ttl,
                status,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """, ("legacy-thought", "THOUGHT", '{"text":"preserve"}', 0.7, 0,
              None, 0, 50, "PENDING", "2026-11-14T00:00:00+00:00",
              "2026-11-14T00:00:00+00:00"))

    queue = PersistentCognitiveQueue(path)
    with queue._conn() as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(cognitive_queue)")}
        row = conn.execute(
            "SELECT * FROM cognitive_queue WHERE id='legacy-thought'"
        ).fetchone()
    assert {"worker_id", "claim_generation"} <= columns
    assert row["content_json"] == '{"text":"preserve"}'
    assert row["worker_id"] is None
    assert row["claim_generation"] == 0
    claimed = queue.claim_item("legacy-thought", worker_id="legacy-worker")
    assert claimed is not None
    assert claimed.claim_generation == 1


def test_generic_mark_cannot_mutate_processing_without_claim_token(tmp_path):
    queue = PersistentCognitiveQueue(tmp_path / "queue-mark-fence.db")
    assert queue.push(CognitiveItem(
        id="live-claim", kind=ItemKind.THOUGHT, content={"text": "live"},
        priority=0.5, depth=0, parent_id=None, created_tick=0,
    ))
    claim = queue.claim_item("live-claim", worker_id="owner-a")
    assert claim is not None
    with pytest.raises(PermissionError, match="worker_id and claim_generation"):
        queue.mark("live-claim", ItemStatus.COMPLETED)
    assert queue.mark_claimed(
        "live-claim", ItemStatus.COMPLETED,
        worker_id="owner-b", claim_generation=claim.claim_generation
    ) is False
    assert queue.mark_claimed(
        "live-claim", ItemStatus.COMPLETED,
        worker_id=claim.worker_id, claim_generation=claim.claim_generation
    ) is True


def test_completed_outbox_reconciliation_repairs_unknown_queue_projection(tmp_path):
    _, _, scheduler = runtime(tmp_path)
    effect_id = stable_effect_id("memory.commit_reflection", "completed-queue-repair")
    assert scheduler.queue.push(CognitiveItem(
        id="completed-queue-repair", kind=ItemKind.ACTION_CANDIDATE,
        content={"candidate": candidate(source="completed-queue-repair")},
        priority=0.8, depth=1, parent_id="source", created_tick=0,
    ))
    scheduler.outbox.record_intent(
        effect_id, "memory.commit_reflection", "completed-queue-repair",
        "digest", queue_item_id="completed-queue-repair"
    )
    queue_claim = scheduler.queue.claim_item(
        "completed-queue-repair", worker_id="worker-a"
    )
    assert queue_claim is not None
    token = claim_args(
        scheduler.outbox, effect_id, "worker-a",
        queue_claim_generation=queue_claim.claim_generation,
    )
    # Construct the legacy split-projection state directly: public wrappers
    # now reject this one-table completion for linked effects.
    with scheduler._conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        assert EffectOutbox._complete_with_conn(
            conn,
            effect_id,
            {"executed": {"ok": True}, "status": "EXECUTED"},
            "observation-completed-repair",
            worker_id=token["worker_id"],
            claim_generation=token["claim_generation"],
        )
        conn.execute(
            "UPDATE cognitive_queue SET status=?,worker_id=NULL WHERE id=?",
            (ItemStatus.UNKNOWN.value, "completed-queue-repair"),
        )
    result = scheduler.reconcile_effect(effect_id, "executed")
    assert result["changed"] is False
    with scheduler._conn() as conn:
        row = conn.execute(
            "SELECT status FROM cognitive_queue WHERE id=?",
            ("completed-queue-repair",)
        ).fetchone()
    assert row["status"] == ItemStatus.COMPLETED.value


def test_action_candidate_stale_callback_cannot_mutate_reconciled_new_claim(tmp_path):
    path = tmp_path / "action-queue-generation.db"
    first = PersistentCognitiveQueue(path)
    assert first.push(CognitiveItem(
        id="action-generation-item", kind=ItemKind.ACTION_CANDIDATE,
        content={"candidate": candidate(source="action-generation-item")},
        priority=0.9, depth=1, parent_id="source", created_tick=0,
    ))
    old = first.claim_item("action-generation-item", worker_id="worker-a")
    assert old is not None
    assert old.claim_generation == 1

    second = PersistentCognitiveQueue(path)
    recovery = second.recover_after_confirmed_shutdown(confirmed_terminated=True)
    assert recovery["quarantined_actions"] == 1
    second.reconcile_mark("action-generation-item", ItemStatus.PENDING)
    current = second.claim_item("action-generation-item", worker_id="worker-b")
    assert current is not None
    assert current.claim_generation == old.claim_generation + 1

    assert first.mark_claimed(
        "action-generation-item", ItemStatus.COMPLETED,
        worker_id=old.worker_id, claim_generation=old.claim_generation
    ) is False
    with second._conn() as conn:
        row = conn.execute(
            "SELECT status,worker_id,claim_generation FROM cognitive_queue WHERE id=?",
            ("action-generation-item",),
        ).fetchone()
    assert row["status"] == ItemStatus.PROCESSING.value
    assert row["worker_id"] == "worker-b"
    assert row["claim_generation"] == current.claim_generation
    assert second.mark_claimed(
        "action-generation-item", ItemStatus.COMPLETED,
        worker_id=current.worker_id, claim_generation=current.claim_generation
    ) is True

def test_confirmed_shutdown_recovery_is_atomic_across_queue_and_outbox(tmp_path):
    _, _, scheduler = runtime(tmp_path)
    item_id = "atomic-recovery-action"
    item = CognitiveItem(
        id=item_id,
        kind=ItemKind.ACTION_CANDIDATE,
        content={"candidate": candidate(source=item_id)},
        priority=0.9,
        depth=1,
        parent_id="source",
        created_tick=0,
    )
    assert scheduler.queue.push(item)
    queue_claim = scheduler.queue.claim_item(item_id, worker_id="worker-a")
    assert queue_claim is not None

    thought_id = "atomic-recovery-thought"
    thought = CognitiveItem(
        id=thought_id,
        kind=ItemKind.THOUGHT,
        content={"text": "recovery thought"},
        priority=0.4,
        depth=0,
        parent_id=None,
        created_tick=0,
    )
    assert scheduler.queue.push(thought)
    thought_claim = scheduler.queue.claim_item(thought_id, worker_id="worker-a")
    assert thought_claim is not None

    effect_id = stable_effect_id("memory.commit_reflection", item_id)
    scheduler.outbox.record_intent(
        effect_id,
        "memory.commit_reflection",
        item_id,
        "atomic-recovery-digest",
        queue_item_id=item_id,
    )
    effect_claim = claim_args(
        scheduler.outbox, effect_id, "worker-a",
        queue_claim_generation=queue_claim.claim_generation,
    )

    def fail_outbox_recovery(conn):
        raise RuntimeError("simulated outbox quarantine failure")

    with mock.patch.object(
        EffectOutbox,
        "_recover_claimed_to_unknown_with_conn",
        side_effect=fail_outbox_recovery,
    ):
        with pytest.raises(RuntimeError, match="simulated outbox quarantine failure"):
            scheduler.queue.recover_after_confirmed_shutdown(confirmed_terminated=True)

    # Failure after the queue UPDATEs must roll back both tables.
    with scheduler._conn() as conn:
        queue_row = conn.execute(
            "SELECT status,worker_id,claim_generation FROM cognitive_queue WHERE id=?",
            (item_id,),
        ).fetchone()
        thought_row = conn.execute(
            "SELECT status,worker_id,claim_generation FROM cognitive_queue WHERE id=?",
            (thought_id,),
        ).fetchone()
        outbox_row = conn.execute(
            "SELECT status,worker_id,claim_generation FROM effect_outbox WHERE effect_id=?",
            (effect_id,),
        ).fetchone()
    assert queue_row["status"] == ItemStatus.PROCESSING.value
    assert queue_row["worker_id"] == queue_claim.worker_id
    assert queue_row["claim_generation"] == queue_claim.claim_generation
    assert thought_row["status"] == ItemStatus.PROCESSING.value
    assert thought_row["worker_id"] == thought_claim.worker_id
    assert thought_row["claim_generation"] == thought_claim.claim_generation
    assert outbox_row["status"] == "CLAIMED"
    assert outbox_row["worker_id"] == effect_claim["worker_id"]
    assert outbox_row["claim_generation"] == effect_claim["claim_generation"]

    recovered = scheduler.queue.recover_after_confirmed_shutdown(confirmed_terminated=True)
    assert recovered == {
        "quarantined_actions": 1,
        "requeued_cognition": 1,
        "quarantined_effects": 1,
    }
    with scheduler._conn() as conn:
        queue_row = conn.execute(
            "SELECT status,worker_id FROM cognitive_queue WHERE id=?",
            (item_id,),
        ).fetchone()
        thought_row = conn.execute(
            "SELECT status,worker_id FROM cognitive_queue WHERE id=?",
            (thought_id,),
        ).fetchone()
        outbox_row = conn.execute(
            "SELECT status,worker_id FROM effect_outbox WHERE effect_id=?",
            (effect_id,),
        ).fetchone()
    assert queue_row["status"] == ItemStatus.UNKNOWN.value
    assert queue_row["worker_id"] is None
    assert thought_row["status"] == ItemStatus.PENDING.value
    assert thought_row["worker_id"] is None
    assert outbox_row["status"] == "UNKNOWN"
    assert outbox_row["worker_id"] is None



def _prepare_unknown_queue_effect(scheduler, item_id):
    """Create a linked UNKNOWN action/outbox pair through the atomic path."""
    effect_id, queue_claim, outbox_claim = _prepare_claimed_linked_effect(
        scheduler, item_id, worker_id="reconcile-worker"
    )
    assert scheduler._mark_linked_effect_unknown(
        effect_id,
        "ambiguous test outcome",
        queue_item_id=item_id,
        outbox_claim_token=outbox_claim,
        queue_claim_token={
            "worker_id": queue_claim.worker_id,
            "claim_generation": queue_claim.claim_generation,
        },
    )
    return effect_id


@pytest.mark.parametrize(
    "operation",
    ["release_claim", "complete", "mark_unknown", "record_transient_failure"],
)
def test_public_outbox_mutators_reject_linked_effects(tmp_path, operation):
    """One-table outbox callbacks cannot split a linked queue projection."""
    _, _, scheduler = runtime(tmp_path)
    item_id = f"linked-mutator-{operation}"
    effect_id, queue_claim, outbox_claim = _prepare_claimed_linked_effect(
        scheduler, item_id
    )
    before_outbox = scheduler.outbox.get(effect_id)
    with scheduler._conn() as conn:
        before_queue = dict(conn.execute(
            "SELECT status,worker_id,claim_generation FROM cognitive_queue WHERE id=?",
            (item_id,),
        ).fetchone())

    with pytest.raises(
        RuntimeError,
        match="linked outbox effects must use CognitiveScheduler's atomic",
    ):
        if operation == "release_claim":
            scheduler.outbox.release_claim(effect_id, **outbox_claim)
        elif operation == "complete":
            scheduler.outbox.complete(
                effect_id, {"ok": True}, "linked-mutator-observation",
                **outbox_claim,
            )
        elif operation == "mark_unknown":
            scheduler.outbox.mark_unknown(
                effect_id, "linked direct quarantine", **outbox_claim
            )
        else:
            scheduler.outbox.record_transient_failure(
                effect_id, "linked direct transient failure", **outbox_claim
            )

    assert scheduler.outbox.get(effect_id) == before_outbox
    with scheduler._conn() as conn:
        after_queue = dict(conn.execute(
            "SELECT status,worker_id,claim_generation FROM cognitive_queue WHERE id=?",
            (item_id,),
        ).fetchone())
    assert after_queue == before_queue
    assert queue_claim.status is ItemStatus.PROCESSING


def test_duplicate_queue_projection_is_completed_without_dispatch(tmp_path):
    """Only the first queue row linked to a stable effect may own its dispatch."""
    _, _, scheduler = runtime(tmp_path)
    calls = counting_registry(scheduler)
    cand = candidate(source="duplicate-projection-source")
    effect_id = effect_id_for_candidate(cand)
    from vos_core.cognitive_scheduler import _payload_digest

    canonical = CognitiveItem(
        id="canonical-action-projection",
        kind=ItemKind.ACTION_CANDIDATE,
        content={"candidate": cand},
        priority=0.9,
        depth=1,
        parent_id="source",
        created_tick=0,
    )
    assert scheduler.queue.push_with_effect_intent(
        canonical,
        effect_id,
        cand["capability"],
        cand["source_item_id"],
        _payload_digest(cand["payload"]),
    )
    duplicate = CognitiveItem(
        id="duplicate-action-projection",
        kind=ItemKind.ACTION_CANDIDATE,
        content={"candidate": cand},
        priority=0.8,
        depth=1,
        parent_id="source",
        created_tick=0,
    )
    assert scheduler.queue.push(duplicate)
    duplicate_claim = scheduler.queue.claim_item(
        duplicate.id, worker_id=scheduler.worker_id
    )
    assert duplicate_claim is not None

    result = scheduler._execute(
        [cand],
        queue_item_id=duplicate.id,
        queue_claim_token={
            "worker_id": duplicate_claim.worker_id,
            "claim_generation": duplicate_claim.claim_generation,
        },
    )

    assert result["status"] == "DEDUPED_DUPLICATE_QUEUE_PROJECTION"
    assert result["canonical_queue_item_id"] == canonical.id
    assert scheduler.outbox.get(effect_id)["status"] == "READY"
    with scheduler._conn() as conn:
        statuses = {
            row["id"]: row["status"]
            for row in conn.execute(
                "SELECT id,status FROM cognitive_queue WHERE id IN (?,?)",
                (canonical.id, duplicate.id),
            ).fetchall()
        }
    assert statuses[canonical.id] == ItemStatus.PENDING.value
    assert statuses[duplicate.id] == ItemStatus.COMPLETED.value
    assert calls == []


def test_linked_outbox_claim_requires_matching_queue_generation(tmp_path):
    """A linked outbox claim must be subordinate to the current queue claim."""
    _, _, scheduler = runtime(tmp_path)
    item_id = "linked-claim-generation"
    item = CognitiveItem(
        id=item_id,
        kind=ItemKind.ACTION_CANDIDATE,
        content={"candidate": candidate(source=item_id)},
        priority=0.8,
        depth=1,
        parent_id="source",
        created_tick=0,
    )
    assert scheduler.queue.push(item)
    effect_id = stable_effect_id("memory.commit_reflection", item_id)
    scheduler.outbox.record_intent(
        effect_id, "memory.commit_reflection", item_id, "linked-claim-digest",
        queue_item_id=item_id,
    )

    with pytest.raises(ValueError, match="queue_claim_generation is required"):
        scheduler.outbox.claim_with_token(effect_id, "worker-a")

    queue_claim = scheduler.queue.claim_item(item_id, worker_id="worker-a")
    assert queue_claim is not None
    with pytest.raises(RuntimeError, match="matching active cognitive-queue claim"):
        scheduler.outbox.claim_with_token(
            effect_id, "worker-a",
            queue_claim_generation=queue_claim.claim_generation + 1,
        )

    token = scheduler.outbox.claim_with_token(
        effect_id, "worker-a",
        queue_claim_generation=queue_claim.claim_generation,
    )
    assert token == {"worker_id": "worker-a", "claim_generation": 1}


def test_linked_ambiguous_failure_quarantines_both_projections_atomically(tmp_path):
    """An ambiguous linked provider outcome moves queue and outbox together."""
    _, _, scheduler = runtime(tmp_path)
    item_id = "linked-timeout-atomic"
    item = CognitiveItem(
        id=item_id,
        kind=ItemKind.ACTION_CANDIDATE,
        content={"candidate": candidate(source=item_id)},
        priority=0.8,
        depth=1,
        parent_id="source",
        created_tick=0,
    )
    assert scheduler.queue.push(item)
    queue_claim = scheduler.queue.claim_item(
        item_id, worker_id=scheduler.worker_id
    )
    assert queue_claim is not None

    def timeout_provider(capability, payload, idempotency_key=None):
        raise TimeoutError("provider did not answer")

    scheduler.registry.execute = timeout_provider
    with pytest.raises(RuntimeError, match="ambiguous provider failure"):
        scheduler._execute(
            [candidate(source=item_id)],
            queue_item_id=item_id,
            queue_claim_token={
                "worker_id": queue_claim.worker_id,
                "claim_generation": queue_claim.claim_generation,
            },
        )

    outbox_row = scheduler.outbox.get(stable_effect_id(
        "memory.commit_reflection", item_id
    ))
    with scheduler._conn() as conn:
        queue_row = conn.execute(
            "SELECT status,worker_id FROM cognitive_queue WHERE id=?",
            (item_id,),
        ).fetchone()
    assert outbox_row["status"] == "UNKNOWN"
    assert outbox_row["worker_id"] is None
    assert queue_row["status"] == ItemStatus.UNKNOWN.value
    # The last owner remains as provenance; UNKNOWN means the claim is no
    # longer active even though the worker identity is retained.
    assert queue_row["worker_id"] == queue_claim.worker_id
    assert scheduler.queue.unknown_count() == 1


def test_linked_ambiguous_quarantine_rolls_back_if_queue_claim_is_stale(tmp_path):
    """A failed queue fence rolls back the preceding outbox quarantine."""
    _, _, scheduler = runtime(tmp_path)
    item_id = "linked-timeout-stale-queue"
    item = CognitiveItem(
        id=item_id,
        kind=ItemKind.ACTION_CANDIDATE,
        content={"candidate": candidate(source=item_id)},
        priority=0.8,
        depth=1,
        parent_id="source",
        created_tick=0,
    )
    assert scheduler.queue.push(item)
    queue_claim = scheduler.queue.claim_item(
        item_id, worker_id=scheduler.worker_id
    )
    assert queue_claim is not None

    def timeout_provider(capability, payload, idempotency_key=None):
        raise TimeoutError("provider did not answer")

    scheduler.registry.execute = timeout_provider
    original_transition = scheduler.queue._transition_claim_with_conn
    scheduler.queue._transition_claim_with_conn = lambda *args, **kwargs: False
    try:
        with pytest.raises(RuntimeError, match="rolling back outbox quarantine"):
            scheduler._execute(
                [candidate(source=item_id)],
                queue_item_id=item_id,
                queue_claim_token={
                    "worker_id": queue_claim.worker_id,
                    "claim_generation": queue_claim.claim_generation,
                },
            )
    finally:
        scheduler.queue._transition_claim_with_conn = original_transition

    effect_id = stable_effect_id("memory.commit_reflection", item_id)
    assert scheduler.outbox.get(effect_id)["status"] == "CLAIMED"
    with scheduler._conn() as conn:
        queue_row = conn.execute(
            "SELECT status,worker_id FROM cognitive_queue WHERE id=?",
            (item_id,),
        ).fetchone()
    assert queue_row["status"] == ItemStatus.PROCESSING.value
    assert queue_row["worker_id"] == queue_claim.worker_id


@pytest.mark.parametrize("outcome", ["executed", "not_executed"])
def test_standalone_outbox_reconcile_rejects_linked_effect(tmp_path, outcome):
    """Linked queue/outbox projections cannot be split by the standalone API."""
    _, _, scheduler = runtime(tmp_path)
    item_id = f"standalone-reconcile-{outcome}"
    effect_id = _prepare_unknown_queue_effect(scheduler, item_id)
    before_outbox = scheduler.outbox.get(effect_id)

    with scheduler._conn() as conn:
        before_queue = conn.execute(
            "SELECT status FROM cognitive_queue WHERE id=?", (item_id,)
        ).fetchone()["status"]

    with pytest.raises(
        RuntimeError,
        match="linked outbox effects must be reconciled atomically",
    ):
        scheduler.outbox.reconcile(
            effect_id, outcome, provider_receipt="unverified-standalone-receipt"
        )

    assert scheduler.outbox.get(effect_id) == before_outbox
    with scheduler._conn() as conn:
        after_queue = conn.execute(
            "SELECT status FROM cognitive_queue WHERE id=?", (item_id,)
        ).fetchone()["status"]
    assert before_queue == after_queue == ItemStatus.UNKNOWN.value


@pytest.mark.parametrize("status", [ItemStatus.PENDING, ItemStatus.COMPLETED])
def test_queue_only_reconcile_rejects_linked_outbox_projection(tmp_path, status):
    """A linked queue row can only be reconciled with its outbox transaction."""
    _, _, scheduler = runtime(tmp_path)
    item_id = f"queue-only-reconcile-{status.value.lower()}"
    effect_id = _prepare_unknown_queue_effect(scheduler, item_id)
    before_outbox = scheduler.outbox.get(effect_id)

    with scheduler._conn() as conn:
        before_queue = conn.execute(
            "SELECT status FROM cognitive_queue WHERE id=?", (item_id,)
        ).fetchone()["status"]

    with pytest.raises(
        RuntimeError,
        match="linked outbox effects must be reconciled atomically",
    ):
        scheduler.queue.reconcile_mark(item_id, status)

    assert scheduler.outbox.get(effect_id) == before_outbox
    with scheduler._conn() as conn:
        after_queue = conn.execute(
            "SELECT status FROM cognitive_queue WHERE id=?", (item_id,)
        ).fetchone()["status"]
    assert before_queue == after_queue == ItemStatus.UNKNOWN.value


@pytest.mark.parametrize(
    ("outcome", "queue_status", "outbox_status"),
    [
        ("executed", ItemStatus.COMPLETED, "COMPLETED"),
        ("not_executed", ItemStatus.PENDING, "READY"),
    ],
)
def test_reconcile_effect_updates_outbox_and_queue_projection_together(
    tmp_path, outcome, queue_status, outbox_status
):
    _, _, scheduler = runtime(tmp_path)
    item_id = f"atomic-reconcile-{outcome}"
    effect_id = _prepare_unknown_queue_effect(scheduler, item_id)

    result = scheduler.reconcile_effect(
        effect_id, outcome, provider_receipt=f"test-receipt-{outcome}"
    )

    assert result["status"] == outbox_status
    assert result["changed"] is True
    with scheduler._conn() as conn:
        queue_row = conn.execute(
            "SELECT status FROM cognitive_queue WHERE id=?", (item_id,)
        ).fetchone()
        outbox_row = conn.execute(
            "SELECT status FROM effect_outbox WHERE effect_id=?", (effect_id,)
        ).fetchone()
    assert queue_row["status"] == queue_status.value
    assert outbox_row["status"] == outbox_status


@pytest.mark.parametrize(
    ("outcome", "blocked_status"),
    [
        ("executed", ItemStatus.COMPLETED.value),
        ("not_executed", ItemStatus.PENDING.value),
    ],
)
def test_reconcile_effect_rolls_back_outbox_when_queue_projection_fails(
    tmp_path, outcome, blocked_status
):
    _, _, scheduler = runtime(tmp_path)
    item_id = f"rollback-reconcile-{outcome}"
    effect_id = _prepare_unknown_queue_effect(scheduler, item_id)

    with scheduler._conn() as conn:
        conn.execute(f"""
            CREATE TRIGGER reject_reconciliation_projection
            BEFORE UPDATE OF status ON cognitive_queue
            WHEN OLD.id='{item_id}' AND NEW.status='{blocked_status}'
            BEGIN
                SELECT RAISE(ABORT, 'injected reconciliation projection failure');
            END;
        """)
        observation_count_before = conn.execute(
            "SELECT COUNT(*) FROM cognitive_queue WHERE kind=?",
            (ItemKind.OBSERVATION.value,),
        ).fetchone()[0]

    with pytest.raises(sqlite3.IntegrityError, match="injected reconciliation projection failure"):
        scheduler.reconcile_effect(
            effect_id, outcome, provider_receipt=f"test-receipt-{outcome}"
        )

    with scheduler._conn() as conn:
        queue_row = conn.execute(
            "SELECT status FROM cognitive_queue WHERE id=?", (item_id,)
        ).fetchone()
        outbox_row = conn.execute(
            "SELECT status,result_json FROM effect_outbox WHERE effect_id=?", (effect_id,)
        ).fetchone()
        result_count = conn.execute(
            "SELECT COUNT(*) FROM capability_results WHERE source_item_id=?",
            (item_id,),
        ).fetchone()[0]
        observation_count_after = conn.execute(
            "SELECT COUNT(*) FROM cognitive_queue WHERE kind=?",
            (ItemKind.OBSERVATION.value,),
        ).fetchone()[0]

    assert queue_row["status"] == ItemStatus.UNKNOWN.value
    assert outbox_row["status"] == "UNKNOWN"
    assert outbox_row["result_json"] is None
    assert result_count == 0
    assert observation_count_after == observation_count_before


def test_record_intent_can_attach_ready_standalone_effect_once(tmp_path):
    outbox = EffectOutbox(tmp_path / "ready-intent-link.db")
    effect_id = stable_effect_id("memory.commit_reflection", "ready-link")

    outbox.record_intent(
        effect_id, "memory.commit_reflection", "ready-link", "digest"
    )
    linked = outbox.record_intent(
        effect_id, "memory.commit_reflection", "ready-link", "digest",
        queue_item_id="queue-ready",
    )
    assert linked["queue_item_id"] == "queue-ready"
    assert outbox.record_intent(
        effect_id, "memory.commit_reflection", "ready-link", "digest",
        queue_item_id="queue-ready",
    )["queue_item_id"] == "queue-ready"


@pytest.mark.parametrize("quarantine", [False, True])
def test_record_intent_cannot_attach_queue_projection_after_claim(tmp_path, quarantine):
    outbox = EffectOutbox(tmp_path / f"late-intent-link-{quarantine}.db")
    effect_id = stable_effect_id(
        "memory.commit_reflection", f"late-link-{quarantine}"
    )
    outbox.record_intent(
        effect_id, "memory.commit_reflection", f"late-link-{quarantine}", "digest"
    )
    token = claim_args(outbox, effect_id, "worker-a")
    if quarantine:
        assert outbox.mark_unknown(effect_id, "ambiguous", **token)
    before = outbox.get(effect_id)

    with pytest.raises(ValueError, match="cannot attach a queue projection"):
        outbox.record_intent(
            effect_id, "memory.commit_reflection", f"late-link-{quarantine}",
            "digest", queue_item_id="late-queue",
        )

    assert outbox.get(effect_id) == before
    assert before["queue_item_id"] is None


def test_record_intent_preserves_first_queue_projection_for_duplicate_candidates(tmp_path):
    outbox = EffectOutbox(tmp_path / "duplicate-intent-link.db")
    effect_id = stable_effect_id("memory.commit_reflection", "duplicate-link")
    outbox.record_intent(
        effect_id, "memory.commit_reflection", "duplicate-link", "digest",
        queue_item_id="queue-first",
    )

    duplicate = outbox.record_intent(
        effect_id, "memory.commit_reflection", "duplicate-link", "digest",
        queue_item_id="queue-second",
    )

    assert duplicate["queue_item_id"] == "queue-first"


@pytest.mark.parametrize(
    ("capability", "source_item_id"),
    [
        ("memory.other_capability", "identity-source"),
        ("memory.commit_reflection", "different-source"),
    ],
)
def test_record_intent_rejects_effect_identity_reuse(tmp_path, capability, source_item_id):
    outbox = EffectOutbox(tmp_path / "intent-identity.db")
    effect_id = stable_effect_id("memory.commit_reflection", "identity-source")
    outbox.record_intent(
        effect_id, "memory.commit_reflection", "identity-source", "digest"
    )
    before = outbox.get(effect_id)

    with pytest.raises(ValueError, match="different capability/source identity"):
        outbox.record_intent(
            effect_id, capability, source_item_id, "digest"
        )

    assert outbox.get(effect_id) == before

