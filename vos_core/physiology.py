"""Victor Computational Physiology — governed organism runtime core.

This module makes governance part of Victor's execution physiology rather than
an after-the-fact safety wrapper. Consequential actions must be evaluated
against organism state and receive a bounded capability lease before execution.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple


CONSTITUTIONAL_INVARIANTS: Tuple[str, ...] = (
    "IDENTITY_CONTINUITY",
    "HUMAN_STOP_AUTHORITY",
    "PROVENANCE_REQUIRED",
    "NO_SILENT_CANONICAL_OVERWRITE",
    "NO_UNAUTHORIZED_CAPABILITY_ESCALATION",
    "IDENTITY_NOT_EQUAL_MODEL_WEIGHTS",
    "EVIDENCE_BEFORE_ASSERTION",
    "UNKNOWN_IS_VALID",
    "AUTHORITY_BOUNDARIES_REQUIRED",
    "CANONICAL_CHANGE_REQUIRES_RECEIPT",
)


class GovernanceMode(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"
    BLACK = "BLACK"


class DecisionStatus(str, Enum):
    AUTHORIZED = "AUTHORIZED"
    DEFERRED = "DEFERRED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"


@dataclass
class VictorPhysiologyState:
    """Authoritative in-process body map consumed by governed execution."""

    identity_integrity: float = 1.0
    continuity_integrity: float = 1.0
    epistemic_confidence: float = 1.0
    resource_pressure: float = 0.0
    authority_conflict: float = 0.0
    memory_conflict: float = 0.0
    security_pressure: float = 0.0
    human_stop: bool = False
    governance_mode: GovernanceMode = GovernanceMode.GREEN
    physiology_receipt_head: str = "GENESIS"
    active_leases: int = 0
    revoked_leases: int = 0
    immune_alerts: int = 0
    unresolved_authority_conflicts: int = 0
    organ_telemetry: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    updated_at: str = field(default_factory=lambda: _now_iso())

    def normalize(self) -> None:
        for name in (
            "identity_integrity",
            "continuity_integrity",
            "epistemic_confidence",
            "resource_pressure",
            "authority_conflict",
            "memory_conflict",
            "security_pressure",
        ):
            setattr(self, name, _clamp01(float(getattr(self, name))))
        self.updated_at = _now_iso()

    def recompute_mode(self) -> GovernanceMode:
        """Derive organism mode from hard-stop/integrity and pressure signals."""
        self.normalize()
        if self.human_stop or self.identity_integrity < 0.70 or self.continuity_integrity < 0.70:
            self.governance_mode = GovernanceMode.BLACK
        elif (
            self.identity_integrity < 0.90
            or self.continuity_integrity < 0.90
            or self.authority_conflict >= 0.70
            or self.security_pressure >= 0.80
            or self.unresolved_authority_conflicts > 0
        ):
            self.governance_mode = GovernanceMode.RED
        elif (
            self.epistemic_confidence < 0.70
            or self.resource_pressure >= 0.75
            or self.memory_conflict >= 0.50
            or self.security_pressure >= 0.50
        ):
            self.governance_mode = GovernanceMode.YELLOW
        else:
            self.governance_mode = GovernanceMode.GREEN
        return self.governance_mode

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["governance_mode"] = self.governance_mode.value
        return data


@dataclass(frozen=True)
class ActionProposal:
    """A proposed external action. It is not execution authority."""

    name: str
    capability: str
    provenance: str
    required_authorities: Tuple[str, ...] = ()
    consequence: float = 0.0
    irreversibility: float = 0.0
    uncertainty: float = 0.0
    novelty: float = 0.0
    arousal: float = 0.0
    urgency: float = 0.0
    capability_power: float = 0.0
    emergency_policy: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    action_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def normalized(self) -> "ActionProposal":
        values = {
            key: _clamp01(float(getattr(self, key)))
            for key in (
                "consequence",
                "irreversibility",
                "uncertainty",
                "novelty",
                "arousal",
                "urgency",
                "capability_power",
            )
        }
        return ActionProposal(
            name=self.name,
            capability=self.capability,
            provenance=self.provenance,
            required_authorities=tuple(self.required_authorities),
            emergency_policy=self.emergency_policy,
            metadata=dict(self.metadata),
            action_id=self.action_id,
            **values,
        )


@dataclass(frozen=True)
class CapabilityLease:
    lease_id: str
    action_id: str
    capability: str
    issued_at: float
    expires_at: float
    governance_mode: str
    receipt_hash: str

    def valid_for(self, action: ActionProposal, now: Optional[float] = None) -> bool:
        current = time.time() if now is None else now
        return (
            self.action_id == action.action_id
            and self.capability == action.capability
            and current <= self.expires_at
        )


@dataclass
class GateDecision:
    action_id: str
    status: DecisionStatus
    governance_mode: GovernanceMode
    risk_score: float
    reasons: List[str]
    receipt_hash: str
    lease: Optional[CapabilityLease] = None
    actual_outcome: Optional[Dict[str, Any]] = None


class PhysiologyReceiptLedger:
    """Append-only, SHA-256 hash-linked receipt ledger with verification."""

    def __init__(self, path: str = "victor_physiology_receipts.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)
        self._last_hash = self._read_last_hash()

    @staticmethod
    def _hash_payload(payload: Mapping[str, Any]) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def append(self, event_type: str, payload: Mapping[str, Any]) -> str:
        event = {
            "timestamp": _now_iso(),
            "event_type": event_type,
            "previous_hash": self._last_hash,
            "payload": dict(payload),
        }
        event_hash = self._hash_payload(event)
        record = {**event, "event_hash": event_hash}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, default=str) + "\n")
        self._last_hash = event_hash
        return event_hash

    def _read_last_hash(self) -> str:
        last = "GENESIS"
        try:
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    last = json.loads(line)["event_hash"]
        except (OSError, ValueError, KeyError, TypeError):
            return "CORRUPT"
        return last

    def verify_integrity(self) -> bool:
        previous = "GENESIS"
        try:
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                record = json.loads(line)
                claimed_hash = record.pop("event_hash")
                if record.get("previous_hash") != previous:
                    return False
                computed = self._hash_payload(record)
                if computed != claimed_hash:
                    return False
                previous = claimed_hash
        except (OSError, ValueError, KeyError, TypeError):
            return False
        return True

    @property
    def last_hash(self) -> str:
        return self._last_hash


class VictorPhysiologyRuntime:
    """Root governed-organism runtime object.

    No consequential action should execute directly. A proposal is evaluated
    against organism state, trusted runtime authority and provenance, then
    receives a bounded capability lease only if it survives the gate.
    """

    def __init__(
        self,
        state: Optional[VictorPhysiologyState] = None,
        receipt_ledger: Optional[PhysiologyReceiptLedger] = None,
        lease_ttl_seconds: int = 30,
        risk_threshold: float = 0.72,
        granted_authorities: Iterable[str] = (),
        allowed_emergency_policies: Iterable[str] = (),
    ):
        if lease_ttl_seconds <= 0:
            raise ValueError("lease_ttl_seconds must be > 0")
        self.state = state or VictorPhysiologyState()
        self.receipts = receipt_ledger or PhysiologyReceiptLedger()
        self.lease_ttl_seconds = int(lease_ttl_seconds)
        self.risk_threshold = _clamp01(float(risk_threshold))
        self._granted_authorities = frozenset(str(a) for a in granted_authorities if str(a).strip())
        self._allowed_emergency_policies = frozenset(
            str(p) for p in allowed_emergency_policies if str(p).strip()
        )
        self._leases: Dict[str, CapabilityLease] = {}
        self.state.recompute_mode()

        if not self.receipts.verify_integrity():
            self.state.security_pressure = 1.0
            self.state.immune_alerts += 1
            self.state.governance_mode = GovernanceMode.BLACK

    def publish_organ_state(self, organ: str, telemetry: Mapping[str, Any]) -> GovernanceMode:
        if not organ.strip():
            raise ValueError("organ name is required")
        self.state.organ_telemetry[organ] = dict(telemetry)
        mode = self.state.recompute_mode()
        self._commit_state_event(
            "organ_state",
            {"organ": organ, "telemetry": dict(telemetry), "mode": mode.value},
        )
        return mode

    def set_human_stop(self, enabled: bool = True) -> GovernanceMode:
        self.state.human_stop = bool(enabled)
        mode = self.state.recompute_mode()
        if enabled:
            self.revoke_all_leases("human_stop")
        self._commit_state_event("human_stop", {"enabled": bool(enabled), "mode": mode.value})
        return mode

    def revoke_all_leases(self, reason: str) -> int:
        count = len(self._leases)
        if count:
            self.state.revoked_leases += count
        self._leases.clear()
        self.state.active_leases = 0
        self._commit_state_event("leases_revoked", {"reason": reason, "count": count})
        return count

    def evaluate(self, proposal: ActionProposal) -> GateDecision:
        proposal = proposal.normalized()
        mode = self.state.recompute_mode()
        reasons: List[str] = []
        missing_authority = sorted(set(proposal.required_authorities) - self._granted_authorities)
        risk = self._independent_risk_score(proposal)
        status = DecisionStatus.AUTHORIZED

        if self.receipts.last_hash == "CORRUPT" or not self.receipts.verify_integrity():
            self.state.security_pressure = 1.0
            self.state.immune_alerts += 1
            self.state.governance_mode = GovernanceMode.BLACK
            mode = GovernanceMode.BLACK
            reasons.append("receipt_ledger_integrity_failure")
            status = DecisionStatus.REJECTED

        if self.state.human_stop:
            reasons.append("human_stop_active")
            status = DecisionStatus.REJECTED
        if self.state.identity_integrity < 0.70:
            reasons.append("identity_integrity_critical")
            status = DecisionStatus.REJECTED
        if self.state.continuity_integrity < 0.70:
            reasons.append("continuity_integrity_critical")
            status = DecisionStatus.REJECTED
        if not proposal.provenance.strip():
            reasons.append("missing_provenance")
            status = DecisionStatus.REJECTED
        if missing_authority:
            reasons.append("missing_authority:" + ",".join(missing_authority))
            status = DecisionStatus.REJECTED
        if mode == GovernanceMode.BLACK:
            reasons.append("black_mode_fail_closed")
            status = DecisionStatus.REJECTED
        elif mode == GovernanceMode.RED and proposal.consequence >= 0.25:
            reasons.append("red_mode_blocks_consequential_action")
            status = DecisionStatus.REJECTED

        high_arousal_irreversible = proposal.arousal >= 0.65 and proposal.irreversibility >= 0.65
        if status == DecisionStatus.AUTHORIZED and high_arousal_irreversible and not self._bounded_emergency(proposal):
            reasons.append("temporal_inhibition_required")
            status = DecisionStatus.DEFERRED
        if status == DecisionStatus.AUTHORIZED and risk >= self.risk_threshold and not self._bounded_emergency(proposal):
            reasons.append("deliberation_required")
            status = DecisionStatus.DEFERRED
        if status == DecisionStatus.AUTHORIZED and mode == GovernanceMode.YELLOW and proposal.consequence >= 0.50:
            reasons.append("yellow_mode_requires_additional_verification")
            status = DecisionStatus.DEFERRED

        if not reasons and status == DecisionStatus.AUTHORIZED:
            reasons.append("constitutional_and_physiological_gates_passed")

        receipt_payload = {
            "action": self._proposal_dict(proposal),
            "state": self.state.to_dict(),
            "risk_score": risk,
            "status": status.value,
            "reasons": reasons,
            "constitutional_invariants": list(CONSTITUTIONAL_INVARIANTS),
            "trusted_authority_context": sorted(self._granted_authorities),
        }
        receipt_hash = self.receipts.append("gate_decision", receipt_payload)
        self.state.physiology_receipt_head = receipt_hash

        lease = None
        if status == DecisionStatus.AUTHORIZED:
            lease = self._issue_lease(proposal, mode, receipt_hash)

        return GateDecision(
            action_id=proposal.action_id,
            status=status,
            governance_mode=self.state.governance_mode,
            risk_score=risk,
            reasons=reasons,
            receipt_hash=receipt_hash,
            lease=lease,
        )

    def execute(self, proposal: ActionProposal, executor: Callable[[], Any]) -> GateDecision:
        """Evaluate, execute only with a valid lease, and record actual outcome."""
        decision = self.evaluate(proposal)
        if decision.status != DecisionStatus.AUTHORIZED or decision.lease is None:
            return decision

        lease = decision.lease
        if not self._consume_valid_lease(lease, proposal):
            failure_hash = self.receipts.append(
                "execution_blocked",
                {"action_id": proposal.action_id, "reason": "invalid_or_expired_lease"},
            )
            self.state.physiology_receipt_head = failure_hash
            decision.status = DecisionStatus.REJECTED
            decision.reasons.append("invalid_or_expired_lease")
            decision.receipt_hash = failure_hash
            decision.lease = None
            return decision

        try:
            result = executor()
            outcome = {"ok": True, "result": result}
            status = DecisionStatus.EXECUTED
        except Exception as exc:
            outcome = {"ok": False, "error_type": type(exc).__name__, "error": str(exc)}
            status = DecisionStatus.FAILED

        final_hash = self.receipts.append(
            "execution_outcome",
            {
                "action_id": proposal.action_id,
                "gate_receipt_hash": decision.receipt_hash,
                "status": status.value,
                "outcome": outcome,
            },
        )
        self.state.physiology_receipt_head = final_hash
        decision.status = status
        decision.actual_outcome = outcome
        decision.receipt_hash = final_hash
        decision.lease = None
        return decision

    def _issue_lease(self, proposal: ActionProposal, mode: GovernanceMode, receipt_hash: str) -> CapabilityLease:
        issued = time.time()
        lease = CapabilityLease(
            lease_id=uuid.uuid4().hex,
            action_id=proposal.action_id,
            capability=proposal.capability,
            issued_at=issued,
            expires_at=issued + self.lease_ttl_seconds,
            governance_mode=mode.value,
            receipt_hash=receipt_hash,
        )
        self._leases[lease.lease_id] = lease
        self.state.active_leases = len(self._leases)
        return lease

    def _consume_valid_lease(self, lease: CapabilityLease, proposal: ActionProposal) -> bool:
        stored = self._leases.get(lease.lease_id)
        if stored is None or stored != lease or not lease.valid_for(proposal):
            self._leases.pop(lease.lease_id, None)
            self.state.active_leases = len(self._leases)
            return False
        del self._leases[lease.lease_id]
        self.state.active_leases = len(self._leases)
        return True

    def _commit_state_event(self, event_type: str, payload: Mapping[str, Any]) -> str:
        receipt_hash = self.receipts.append(event_type, payload)
        self.state.physiology_receipt_head = receipt_hash
        return receipt_hash

    def _bounded_emergency(self, proposal: ActionProposal) -> bool:
        return bool(
            proposal.emergency_policy
            and proposal.emergency_policy in self._allowed_emergency_policies
            and proposal.urgency >= 0.85
            and proposal.capability_power <= 0.35
            and proposal.consequence <= 0.50
        )

    def _independent_risk_score(self, proposal: ActionProposal) -> float:
        raw = (
            0.20 * proposal.consequence
            + 0.18 * proposal.irreversibility
            + 0.17 * proposal.uncertainty
            + 0.10 * proposal.novelty
            + 0.12 * proposal.arousal
            + 0.13 * proposal.capability_power
            + 0.05 * self.state.security_pressure
            + 0.05 * self.state.authority_conflict
            - 0.08 * (1.0 - proposal.irreversibility)
            - 0.05 * proposal.urgency
        )
        return _clamp01(raw)

    @staticmethod
    def _proposal_dict(proposal: ActionProposal) -> Dict[str, Any]:
        data = asdict(proposal)
        data["metadata"] = dict(proposal.metadata)
        return data


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
