#!/usr/bin/env python3
# =============================================================================
# SAVE3 STANDARD
# artifact: victor_cognition_stack/victor_cognitive_scheduler.py
# version: 1.0.0
# schema_version: 1
# trust: 0.95
# handoff: builder_ready
# error_proof: depth_limits + budgeted_popping + ttl_enforcement + fail_closed_gates
# future_proof: event_bus_pubsub + pluggable_reasoning_adapters
# constraints:
#   - zero third-party dependencies
#   - no recursive think() execution
#   - thoughts enqueue new thoughts
#   - queries expand into thought chains
# =============================================================================

import queue
import time
import uuid
import json
import hashlib
import sqlite3
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime, timezone
from pathlib import Path

from .victor_cognition_stack import VictorCognitionStack
from .physiology import ActionProposal, VictorPhysiologyRuntime

MAX_DEPTH = 5
DEFAULT_TTL_TICKS = 50

def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()

def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

class ItemKind(str, Enum):
    QUERY = "QUERY"
    THOUGHT = "THOUGHT"
    GOAL = "GOAL"
    CONFLICT = "CONFLICT"
    PREDICTION = "PREDICTION"
    REFLECTION = "REFLECTION"
    ACTION_CANDIDATE = "ACTION_CANDIDATE"
    OBSERVATION = "OBSERVATION"

class ItemStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    UNKNOWN = "UNKNOWN"  # In-flight capability effect; requires reconciliation.
    COMPLETED = "COMPLETED"
    DROPPED_DEPTH = "DROPPED_DEPTH"
    DROPPED_TTL = "DROPPED_TTL"
    DROPPED_BUDGET = "DROPPED_BUDGET"
    FAILED = "FAILED"

@dataclass
class CognitiveItem:
    id: str
    kind: ItemKind
    content: Dict[str, Any]
    priority: float          # Higher = more important
    depth: int
    parent_id: Optional[str]
    created_tick: int
    ttl: int = DEFAULT_TTL_TICKS
    status: ItemStatus = ItemStatus.PENDING
    # Durable fencing token for the most recent claim. The generation advances
    # on every successful claim, including a retry by the same worker ID.
    worker_id: Optional[str] = None
    claim_generation: int = 0
    
    # For PriorityQueue sorting: highest priority first, then oldest first
    def __lt__(self, other: 'CognitiveItem') -> bool:
        if self.priority != other.priority:
            return self.priority > other.priority
        return self.created_tick < other.created_tick


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False)

def _hash_payload(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()

def stable_effect_id(capability: str, source_item_id: Optional[str]) -> str:
    """Deterministic effect ID for one capability dispatch from one source.

    The same source + capability always yields the same effect ID, so a
    re-derived candidate after a crash maps to the same outbox record and
    the same provider idempotency key. The payload digest is stored
    separately: the same effect ID with a different payload is a conflict,
    never a silent re-dispatch.
    """
    key = {"capability": str(capability), "source_item_id": str(source_item_id or "")}
    return "eff_" + _hash_payload(key)[:32]

def effect_id_for_candidate(candidate: Dict[str, Any]) -> str:
    return stable_effect_id(candidate.get("capability"), candidate.get("source_item_id"))

def _payload_digest(payload: Any) -> str:
    return _hash_payload(payload or {})

# Outbox statuses. READY = intent recorded, never dispatched. CLAIMED = one
# worker holds a bounded lease. COMPLETED = outcome durably recorded.
# UNKNOWN = ambiguous outcome, fail-closed quarantine, never auto-replayed.
# FAILED = DLQ: transient-failure budget exhausted, terminal.
OUTBOX_MAX_ATTEMPTS = 3
_AMBIGUOUS_ERROR_TYPES = ("TimeoutError", "ConnectionError", "Timeout")

class EffectOutbox:
    """Durable transactional outbox for capability effects.

    Lives in the same SQLite file as the cognitive queue so intent records,
    claims and completions are atomic with the queue rows they guard. This
    is the Issue #19 fix: a stable effect ID + payload digest is recorded
    before any external dispatch, dispatch carries that ID as the provider
    idempotency key, and completion is co-committed with the capability
    result and observation. Without provider-supported idempotency or a
    provider receipt, exactly-once external execution cannot be promised;
    ambiguous outcomes stay UNKNOWN until explicit reconciliation.
    """
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._init_schema()

    def _conn(self):
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_schema(self):
        with self._conn() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS effect_outbox(
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
                claim_generation INTEGER NOT NULL DEFAULT 0,
                lease_expires_at TEXT,
                result_json TEXT,
                observation_event_id TEXT UNIQUE,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_outbox_status
              ON effect_outbox(status, created_at ASC);
            """)

            columns = {row["name"] for row in conn.execute("PRAGMA table_info(effect_outbox)")}
            if "claim_generation" not in columns:
                conn.execute(
                    "ALTER TABLE effect_outbox ADD COLUMN claim_generation INTEGER NOT NULL DEFAULT 0"
                )

    @staticmethod
    def _row_dict(row) -> Optional[Dict[str, Any]]:
        if row is None:
            return None
        d = dict(row)
        d["attempts"] = int(d["attempts"])
        d["max_attempts"] = int(d["max_attempts"])
        d["claim_generation"] = int(d.get("claim_generation") or 0)
        return d

    @staticmethod
    def _record_with_conn(conn, effect_id, capability, source_item_id,
                          payload_digest, queue_item_id=None, max_attempts=OUTBOX_MAX_ATTEMPTS):
        now = _utcnow()
        conn.execute("""
          INSERT OR IGNORE INTO effect_outbox
          (effect_id, capability, source_item_id, queue_item_id, payload_digest,
           idempotency_key, status, attempts, max_attempts, created_at, updated_at)
          VALUES(?,?,?,?,?,?, 'READY', 0, ?, ?, ?)
        """, (effect_id, str(capability), str(source_item_id) if source_item_id is not None else None,
              queue_item_id, payload_digest, effect_id, int(max_attempts), now, now))
        row = conn.execute("SELECT * FROM effect_outbox WHERE effect_id=?", (effect_id,)).fetchone()
        if row is None:
            raise RuntimeError(f"effect outbox intent not recorded: {effect_id}")
        expected_source_item_id = (
            str(source_item_id) if source_item_id is not None else None
        )
        if (row["capability"] != str(capability)
                or row["source_item_id"] != expected_source_item_id):
            raise ValueError(
                f"effect_id {effect_id} already recorded with a different "
                "capability/source identity; refusing to reuse the intent")
        if row["payload_digest"] != payload_digest:
            raise ValueError(
                f"effect_id {effect_id} already recorded with a different payload digest; "
                "refusing to dispatch")
        if queue_item_id is not None and row["queue_item_id"] is None:
            queue_item_id = str(queue_item_id)
            if row["status"] in ("CLAIMED", "UNKNOWN"):
                raise ValueError(
                    f"effect_id {effect_id} cannot attach a queue projection "
                    f"while status is {row['status']}")
            # One stable effect may be referenced by duplicate queue candidates.
            # Preserve the first queue projection as canonical; later candidates
            # are deduplicated by effect_id and must not rebind that projection.
            changed = conn.execute("""
                UPDATE effect_outbox SET queue_item_id=?, updated_at=?
                WHERE effect_id=? AND queue_item_id IS NULL
                  AND status NOT IN ('CLAIMED', 'UNKNOWN')
            """, (queue_item_id, now, effect_id)).rowcount
            if changed != 1:
                row = conn.execute(
                    "SELECT * FROM effect_outbox WHERE effect_id=?", (effect_id,)
                ).fetchone()
                if row is None:
                    raise RuntimeError(
                        f"effect outbox intent disappeared during link: {effect_id}"
                    )
                if row["queue_item_id"] is None:
                    if row["status"] in ("CLAIMED", "UNKNOWN"):
                        raise ValueError(
                            f"effect_id {effect_id} cannot attach a queue projection "
                            f"while status is {row['status']}")
                    raise RuntimeError(
                        f"effect_id {effect_id} queue projection was not attached")
            else:
                row = conn.execute(
                    "SELECT * FROM effect_outbox WHERE effect_id=?", (effect_id,)
                ).fetchone()
        return EffectOutbox._row_dict(row)

    def record_intent(self, effect_id, capability, source_item_id, payload_digest,
                      queue_item_id=None, max_attempts=OUTBOX_MAX_ATTEMPTS) -> Dict[str, Any]:
        with self._conn() as conn:
            return self._record_with_conn(conn, effect_id, capability, source_item_id,
                                          payload_digest, queue_item_id, max_attempts)

    def get(self, effect_id) -> Optional[Dict[str, Any]]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM effect_outbox WHERE effect_id=?", (effect_id,)).fetchone()
        return self._row_dict(row)

    @staticmethod
    def _require_claim_token(worker_id, claim_generation):
        if not isinstance(worker_id, str) or not worker_id:
            raise ValueError("worker_id is required for claim transition")
        if type(claim_generation) is not int or claim_generation < 1:
            raise ValueError("claim_generation must be a positive integer")
        return worker_id, claim_generation

    def claim_with_token(self, effect_id, worker_id, lease_seconds: int = 30) -> Optional[Dict[str, Any]]:
        """Atomically claim READY and return the durable owner/generation token.

        A generation advances on every successful claim, including a retry by
        the same worker incarnation. The token must accompany every callback
        that mutates this claim; a stale token changes zero rows.
        """
        if not isinstance(worker_id, str) or not worker_id:
            raise ValueError("worker_id is required")
        import datetime as _dt
        lease_until = (_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(seconds=int(lease_seconds))).isoformat()
        now = _utcnow()
        with self._conn() as conn:
            changed = conn.execute("""
              UPDATE effect_outbox
              SET status='CLAIMED', worker_id=?, lease_expires_at=?,
                  attempts=attempts+1, claim_generation=claim_generation+1,
                  updated_at=?
              WHERE effect_id=? AND status='READY'
            """, (worker_id, lease_until, now, effect_id)).rowcount
            if changed != 1:
                return None
            row = conn.execute(
                "SELECT claim_generation FROM effect_outbox WHERE effect_id=? AND status='CLAIMED' AND worker_id=?",
                (effect_id, worker_id),
            ).fetchone()
            if row is None:
                raise RuntimeError("claimed effect disappeared before token read")
            return {
                "worker_id": worker_id,
                "claim_generation": int(row["claim_generation"]),
            }

    def claim(self, effect_id, worker_id, lease_seconds: int = 30) -> bool:
        """Compatibility predicate for callers that only need claim success.

        Mutation callbacks must use claim_with_token() and retain its token.
        """
        return self.claim_with_token(effect_id, worker_id, lease_seconds) is not None

    @staticmethod
    def _release_claim_with_conn(conn, effect_id, worker_id, claim_generation) -> bool:
        worker_id, claim_generation = EffectOutbox._require_claim_token(
            worker_id, claim_generation
        )
        changed = conn.execute("""
          UPDATE effect_outbox SET status='READY', worker_id=NULL,
            lease_expires_at=NULL, updated_at=?
          WHERE effect_id=? AND status='CLAIMED'
            AND worker_id=? AND claim_generation=?
        """, (_utcnow(), effect_id, worker_id, claim_generation)).rowcount
        return bool(changed)

    def release_claim(self, effect_id, *, worker_id=None, claim_generation=None) -> bool:
        """Release only the exact active claim that provably never dispatched."""
        with self._conn() as conn:
            return self._release_claim_with_conn(
                conn,effect_id,worker_id,claim_generation
            )

    @staticmethod
    def _complete_with_conn(conn, effect_id, result, observation_event_id,
                            expected_status="CLAIMED", *, worker_id=None,
                            claim_generation=None):
        """Complete UNKNOWN only through reconciliation; fence ordinary claims."""
        if expected_status not in ("CLAIMED", "UNKNOWN"):
            raise ValueError("invalid outbox completion state")
        where = "WHERE effect_id=? AND status=?"
        params = (_canonical_json(result), observation_event_id, _utcnow(),
                  effect_id, expected_status)
        if expected_status == "CLAIMED":
            worker_id, claim_generation = EffectOutbox._require_claim_token(
                worker_id, claim_generation)
            where += " AND worker_id=? AND claim_generation=?"
            params += (worker_id, claim_generation)
        changed = conn.execute(f"""
          UPDATE effect_outbox SET status='COMPLETED', result_json=?,
            observation_event_id=?, worker_id=NULL, lease_expires_at=NULL, updated_at=?
          {where}
        """, params).rowcount
        return bool(changed)

    def complete(self, effect_id, result, observation_event_id, *,
                 worker_id=None, claim_generation=None) -> bool:
        with self._conn() as conn:
            return self._complete_with_conn(
                conn, effect_id, result, observation_event_id,
                worker_id=worker_id, claim_generation=claim_generation)

    def mark_unknown(self, effect_id, error: Optional[str] = None, *,
                     worker_id=None, claim_generation=None) -> bool:
        """Quarantine only the exact active claim that observed ambiguity."""
        worker_id, claim_generation = self._require_claim_token(worker_id, claim_generation)
        with self._conn() as conn:
            changed = conn.execute("""
              UPDATE effect_outbox SET status='UNKNOWN', error=?, worker_id=NULL,
                lease_expires_at=NULL, updated_at=?
              WHERE effect_id=? AND status='CLAIMED'
                AND worker_id=? AND claim_generation=?
            """, (str(error)[:500] if error else None, _utcnow(),
                  effect_id, worker_id, claim_generation)).rowcount
        return bool(changed)

    def record_transient_failure(self, effect_id, error: Optional[str] = None, *,
                                 worker_id=None, claim_generation=None) -> Dict[str, Any]:
        """Account a confirmed non-execution failure for the exact active claim.

        Returns the record to READY while attempts remain, otherwise moves it
        to FAILED (dead-letter queue). Ambiguous failures must use mark_unknown.
        """
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM effect_outbox WHERE effect_id=?", (effect_id,)).fetchone()
            if row is None:
                raise KeyError(f"unknown effect_id: {effect_id}")
            worker_id, claim_generation = self._require_claim_token(
                worker_id, claim_generation)
            attempts = int(row["attempts"])
            status = "FAILED" if attempts >= int(row["max_attempts"]) else "READY"
            changed = conn.execute("""
              UPDATE effect_outbox SET status=?, error=?,
                worker_id=NULL, lease_expires_at=NULL, updated_at=?
              WHERE effect_id=? AND status='CLAIMED'
                AND worker_id=? AND claim_generation=?
            """, (status, str(error)[:500] if error else None, _utcnow(),
                  effect_id, worker_id, claim_generation)).rowcount
            if changed != 1:
                raise ValueError(
                    f"effect {effect_id} claim token is stale or no longer CLAIMED")
            row = conn.execute("SELECT * FROM effect_outbox WHERE effect_id=?", (effect_id,)).fetchone()
        return self._row_dict(row)

    @staticmethod
    def _recover_claimed_to_unknown_with_conn(conn) -> int:
        """Quarantine every claimed effect using the caller's transaction."""
        changed = conn.execute("""
          UPDATE effect_outbox SET status='UNKNOWN', worker_id=NULL,
            lease_expires_at=NULL, updated_at=?
          WHERE status='CLAIMED'
        """, (_utcnow(),)).rowcount
        return int(changed)

    def recover_claimed_to_unknown(self, *, confirmed_terminated: bool = False) -> int:
        """Recover standalone outbox claims only after confirmed worker termination.

        Claims linked to cognitive_queue rows must use
        PersistentCognitiveQueue.recover_after_confirmed_shutdown so both
        projections change in one transaction. The boolean is an explicit
        caller assertion, not independent proof; lease expiry is not proof.
        """
        if confirmed_terminated is not True:
            raise PermissionError(
                "recovery requires confirmed termination of all previous workers"
            )
        with self._conn() as conn:
            # Acquire the writer lock before checking links so a concurrent
            # intent/claim cannot appear between the guard and quarantine.
            conn.execute("BEGIN IMMEDIATE")
            linked_claim = conn.execute("""
                SELECT 1 FROM effect_outbox
                WHERE status='CLAIMED' AND queue_item_id IS NOT NULL
                LIMIT 1
            """).fetchone()
            if linked_claim is not None:
                raise RuntimeError(
                    "linked outbox claims must be recovered atomically through "
                    "PersistentCognitiveQueue.recover_after_confirmed_shutdown"
                )
            return self._recover_claimed_to_unknown_with_conn(conn)

    @staticmethod
    def _reconcile_with_conn(conn, effect_id, outcome, provider_receipt=None,
                             result=None, observation_event_id=None) -> Dict[str, Any]:
        """Reconcile one UNKNOWN outbox row inside the caller's transaction."""
        if outcome not in ("executed", "not_executed", "unknown"):
            raise ValueError(f"unknown reconciliation outcome: {outcome!r}")
        row = conn.execute(
            "SELECT * FROM effect_outbox WHERE effect_id=?", (effect_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown effect_id: {effect_id}")
        current = EffectOutbox._row_dict(row)
        if outcome == "unknown":
            return {**current, "changed": False}
        if current["status"] == "COMPLETED":
            if outcome == "executed":
                return {**current, "changed": False}
            raise ValueError(
                f"effect {effect_id} already recorded COMPLETED; "
                "provider 'not_executed' contradicts the recorded outcome")
        if current["status"] != "UNKNOWN":
            raise ValueError(
                f"effect {effect_id} in {current['status']} cannot be reconciled; "
                "only UNKNOWN effects may transition")
        if outcome == "not_executed":
            stored = result if result is not None else {
                "reconciled": True, "provider_receipt": provider_receipt,
                "outcome": "not_executed"}
            changed = conn.execute("""
              UPDATE effect_outbox SET status='READY', result_json=?, error=NULL,
                worker_id=NULL, lease_expires_at=NULL, updated_at=?
              WHERE effect_id=? AND status='UNKNOWN'
            """, (_canonical_json(stored), _utcnow(), effect_id)).rowcount
        else:
            stored = result if result is not None else {
                "reconciled": True, "provider_receipt": provider_receipt,
                "outcome": "executed"}
            obs_id = observation_event_id or current.get("observation_event_id")
            changed = conn.execute("""
              UPDATE effect_outbox SET status='COMPLETED', result_json=?,
                observation_event_id=?, worker_id=NULL, lease_expires_at=NULL, updated_at=?
              WHERE effect_id=? AND status='UNKNOWN'
            """, (_canonical_json(stored), obs_id, _utcnow(), effect_id)).rowcount
        if changed != 1:
            raise RuntimeError(f"effect {effect_id} reconciliation state changed")
        updated = conn.execute(
            "SELECT * FROM effect_outbox WHERE effect_id=?", (effect_id,)
        ).fetchone()
        return {**EffectOutbox._row_dict(updated), "changed": True}

    def reconcile(self, effect_id, outcome, provider_receipt=None, result=None,
                  observation_event_id=None) -> Dict[str, Any]:
        """Reconcile only a standalone outbox effect with no queue projection.

        Linked effects must use CognitiveScheduler.reconcile_effect so the
        outbox state and cognitive_queue projection change in one transaction.
        """
        if outcome not in ("executed", "not_executed", "unknown"):
            raise ValueError(f"unknown reconciliation outcome: {outcome!r}")
        with self._conn() as conn:
            # Serialize the link check with any concurrent intent association.
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT queue_item_id FROM effect_outbox WHERE effect_id=?",
                (effect_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"unknown effect_id: {effect_id}")
            if outcome != "unknown" and row["queue_item_id"] is not None:
                raise RuntimeError(
                    "linked outbox effects must be reconciled atomically through "
                    "CognitiveScheduler.reconcile_effect"
                )
            return self._reconcile_with_conn(
                conn, effect_id, outcome, provider_receipt=provider_receipt,
                result=result, observation_event_id=observation_event_id)



class PersistentCognitiveQueue:
    """SQLite-backed priority queue. Pending thoughts survive process death/reboot."""
    def __init__(self, db_path: str | Path, worker_id: Optional[str] = None):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.worker_id = worker_id or f"queue-{uuid.uuid4().hex}"
        if not isinstance(self.worker_id, str) or not self.worker_id:
            raise ValueError("worker_id must be a non-empty string")
        self._init_schema()
        self.outbox = EffectOutbox(self.db_path)
        # Construction is not evidence that another worker terminated.
        # Never mutate another instance's in-flight cognition or outbox claim
        # merely because this queue object was opened.

    def recover_after_confirmed_shutdown(self, *, confirmed_terminated: bool = False) -> Dict[str, int]:
        """Operator-gated recovery ONLY after exclusive worker termination is proven.

        Caller must establish that ALL previous workers using this database
        have terminated and no concurrent scheduler can resume. Lease expiry,
        opening a new instance, and process-local exceptions are not proof.
        Do not call during ordinary startup. External effects are quarantined,
        never redispatched, pending authoritative provider reconciliation.
        """
        if confirmed_terminated is not True:
            raise PermissionError("recovery requires confirmed termination of all previous workers")
        # Queue and outbox rows share this SQLite database. Keep all recovery
        # transitions in one transaction so an interrupted recovery cannot
        # leave the local projections in different states.
        with self._conn() as conn:
            action_count = conn.execute(
                "UPDATE cognitive_queue SET status=?, worker_id=NULL, updated_at=? WHERE status=? AND kind=?",
                (ItemStatus.UNKNOWN.value, _utcnow(), ItemStatus.PROCESSING.value,
                 ItemKind.ACTION_CANDIDATE.value),
            ).rowcount
            cognition_count = conn.execute(
                "UPDATE cognitive_queue SET status=?, worker_id=NULL, updated_at=? WHERE status=?",
                (ItemStatus.PENDING.value, _utcnow(), ItemStatus.PROCESSING.value),
            ).rowcount
            effect_count = EffectOutbox._recover_claimed_to_unknown_with_conn(conn)
        return {"quarantined_actions": int(action_count),
                "requeued_cognition": int(cognition_count),
                "quarantined_effects": effect_count}

    def _conn(self):
        conn=sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory=sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_schema(self):
        with self._conn() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS cognitive_queue(
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                content_json TEXT NOT NULL,
                priority REAL NOT NULL,
                depth INTEGER NOT NULL,
                parent_id TEXT,
                created_tick INTEGER NOT NULL,
                ttl INTEGER NOT NULL,
                status TEXT NOT NULL,
                worker_id TEXT,
                claim_generation INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_cq_status_priority
              ON cognitive_queue(status, priority DESC, created_tick ASC);
            CREATE TABLE IF NOT EXISTS scheduler_state(
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS scheduler_receipts(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tick INTEGER NOT NULL,
                previous_hash TEXT NOT NULL,
                receipt_hash TEXT NOT NULL UNIQUE,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS capability_results(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tick INTEGER NOT NULL,
                capability TEXT NOT NULL,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                receipt_hash TEXT,
                observation_event_id TEXT UNIQUE,
                source_item_id TEXT,
                source_depth INTEGER,
                priority REAL,
                created_at TEXT NOT NULL
            );
            """)
            queue_columns={row["name"] for row in conn.execute("PRAGMA table_info(cognitive_queue)")}
            if "worker_id" not in queue_columns:
                conn.execute("ALTER TABLE cognitive_queue ADD COLUMN worker_id TEXT")
            if "claim_generation" not in queue_columns:
                conn.execute(
                    "ALTER TABLE cognitive_queue ADD COLUMN claim_generation INTEGER NOT NULL DEFAULT 0"
                )
            columns={row["name"] for row in conn.execute("PRAGMA table_info(capability_results)")}
            for name,definition in (
                ("observation_event_id","TEXT"),
                ("source_item_id","TEXT"),
                ("source_depth","INTEGER"),
                ("priority","REAL"),
            ):
                if name not in columns:
                    conn.execute(f"ALTER TABLE capability_results ADD COLUMN {name} {definition}")
            conn.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_capability_observation
              ON capability_results(observation_event_id)
              WHERE observation_event_id IS NOT NULL""")

    @staticmethod
    def _insert_with_conn(conn,item:CognitiveItem)->bool:
        """Insert one queue item using the caller's transaction."""
        if item.kind is not ItemKind.OBSERVATION and item.depth>MAX_DEPTH:
            item.status=ItemStatus.DROPPED_DEPTH
            return False
        now=_utcnow()
        changed=conn.execute("""
          INSERT OR IGNORE INTO cognitive_queue
          (id,kind,content_json,priority,depth,parent_id,created_tick,ttl,status,created_at,updated_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """,(item.id,item.kind.value,_canonical_json(item.content),float(item.priority),
             int(item.depth),item.parent_id,int(item.created_tick),int(item.ttl),
             ItemStatus.PENDING.value,now,now)).rowcount
        return bool(changed)

    def push(self, item: CognitiveItem) -> bool:
        with self._conn() as conn:
            return self._insert_with_conn(conn,item)

    def push_with_effect_intent(self, item: CognitiveItem, effect_id: str,
                                capability: str, source_item_id, payload_digest: str) -> bool:
        """Atomically persist an action candidate AND its outbox intent.

        One transaction: either both the queue row and the intent record
        exist, or neither does. A payload-digest conflict for the same
        effect ID raises ValueError and rolls the whole transaction back.
        """
        with self._conn() as conn:
            inserted = self._insert_with_conn(conn, item)
            if not inserted:
                return False
            EffectOutbox._record_with_conn(conn, effect_id, capability, source_item_id,
                                           payload_digest, queue_item_id=item.id)
            return True

    @staticmethod
    def _reconcile_mark_with_conn(conn, item_id: str, status: ItemStatus,
                                  *, allow_already_target: bool = False) -> bool:
        """Move one UNKNOWN action projection within a caller-owned transaction."""
        if status not in (ItemStatus.COMPLETED, ItemStatus.PENDING):
            raise ValueError("reconciliation may only resolve UNKNOWN to COMPLETED or PENDING")
        changed = conn.execute("""
          UPDATE cognitive_queue SET status=?, updated_at=?
          WHERE id=? AND kind=? AND status=?
        """, (status.value, _utcnow(), item_id,
              ItemKind.ACTION_CANDIDATE.value, ItemStatus.UNKNOWN.value)).rowcount
        if changed == 1:
            return True
        if allow_already_target:
            row = conn.execute(
                "SELECT kind,status FROM cognitive_queue WHERE id=?", (item_id,)
            ).fetchone()
            if (row is not None
                    and row["kind"] == ItemKind.ACTION_CANDIDATE.value
                    and row["status"] == status.value):
                return False
        raise ValueError("only a quarantined UNKNOWN action candidate can be reconciled")

    def reconcile_mark(self, item_id: str, status: ItemStatus):
        """Explicit reconciliation transition for a quarantined action claim."""
        with self._conn() as conn:
            return self._reconcile_mark_with_conn(conn, item_id, status)


    @staticmethod
    def _require_claim_token(worker_id, claim_generation):
        if not isinstance(worker_id, str) or not worker_id:
            raise ValueError("worker_id is required for queue claim transition")
        if type(claim_generation) is not int or claim_generation < 1:
            raise ValueError("claim_generation must be a positive integer")
        return worker_id, claim_generation

    @staticmethod
    def _transition_claim_with_conn(conn, item_id, status, worker_id, claim_generation):
        worker_id, claim_generation = PersistentCognitiveQueue._require_claim_token(
            worker_id, claim_generation
        )
        if status is ItemStatus.PROCESSING:
            raise ValueError("PROCESSING must be acquired through an atomic queue claim")
        changed = conn.execute("""
          UPDATE cognitive_queue SET status=?, updated_at=?
          WHERE id=? AND status=? AND worker_id=? AND claim_generation=?
        """, (status.value, _utcnow(), item_id, ItemStatus.PROCESSING.value,
              worker_id, claim_generation)).rowcount
        return bool(changed)

    def claim_item(self, item_id: str, worker_id: Optional[str] = None) -> Optional[CognitiveItem]:
        """Atomically claim one known PENDING item and return its fencing token."""
        worker_id = worker_id or self.worker_id
        if not isinstance(worker_id, str) or not worker_id:
            raise ValueError("worker_id must be a non-empty string")
        with self._conn() as conn:
            changed = conn.execute("""
              UPDATE cognitive_queue
              SET status=?, worker_id=?, claim_generation=claim_generation+1, updated_at=?
              WHERE id=? AND status=?
            """, (ItemStatus.PROCESSING.value, worker_id, _utcnow(),
                  item_id, ItemStatus.PENDING.value)).rowcount
            if changed != 1:
                return None
            row = conn.execute("""
              SELECT * FROM cognitive_queue
              WHERE id=? AND status=? AND worker_id=?
            """, (item_id, ItemStatus.PROCESSING.value, worker_id)).fetchone()
            if row is None:
                raise RuntimeError("claimed cognitive item disappeared before token read")
        return self._row(row, ItemStatus.PROCESSING)

    @staticmethod
    def _owns_claim_with_conn(conn, item_id, *, worker_id, claim_generation) -> bool:
        worker_id, claim_generation = PersistentCognitiveQueue._require_claim_token(
            worker_id, claim_generation
        )
        row = conn.execute("""
          SELECT 1 FROM cognitive_queue
          WHERE id=? AND status=? AND worker_id=? AND claim_generation=?
        """, (item_id, ItemStatus.PROCESSING.value, worker_id, claim_generation)).fetchone()
        return row is not None

    def assert_claim_owned_with_conn(self, conn, item_id, *, worker_id, claim_generation) -> None:
        """Fail closed unless this exact worker generation still owns the row."""
        if not self._owns_claim_with_conn(
            conn, item_id, worker_id=worker_id, claim_generation=claim_generation
        ):
            raise PermissionError("cognitive claim is no longer owned by this worker generation")

    def owns_claim(self, item_id: str, *, worker_id, claim_generation) -> bool:
        worker_id, claim_generation = self._require_claim_token(worker_id, claim_generation)
        with self._conn() as conn:
            return self._owns_claim_with_conn(
                conn, item_id, worker_id=worker_id, claim_generation=claim_generation
            )

    def pop_budgeted(self,current_tick:int,max_items:int=8,max_ms:int=300,
                     worker_id:Optional[str]=None)->List[CognitiveItem]:
        worker_id = worker_id or self.worker_id
        if not isinstance(worker_id, str) or not worker_id:
            raise ValueError("worker_id must be a non-empty string")
        start=time.perf_counter(); out=[]
        while len(out)<max_items and (time.perf_counter()-start)*1000<max_ms:
            with self._conn() as conn:
                row=conn.execute("""
                  SELECT * FROM cognitive_queue WHERE status=?
                  ORDER BY priority DESC, created_tick ASC LIMIT 1
                """,(ItemStatus.PENDING.value,)).fetchone()
                if row is None: break
                if current_tick-int(row["created_tick"])>int(row["ttl"]):
                    conn.execute("""
                      UPDATE cognitive_queue SET status=?,updated_at=?
                      WHERE id=? AND status=?
                    """,(ItemStatus.DROPPED_TTL.value,_utcnow(),row["id"],
                         ItemStatus.PENDING.value))
                    continue
                changed=conn.execute("""
                  UPDATE cognitive_queue
                  SET status=?,worker_id=?,claim_generation=claim_generation+1,updated_at=?
                  WHERE id=? AND status=?
                """,(ItemStatus.PROCESSING.value,worker_id,_utcnow(),row["id"],
                     ItemStatus.PENDING.value)).rowcount
                if not changed: continue
                claimed=conn.execute("""
                  SELECT * FROM cognitive_queue
                  WHERE id=? AND status=? AND worker_id=?
                """,(row["id"],ItemStatus.PROCESSING.value,worker_id)).fetchone()
                if claimed is None:
                    raise RuntimeError("claimed cognitive item disappeared before token read")
            out.append(self._row(claimed,ItemStatus.PROCESSING))
        return out

    def mark_claimed(self,item_id:str,status:ItemStatus,*,worker_id,claim_generation)->bool:
        """Transition only the exact worker/generation currently holding an item."""
        with self._conn() as conn:
            return self._transition_claim_with_conn(
                conn,item_id,status,worker_id,claim_generation
            )

    def complete_claim_with_followups_with_conn(self,conn,item_id:str,
                                                followups:List[CognitiveItem],*,
                                                worker_id,claim_generation)->Optional[int]:
        """Complete a claim and publish follow-ups in the caller's transaction."""
        if not self._transition_claim_with_conn(
            conn,item_id,ItemStatus.COMPLETED,worker_id,claim_generation
        ):
            return None
        inserted=0
        for item in followups:
            if self._insert_with_conn(conn,item):
                inserted+=1
        return inserted

    def complete_claim_with_followups(self,item_id:str,followups:List[CognitiveItem],*,
                                      worker_id,claim_generation)->Optional[int]:
        """Complete one exact claim and insert its follow-up thoughts atomically."""
        with self._conn() as conn:
            return self.complete_claim_with_followups_with_conn(
                conn,item_id,followups,worker_id=worker_id,
                claim_generation=claim_generation
            )

    def mark(self,item_id:str,status:ItemStatus):
        """Compatibility state API that cannot mutate a live or ambiguous claim.

        PROCESSING ownership transitions require mark_claimed() with the durable
        worker/generation token. ACTION_CANDIDATE quarantine is only permitted
        from a live claim; UNKNOWN can leave only through reconcile_mark().
        """
        with self._conn() as conn:
            row=conn.execute(
                "SELECT kind,status FROM cognitive_queue WHERE id=?",(item_id,)
            ).fetchone()
            if row is None:
                return
            current=ItemStatus(row["status"])
            kind=row["kind"]
            if (kind==ItemKind.ACTION_CANDIDATE.value
                    and current is ItemStatus.UNKNOWN and status is not ItemStatus.UNKNOWN):
                raise ValueError("quarantined capability effect requires explicit reconciliation")
            if current is ItemStatus.PROCESSING:
                raise PermissionError(
                    "PROCESSING queue transitions require worker_id and claim_generation"
                )
            if status is ItemStatus.PROCESSING:
                raise ValueError(
                    "PROCESSING status must be acquired through claim_item() or pop_budgeted()"
                )
            if (kind==ItemKind.ACTION_CANDIDATE.value
                    and status is ItemStatus.UNKNOWN and current is not ItemStatus.UNKNOWN):
                raise PermissionError("action candidates must be claimed before quarantine")
            conn.execute("""
              UPDATE cognitive_queue SET status=?,updated_at=?
              WHERE id=? AND status=?
            """,(status.value,_utcnow(),item_id,current.value))

    def pending_count(self)->int:
        with self._conn() as conn:
            return int(conn.execute("SELECT COUNT(*) c FROM cognitive_queue WHERE status=?",
                                    (ItemStatus.PENDING.value,)).fetchone()["c"])

    def unknown_count(self)->int:
        """Count quarantined capability effects requiring reconciliation."""
        with self._conn() as conn:
            return int(conn.execute(
                "SELECT COUNT(*) c FROM cognitive_queue WHERE kind=? AND status=?",
                (ItemKind.ACTION_CANDIDATE.value, ItemStatus.UNKNOWN.value),
            ).fetchone()["c"])

    def unknown_effects(self, limit: int = 25) -> List[Dict[str, Any]]:
        """Read-only, payload-redacted reconciliation inventory.

        Counts remain authoritative through unknown_count(); this bounded list
        never returns capability arguments or authorizes a retry.
        """
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be an integer between 1 and 100")
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT id, parent_id, created_tick, content_json
                   FROM cognitive_queue WHERE kind=? AND status=?
                   ORDER BY created_tick ASC, id ASC LIMIT ?""",
                (ItemKind.ACTION_CANDIDATE.value, ItemStatus.UNKNOWN.value, limit),
            ).fetchall()
        effects = []
        for row in rows:
            # Damaged persisted payloads must not hide an unresolved effect or
            # prevent operators from inspecting the remaining quarantine queue.
            # Preserve the raw-content digest for offline reconciliation.
            try:
                content = json.loads(row["content_json"])
            except (ValueError, TypeError):
                content = None
            candidate = content.get("candidate") if isinstance(content, dict) else None
            capability = candidate.get("capability") if isinstance(candidate, dict) else None
            effects.append({
                "id": row["id"],
                "parent_id": row["parent_id"],
                "created_tick": int(row["created_tick"]),
                "capability": capability if isinstance(capability, str) else None,
                "content_sha256": _sha256(row["content_json"]),
            })
        return effects

    def pending_items(self,limit:int=25)->List[Dict[str,Any]]:
        with self._conn() as conn:
            rows=conn.execute("""
              SELECT * FROM cognitive_queue WHERE status=?
              ORDER BY priority DESC,created_tick ASC LIMIT ?
            """,(ItemStatus.PENDING.value,int(limit))).fetchall()
        return [{"id":r["id"],"kind":r["kind"],"content":json.loads(r["content_json"]),
                 "priority":float(r["priority"]),"depth":int(r["depth"]),
                 "parent_id":r["parent_id"],"created_tick":int(r["created_tick"]),
                 "ttl":int(r["ttl"])} for r in rows]

    @staticmethod
    def _row(r,status):
        keys=set(r.keys())
        return CognitiveItem(id=r["id"],kind=ItemKind(r["kind"]),content=json.loads(r["content_json"]),
          priority=float(r["priority"]),depth=int(r["depth"]),parent_id=r["parent_id"],
          created_tick=int(r["created_tick"]),ttl=int(r["ttl"]),status=status,
          worker_id=r["worker_id"] if "worker_id" in keys else None,
          claim_generation=int(r["claim_generation"] or 0) if "claim_generation" in keys else 0)

class CognitiveEventBus:
    def __init__(self): self._subscribers=[]
    def subscribe(self,callback): self._subscribers.append(callback)
    def publish(self,event_type,payload):
        for callback in list(self._subscribers):
            callback(event_type,dict(payload))

class WindowsCapabilityRegistry:
    """Bounded local prototype registry; no silent privilege escalation."""
    def __init__(self,stack:VictorCognitionStack):
        self.stack=stack
        self.handlers={
          "memory.commit_reflection":self._commit_reflection,
          "cognition.queue_human_review":self._queue_human_review,
        }
    def contains(self,capability): return capability in self.handlers
    def execute(self,capability,payload,idempotency_key=None):
        if capability not in self.handlers: raise KeyError("unregistered capability: "+capability)
        # The stable effect ID travels with the dispatch as the provider
        # idempotency key. Handlers ignore the extra key; a provider that
        # honours it can dedupe a retried dispatch by this key.
        if idempotency_key is not None:
            payload = {**dict(payload), "_idempotency_key": idempotency_key}
        return self.handlers[capability](payload)
    def _commit_reflection(self,payload):
        text=str(payload.get("text","")).strip()
        if not text: raise ValueError("reflection text required")
        return {"memory":self.stack.remember(text,source="scheduler",kind="reflection",
          metadata={"scheduler_item_id":payload.get("item_id")})}
    def _queue_human_review(self,payload):
        aid=int(payload["stack_action_id"])
        actions={a["id"]:a for a in self.stack.actions()}
        action=actions.get(aid)
        if action is None: raise ValueError(f"unknown stack action {aid}")
        # Critical boundary: scheduler never calls approve_action().
        return {"queued":action["status"]=="proposed","requires_human_approval":True,"action":action}

class CognitiveScheduler:
    """One persistent macrotick clock coordinating cognition without recursive think()."""
    def __init__(self,stack:VictorCognitionStack,physiology:VictorPhysiologyRuntime,db_path:str|Path):
        self.stack=stack; self.physiology=physiology; self.db_path=Path(db_path)
        if Path(self.stack.db_path).resolve() != self.db_path.resolve():
            raise ValueError(
                "CognitiveScheduler requires the cognition stack and queue to share one SQLite database"
            )
        # One durable identity is shared by cognitive-queue and outbox claims.
        self.worker_incarnation_id = uuid.uuid4().hex
        self.worker_id = f"scheduler-{self.worker_incarnation_id}"
        self.queue=PersistentCognitiveQueue(self.db_path,worker_id=self.worker_id)
        self.outbox=self.queue.outbox
        # Crash-injection hook (tests only): called with the effect ID after
        # a successful dispatch and before the result is committed. Raising
        # BaseException here simulates a process kill in that window.
        self.crash_hook: Optional[Callable[[str], None]] = None
        self.outbox_lease_seconds = 30
        self.registry=WindowsCapabilityRegistry(stack)
        self.bus=CognitiveEventBus(); self.bus.subscribe(self._ingest_event)
        self.current_tick=max(self._load_tick(),int(self.stack.tick))
        self._recover_missing_observations()

    def _conn(self):
        conn=sqlite3.connect(self.db_path,timeout=30); conn.row_factory=sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _load_tick(self):
        with self._conn() as conn:
            row=conn.execute("SELECT value FROM scheduler_state WHERE key='current_tick'").fetchone()
        try: return max(0,int(row["value"])) if row else 0
        except (TypeError,ValueError): return 0

    def _save_tick(self):
        with self._conn() as conn:
            conn.execute("""INSERT INTO scheduler_state(key,value,updated_at)
              VALUES('current_tick',?,?)
              ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at""",
              (str(self.current_tick),_utcnow()))

    def publish_query(self,text:str,priority:float=1.0)->str:
        text=(text or "").strip()
        if not text: raise ValueError("query text cannot be empty")
        eid=uuid.uuid4().hex
        self.bus.publish("query",{"event_id":eid,"text":text,"priority":float(priority)})
        return eid

    def _ingest_event(self,event_type,payload):
        mapping={"query":ItemKind.QUERY,"conflict":ItemKind.CONFLICT,
          "prediction_expired":ItemKind.PREDICTION,"goal_unsatisfied":ItemKind.GOAL,
          "sensor_change":ItemKind.THOUGHT,"action_observation":ItemKind.OBSERVATION}
        depth=max(0,int(payload.get("_depth",0)))
        parent_id=payload.get("_parent_id")
        content={k:v for k,v in payload.items() if not str(k).startswith("_")}
        self.queue.push(CognitiveItem(
          id=payload.get("event_id") or uuid.uuid4().hex,
          kind=mapping.get(event_type,ItemKind.THOUGHT),
          content={"event_type":event_type,**content},
          priority=max(0.0,min(1.0,float(payload.get("priority",0.5)))),
          depth=depth,parent_id=parent_id,created_tick=self.current_tick))

    def _retrieve_context(self,item):
        query=str(item.content.get("text") or item.content.get("step") or item.content.get("event_type") or _canonical_json(item.content))
        return {
          "relevant_memories":self.stack.search(query,limit=8),
          "active_goals":[g for g in self.stack.goals() if g.get("status")=="active"][:12],
        }

    def _reason(self,item,context,*,connection=None):
        out={"followup_thoughts":[],"candidate_actions":[]}
        if item.kind in (ItemKind.QUERY,ItemKind.GOAL,ItemKind.CONFLICT,ItemKind.PREDICTION):
            text=str(item.content.get("text") or item.content.get("message") or _canonical_json(item.content))
            before={a["id"] for a in self.stack.actions(connection=connection)}
            report=self.stack.cycle(
                text,source="scheduler",tick=self.current_tick,connection=connection
            )
            after=[a for a in self.stack.actions(connection=connection) if a["id"] not in before]
            out["followup_thoughts"].append({
              "kind":ItemKind.THOUGHT,
              "content":{"step":"review_cognition_cycle","origin_item_id":item.id,"text":text,
                         "stack_tick":report["tick"],"stack_action_ids":[a["id"] for a in after]},
              "priority":max(0.05,item.priority-0.05)})
            return out

        if item.kind==ItemKind.OBSERVATION:
            out["followup_thoughts"].append({
              "kind":ItemKind.THOUGHT,
              "content":{"step":"review_action_observation","origin_item_id":item.id,
                         "capability":item.content.get("capability"),
                         "status":item.content.get("status"),
                         "receipt_hash":item.content.get("receipt_hash"),
                         "outcome":item.content.get("outcome")},
              "priority":max(0.05,item.priority-0.05)})
            return out

        if item.kind==ItemKind.ACTION_CANDIDATE:
            candidate=item.content.get("candidate")
            if isinstance(candidate,dict):
                out["candidate_actions"].append(dict(candidate))
            return out

        if item.kind==ItemKind.THOUGHT:
            # Observation review is the terminal cognition node for one action chain.
            # It becomes a real next thought without recursively spawning another
            # capability execution loop.
            if item.content.get("step")=="review_action_observation":
                return out
            action_ids=[int(x) for x in item.content.get("stack_action_ids",[])]
            actions={a["id"]:a for a in self.stack.actions(connection=connection)}
            for aid in action_ids:
                action=actions.get(aid)
                if action and action["status"]=="proposed":
                    out["candidate_actions"].append({
                      "capability":"cognition.queue_human_review",
                      "payload":{"stack_action_id":aid},"score":0.8,
                      "source_item_id":item.id,"source_depth":item.depth})
            reflection=(f"Scheduler reflection for item {item.id}: "
                        f"{len(context['relevant_memories'])} relevant memories, "
                        f"{len(context['active_goals'])} active goals, "
                        f"{len(action_ids)} new proposed actions.")
            out["candidate_actions"].append({
              "capability":"memory.commit_reflection",
              "payload":{"text":reflection,"item_id":item.id},
              "score":max(0.1,item.priority-0.15),"source_item_id":item.id,
              "source_depth":item.depth})
        return out

    @staticmethod
    def _choice_rank(candidates):
        valid=[dict(c) for c in candidates if c.get("capability") and 0<=float(c.get("score",0))<=1]
        return sorted(valid,key=lambda c:(float(c.get("score",0)),str(c["capability"]),str(c.get("source_item_id",""))),reverse=True)

    def _execute(self,ranked,queue_item_id=None,queue_claim_token=None):
        if not ranked: return {"executed":None,"status":"NO_ACTION"}
        if queue_item_id is not None:
            if not isinstance(queue_claim_token,dict):
                raise ValueError("queue claim token is required for selected action execution")
            self.queue._require_claim_token(
                queue_claim_token.get("worker_id"),queue_claim_token.get("claim_generation")
            )
        c=ranked[0]; capability=str(c["capability"])
        if not self.registry.contains(capability):
            return {"executed":None,"status":"BLOCKED_UNREGISTERED_CAPABILITY","capability":capability}
        payload=dict(c.get("payload",{}))
        effect_id=effect_id_for_candidate(c)
        digest=_payload_digest(payload)
        # 1. Atomic intent record, before any dispatch. Same effect ID with
        # a different payload raises ValueError: never silently re-dispatch.
        intent=self.outbox.record_intent(
            effect_id,capability,c.get("source_item_id"),digest,
            queue_item_id=queue_item_id)
        # 2. Dedupe: an already-completed effect returns its stored outcome
        # without touching the provider again.
        if intent["status"]=="COMPLETED" and intent.get("result_json"):
            stored=json.loads(intent["result_json"])
            if queue_item_id is not None:
                with self._conn() as conn:
                    if not self.queue._transition_claim_with_conn(
                        conn,queue_item_id,ItemStatus.COMPLETED,
                        queue_claim_token["worker_id"],queue_claim_token["claim_generation"]
                    ):
                        raise RuntimeError("queue claim changed before completed-effect acknowledgement")
            return stored
        if intent["status"]=="UNKNOWN":
            raise RuntimeError(
                f"ambiguous capability effect {effect_id} requires reconciliation")
        if intent["status"]=="FAILED":
            return {"executed":None,"status":"BLOCKED_DLQ","capability":capability,
                    "effect_id":effect_id}
        # 3. Concurrency-safe claim: exactly one worker may dispatch.
        worker_id=self.worker_id
        claim_token=self.outbox.claim_with_token(
            effect_id,worker_id,lease_seconds=self.outbox_lease_seconds)
        if claim_token is None:
            return {"executed":None,"status":"BLOCKED_CLAIMED","capability":capability,
                    "effect_id":effect_id}
        claim_generation=claim_token["claim_generation"]
        proposal=ActionProposal(
          name=capability,capability=capability,provenance="victor-cognitive-scheduler",
          required_authorities=("local_owner",),consequence=.08,irreversibility=.05,
          uncertainty=max(0.0,1.0-float(c.get("score",.5))),novelty=.10,arousal=0,
          urgency=0,capability_power=.10,
          metadata={"scheduler_tick":self.current_tick,"source_item_id":c.get("source_item_id"),
                    "effect_id":effect_id,"idempotency_key":effect_id})
        # 4. Dispatch with the stable effect ID as the provider idempotency key.
        d=self.physiology.execute(proposal,
            lambda:self.registry.execute(capability,payload,idempotency_key=effect_id))
        # Governance rejected before the executor ran: provably no effect,
        # so release the claim and record the rejection exactly as before.
        # A governance rejection provably never ran. Its outbox release is
        # committed with the queue/result/observation transaction below.
        # A provider timeout / connection failure is ambiguous: the effect
        # may or may not have happened. Quarantine it; never record a
        # terminal outcome and never auto-retry.
        if d.status.value=="FAILED":
            outcome=d.actual_outcome or {}
            error_type=str(outcome.get("error_type",""))
            if error_type in _AMBIGUOUS_ERROR_TYPES:
                if not self.outbox.mark_unknown(
                    effect_id,
                    f"ambiguous provider failure: {error_type}: {outcome.get('error','')}",
                    worker_id=worker_id,claim_generation=claim_generation):
                    raise RuntimeError("outbox claim changed before ambiguous failure quarantine")
                raise RuntimeError(
                    f"ambiguous provider failure for effect {effect_id} "
                    f"({error_type}); requires reconciliation")
        observation_id=uuid.uuid4().hex
        result={"capability":capability,"decision_status":d.status.value,
          "governance_mode":d.governance_mode.value,"reasons":list(d.reasons),
          "receipt_hash":d.receipt_hash,"outcome":d.actual_outcome,
          "observation_event_id":observation_id,
          "effect_id":effect_id,"idempotency_key":effect_id}
        # Crash-injection point (tests only): after dispatch, before commit.
        if self.crash_hook is not None:
            self.crash_hook(effect_id)
        observation=CognitiveItem(
          id=observation_id,kind=ItemKind.OBSERVATION,
          content={"event_type":"action_observation","capability":capability,
            "status":d.status.value,"governance_mode":d.governance_mode.value,
            "reasons":list(d.reasons),"receipt_hash":d.receipt_hash,
            "outcome":d.actual_outcome},
          priority=max(0.05,min(1.0,float(c.get("score",0.5)))),
          depth=int(c.get("source_depth",0))+1,
          parent_id=c.get("source_item_id"),created_tick=self.current_tick)
        # 5. One atomic transaction: capability result + observation +
        # outbox completion. If any part fails, all of it rolls back and the
        # outbox stays CLAIMED (restart recovery quarantines it UNKNOWN).
        # A REJECTED dispatch provably never ran, so its outcome is recorded
        # in capability_results exactly as before but the outbox is NOT
        # completed: a later dispatch must re-evaluate governance.
        record_outcome = d.status.value != "REJECTED"
        with self._conn() as conn:
            conn.execute("""INSERT INTO capability_results
              (tick,capability,status,payload_json,receipt_hash,observation_event_id,
               source_item_id,source_depth,priority,created_at)
              VALUES(?,?,?,?,?,?,?,?,?,?)""",
              (self.current_tick,capability,d.status.value,_canonical_json(result),d.receipt_hash,
               observation_id,c.get("source_item_id"),int(c.get("source_depth",0)),
               float(c.get("score",0.5)),_utcnow()))
            if not self.queue._insert_with_conn(conn,observation):
                raise RuntimeError("durable observation id collision")
            if record_outcome:
                if not EffectOutbox._complete_with_conn(
                    conn,effect_id,{"executed":result,"status":d.status.value},observation_id,
                    worker_id=worker_id,claim_generation=claim_generation):
                    raise RuntimeError("outbox claim changed before completion; rolling back result")
            else:
                if not EffectOutbox._release_claim_with_conn(
                    conn,effect_id,worker_id,claim_generation
                ):
                    raise RuntimeError("outbox claim changed before governance rejection release")
            if queue_item_id is not None:
                if not self.queue._transition_claim_with_conn(
                    conn,queue_item_id,ItemStatus.COMPLETED,
                    queue_claim_token["worker_id"],queue_claim_token["claim_generation"]
                ):
                    raise RuntimeError("queue claim changed before result commit; rolling back result")
        return {"executed":result,"status":d.status.value}

    def reconcile_effect(self, effect_id, outcome, provider_receipt=None):
        """Reconcile an UNKNOWN effect and its queue projection atomically.

        The outbox row, capability result, observation, and linked action queue
        projection share one SQLite transaction. A crash or failed queue update
        therefore cannot leave READY/COMPLETED in one table and UNKNOWN in the
        other. Provider receipt authenticity remains an external approval gate.
        """
        if outcome not in ("executed", "not_executed", "unknown"):
            raise ValueError(f"unknown reconciliation outcome: {outcome!r}")
        with self._conn() as conn:
            raw = conn.execute(
                "SELECT * FROM effect_outbox WHERE effect_id=?", (effect_id,)
            ).fetchone()
            if raw is None:
                raise KeyError(f"unknown effect_id: {effect_id}")
            row = EffectOutbox._row_dict(raw)
            if outcome == "unknown":
                return {"effect_id": effect_id, "status": row["status"],
                        "outcome": "unknown", "changed": False}

            if row["status"] == "COMPLETED" and row.get("result_json"):
                if outcome == "not_executed":
                    raise ValueError(
                        f"effect {effect_id} already recorded COMPLETED; "
                        "provider 'not_executed' contradicts the recorded outcome")
                if row.get("queue_item_id"):
                    try:
                        self.queue._reconcile_mark_with_conn(
                            conn, row["queue_item_id"], ItemStatus.COMPLETED,
                            allow_already_target=True)
                    except ValueError:
                        # Preserve the existing idempotent repair behavior for
                        # legacy/missing queue projections; do not rewrite them.
                        pass
                return {"effect_id": effect_id, "status": "COMPLETED",
                        "outcome": "executed", "changed": False,
                        "executed": json.loads(row["result_json"])}

            if row["status"] != "UNKNOWN":
                raise ValueError(
                    f"effect {effect_id} in {row['status']} cannot be reconciled; "
                    "only UNKNOWN effects may transition")

            if outcome == "not_executed":
                # Update outbox first intentionally: the following queue update
                # must roll it back if the queue projection is missing or invalid.
                reconciled = EffectOutbox._reconcile_with_conn(
                    conn, effect_id, "not_executed",
                    provider_receipt=provider_receipt)
                if row.get("queue_item_id"):
                    self.queue._reconcile_mark_with_conn(
                        conn, row["queue_item_id"], ItemStatus.PENDING,
                        allow_already_target=True)
                return {"effect_id": effect_id, "status": reconciled["status"],
                        "outcome": "not_executed",
                        "changed": reconciled["changed"]}

            # outcome == "executed"
            observation_id = row.get("observation_event_id") or uuid.uuid4().hex
            result = {
                "capability": row["capability"],
                "decision_status": "EXECUTED",
                "governance_mode": "GREEN",
                "reasons": ["provider_reconciliation"],
                "receipt_hash": (
                    row.get("result_json")
                    and json.loads(row["result_json"]).get("executed", {}).get("receipt_hash")
                ),
                "outcome": {
                    "ok": True,
                    "result": {"reconciled": True, "provider_receipt": provider_receipt},
                },
                "observation_event_id": observation_id,
                "effect_id": effect_id,
                "idempotency_key": effect_id,
            }
            stored = {"executed": result, "status": "EXECUTED"}
            conn.execute("""INSERT OR IGNORE INTO capability_results
              (tick,capability,status,payload_json,receipt_hash,observation_event_id,
               source_item_id,source_depth,priority,created_at)
              VALUES(?,?,?,?,?,?,?,?,?,?)""",
              (self.current_tick, row["capability"], "EXECUTED",
               _canonical_json(result), result["receipt_hash"], observation_id,
               row.get("source_item_id"), 0, 0.5, _utcnow()))
            observation = CognitiveItem(
                id=observation_id,
                kind=ItemKind.OBSERVATION,
                content={
                    "event_type": "action_observation",
                    "capability": row["capability"],
                    "status": "EXECUTED",
                    "governance_mode": "GREEN",
                    "reasons": ["provider_reconciliation"],
                    "receipt_hash": result["receipt_hash"],
                    "outcome": result["outcome"],
                    "reconciled": True,
                },
                priority=0.5,
                depth=1,
                parent_id=row.get("source_item_id"),
                created_tick=self.current_tick,
            )
            self.queue._insert_with_conn(conn, observation)
            reconciled = EffectOutbox._reconcile_with_conn(
                conn, effect_id, "executed", result=stored,
                observation_event_id=observation_id)
            if row.get("queue_item_id"):
                self.queue._reconcile_mark_with_conn(
                    conn, row["queue_item_id"], ItemStatus.COMPLETED,
                    allow_already_target=True)
            return {"effect_id": effect_id, "status": reconciled["status"],
                    "outcome": "executed", "changed": reconciled["changed"],
                    "executed": stored}

    def _recover_missing_observations(self):
        """Project legacy committed results into exactly one durable observation."""
        with self._conn() as conn:
            rows=conn.execute("""SELECT * FROM capability_results
              WHERE observation_event_id IS NULL ORDER BY id""").fetchall()
            for row in rows:
                result=json.loads(row["payload_json"])
                observation_id=f"recovered-action-observation-{int(row['id'])}"
                observation=CognitiveItem(
                  id=observation_id,kind=ItemKind.OBSERVATION,
                  content={"event_type":"action_observation",
                    "capability":row["capability"],"status":row["status"],
                    "governance_mode":result.get("governance_mode"),
                    "reasons":list(result.get("reasons") or []),
                    "receipt_hash":row["receipt_hash"],"outcome":result.get("outcome"),
                    "recovered":True},
                  priority=max(0.05,min(1.0,float(row["priority"] or 0.5))),
                  depth=int(row["source_depth"] or 0)+1,
                  parent_id=row["source_item_id"],created_tick=int(row["tick"]))
                self.queue._insert_with_conn(conn,observation)
                conn.execute("UPDATE capability_results SET observation_event_id=? WHERE id=?",
                             (observation_id,row["id"]))

    def _write_tick_receipt(self,payload):
        with self._conn() as conn:
            last=conn.execute("SELECT receipt_hash FROM scheduler_receipts ORDER BY id DESC LIMIT 1").fetchone()
            prev=last["receipt_hash"] if last else "GENESIS"
            h=_hash_payload({"previous_hash":prev,"payload":payload})
            conn.execute("""INSERT INTO scheduler_receipts
              (tick,previous_hash,receipt_hash,payload_json,created_at) VALUES(?,?,?,?,?)""",
              (self.current_tick,prev,h,_canonical_json(payload),_utcnow()))
        return h

    def verify_receipts(self):
        prev="GENESIS"
        with self._conn() as conn:
            rows=conn.execute("SELECT * FROM scheduler_receipts ORDER BY id").fetchall()
        for r in rows:
            payload=json.loads(r["payload_json"])
            if r["previous_hash"]!=prev: return False
            if _hash_payload({"previous_hash":prev,"payload":payload})!=r["receipt_hash"]: return False
            prev=r["receipt_hash"]
        return True

    def run_until_quiescent(self,max_ticks:int=8,max_items:int=8,max_ms:int=300):
        if max_ticks<1 or max_ticks>100:
            raise ValueError("max_ticks must be between 1 and 100")
        receipts=[]
        for _ in range(max_ticks):
            if self.queue.pending_count()==0:
                break
            receipts.append(self.tick(max_items=max_items,max_ms=max_ms))
        pending=self.queue.pending_count()
        unknown=self.queue.unknown_count()
        return {"ticks":len(receipts),"quiescent":pending==0 and unknown==0,
                "pending":pending,"unknown":unknown,
                "unknown_effects":self.queue.unknown_effects(),
                "blocked_on_reconciliation":unknown>0,"receipts":receipts}

    def tick(self,max_items:int=8,max_ms:int=300):
        self.current_tick+=1; self._save_tick()
        receipt={"tick":self.current_tick,"queue_size_start":self.queue.pending_count(),
          "processed":0,"generated_thoughts":0,"generated_actions":0,
          "deferred_actions":0,"execution":None}
        work=self.queue.pop_budgeted(
            self.current_tick,max_items,max_ms,worker_id=self.worker_id
        )
        receipt["processed"]=len(work); candidates=[]
        for item in work:
            claim_token={"worker_id":item.worker_id,
                         "claim_generation":item.claim_generation}
            if not self.queue.owns_claim(item.id,**claim_token):
                receipt.setdefault("stale_claims",[]).append(item.id)
                continue
            try:
                context=self._retrieve_context(item)
                connection=self._conn()
                previous_stack_tick=self.stack.tick
                try:
                    # Hold SQLite's writer lock from claim validation through
                    # cognition persistence and parent/follow-up publication.
                    connection.execute("BEGIN IMMEDIATE")
                    self.queue.assert_claim_owned_with_conn(
                        connection,item.id,**claim_token
                    )
                    reasoned=self._reason(item,context,connection=connection)
                    followups=[]
                    for f in reasoned["followup_thoughts"]:
                        followups.append(CognitiveItem(
                          id=uuid.uuid4().hex,kind=f["kind"],content=dict(f["content"]),
                          priority=max(0,min(1,float(f.get("priority",.5)))),depth=item.depth+1,
                          parent_id=item.id,created_tick=self.current_tick))
                    inserted=self.queue.complete_claim_with_followups_with_conn(
                        connection,item.id,followups,**claim_token
                    )
                    if inserted is None:
                        raise RuntimeError(f"stale queue completion: {item.id}")
                    connection.commit()
                except BaseException:
                    if connection.in_transaction:
                        connection.rollback()
                    self.stack.tick=previous_stack_tick
                    raise
                finally:
                    connection.close()
                receipt["generated_thoughts"]+=inserted
                candidates.extend(reasoned["candidate_actions"])
                receipt["generated_actions"]+=len(reasoned["candidate_actions"])
            except Exception as exc:
                if not self.queue.mark_claimed(
                    item.id,ItemStatus.FAILED,**claim_token
                ):
                    receipt.setdefault("errors",[]).append(
                        f"stale queue failure transition: {item.id}"
                    )
                receipt.setdefault("errors",[]).append(f"{type(exc).__name__}: {exc}")
        ranked=self._choice_rank(candidates)
        selected_action_id=None
        selected_action_token=None
        # Persist each candidate together with its outbox intent in one
        # atomic transaction. A payload-digest conflict for a stable effect
        # ID is fail-closed: the candidate is never dispatched.
        durable_ranked=[]
        for candidate in ranked:
            effect_id=effect_id_for_candidate(candidate)
            durable_action=CognitiveItem(
              id=uuid.uuid4().hex,kind=ItemKind.ACTION_CANDIDATE,
              content={"candidate":candidate},priority=float(candidate.get("score",0.5)),
              depth=int(candidate.get("source_depth",0)),
              parent_id=candidate.get("source_item_id"),created_tick=self.current_tick)
            try:
                pushed=self.queue.push_with_effect_intent(
                    durable_action,effect_id,str(candidate["capability"]),
                    candidate.get("source_item_id"),_payload_digest(candidate.get("payload",{})))
            except ValueError as exc:
                receipt.setdefault("errors",[]).append(f"effect intent conflict: {exc}")
                continue
            if not pushed:
                raise RuntimeError("failed to persist action candidate")
            durable_ranked.append((durable_action,candidate))
        ranked=[candidate for _,candidate in durable_ranked]
        for index,(durable_action,candidate) in enumerate(durable_ranked):
            if index==0:
                claimed_action=self.queue.claim_item(
                    durable_action.id,worker_id=self.worker_id
                )
                if claimed_action is None:
                    receipt["execution"]={
                        "executed":None,"status":"BLOCKED_QUEUE_CLAIM",
                        "queue_item_id":durable_action.id
                    }
                    receipt["execution_blocked"]="BLOCKED_QUEUE_CLAIM"
                else:
                    selected_action_id=durable_action.id
                    selected_action_token={
                        "worker_id":claimed_action.worker_id,
                        "claim_generation":claimed_action.claim_generation
                    }
            else:
                receipt["deferred_actions"]+=1
        # The queue item token and outbox token are separate fences. The
        # selected queue item is completed in the same SQLite transaction as
        # its capability result, observation, and outbox completion/release.
        if selected_action_id is not None:
            try:
                receipt["execution"]=self._execute(
                    ranked,queue_item_id=selected_action_id,
                    queue_claim_token=selected_action_token
                )
            except BaseException:
                self.queue.mark_claimed(
                    selected_action_id,ItemStatus.UNKNOWN,**selected_action_token
                )
                raise
            else:
                status=str(receipt["execution"].get("status",""))
                if status in ("BLOCKED_DLQ","BLOCKED_UNREGISTERED_CAPABILITY"):
                    if not self.queue.mark_claimed(
                        selected_action_id,ItemStatus.FAILED,**selected_action_token
                    ):
                        receipt.setdefault("errors",[]).append(
                            f"stale queue failure transition: {selected_action_id}"
                        )
                elif status.startswith("BLOCKED_"):
                    if not self.queue.mark_claimed(
                        selected_action_id,ItemStatus.UNKNOWN,**selected_action_token
                    ):
                        receipt.setdefault("errors",[]).append(
                            f"stale queue quarantine transition: {selected_action_id}"
                        )
        receipt["queue_size_end"]=self.queue.pending_count()
        receipt["receipt_hash"]=self._write_tick_receipt({k:v for k,v in receipt.items() if k!="receipt_hash"})
        return receipt
