import json

from vos_core.physiology import (
    ActionProposal,
    DecisionStatus,
    GovernanceMode,
    PhysiologyReceiptLedger,
    VictorPhysiologyRuntime,
    VictorPhysiologyState,
)


def runtime(tmp_path, state=None, granted_authorities=("operator",), allowed_emergency_policies=()):
    ledger = PhysiologyReceiptLedger(str(tmp_path / "physiology.jsonl"))
    return VictorPhysiologyRuntime(
        state=state,
        receipt_ledger=ledger,
        granted_authorities=granted_authorities,
        allowed_emergency_policies=allowed_emergency_policies,
    )


def safe_action(**overrides):
    data = dict(
        name="read_local_state",
        capability="read.local",
        provenance="unit-test",
        required_authorities=("operator",),
        consequence=0.05,
        irreversibility=0.0,
        uncertainty=0.05,
        novelty=0.05,
        arousal=0.0,
        urgency=0.0,
        capability_power=0.05,
    )
    data.update(overrides)
    return ActionProposal(**data)


def test_default_state_is_green(tmp_path):
    r = runtime(tmp_path)
    assert r.state.governance_mode == GovernanceMode.GREEN


def test_missing_provenance_fails_closed(tmp_path):
    r = runtime(tmp_path)
    d = r.evaluate(safe_action(provenance=""))
    assert d.status == DecisionStatus.REJECTED
    assert "missing_provenance" in d.reasons


def test_missing_authority_fails_closed(tmp_path):
    r = runtime(tmp_path, granted_authorities=())
    d = r.evaluate(safe_action(required_authorities=("operator",)))
    assert d.status == DecisionStatus.REJECTED
    assert any(x.startswith("missing_authority:") for x in d.reasons)


def test_proposal_cannot_self_authorize(tmp_path):
    r = runtime(tmp_path, granted_authorities=())
    a = safe_action(metadata={"claimed_authority": "operator"})
    d = r.evaluate(a)
    assert d.status == DecisionStatus.REJECTED
    assert any(x.startswith("missing_authority:") for x in d.reasons)


def test_untrusted_emergency_policy_cannot_bypass_inhibition(tmp_path):
    r = runtime(tmp_path, allowed_emergency_policies=())
    d = r.evaluate(
        safe_action(
            name="emergency_claim",
            capability="write.local",
            consequence=0.45,
            irreversibility=0.9,
            uncertainty=0.8,
            novelty=0.8,
            arousal=0.9,
            urgency=1.0,
            capability_power=0.3,
            emergency_policy="self-declared",
        )
    )
    assert d.status == DecisionStatus.DEFERRED
    assert d.lease is None


def test_low_risk_action_receives_bounded_lease(tmp_path):
    r = runtime(tmp_path)
    a = safe_action()
    d = r.evaluate(a)
    assert d.status == DecisionStatus.AUTHORIZED
    assert d.lease is not None
    assert d.lease.valid_for(a)
    assert d.lease.capability == "read.local"


def test_high_risk_irreversible_action_is_deferred(tmp_path):
    r = runtime(tmp_path)
    d = r.evaluate(
        safe_action(
            name="destructive_change",
            capability="repo.delete",
            consequence=1.0,
            irreversibility=1.0,
            uncertainty=0.9,
            novelty=0.8,
            arousal=0.9,
            capability_power=1.0,
        )
    )
    assert d.status == DecisionStatus.DEFERRED
    assert d.lease is None


def test_human_stop_revokes_and_blocks(tmp_path):
    r = runtime(tmp_path)
    first = r.evaluate(safe_action())
    assert first.lease is not None
    r.set_human_stop(True)
    assert r.state.active_leases == 0
    assert r.state.governance_mode == GovernanceMode.BLACK
    blocked = r.evaluate(safe_action())
    assert blocked.status == DecisionStatus.REJECTED


def test_identity_damage_forces_black_mode(tmp_path):
    state = VictorPhysiologyState(identity_integrity=0.60)
    r = runtime(tmp_path, state)
    assert r.state.governance_mode == GovernanceMode.BLACK
    assert r.evaluate(safe_action()).status == DecisionStatus.REJECTED


def test_executor_never_runs_when_gate_denies(tmp_path):
    r = runtime(tmp_path)
    called = {"value": False}

    def executor():
        called["value"] = True
        return "bad"

    d = r.execute(safe_action(provenance=""), executor)
    assert d.status == DecisionStatus.REJECTED
    assert called["value"] is False


def test_authorized_execution_consumes_lease_and_receipts_outcome(tmp_path):
    r = runtime(tmp_path)
    d = r.execute(safe_action(), lambda: {"value": 42})
    assert d.status == DecisionStatus.EXECUTED
    assert d.actual_outcome == {"ok": True, "result": {"value": 42}}
    assert r.state.active_leases == 0
    assert r.receipts.verify_integrity()


def test_receipt_chain_detects_tampering(tmp_path):
    path = tmp_path / "physiology.jsonl"
    r = VictorPhysiologyRuntime(
        receipt_ledger=PhysiologyReceiptLedger(str(path)),
        granted_authorities=("operator",),
    )
    r.evaluate(safe_action())
    lines = path.read_text().splitlines()
    record = json.loads(lines[0])
    record["payload"]["status"] = "AUTHORIZED_BY_ATTACKER"
    lines[0] = json.dumps(record)
    path.write_text("\n".join(lines) + "\n")
    assert PhysiologyReceiptLedger(str(path)).verify_integrity() is False


def test_corrupt_ledger_on_restart_forces_black_mode(tmp_path):
    path = tmp_path / "physiology.jsonl"
    path.write_text('{"garbled": true}\n')
    r = VictorPhysiologyRuntime(receipt_ledger=PhysiologyReceiptLedger(str(path)))
    assert r.state.governance_mode == GovernanceMode.BLACK
    assert r.state.immune_alerts >= 1
