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
    return stack, phys, CognitiveScheduler(stack, phys, tmp_path / "victor_stack.db")


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
    # After the lease expires the claim can be taken by another worker;
    # while worker-b holds it, a dispatch attempt is blocked, not duplicated.
    assert s.outbox.claim(effect_id, "worker-b", lease_seconds=0) is False
    # (lease was issued for 30s; expiry is time-based, so force it in the test DB)
    with s._conn() as conn:
        conn.execute("UPDATE effect_outbox SET lease_expires_at='2000-01-01T00:00:00+00:00' "
                     "WHERE effect_id=?", (effect_id,))
    assert s.outbox.claim(effect_id, "worker-b") is True
    assert s._execute([cand])["status"] == "BLOCKED_CLAIMED"
    assert calls == []
    with s._conn() as conn:
        conn.execute("UPDATE effect_outbox SET lease_expires_at='2000-01-01T00:00:00+00:00' "
                     "WHERE effect_id=?", (effect_id,))
    assert s._execute([cand])["status"] == "EXECUTED"
    assert len(calls) == 1


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
    assert s.outbox.claim(effect_id, "worker-a") is True
    first = s.outbox.record_transient_failure(effect_id, "provider 503")
    assert first["status"] == "READY"
    assert first["attempts"] == 1  # the claim counted as attempt 1
    assert s.outbox.claim(effect_id, "worker-a") is True
    second = s.outbox.record_transient_failure(effect_id, "provider 503")
    assert second["status"] == "READY"
    assert second["attempts"] == 2
    assert s.outbox.claim(effect_id, "worker-a") is True
    last = s.outbox.record_transient_failure(effect_id, "provider 503")
    assert last["status"] == "FAILED"  # DLQ
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
    queue.mark("quarantined-effect", ItemStatus.UNKNOWN)
    for unsafe in (ItemStatus.PENDING, ItemStatus.COMPLETED):
        with pytest.raises(ValueError, match="requires explicit reconciliation"):
            queue.mark("quarantined-effect", unsafe)
    # Only the explicit reconciliation path may resolve it.
    queue.reconcile_mark("quarantined-effect", ItemStatus.PENDING)
    assert queue.pending_count() == 1
