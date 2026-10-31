from __future__ import annotations

import sqlite3

import pytest

from vos_core.native_kernel import (
    ChronosPromotionAdapter,
    KernelActionCandidate,
    NativeKernel,
)
from vos_core.physiology import (
    DecisionStatus,
    PhysiologyReceiptLedger,
    VictorPhysiologyRuntime,
)


class AcceptingChronosAdapter(ChronosPromotionAdapter):
    def __init__(self):
        self.calls = []

    def promote(self, candidate):
        self.calls.append(candidate)
        return {
            "accepted": True,
            "chronos_receipt_hash": "chronos-receipt-001",
            "chronos_head": "chronos-head-001",
            "verification": {"independent": True},
        }


class BrokenChronosAdapter(ChronosPromotionAdapter):
    def promote(self, candidate):
        return {"accepted": True}


def make_kernel(tmp_path, **kwargs):
    return NativeKernel(
        tmp_path / "native.db",
        resonance_db_path=tmp_path / "resonance.db",
        physiology_receipt_path=tmp_path / "physiology.jsonl",
        **kwargs,
    )


def first_gestalt(kernel, episode_id):
    gestalts = kernel.gestalts_for_episode(episode_id)
    assert gestalts
    return gestalts[0]


def test_duplicate_content_remains_two_distinct_episodes(tmp_path):
    with make_kernel(tmp_path) as kernel:
        first = kernel.run_episode("Victor native cognition integration.")
        second = kernel.run_episode("Victor native cognition integration.")

        assert first["episode"]["episode_id"] != second["episode"]["episode_id"]
        counts = kernel.counts()
        assert counts["episodes"] == 2
        assert counts["content_objects"] == 1
        assert kernel.stack.crystallizations() == []
        assert kernel.verify_receipt_chain() is True


def test_membrane_resonance_is_scoped_to_episode_and_tick(tmp_path):
    with make_kernel(tmp_path, gestalt_quorum=3) as kernel:
        ep1 = kernel.begin_episode("same observation")
        kernel.publish_signal(
            episode_id=ep1.episode_id,
            tick=ep1.tick,
            concept_id=ep1.concept_id,
            organ="sensory",
            event="input",
            payload={"x": 1},
            evidence_state="OBSERVED",
        )
        kernel.publish_signal(
            episode_id=ep1.episode_id,
            tick=ep1.tick,
            concept_id=ep1.concept_id,
            organ="attention",
            event="salience",
            payload={"score": 0.8},
        )
        assert kernel.gestalts_for_episode(ep1.episode_id) == []

        ep2 = kernel.begin_episode("same observation")
        kernel.publish_signal(
            episode_id=ep2.episode_id,
            tick=ep2.tick,
            concept_id=ep2.concept_id,
            organ="memory",
            event="recall",
            payload={"count": 1},
        )
        assert kernel.gestalts_for_episode(ep2.episode_id) == []
        assert kernel.gestalts_for_episode(ep1.episode_id) == []


def test_resonance_creates_candidate_not_truth_or_canon(tmp_path):
    with make_kernel(tmp_path) as kernel:
        result = kernel.run_episode("Victor memory governance and cognition.")
        gestalt = first_gestalt(kernel, result["episode"]["episode_id"])

        assert gestalt.status == "CANDIDATE"
        with kernel._conn() as conn:
            assert conn.execute(
                "SELECT COUNT(*) FROM transition_candidates"
            ).fetchone()[0] == 0


def test_verification_requires_explicit_verifier_and_evidence(tmp_path):
    with make_kernel(tmp_path) as kernel:
        result = kernel.run_episode("Evidence must precede canonical promotion.")
        gestalt = first_gestalt(kernel, result["episode"]["episode_id"])

        with pytest.raises(ValueError, match="verifier"):
            kernel.verify_gestalt(
                gestalt.gestalt_id,
                passed=True,
                verifier="",
                evidence_refs=["receipt-a"],
            )

        with pytest.raises(ValueError, match="evidence"):
            kernel.verify_gestalt(
                gestalt.gestalt_id,
                passed=True,
                verifier="independent-test",
                evidence_refs=[],
            )


def test_failed_verification_cannot_create_transition(tmp_path):
    with make_kernel(tmp_path) as kernel:
        result = kernel.run_episode("Contradiction pressure stays explicit.")
        gestalt = first_gestalt(kernel, result["episode"]["episode_id"])

        transition = kernel.verify_gestalt(
            gestalt.gestalt_id,
            passed=False,
            verifier="independent-test",
            evidence_refs=["evidence-1"],
            notes="candidate not sufficiently supported",
        )

        assert transition is None
        assert kernel.gestalt(gestalt.gestalt_id).status == "REJECTED"
        assert kernel.counts()["transition_candidates"] == 0


def test_verified_gestalt_becomes_noncanonical_transition_candidate(tmp_path):
    with make_kernel(tmp_path) as kernel:
        result = kernel.run_episode("Verified evidence may become a transition candidate.")
        gestalt = first_gestalt(kernel, result["episode"]["episode_id"])

        transition = kernel.verify_gestalt(
            gestalt.gestalt_id,
            passed=True,
            verifier="independent-test",
            evidence_refs=["kernel-receipt", "a1-source"],
            expected_prior_chronos_head="head-before",
        )

        assert transition is not None
        assert transition.status == "VERIFIED_CANDIDATE"
        assert transition.payload["canonical"] is False
        assert transition.expected_prior_chronos_head == "head-before"


def test_chronos_promotion_requires_real_receipt_and_head(tmp_path):
    with make_kernel(tmp_path) as kernel:
        result = kernel.run_episode("Chronos promotion is a governed boundary.")
        gestalt = first_gestalt(kernel, result["episode"]["episode_id"])
        transition = kernel.verify_gestalt(
            gestalt.gestalt_id,
            passed=True,
            verifier="independent-test",
            evidence_refs=["proof-1"],
        )
        assert transition is not None

        with pytest.raises(RuntimeError, match="receipt hash and head"):
            kernel.promote_transition(
                transition.transition_id,
                BrokenChronosAdapter(),
            )

        adapter = AcceptingChronosAdapter()
        accepted = kernel.promote_transition(transition.transition_id, adapter)
        assert accepted["accepted"] is True
        assert len(adapter.calls) == 1

        with kernel._conn() as conn:
            row = conn.execute(
                """
                SELECT status, chronos_receipt_hash, chronos_head
                FROM transition_candidates WHERE transition_id=?
                """,
                (transition.transition_id,),
            ).fetchone()
        assert row["status"] == "PROMOTED"
        assert row["chronos_receipt_hash"] == "chronos-receipt-001"
        assert row["chronos_head"] == "chronos-head-001"


def test_human_stop_blocks_native_kernel_effect(tmp_path):
    physiology = VictorPhysiologyRuntime(
        receipt_ledger=PhysiologyReceiptLedger(str(tmp_path / "physiology-stop.jsonl")),
        granted_authorities=("local_owner",),
    )
    physiology.set_human_stop(True)
    called = []

    with make_kernel(tmp_path, physiology=physiology) as kernel:
        candidate = KernelActionCandidate(
            name="memory-write",
            capability="memory.commit_reflection",
            provenance="test",
            score=0.9,
            required_authorities=("local_owner",),
            consequence=0.1,
            irreversibility=0.05,
            uncertainty=0.05,
            capability_power=0.1,
        )
        decision = kernel.execute_action(
            candidate,
            lambda: called.append("executed"),
        )

    assert decision.status == DecisionStatus.REJECTED
    assert called == []
    assert "human_stop_active" in decision.reasons


def test_kernel_receipt_tamper_is_detected(tmp_path):
    with make_kernel(tmp_path) as kernel:
        kernel.run_episode("Receipt integrity must fail closed under tampering.")
        assert kernel.verify_receipt_chain() is True

        with kernel._conn() as conn:
            conn.execute(
                "UPDATE native_kernel_receipts SET payload_json='{}' WHERE seq=1"
            )

        assert kernel.verify_receipt_chain() is False


def test_a1_evidence_chain_remains_separate_and_valid(tmp_path):
    with make_kernel(tmp_path) as kernel:
        result = kernel.run_episode("A1 remains evidence substrate, not Chronos.")
        episode_id = result["episode"]["episode_id"]
        episode = kernel.episode(episode_id)

        report = kernel.resonance.verify_integrity()
        assert report["ok"] is True
        assert episode.resonance_source_id
        assert first_gestalt(kernel, episode_id).status == "CANDIDATE"
