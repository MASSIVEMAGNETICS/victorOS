"""Victor Native Kernel v0.3 — episode-scoped deterministic integration kernel.

This module welds the existing zero-LLM cognitive stack, A1 evidence/resonance
ledger, and governed physiology runtime into one bounded loop without creating a
parallel truth store.

Hard boundaries:
- zero third-party runtime dependencies in this module
- duplicate content may occur in multiple distinct episodes
- resonance creates candidate gestalts, never truth
- membrane state is scoped by (episode_id, tick, concept_id)
- no canonical Chronos mutation occurs without an injected verified adapter
- consequential effects pass through VictorPhysiologyRuntime capability leases
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence

from .physiology import (
    ActionProposal,
    GateDecision,
    PhysiologyReceiptLedger,
    VictorPhysiologyRuntime,
)
from .resonance_ledger import ResonanceLedger
from .victor_cognition_stack import VictorCognitionStack


KERNEL_VERSION = "0.3.0"
KERNEL_SCHEMA_VERSION = 1
DEFAULT_GESTALT_QUORUM = 3

EVIDENCE_STATES = {
    "UNKNOWN",
    "REPORTED",
    "EXTRACTED",
    "OBSERVED",
    "SOURCE_BOUND",
    "CORROBORATED",
    "VERIFIED",
    "DISPUTED",
    "CONTRADICTED",
    "INVALIDATED",
}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _stable_id(prefix: str, value: Any, width: int = 24) -> str:
    return f"{prefix}-{_sha256(_canonical_json(value))[:width].upper()}"


def _normalize_concept(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()
    return re.sub(r"\s+", " ", normalized)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@dataclass(frozen=True)
class Episode:
    episode_id: str
    content_hash: str
    source: str
    title: str
    tick: int
    concept_id: str
    resonance_source_id: str
    prior_kernel_head: str
    status: str
    created_at: str
    closed_at: Optional[str] = None


@dataclass(frozen=True)
class OrganSignal:
    signal_id: str
    episode_id: str
    tick: int
    concept_id: str
    organ: str
    event: str
    payload: Mapping[str, Any]
    confidence: float
    evidence_state: str
    created_at: str


@dataclass(frozen=True)
class CandidateGestalt:
    gestalt_id: str
    episode_id: str
    tick: int
    concept_id: str
    organs: tuple[str, ...]
    signal_ids: tuple[str, ...]
    gestalt_hash: str
    status: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ExperienceTransitionCandidate:
    transition_id: str
    episode_id: str
    gestalt_id: str
    observation_hash: str
    gestalt_hash: str
    verification_receipt_hash: str
    expected_prior_chronos_head: Optional[str]
    status: str
    payload: Mapping[str, Any]
    created_at: str


@dataclass(frozen=True)
class KernelActionCandidate:
    name: str
    capability: str
    provenance: str
    score: float
    payload: Mapping[str, Any] = field(default_factory=dict)
    required_authorities: tuple[str, ...] = ()
    consequence: float = 0.0
    irreversibility: float = 0.0
    uncertainty: float = 0.0
    novelty: float = 0.0
    arousal: float = 0.0
    urgency: float = 0.0
    capability_power: float = 0.0


class NativeOrganStack(VictorCognitionStack):
    """VictorCognitionStack with its legacy global membrane disabled.

    The legacy stack still provides deterministic memory, attention, association,
    rule inference, goal activation and planning. NativeKernel owns the only
    membrane used by this integration path, so legacy crystallizations cannot
    silently become competing gestalts.
    """

    def _publish(self, conn, organ, event, concept, payload):  # type: ignore[override]
        self._audit(
            conn,
            organ,
            event,
            {
                "concept": concept,
                "payload": payload,
                "native_kernel_membrane": True,
                "legacy_resonance_disabled": True,
            },
        )

    def check_emergence(self, conn):  # type: ignore[override]
        return 0


class ChronosPromotionAdapter:
    """Interface boundary for a real canonical Chronos implementation.

    Implementations MUST independently verify the candidate and return a mapping:
      {
        "accepted": bool,
        "chronos_receipt_hash": str | None,
        "chronos_head": str | None,
        "verification": {...}
      }

    NativeKernel never fabricates a successful canonical receipt.
    """

    def promote(self, candidate: ExperienceTransitionCandidate) -> Mapping[str, Any]:
        raise NotImplementedError


class NativeKernel:
    """Episode -> organs -> membrane -> verification -> promotion boundary."""

    def __init__(
        self,
        db_path: str | Path = ".victor/native_kernel.db",
        *,
        resonance_db_path: str | Path | None = None,
        physiology: VictorPhysiologyRuntime | None = None,
        physiology_receipt_path: str | Path | None = None,
        granted_authorities: Sequence[str] = (),
        gestalt_quorum: int = DEFAULT_GESTALT_QUORUM,
    ) -> None:
        if gestalt_quorum < 2:
            raise ValueError("gestalt_quorum must be >= 2")

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.gestalt_quorum = int(gestalt_quorum)
        self._init_schema()

        self.stack = NativeOrganStack(str(self.db_path))

        rpath = (
            Path(resonance_db_path)
            if resonance_db_path is not None
            else self.db_path.with_name(self.db_path.stem + ".resonance.db")
        )
        self.resonance = ResonanceLedger(rpath)

        if physiology is None:
            ppath = (
                Path(physiology_receipt_path)
                if physiology_receipt_path is not None
                else self.db_path.with_name(self.db_path.stem + ".physiology.jsonl")
            )
            physiology = VictorPhysiologyRuntime(
                receipt_ledger=PhysiologyReceiptLedger(str(ppath)),
                granted_authorities=tuple(granted_authorities),
            )
        self.physiology = physiology

    def close(self) -> None:
        self.resonance.close()

    def __enter__(self) -> "NativeKernel":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=FULL")
        return conn

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS native_kernel_metadata(
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS content_objects(
                    content_hash TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS episodes(
                    episode_id TEXT PRIMARY KEY,
                    content_hash TEXT NOT NULL REFERENCES content_objects(content_hash),
                    source TEXT NOT NULL,
                    title TEXT NOT NULL,
                    tick INTEGER NOT NULL,
                    concept_id TEXT NOT NULL,
                    resonance_source_id TEXT NOT NULL,
                    prior_kernel_head TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    closed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_native_episode_tick
                    ON episodes(tick);
                CREATE INDEX IF NOT EXISTS idx_native_episode_content
                    ON episodes(content_hash);

                CREATE TABLE IF NOT EXISTS organ_signals(
                    signal_id TEXT PRIMARY KEY,
                    episode_id TEXT NOT NULL REFERENCES episodes(episode_id),
                    tick INTEGER NOT NULL,
                    concept_id TEXT NOT NULL,
                    organ TEXT NOT NULL,
                    event TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    confidence REAL NOT NULL CHECK(confidence >= 0.0 AND confidence <= 1.0),
                    evidence_state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(episode_id, tick, concept_id, organ, event)
                );
                CREATE INDEX IF NOT EXISTS idx_native_signal_scope
                    ON organ_signals(episode_id, tick, concept_id);

                CREATE TABLE IF NOT EXISTS candidate_gestalts(
                    gestalt_id TEXT PRIMARY KEY,
                    episode_id TEXT NOT NULL REFERENCES episodes(episode_id),
                    tick INTEGER NOT NULL,
                    concept_id TEXT NOT NULL,
                    organs_json TEXT NOT NULL,
                    signal_ids_json TEXT NOT NULL,
                    gestalt_hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(episode_id, tick, concept_id)
                );

                CREATE TABLE IF NOT EXISTS gestalt_verifications(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    gestalt_id TEXT NOT NULL REFERENCES candidate_gestalts(gestalt_id),
                    passed INTEGER NOT NULL CHECK(passed IN (0, 1)),
                    verifier TEXT NOT NULL,
                    evidence_refs_json TEXT NOT NULL,
                    notes TEXT NOT NULL,
                    receipt_hash TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS transition_candidates(
                    transition_id TEXT PRIMARY KEY,
                    episode_id TEXT NOT NULL REFERENCES episodes(episode_id),
                    gestalt_id TEXT NOT NULL REFERENCES candidate_gestalts(gestalt_id),
                    observation_hash TEXT NOT NULL,
                    gestalt_hash TEXT NOT NULL,
                    verification_receipt_hash TEXT NOT NULL,
                    expected_prior_chronos_head TEXT,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    chronos_receipt_hash TEXT,
                    chronos_head TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS native_kernel_receipts(
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO native_kernel_metadata(key, value)
                VALUES('schema_version', ?)
                """,
                (str(KERNEL_SCHEMA_VERSION),),
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO native_kernel_metadata(key, value)
                VALUES('kernel_version', ?)
                """,
                (KERNEL_VERSION,),
            )

    def _last_kernel_hash(self, conn: sqlite3.Connection) -> str:
        row = conn.execute(
            "SELECT event_hash FROM native_kernel_receipts ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        return str(row["event_hash"]) if row else "GENESIS"

    def _append_receipt(
        self, conn: sqlite3.Connection, event_type: str, payload: Mapping[str, Any]
    ) -> str:
        previous_hash = self._last_kernel_hash(conn)
        created_at = _utcnow()
        envelope = {
            "event_type": event_type,
            "payload": dict(payload),
            "previous_hash": previous_hash,
            "created_at": created_at,
        }
        event_hash = _sha256(_canonical_json(envelope))
        conn.execute(
            """
            INSERT INTO native_kernel_receipts(
                event_type, payload_json, previous_hash, event_hash, created_at
            ) VALUES(?, ?, ?, ?, ?)
            """,
            (
                event_type,
                _canonical_json(payload),
                previous_hash,
                event_hash,
                created_at,
            ),
        )
        return event_hash

    def verify_receipt_chain(self) -> bool:
        previous = "GENESIS"
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM native_kernel_receipts ORDER BY seq"
            ).fetchall()
        for row in rows:
            payload = json.loads(row["payload_json"])
            envelope = {
                "event_type": row["event_type"],
                "payload": payload,
                "previous_hash": row["previous_hash"],
                "created_at": row["created_at"],
            }
            if row["previous_hash"] != previous:
                return False
            if _sha256(_canonical_json(envelope)) != row["event_hash"]:
                return False
            previous = row["event_hash"]
        return True

    def _concept_for_content(self, content_hash: str) -> tuple[str, str]:
        name = f"focus {content_hash[:16]}"
        normalized = _normalize_concept(name)
        return _stable_id("C", normalized, width=16), name

    def begin_episode(
        self,
        observation: str,
        *,
        source: str = "user",
        title: str = "",
    ) -> Episode:
        text = (observation or "").strip()
        if not text:
            raise ValueError("observation must not be empty")

        content_hash = _sha256(text)
        concept_id, concept_name = self._concept_for_content(content_hash)
        episode_id = f"EP-{uuid.uuid4().hex}"
        created_at = _utcnow()

        resonance_source_id = self.resonance.ingest_text(
            text,
            source_type="episode",
            title=title or episode_id,
            domains=["victoros", "native-kernel"],
            author=source,
            source_timestamp=created_at,
            source_id=f"SRC-{episode_id}",
        )
        self.resonance.record_observation(
            concept_name,
            resonance_source_id,
            text[:1000],
            confidence=1.0,
            interpretation_state="episode_input",
            evidence_state="OBSERVED",
        )

        with self._conn() as conn:
            prior_head = self._last_kernel_hash(conn)
            conn.execute(
                """
                INSERT OR IGNORE INTO content_objects(content_hash, content, created_at)
                VALUES(?, ?, ?)
                """,
                (content_hash, text, created_at),
            )
            tick = max(1, int(self.stack.tick) + 1)
            conn.execute(
                """
                INSERT INTO episodes(
                    episode_id, content_hash, source, title, tick, concept_id,
                    resonance_source_id, prior_kernel_head, status, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?)
                """,
                (
                    episode_id,
                    content_hash,
                    source,
                    title,
                    tick,
                    concept_id,
                    resonance_source_id,
                    prior_head,
                    created_at,
                ),
            )
            self._append_receipt(
                conn,
                "EPISODE_OPENED",
                {
                    "episode_id": episode_id,
                    "content_hash": content_hash,
                    "source": source,
                    "tick": tick,
                    "concept_id": concept_id,
                    "resonance_source_id": resonance_source_id,
                },
            )

        return self.episode(episode_id)

    def episode(self, episode_id: str) -> Episode:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM episodes WHERE episode_id=?", (episode_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown episode: {episode_id}")
        return Episode(**dict(row))

    def publish_signal(
        self,
        *,
        episode_id: str,
        tick: int,
        concept_id: str,
        organ: str,
        event: str,
        payload: Mapping[str, Any],
        confidence: float = 0.7,
        evidence_state: str = "INFERRED",
    ) -> OrganSignal:
        if not organ.strip() or not event.strip():
            raise ValueError("organ and event are required")
        if evidence_state == "INFERRED":
            evidence_state = "EXTRACTED"
        evidence_state = evidence_state.upper()
        if evidence_state not in EVIDENCE_STATES:
            raise ValueError(f"unsupported evidence_state: {evidence_state}")

        episode = self.episode(episode_id)
        if episode.tick != int(tick) or episode.concept_id != concept_id:
            raise ValueError("signal scope must match its episode tick and concept")

        identity = {
            "episode_id": episode_id,
            "tick": int(tick),
            "concept_id": concept_id,
            "organ": organ,
            "event": event,
        }
        signal_id = _stable_id("SIG", identity)
        now = _utcnow()

        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO organ_signals(
                    signal_id, episode_id, tick, concept_id, organ, event,
                    payload_json, confidence, evidence_state, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    signal_id,
                    episode_id,
                    int(tick),
                    concept_id,
                    organ,
                    event,
                    _canonical_json(payload),
                    _clamp01(confidence),
                    evidence_state,
                    now,
                ),
            )
            self._append_receipt(
                conn,
                "ORGAN_SIGNAL",
                {
                    **identity,
                    "signal_id": signal_id,
                    "confidence": _clamp01(confidence),
                    "evidence_state": evidence_state,
                    "payload_hash": _sha256(_canonical_json(payload)),
                },
            )
            self._refresh_gestalt(conn, episode_id, int(tick), concept_id)

        return self.signal(signal_id)

    def signal(self, signal_id: str) -> OrganSignal:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM organ_signals WHERE signal_id=?", (signal_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown signal: {signal_id}")
        data = dict(row)
        data["payload"] = json.loads(data.pop("payload_json"))
        return OrganSignal(**data)

    def _refresh_gestalt(
        self,
        conn: sqlite3.Connection,
        episode_id: str,
        tick: int,
        concept_id: str,
    ) -> Optional[str]:
        rows = conn.execute(
            """
            SELECT signal_id, organ, event, payload_json, confidence, evidence_state
            FROM organ_signals
            WHERE episode_id=? AND tick=? AND concept_id=?
            ORDER BY organ, event, signal_id
            """,
            (episode_id, tick, concept_id),
        ).fetchall()
        organs = tuple(sorted({str(row["organ"]) for row in rows}))
        if len(organs) < self.gestalt_quorum:
            return None

        gestalt_id = _stable_id(
            "GST",
            {"episode_id": episode_id, "tick": tick, "concept_id": concept_id},
        )
        signal_ids = tuple(str(row["signal_id"]) for row in rows)
        payload = {
            "type": "candidate_gestalt",
            "episode_id": episode_id,
            "tick": tick,
            "concept_id": concept_id,
            "organs": organs,
            "signals": [
                {
                    "signal_id": row["signal_id"],
                    "organ": row["organ"],
                    "event": row["event"],
                    "payload": json.loads(row["payload_json"]),
                    "confidence": row["confidence"],
                    "evidence_state": row["evidence_state"],
                }
                for row in rows
            ],
            "canonical": False,
        }
        gestalt_hash = _sha256(_canonical_json(payload))
        now = _utcnow()
        existing = conn.execute(
            "SELECT status FROM candidate_gestalts WHERE gestalt_id=?", (gestalt_id,)
        ).fetchone()
        if existing is not None and existing["status"] != "CANDIDATE":
            return gestalt_id

        conn.execute(
            """
            INSERT INTO candidate_gestalts(
                gestalt_id, episode_id, tick, concept_id, organs_json,
                signal_ids_json, gestalt_hash, status, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, 'CANDIDATE', ?, ?)
            ON CONFLICT(gestalt_id) DO UPDATE SET
                organs_json=excluded.organs_json,
                signal_ids_json=excluded.signal_ids_json,
                gestalt_hash=excluded.gestalt_hash,
                updated_at=excluded.updated_at
            """,
            (
                gestalt_id,
                episode_id,
                tick,
                concept_id,
                _canonical_json(organs),
                _canonical_json(signal_ids),
                gestalt_hash,
                now,
                now,
            ),
        )
        self._append_receipt(
            conn,
            "CANDIDATE_GESTALT",
            {
                "gestalt_id": gestalt_id,
                "episode_id": episode_id,
                "tick": tick,
                "concept_id": concept_id,
                "organs": organs,
                "signal_ids": signal_ids,
                "gestalt_hash": gestalt_hash,
                "canonical": False,
            },
        )
        return gestalt_id

    def gestalt(self, gestalt_id: str) -> CandidateGestalt:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM candidate_gestalts WHERE gestalt_id=?", (gestalt_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown gestalt: {gestalt_id}")
        data = dict(row)
        data["organs"] = tuple(json.loads(data.pop("organs_json")))
        data["signal_ids"] = tuple(json.loads(data.pop("signal_ids_json")))
        return CandidateGestalt(**data)

    def gestalts_for_episode(self, episode_id: str) -> list[CandidateGestalt]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT gestalt_id FROM candidate_gestalts
                WHERE episode_id=? ORDER BY created_at, gestalt_id
                """,
                (episode_id,),
            ).fetchall()
        return [self.gestalt(str(row["gestalt_id"])) for row in rows]

    def run_episode(
        self,
        observation: str,
        *,
        source: str = "user",
        title: str = "",
    ) -> dict[str, Any]:
        episode = self.begin_episode(observation, source=source, title=title)
        report = self.stack.cycle(observation, source=source, tick=episode.tick)

        organ_map = (
            ("sensory", "sensory_input"),
            ("attention", "salience"),
            ("association", "memory_association"),
            ("inference", "rule_inference"),
            ("planning", "goal_planning"),
            ("executive", "execution_hold"),
        )
        for organ, event in organ_map:
            payload = report["steps"].get(organ)
            if payload is None:
                continue
            evidence_state = "OBSERVED" if organ == "sensory" else "EXTRACTED"
            confidence = 1.0 if organ == "sensory" else 0.65
            self.publish_signal(
                episode_id=episode.episode_id,
                tick=episode.tick,
                concept_id=episode.concept_id,
                organ=organ,
                event=event,
                payload=payload,
                confidence=confidence,
                evidence_state=evidence_state,
            )

        with self._conn() as conn:
            conn.execute(
                "UPDATE episodes SET status='PROCESSED', closed_at=? WHERE episode_id=?",
                (_utcnow(), episode.episode_id),
            )
            gestalts = conn.execute(
                """
                SELECT gestalt_id, gestalt_hash, status
                FROM candidate_gestalts WHERE episode_id=?
                ORDER BY created_at
                """,
                (episode.episode_id,),
            ).fetchall()
            receipt_hash = self._append_receipt(
                conn,
                "EPISODE_PROCESSED",
                {
                    "episode_id": episode.episode_id,
                    "tick": episode.tick,
                    "stack_report_hash": _sha256(_canonical_json(report)),
                    "gestalts": [dict(row) for row in gestalts],
                },
            )

        return {
            "kernel_version": KERNEL_VERSION,
            "episode": asdict(self.episode(episode.episode_id)),
            "organ_report": report,
            "gestalts": [
                asdict(item) for item in self.gestalts_for_episode(episode.episode_id)
            ],
            "receipt_hash": receipt_hash,
            "receipt_chain_ok": self.verify_receipt_chain(),
        }

    def verify_gestalt(
        self,
        gestalt_id: str,
        *,
        passed: bool,
        verifier: str,
        evidence_refs: Sequence[str],
        notes: str = "",
        expected_prior_chronos_head: str | None = None,
    ) -> Optional[ExperienceTransitionCandidate]:
        verifier = (verifier or "").strip()
        refs = tuple(sorted({str(ref).strip() for ref in evidence_refs if str(ref).strip()}))
        if not verifier:
            raise ValueError("verifier is required")
        if not refs:
            raise ValueError("at least one evidence reference is required")

        gestalt = self.gestalt(gestalt_id)
        if gestalt.status != "CANDIDATE":
            raise ValueError(f"gestalt is not awaiting verification: {gestalt.status}")
        episode = self.episode(gestalt.episode_id)

        with self._conn() as conn:
            verification_payload = {
                "gestalt_id": gestalt_id,
                "passed": bool(passed),
                "verifier": verifier,
                "evidence_refs": refs,
                "notes": notes,
                "gestalt_hash": gestalt.gestalt_hash,
            }
            receipt_hash = self._append_receipt(
                conn, "GESTALT_VERIFICATION", verification_payload
            )
            conn.execute(
                """
                INSERT INTO gestalt_verifications(
                    gestalt_id, passed, verifier, evidence_refs_json,
                    notes, receipt_hash, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    gestalt_id,
                    1 if passed else 0,
                    verifier,
                    _canonical_json(refs),
                    notes,
                    receipt_hash,
                    _utcnow(),
                ),
            )
            conn.execute(
                """
                UPDATE candidate_gestalts
                SET status=?, updated_at=? WHERE gestalt_id=?
                """,
                ("VERIFIED" if passed else "REJECTED", _utcnow(), gestalt_id),
            )

            if not passed:
                return None

            transition_payload = {
                "type": "ExperienceTransitionCandidate",
                "kernel_version": KERNEL_VERSION,
                "episode_id": episode.episode_id,
                "tick": episode.tick,
                "concept_id": episode.concept_id,
                "observation_hash": episode.content_hash,
                "gestalt_id": gestalt_id,
                "gestalt_hash": gestalt.gestalt_hash,
                "verification_receipt_hash": receipt_hash,
                "verification": {
                    "verifier": verifier,
                    "evidence_refs": refs,
                    "notes": notes,
                },
                "expected_prior_chronos_head": expected_prior_chronos_head,
                "canonical": False,
            }
            transition_id = _stable_id("XTC", transition_payload)
            now = _utcnow()
            conn.execute(
                """
                INSERT INTO transition_candidates(
                    transition_id, episode_id, gestalt_id, observation_hash,
                    gestalt_hash, verification_receipt_hash,
                    expected_prior_chronos_head, payload_json, status,
                    created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, 'VERIFIED_CANDIDATE', ?, ?)
                """,
                (
                    transition_id,
                    episode.episode_id,
                    gestalt_id,
                    episode.content_hash,
                    gestalt.gestalt_hash,
                    receipt_hash,
                    expected_prior_chronos_head,
                    _canonical_json(transition_payload),
                    now,
                    now,
                ),
            )
            self._append_receipt(
                conn,
                "TRANSITION_CANDIDATE_CREATED",
                {
                    "transition_id": transition_id,
                    "gestalt_id": gestalt_id,
                    "verification_receipt_hash": receipt_hash,
                    "canonical": False,
                },
            )

        return self.transition(transition_id)

    def transition(self, transition_id: str) -> ExperienceTransitionCandidate:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM transition_candidates WHERE transition_id=?",
                (transition_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown transition candidate: {transition_id}")
        data = dict(row)
        data["payload"] = json.loads(data.pop("payload_json"))
        data.pop("chronos_receipt_hash")
        data.pop("chronos_head")
        data.pop("updated_at")
        return ExperienceTransitionCandidate(**data)

    def promote_transition(
        self,
        transition_id: str,
        adapter: ChronosPromotionAdapter,
    ) -> Mapping[str, Any]:
        candidate = self.transition(transition_id)
        if candidate.status != "VERIFIED_CANDIDATE":
            raise ValueError(f"transition is not promotable: {candidate.status}")
        if adapter is None:
            raise ValueError("a real Chronos promotion adapter is required")

        result = dict(adapter.promote(candidate))
        accepted = bool(result.get("accepted"))
        receipt = str(result.get("chronos_receipt_hash") or "").strip()
        head = str(result.get("chronos_head") or "").strip()

        if accepted and (not receipt or not head):
            raise RuntimeError(
                "Chronos adapter claimed acceptance without receipt hash and head"
            )

        status = "PROMOTED" if accepted else "PROMOTION_REJECTED"
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE transition_candidates
                SET status=?, chronos_receipt_hash=?, chronos_head=?, updated_at=?
                WHERE transition_id=?
                """,
                (
                    status,
                    receipt or None,
                    head or None,
                    _utcnow(),
                    transition_id,
                ),
            )
            self._append_receipt(
                conn,
                "CHRONOS_PROMOTION_RESULT",
                {
                    "transition_id": transition_id,
                    "status": status,
                    "chronos_receipt_hash": receipt or None,
                    "chronos_head": head or None,
                    "adapter_verification": result.get("verification"),
                },
            )
        return result

    @staticmethod
    def rank_actions(
        candidates: Sequence[KernelActionCandidate],
    ) -> list[KernelActionCandidate]:
        def utility(candidate: KernelActionCandidate) -> tuple[float, str, str]:
            reversible = 1.0 - _clamp01(candidate.irreversibility)
            effective = (
                _clamp01(candidate.score)
                + 0.20 * reversible
                - 0.20 * _clamp01(candidate.consequence)
                - 0.15 * _clamp01(candidate.uncertainty)
            )
            return (effective, candidate.capability, candidate.name)

        return sorted(candidates, key=utility, reverse=True)

    def execute_action(
        self,
        candidate: KernelActionCandidate,
        executor: Callable[[], Any],
    ) -> GateDecision:
        proposal = ActionProposal(
            name=candidate.name,
            capability=candidate.capability,
            provenance=candidate.provenance,
            required_authorities=tuple(candidate.required_authorities),
            consequence=_clamp01(candidate.consequence),
            irreversibility=_clamp01(candidate.irreversibility),
            uncertainty=_clamp01(candidate.uncertainty),
            novelty=_clamp01(candidate.novelty),
            arousal=_clamp01(candidate.arousal),
            urgency=_clamp01(candidate.urgency),
            capability_power=_clamp01(candidate.capability_power),
            metadata={
                "native_kernel_version": KERNEL_VERSION,
                "candidate_payload_hash": _sha256(_canonical_json(candidate.payload)),
                "candidate_score": _clamp01(candidate.score),
            },
        )
        decision = self.physiology.execute(proposal, executor)
        with self._conn() as conn:
            self._append_receipt(
                conn,
                "ACTION_DECISION",
                {
                    "name": candidate.name,
                    "capability": candidate.capability,
                    "physiology_status": decision.status.value,
                    "governance_mode": decision.governance_mode.value,
                    "risk_score": decision.risk_score,
                    "reasons": list(decision.reasons),
                    "physiology_receipt_hash": decision.receipt_hash,
                    "executed": decision.actual_outcome is not None,
                },
            )
        return decision

    def counts(self) -> dict[str, int]:
        tables = (
            "content_objects",
            "episodes",
            "organ_signals",
            "candidate_gestalts",
            "gestalt_verifications",
            "transition_candidates",
            "native_kernel_receipts",
        )
        with self._conn() as conn:
            return {
                table: int(
                    conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"]
                )
                for table in tables
            }
