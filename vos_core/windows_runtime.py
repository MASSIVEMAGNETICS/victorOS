"""Windows VictorOS prototype runtime with persistent cognition.

Owner input is accepted through the physiology gate, converted into a durable
scheduler query, and advanced by non-recursive macroticks.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from .cognitive_scheduler import CognitiveScheduler
from .physiology import (
    ActionProposal,
    PhysiologyReceiptLedger,
    VictorPhysiologyRuntime,
    VictorPhysiologyState,
)
from .victor_cognition_stack import VictorCognitionStack


STATE_SCHEMA_VERSION = 2


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class StateCorruptionError(RuntimeError):
    """Raised when the persistent Windows state cannot be trusted."""


class AtomicJSONState:
    """Small fail-closed JSON state store with atomic replacement writes."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def default() -> Dict[str, Any]:
        now = _now_iso()
        return {
            "schema_version": STATE_SCHEMA_VERSION,
            "created_at": now,
            "updated_at": now,
            "boot_count": 0,
            "episode_count": 0,
            "human_stop": False,
            "last_receipt": "GENESIS",
        }

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return self.default()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StateCorruptionError(f"state_unreadable:{type(exc).__name__}") from exc
        if not isinstance(data, dict):
            raise StateCorruptionError("state_root_not_object")
        if data.get("schema_version") == 1:
            data["schema_version"] = STATE_SCHEMA_VERSION
        if data.get("schema_version") != STATE_SCHEMA_VERSION:
            raise StateCorruptionError("unsupported_state_schema")
        for key in ("boot_count", "episode_count"):
            if not isinstance(data.get(key), int) or data[key] < 0:
                raise StateCorruptionError(f"invalid_{key}")
        if not isinstance(data.get("human_stop"), bool):
            raise StateCorruptionError("invalid_human_stop")
        if not isinstance(data.get("last_receipt"), str):
            raise StateCorruptionError("invalid_last_receipt")
        return data

    def save(self, data: Mapping[str, Any]) -> None:
        payload = dict(data)
        payload["schema_version"] = STATE_SCHEMA_VERSION
        payload["updated_at"] = _now_iso()
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
            encoding="utf-8",
        )
        temp.replace(self.path)


class WindowsEpisodeLedger:
    """Append-only SHA-256 hash-linked episode ledger."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)
        self._last_hash = self._read_last_hash()

    @staticmethod
    def _hash_payload(payload: Mapping[str, Any]) -> str:
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _read_last_hash(self) -> str:
        last = "GENESIS"
        try:
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    last = json.loads(line)["event_hash"]
        except (OSError, ValueError, KeyError, TypeError):
            return "CORRUPT"
        return last

    @property
    def last_hash(self) -> str:
        return self._last_hash

    def append(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        record_without_hash = {
            "timestamp": _now_iso(),
            "episode_id": uuid.uuid4().hex,
            "previous_hash": self._last_hash,
            **dict(payload),
        }
        event_hash = self._hash_payload(record_without_hash)
        record = {**record_without_hash, "event_hash": event_hash}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, default=str, ensure_ascii=False) + "\n")
        self._last_hash = event_hash
        return record

    def verify_integrity(self) -> bool:
        previous = "GENESIS"
        try:
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                record = json.loads(line)
                claimed = record.pop("event_hash")
                if record.get("previous_hash") != previous:
                    return False
                if self._hash_payload(record) != claimed:
                    return False
                previous = claimed
        except (OSError, ValueError, KeyError, TypeError):
            return False
        return True

    def recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit), 100))
        rows: List[Dict[str, Any]] = []
        try:
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rows.append(json.loads(line))
        except (OSError, ValueError):
            return []
        return rows[-limit:][::-1]


class VictorWindowsRuntime:
    """Governed Windows prototype runtime with continuity across restarts."""

    def __init__(self, workdir: str = "."):
        self.workdir = Path(workdir).resolve()
        self.state_dir = self.workdir / "state"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_store = AtomicJSONState(self.state_dir / "windows_state.json")
        self.startup_fault: Optional[str] = None
        self.state_writable = True

        try:
            self.state = self.state_store.load()
        except StateCorruptionError as exc:
            self.state = AtomicJSONState.default()
            self.state["human_stop"] = True
            self.startup_fault = str(exc)
            self.state_writable = False

        self.episodes = WindowsEpisodeLedger(self.state_dir / "windows_episodes.jsonl")
        self.receipts = PhysiologyReceiptLedger(str(self.state_dir / "windows_receipts.jsonl"))
        physiology_state = VictorPhysiologyState(human_stop=bool(self.state["human_stop"]))
        self.physiology = VictorPhysiologyRuntime(
            state=physiology_state,
            receipt_ledger=self.receipts,
            granted_authorities=("local_owner",),
        )
        self.stack = VictorCognitionStack(db_path=self.state_dir / "victor_stack.db")
        self.scheduler = CognitiveScheduler(
            stack=self.stack,
            physiology=self.physiology,
            db_path=self.state_dir / "victor_stack.db",
        )

        if not self.episodes.verify_integrity():
            self.startup_fault = self.startup_fault or "episode_ledger_integrity_failure"
        if not self.scheduler.verify_receipts():
            self.startup_fault = self.startup_fault or "scheduler_receipt_integrity_failure"
        if self.startup_fault:
            # Integrity failure is not merely "high pressure". It invalidates the
            # authority substrate, so force the existing constitutional Human STOP
            # boundary and persist it when the state store itself is still writable.
            self.physiology.state.security_pressure = 1.0
            self.physiology.set_human_stop(True)
            self.state["human_stop"] = True
            self._save_state_if_safe()

        self.state["boot_count"] = int(self.state.get("boot_count", 0)) + 1
        boot_receipt = self.receipts.append(
            "windows_boot",
            {
                "boot_count": self.state["boot_count"],
                "human_stop": self.physiology.state.human_stop,
                "episode_chain_ok": self.episodes.verify_integrity(),
                "scheduler_receipts_ok": self.scheduler.verify_receipts(),
                "scheduler_tick": self.scheduler.current_tick,
                "queue_pending": self.scheduler.queue.pending_count(),
                "startup_fault": self.startup_fault,
            },
        )
        self.physiology.state.physiology_receipt_head = boot_receipt
        self.state["last_receipt"] = boot_receipt
        self._save_state_if_safe()

    def _save_state_if_safe(self) -> None:
        if self.state_writable:
            self.state_store.save(self.state)

    def status(self) -> Dict[str, Any]:
        return {
            "boot_count": self.state["boot_count"],
            "episode_count": self.state["episode_count"],
            "human_stop": self.physiology.state.human_stop,
            "governance_mode": self.physiology.state.governance_mode.value,
            "receipt_chain_ok": self.receipts.verify_integrity(),
            "episode_chain_ok": self.episodes.verify_integrity(),
            "scheduler_receipt_chain_ok": self.scheduler.verify_receipts(),
            "scheduler_tick": self.scheduler.current_tick,
            "stack_tick": self.stack.tick,
            "cognitive_queue_pending": self.scheduler.queue.pending_count(),
            "last_receipt": self.physiology.state.physiology_receipt_head,
            "startup_fault": self.startup_fault,
            "state_writable": self.state_writable,
        }

    def set_human_stop(self, enabled: bool) -> Dict[str, Any]:
        if not enabled and self.startup_fault:
            raise RuntimeError("Cannot reset Human STOP while an integrity/startup fault is active.")
        mode = self.physiology.set_human_stop(bool(enabled))
        self.state["human_stop"] = bool(enabled)
        self.state["last_receipt"] = self.physiology.state.physiology_receipt_head
        self._save_state_if_safe()
        return {"human_stop": bool(enabled), "governance_mode": mode.value}

    def process_episode(self, text: str) -> Dict[str, Any]:
        text=(text or "").strip()
        if not text:
            raise ValueError("Episode input cannot be empty.")
        proposal=ActionProposal(
            name="enqueue_owner_query",
            capability="cognition.enqueue_query",
            provenance="windows-prototype-owner-input",
            required_authorities=("local_owner",),
            consequence=0.02, irreversibility=0.0, uncertainty=0.02,
            novelty=0.05, arousal=0.0, urgency=0.0, capability_power=0.03,
            metadata={"input_sha256":_sha256_text(text),"input_length":len(text)},
        )
        decision=self.physiology.execute(
            proposal, lambda:self.scheduler.publish_query(text,priority=1.0)
        )
        tick_receipt=None
        event_id=None
        if decision.actual_outcome and decision.actual_outcome.get("ok"):
            event_id=str(decision.actual_outcome.get("result"))
            tick_receipt=self.scheduler.tick(max_items=1)
        episode=self.episodes.append({
            "input":text,
            "input_sha256":_sha256_text(text),
            "status":decision.status.value,
            "governance_mode":decision.governance_mode.value,
            "reasons":list(decision.reasons),
            "receipt_hash":decision.receipt_hash,
            "scheduler_event_id":event_id,
            "scheduler_tick_receipt":tick_receipt,
        })
        self.state["episode_count"]=int(self.state.get("episode_count",0))+1
        self.state["human_stop"]=self.physiology.state.human_stop
        self.state["last_receipt"]=decision.receipt_hash
        self._save_state_if_safe()
        return episode

    def advance_cognition(self,ticks:int=1)->List[Dict[str,Any]]:
        if ticks<1 or ticks>20:
            raise ValueError("ticks must be between 1 and 20")
        receipts=[self.scheduler.tick() for _ in range(ticks)]
        self.state["last_receipt"]=self.physiology.state.physiology_receipt_head
        self._save_state_if_safe()
        return receipts

    def pending_cognition(self,limit:int=25)->List[Dict[str,Any]]:
        return self.scheduler.queue.pending_items(limit)

    def recent_episodes(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self.episodes.recent(limit)

    def proposed_actions(self) -> List[Dict[str, Any]]:
        return [a for a in self.stack.actions() if a.get("status") == "proposed"]
