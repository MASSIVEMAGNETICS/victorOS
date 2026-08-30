from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


RELATIONS = {
    "SUPPORTS",
    "CONTRADICTS",
    "DEPENDS_ON",
    "IMPLEMENTS",
    "SUPERSEDES",
    "DERIVED_FROM",
    "VALIDATES",
    "INVALIDATES",
    "EXPANDS",
    "NARROWS",
    "MIRRORS",
    "CAUSED_BY",
    "RESULTED_IN",
}

EVIDENCE_WEIGHTS = {
    "VERIFIED": 1.00,
    "CORROBORATED": 0.90,
    "SOURCE_BOUND": 0.80,
    "OBSERVED": 0.70,
    "EXTRACTED": 0.55,
    "REPORTED": 0.50,
    "DISPUTED": 0.35,
    "CONTRADICTED": 0.20,
    "INVALIDATED": 0.10,
    "UNKNOWN": 0.15,
}

CONTRADICTION_RELATIONS = {"CONTRADICTS", "INVALIDATES", "SUPERSEDES"}

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "but", "by",
    "can", "could", "did", "do", "does", "for", "from", "had", "has", "have",
    "he", "her", "hers", "him", "his", "how", "i", "if", "in", "into", "is",
    "it", "its", "may", "me", "more", "most", "must", "my", "no", "not", "of",
    "on", "or", "our", "ours", "shall", "she", "should", "so", "than", "that",
    "the", "their", "theirs", "them", "then", "there", "these", "they", "this",
    "those", "to", "too", "us", "was", "we", "were", "what", "when", "where",
    "which", "while", "who", "why", "will", "with", "would", "you", "your",
    "yours", "about", "after", "again", "all", "also", "any", "before", "between",
    "both", "each", "few", "further", "here", "once", "only", "other", "same",
    "some", "such", "through", "under", "until", "very", "over", "own", "up",
    "down", "out", "off", "just", "now", "still", "every", "whole", "never",
}


@dataclass(frozen=True)
class ResonanceVector:
    concept_id: str
    concept: str
    persistence: float
    domain_diversity: float
    centrality: float
    evidence_quality: float
    volatility: float
    contradiction_pressure: float
    resonance_score: float
    observations: int
    sources: int
    domains: int
    classification: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_name(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
    return re.sub(r"\s+", " ", normalized)


def _stable_id(prefix: str, payload: str, width: int = 16) -> str:
    return f"{prefix}-{_sha256_text(payload)[:width].upper()}"


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


class ResonanceLedger:
    """A1-RL-001: local, append-only evidence/resonance ledger.

    This ledger is intentionally *not* the canonical Chronos identity/state head.
    It is a bounded research/continuity subsystem whose events can later be
    promoted into Chronos through an independently verified adapter.
    """

    SCHEMA_VERSION = "1"

    def __init__(self, db_path: str | Path = ".victor/resonance.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA synchronous = FULL")
        self._init_schema()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "ResonanceLedger":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sources (
                source_id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                title TEXT NOT NULL,
                source_timestamp TEXT,
                domains_json TEXT NOT NULL,
                author TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_sources_sha256 ON sources(sha256);

            CREATE TABLE IF NOT EXISTS concepts (
                concept_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                normalized_name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'candidate',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS aliases (
                normalized_alias TEXT PRIMARY KEY,
                concept_id TEXT NOT NULL REFERENCES concepts(concept_id)
            );

            CREATE TABLE IF NOT EXISTS observations (
                observation_id TEXT PRIMARY KEY,
                concept_id TEXT NOT NULL REFERENCES concepts(concept_id),
                source_id TEXT NOT NULL REFERENCES sources(source_id),
                evidence_span TEXT NOT NULL,
                confidence REAL NOT NULL CHECK(confidence >= 0.0 AND confidence <= 1.0),
                interpretation_state TEXT NOT NULL,
                evidence_state TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(concept_id, source_id, evidence_span, interpretation_state, evidence_state)
            );
            CREATE INDEX IF NOT EXISTS idx_observations_concept ON observations(concept_id);
            CREATE INDEX IF NOT EXISTS idx_observations_source ON observations(source_id);

            CREATE TABLE IF NOT EXISTS edges (
                edge_id TEXT PRIMARY KEY,
                from_concept_id TEXT NOT NULL REFERENCES concepts(concept_id),
                relation TEXT NOT NULL,
                to_concept_id TEXT NOT NULL REFERENCES concepts(concept_id),
                confidence REAL NOT NULL CHECK(confidence >= 0.0 AND confidence <= 1.0),
                status TEXT NOT NULL,
                source_id TEXT REFERENCES sources(source_id),
                created_at TEXT NOT NULL,
                UNIQUE(from_concept_id, relation, to_concept_id, source_id, status)
            );
            CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(from_concept_id);
            CREATE INDEX IF NOT EXISTS idx_edges_to ON edges(to_concept_id);

            CREATE TABLE IF NOT EXISTS events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                prev_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            );
            """
        )
        self.conn.execute(
            "INSERT OR IGNORE INTO metadata(key, value) VALUES('schema_version', ?)",
            (self.SCHEMA_VERSION,),
        )
        self.conn.commit()

    def _append_event(self, event_type: str, payload: dict[str, Any]) -> str:
        row = self.conn.execute(
            "SELECT event_hash FROM events ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        prev_hash = row["event_hash"] if row else "GENESIS"
        created_at = _utc_now()
        envelope = {
            "event_type": event_type,
            "payload": payload,
            "prev_hash": prev_hash,
            "created_at": created_at,
        }
        event_hash = _sha256_text(_canonical_json(envelope))
        self.conn.execute(
            """
            INSERT INTO events(event_type, payload_json, prev_hash, event_hash, created_at)
            VALUES(?, ?, ?, ?, ?)
            """,
            (event_type, _canonical_json(payload), prev_hash, event_hash, created_at),
        )
        return event_hash

    def ingest_text(
        self,
        text: str,
        *,
        source_type: str = "episode",
        title: str = "",
        domains: Sequence[str] = (),
        author: str = "unknown",
        source_timestamp: str | None = None,
        source_id: str | None = None,
    ) -> str:
        if not text or not text.strip():
            raise ValueError("source text must not be empty")
        clean_domains = sorted({_normalize_name(d) for d in domains if _normalize_name(d)})
        content_hash = _sha256_text(text)
        sid = source_id or _stable_id("SRC", f"{source_type}:{content_hash}")

        existing = self.conn.execute(
            "SELECT * FROM sources WHERE source_id = ?", (sid,)
        ).fetchone()
        if existing:
            if existing["sha256"] != content_hash:
                raise ValueError(f"source_id {sid!r} already exists with different content")
            return sid

        duplicate = self.conn.execute(
            "SELECT source_id FROM sources WHERE source_type = ? AND sha256 = ? LIMIT 1",
            (source_type, content_hash),
        ).fetchone()
        if duplicate:
            return str(duplicate["source_id"])

        created_at = _utc_now()
        self.conn.execute(
            """
            INSERT INTO sources(
                source_id, source_type, title, source_timestamp, domains_json,
                author, sha256, raw_text, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sid,
                source_type,
                title,
                source_timestamp,
                _canonical_json(clean_domains),
                author,
                content_hash,
                text,
                created_at,
            ),
        )
        self._append_event(
            "SOURCE_INGESTED",
            {
                "source_id": sid,
                "source_type": source_type,
                "sha256": content_hash,
                "domains": clean_domains,
                "author": author,
                "source_timestamp": source_timestamp,
            },
        )
        self.conn.commit()
        return sid

    def source(self, source_id: str) -> dict[str, Any]:
        row = self.conn.execute(
            "SELECT * FROM sources WHERE source_id = ?", (source_id,)
        ).fetchone()
        if not row:
            raise KeyError(f"unknown source_id: {source_id}")
        data = dict(row)
        data["domains"] = json.loads(data.pop("domains_json"))
        return data

    def get_or_create_concept(
        self, name: str, *, description: str = "", status: str = "candidate"
    ) -> str:
        normalized = _normalize_name(name)
        if not normalized:
            raise ValueError("concept name must contain alphanumeric characters")
        alias = self.conn.execute(
            "SELECT concept_id FROM aliases WHERE normalized_alias = ?", (normalized,)
        ).fetchone()
        if alias:
            return str(alias["concept_id"])
        row = self.conn.execute(
            "SELECT concept_id FROM concepts WHERE normalized_name = ?", (normalized,)
        ).fetchone()
        if row:
            return str(row["concept_id"])

        concept_id = _stable_id("C", normalized)
        self.conn.execute(
            """
            INSERT INTO concepts(concept_id, name, normalized_name, description, status, created_at)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (concept_id, name.strip(), normalized, description, status, _utc_now()),
        )
        self.conn.execute(
            "INSERT INTO aliases(normalized_alias, concept_id) VALUES(?, ?)",
            (normalized, concept_id),
        )
        self._append_event(
            "CONCEPT_CREATED",
            {"concept_id": concept_id, "name": name.strip(), "status": status},
        )
        self.conn.commit()
        return concept_id

    def add_alias(self, concept: str, alias: str) -> None:
        concept_id = self.resolve_concept(concept)
        normalized = _normalize_name(alias)
        if not normalized:
            raise ValueError("alias must contain alphanumeric characters")
        existing = self.conn.execute(
            "SELECT concept_id FROM aliases WHERE normalized_alias = ?", (normalized,)
        ).fetchone()
        if existing and existing["concept_id"] != concept_id:
            raise ValueError(f"alias {alias!r} already belongs to another concept")
        self.conn.execute(
            "INSERT OR REPLACE INTO aliases(normalized_alias, concept_id) VALUES(?, ?)",
            (normalized, concept_id),
        )
        self._append_event(
            "ALIAS_BOUND", {"concept_id": concept_id, "alias": alias.strip()}
        )
        self.conn.commit()

    def resolve_concept(self, name_or_id: str) -> str:
        if name_or_id.startswith("C-"):
            row = self.conn.execute(
                "SELECT concept_id FROM concepts WHERE concept_id = ?", (name_or_id,)
            ).fetchone()
            if row:
                return str(row["concept_id"])
        normalized = _normalize_name(name_or_id)
        row = self.conn.execute(
            "SELECT concept_id FROM aliases WHERE normalized_alias = ?", (normalized,)
        ).fetchone()
        if row:
            return str(row["concept_id"])
        row = self.conn.execute(
            "SELECT concept_id FROM concepts WHERE normalized_name = ?", (normalized,)
        ).fetchone()
        if row:
            return str(row["concept_id"])
        raise KeyError(f"unknown concept: {name_or_id}")

    def record_observation(
        self,
        concept: str,
        source_id: str,
        evidence_span: str,
        *,
        confidence: float = 0.7,
        interpretation_state: str = "explicit",
        evidence_state: str = "OBSERVED",
    ) -> str:
        if not evidence_span.strip():
            raise ValueError("evidence_span must not be empty")
        confidence = _clamp01(confidence)
        evidence_state = evidence_state.upper()
        if evidence_state not in EVIDENCE_WEIGHTS:
            raise ValueError(f"unsupported evidence_state: {evidence_state}")
        self.source(source_id)
        try:
            concept_id = self.resolve_concept(concept)
        except KeyError:
            concept_id = self.get_or_create_concept(concept)
        identity = _canonical_json(
            {
                "concept_id": concept_id,
                "source_id": source_id,
                "evidence_span": evidence_span.strip(),
                "interpretation_state": interpretation_state,
                "evidence_state": evidence_state,
            }
        )
        observation_id = _stable_id("OBS", identity)
        self.conn.execute(
            """
            INSERT OR IGNORE INTO observations(
                observation_id, concept_id, source_id, evidence_span, confidence,
                interpretation_state, evidence_state, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                observation_id,
                concept_id,
                source_id,
                evidence_span.strip(),
                confidence,
                interpretation_state,
                evidence_state,
                _utc_now(),
            ),
        )
        self._append_event(
            "OBSERVATION_RECORDED",
            {
                "observation_id": observation_id,
                "concept_id": concept_id,
                "source_id": source_id,
                "confidence": confidence,
                "interpretation_state": interpretation_state,
                "evidence_state": evidence_state,
            },
        )
        self.conn.commit()
        return observation_id

    @staticmethod
    def _sentences(text: str) -> list[str]:
        pieces = re.split(r"(?<=[.!?])\s+|\n+", text)
        return [piece.strip() for piece in pieces if piece.strip()]

    @classmethod
    def _candidate_phrases(cls, text: str) -> list[tuple[str, float, str]]:
        counts: Counter[str] = Counter()
        first_span: dict[str, str] = {}
        spread: defaultdict[str, set[int]] = defaultdict(set)

        for idx, sentence in enumerate(cls._sentences(text)):
            tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9'_-]*", sentence.lower())
            chunks: list[list[str]] = []
            current: list[str] = []
            for token in tokens:
                norm = token.strip("'_- ")
                if not norm or norm in STOPWORDS or len(norm) < 3:
                    if current:
                        chunks.append(current)
                        current = []
                else:
                    current.append(norm)
            if current:
                chunks.append(current)

            for chunk in chunks:
                if len(chunk) > 8:
                    chunk = chunk[:8]
                for n in (3, 2, 1):
                    if len(chunk) < n:
                        continue
                    for start in range(0, len(chunk) - n + 1):
                        phrase = " ".join(chunk[start : start + n])
                        if n == 1 and (len(phrase) < 5 or phrase.isdigit()):
                            continue
                        counts[phrase] += 1
                        spread[phrase].add(idx)
                        first_span.setdefault(phrase, sentence[:500])

        candidates: list[tuple[str, float, str]] = []
        for phrase, count in counts.items():
            n = len(phrase.split())
            sentence_spread = len(spread[phrase])
            score = (count * (1.0 + 0.75 * (n - 1))) + (0.35 * sentence_spread)
            if n == 1 and count < 2:
                continue
            candidates.append((phrase, score, first_span[phrase]))
        candidates.sort(key=lambda item: (-item[1], -len(item[0].split()), item[0]))
        return candidates

    def extract(self, source_id: str, *, max_concepts: int = 20) -> list[dict[str, Any]]:
        if max_concepts < 1:
            raise ValueError("max_concepts must be >= 1")
        src = self.source(source_id)
        selected: list[dict[str, Any]] = []
        covered_tokens: set[str] = set()
        for phrase, score, span in self._candidate_phrases(src["raw_text"]):
            phrase_tokens = set(phrase.split())
            if phrase_tokens and phrase_tokens <= covered_tokens and len(phrase_tokens) <= 2:
                continue
            concept_id = self.get_or_create_concept(phrase)
            observation_id = self.record_observation(
                concept_id,
                source_id,
                span,
                confidence=0.55,
                interpretation_state="heuristic_candidate",
                evidence_state="EXTRACTED",
            )
            selected.append(
                {
                    "concept_id": concept_id,
                    "concept": phrase,
                    "heuristic_score": round(score, 6),
                    "observation_id": observation_id,
                    "evidence_state": "EXTRACTED",
                }
            )
            covered_tokens.update(phrase_tokens)
            if len(selected) >= max_concepts:
                break
        self._append_event(
            "SOURCE_EXTRACTED",
            {"source_id": source_id, "count": len(selected), "max_concepts": max_concepts},
        )
        self.conn.commit()
        return selected

    def link(
        self,
        from_concept: str,
        relation: str,
        to_concept: str,
        *,
        source_id: str | None = None,
        confidence: float = 0.8,
        status: str = "inference",
    ) -> str:
        relation = relation.upper()
        if relation not in RELATIONS:
            raise ValueError(f"unsupported relation: {relation}")
        confidence = _clamp01(confidence)
        if source_id is not None:
            self.source(source_id)
        try:
            from_id = self.resolve_concept(from_concept)
        except KeyError:
            from_id = self.get_or_create_concept(from_concept)
        try:
            to_id = self.resolve_concept(to_concept)
        except KeyError:
            to_id = self.get_or_create_concept(to_concept)
        identity = _canonical_json(
            {
                "from": from_id,
                "relation": relation,
                "to": to_id,
                "source_id": source_id,
                "status": status,
            }
        )
        edge_id = _stable_id("EDGE", identity)
        self.conn.execute(
            """
            INSERT OR IGNORE INTO edges(
                edge_id, from_concept_id, relation, to_concept_id,
                confidence, status, source_id, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (edge_id, from_id, relation, to_id, confidence, status, source_id, _utc_now()),
        )
        self._append_event(
            "EDGE_RECORDED",
            {
                "edge_id": edge_id,
                "from_concept_id": from_id,
                "relation": relation,
                "to_concept_id": to_id,
                "confidence": confidence,
                "status": status,
                "source_id": source_id,
            },
        )
        self.conn.commit()
        return edge_id

    def _concept_stats(self) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """
                SELECT
                    c.concept_id,
                    c.name,
                    c.status,
                    COUNT(o.observation_id) AS obs_count,
                    COUNT(DISTINCT o.source_id) AS source_count,
                    AVG(o.confidence) AS avg_confidence
                FROM concepts c
                LEFT JOIN observations o ON o.concept_id = c.concept_id
                GROUP BY c.concept_id
                ORDER BY c.name COLLATE NOCASE
                """
            )
        )

    def scan(self) -> list[ResonanceVector]:
        stats = self._concept_stats()
        if not stats:
            return []
        total_sources = int(
            self.conn.execute("SELECT COUNT(*) AS n FROM sources").fetchone()["n"]
        )
        all_domains: set[str] = set()
        for row in self.conn.execute("SELECT domains_json FROM sources"):
            all_domains.update(json.loads(row["domains_json"]))
        max_source_count = max(int(row["source_count"]) for row in stats) or 1

        degree: Counter[str] = Counter()
        negative_degree: Counter[str] = Counter()
        for edge in self.conn.execute(
            "SELECT from_concept_id, relation, to_concept_id FROM edges"
        ):
            degree[edge["from_concept_id"]] += 1
            degree[edge["to_concept_id"]] += 1
            if edge["relation"] in CONTRADICTION_RELATIONS:
                negative_degree[edge["from_concept_id"]] += 1
                negative_degree[edge["to_concept_id"]] += 1
        max_degree = max(degree.values(), default=1)

        output: list[ResonanceVector] = []
        for row in stats:
            cid = str(row["concept_id"])
            source_count = int(row["source_count"])
            obs_count = int(row["obs_count"])

            if source_count == 0:
                persistence = 0.0
            else:
                relative = math.log1p(source_count) / math.log1p(max_source_count)
                absolute = source_count / max(total_sources, 1)
                persistence = _clamp01(0.75 * relative + 0.25 * absolute)

            concept_domains: set[str] = set()
            for drow in self.conn.execute(
                """
                SELECT s.domains_json
                FROM observations o JOIN sources s ON s.source_id = o.source_id
                WHERE o.concept_id = ?
                """,
                (cid,),
            ):
                concept_domains.update(json.loads(drow["domains_json"]))
            if all_domains:
                domain_diversity = _clamp01(len(concept_domains) / len(all_domains))
            else:
                domain_diversity = 1.0 if source_count else 0.0

            centrality = _clamp01(degree[cid] / max_degree) if max_degree else 0.0

            evidence_rows = list(
                self.conn.execute(
                    "SELECT confidence, evidence_state, interpretation_state FROM observations WHERE concept_id = ?",
                    (cid,),
                )
            )
            if evidence_rows:
                weighted = [
                    float(erow["confidence"])
                    * EVIDENCE_WEIGHTS.get(str(erow["evidence_state"]).upper(), 0.15)
                    for erow in evidence_rows
                ]
                evidence_quality = _clamp01(sum(weighted) / len(weighted))
                interpretation_states = {str(erow["interpretation_state"]) for erow in evidence_rows}
                disputed = sum(
                    1
                    for erow in evidence_rows
                    if str(erow["evidence_state"]).upper()
                    in {"DISPUTED", "CONTRADICTED", "INVALIDATED"}
                )
            else:
                evidence_quality = 0.0
                interpretation_states = set()
                disputed = 0

            state_volatility = (
                max(0, len(interpretation_states) - 1) / max(obs_count, 1)
                if obs_count
                else 0.0
            )
            contradiction_pressure = _clamp01(
                (negative_degree[cid] + disputed)
                / max(degree[cid] + obs_count, 1)
            )
            volatility = _clamp01(0.7 * state_volatility + 0.3 * contradiction_pressure)

            resonance_score = _clamp01(
                persistence * domain_diversity * centrality * evidence_quality
            )
            classification = self._classify(
                resonance_score,
                volatility,
                contradiction_pressure,
                source_count,
                obs_count,
            )
            output.append(
                ResonanceVector(
                    concept_id=cid,
                    concept=str(row["name"]),
                    persistence=round(persistence, 6),
                    domain_diversity=round(domain_diversity, 6),
                    centrality=round(centrality, 6),
                    evidence_quality=round(evidence_quality, 6),
                    volatility=round(volatility, 6),
                    contradiction_pressure=round(contradiction_pressure, 6),
                    resonance_score=round(resonance_score, 6),
                    observations=obs_count,
                    sources=source_count,
                    domains=len(concept_domains),
                    classification=classification,
                )
            )
        output.sort(
            key=lambda item: (
                -item.resonance_score,
                -item.persistence,
                -item.evidence_quality,
                item.concept.lower(),
            )
        )
        return output

    @staticmethod
    def _classify(
        resonance_score: float,
        volatility: float,
        contradiction_pressure: float,
        source_count: int,
        obs_count: int,
    ) -> str:
        if contradiction_pressure >= 0.45:
            return "CONTRADICTION_PRESSURE"
        if source_count >= 3 and resonance_score >= 0.45 and volatility <= 0.25:
            return "NODAL_INVARIANT_CANDIDATE"
        if source_count >= 2 and resonance_score >= 0.45 and volatility > 0.25:
            return "ACTIVE_RESONANT_MODE"
        if source_count <= 1 and (volatility >= 0.20 or resonance_score >= 0.45):
            return "EXPERIMENT"
        if obs_count:
            return "DORMANT_OR_INCIDENTAL"
        return "UNOBSERVED"

    def history(self, concept: str) -> dict[str, Any]:
        concept_id = self.resolve_concept(concept)
        concept_row = self.conn.execute(
            "SELECT * FROM concepts WHERE concept_id = ?", (concept_id,)
        ).fetchone()
        observations = [
            dict(row)
            for row in self.conn.execute(
                """
                SELECT o.*, s.title AS source_title, s.source_type, s.source_timestamp, s.sha256 AS source_sha256
                FROM observations o JOIN sources s ON s.source_id = o.source_id
                WHERE o.concept_id = ? ORDER BY o.created_at, o.observation_id
                """,
                (concept_id,),
            )
        ]
        edges = [
            dict(row)
            for row in self.conn.execute(
                """
                SELECT e.*, cf.name AS from_name, ct.name AS to_name
                FROM edges e
                JOIN concepts cf ON cf.concept_id = e.from_concept_id
                JOIN concepts ct ON ct.concept_id = e.to_concept_id
                WHERE e.from_concept_id = ? OR e.to_concept_id = ?
                ORDER BY e.created_at, e.edge_id
                """,
                (concept_id, concept_id),
            )
        ]
        aliases = [
            row["normalized_alias"]
            for row in self.conn.execute(
                "SELECT normalized_alias FROM aliases WHERE concept_id = ? ORDER BY normalized_alias",
                (concept_id,),
            )
        ]
        return {
            "concept": dict(concept_row) if concept_row else None,
            "aliases": aliases,
            "observations": observations,
            "edges": edges,
        }

    def verify_integrity(self) -> dict[str, Any]:
        source_errors: list[str] = []
        for row in self.conn.execute("SELECT source_id, sha256, raw_text FROM sources"):
            actual = _sha256_text(str(row["raw_text"]))
            if actual != row["sha256"]:
                source_errors.append(str(row["source_id"]))

        event_errors: list[int] = []
        expected_prev = "GENESIS"
        for row in self.conn.execute("SELECT * FROM events ORDER BY seq"):
            if row["prev_hash"] != expected_prev:
                event_errors.append(int(row["seq"]))
            envelope = {
                "event_type": row["event_type"],
                "payload": json.loads(row["payload_json"]),
                "prev_hash": row["prev_hash"],
                "created_at": row["created_at"],
            }
            actual_hash = _sha256_text(_canonical_json(envelope))
            if actual_hash != row["event_hash"]:
                event_errors.append(int(row["seq"]))
            expected_prev = str(row["event_hash"])

        fk_errors = [tuple(row) for row in self.conn.execute("PRAGMA foreign_key_check")]
        event_errors = sorted(set(event_errors))
        ok = not source_errors and not event_errors and not fk_errors
        return {
            "ok": ok,
            "source_hash_errors": source_errors,
            "event_chain_errors": event_errors,
            "foreign_key_errors": fk_errors,
            "sources": int(self.conn.execute("SELECT COUNT(*) AS n FROM sources").fetchone()["n"]),
            "concepts": int(self.conn.execute("SELECT COUNT(*) AS n FROM concepts").fetchone()["n"]),
            "observations": int(self.conn.execute("SELECT COUNT(*) AS n FROM observations").fetchone()["n"]),
            "edges": int(self.conn.execute("SELECT COUNT(*) AS n FROM edges").fetchone()["n"]),
            "events": int(self.conn.execute("SELECT COUNT(*) AS n FROM events").fetchone()["n"]),
        }

    def export_scan(self) -> list[dict[str, Any]]:
        return [asdict(item) for item in self.scan()]
