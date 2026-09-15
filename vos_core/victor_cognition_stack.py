#!/usr/bin/env python3
# =============================================================================
# SAVE3 STANDARD
# artifact: victor_cognition_stack/victor_cognition_stack.py
# version: 1.0.0
# schema_version: 1
# trust: 0.85
# handoff: builder_ready
# error_proof: single_db + single_tick_clock + single_audit + hash_dedupe + wal
# future_proof: schema_migrations + organ_registry + provenance_layers
# constraints:
#   - zero third-party dependencies
#   - zero LLM cognition / inference / generation / models
#   - emergence = deterministic resonance phase transition
#   - no autonomous execution; executive gate is approval-only
# =============================================================================

import argparse
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

APP_NAME = "Victor Cognition Stack"
VERSION = "1.0.0"
SCHEMA_VERSION = 2
EMERGENCE_THRESHOLD = 3

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "but", "by",
    "can", "could", "did", "do", "does", "done", "for", "from", "had", "has",
    "have", "he", "her", "here", "him", "his", "how", "i", "if", "in", "into",
    "is", "it", "its", "just", "me", "my", "no", "not", "of", "off", "on",
    "or", "our", "out", "over", "she", "so", "some", "than", "that", "the",
    "their", "them", "then", "there", "these", "they", "this", "those",
    "through", "to", "under", "until", "up", "us", "was", "we", "were",
    "what", "when", "where", "which", "who", "whom", "why", "will", "with",
    "would", "you", "your", "yours"
}

TOKEN_RE = re.compile(r"[a-z0-9_@#]{2,}")

HIGH_SIGNAL = {
    "victor", "victorios", "victory", "bando", "bandobandz", "tori",
    "bloodline", "memory", "organ", "organs", "cognition", "membrane",
    "wake", "goal", "plan", "build", "ship", "deploy", "release",
    "security", "error", "fail", "failure", "crash", "sovereign",
    "governance", "album", "song"
}

SOURCE_TRUST = {
    "manual": 0.85,
    "user": 0.85,
    "bando": 0.90,
    "system": 0.65,
    "derived": 0.60,
    "web": 0.50,
    "unknown": 0.40
}

MODE_WHITELIST = {"manual", "web_bridge", "file", "local"}

ACTION_WHITELIST = {
    "inject_text",
    "click_send",
    "capture_selection",
    "capture_last_visible",
    "review_goal",
    "noop"
}

RESULT_WHITELIST = {"success", "error", "blocked"}

DEFAULT_RULES = [
    {
        "name": "victor_memory_focus",
        "condition": {"all_terms": ["victor", "memory"]},
        "action": {
            "add_fact": {
                "key": "topic/victor/memory",
                "value": {"domain": "victor_memory", "priority": 0.9}
            },
            "activate_goal": {
                "key": "advance_victor_memory",
                "title": "Advance Victor local memory",
                "priority": 0.9
            }
        }
    },
    {
        "name": "cognition_organ_focus",
        "condition": {"any_terms": ["cognition", "organ", "organs", "membrane"]},
        "action": {
            "activate_goal": {
                "key": "build_cognitive_organs",
                "title": "Build Victor cognitive organs",
                "priority": 0.9
            }
        }
    },
    {
        "name": "error_signal",
        "condition": {"any_terms": ["error", "fail", "failure", "crash"]},
        "action": {
            "add_fact": {
                "key": "signal/error",
                "value": {"needs_review": True}
            },
            "activate_goal": {
                "key": "reduce_failure_risk",
                "title": "Reduce failure risk",
                "priority": 0.85
            }
        }
    },
    {
        "name": "bando_identity",
        "condition": {"any_terms": ["bando", "bandobandz", "iambandobandz"]},
        "action": {
            "add_fact": {
                "key": "identity/speaker/bando",
                "value": {"speaker": "bando"}
            }
        }
    },
    {
        "name": "music_focus",
        "condition": {"any_terms": ["album", "song", "verse", "chorus"]},
        "action": {
            "activate_goal": {
                "key": "advance_music_artifact",
                "title": "Advance music artifact",
                "priority": 0.7
            }
        }
    }
]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp01(value) -> float:
    try:
        value = float(value)
    except Exception:
        return 0.5
    return max(0.0, min(1.0, value))


def _terms(text: str):
    if not text:
        return []
    raw = TOKEN_RE.findall(text.lower())
    seen = set()
    out = []
    for t in raw:
        if t in STOPWORDS or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out[:500]


class VictorCognitionStack:
    """
    The welded cognition stack.
    One DB. One tick clock. One audit ledger. One provenance law.
    """

    def __init__(self, db_path=None):
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = (
                Path(__file__).resolve().parent / ".victor_stack" / "victor_stack.db"
            )
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
        self.tick = self._load_tick()

    # ------------------------------------------------------------------ schema
    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_schema(self) -> None:
        conn = self._conn()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS runtime_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                layer TEXT NOT NULL DEFAULT 'input',
                kind TEXT NOT NULL DEFAULT 'note',
                key TEXT,
                content TEXT NOT NULL,
                content_hash TEXT NOT NULL UNIQUE,
                source TEXT NOT NULL DEFAULT 'manual',
                importance REAL NOT NULL DEFAULT 0.5,
                trust REAL NOT NULL DEFAULT 0.5,
                status TEXT NOT NULL DEFAULT 'active',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_memories_layer ON memories(layer);
            CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at);

            CREATE TABLE IF NOT EXISTS memory_terms (
                memory_id INTEGER NOT NULL,
                term TEXT NOT NULL,
                UNIQUE(memory_id, term),
                FOREIGN KEY(memory_id) REFERENCES memories(id)
            );

            CREATE INDEX IF NOT EXISTS idx_memory_terms_term ON memory_terms(term);

            CREATE TABLE IF NOT EXISTS memory_links (
                source_id INTEGER NOT NULL,
                target_id INTEGER NOT NULL,
                relation TEXT NOT NULL DEFAULT 'shared_term',
                weight REAL NOT NULL DEFAULT 0.5,
                created_at TEXT NOT NULL,
                UNIQUE(source_id, target_id, relation),
                FOREIGN KEY(source_id) REFERENCES memories(id),
                FOREIGN KEY(target_id) REFERENCES memories(id)
            );

            CREATE TABLE IF NOT EXISTS goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal_key TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                priority REAL NOT NULL DEFAULT 0.5,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal_key TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                plan_hash TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'proposed',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                condition_json TEXT NOT NULL,
                action_json TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                label TEXT NOT NULL,
                mode TEXT NOT NULL DEFAULT 'manual',
                settings_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER,
                kind TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'proposed',
                result_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS resonance (
                concept_hash TEXT PRIMARY KEY,
                concept TEXT NOT NULL,
                organs_json TEXT NOT NULL DEFAULT '[]',
                payloads_json TEXT NOT NULL DEFAULT '{}',
                tick INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'live',
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS crystallizations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                concept_hash TEXT NOT NULL,
                concept TEXT NOT NULL,
                organs_json TEXT NOT NULL,
                gestalt_json TEXT NOT NULL,
                tick INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tick INTEGER NOT NULL,
                organ TEXT NOT NULL,
                event TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            """
        )

        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (SCHEMA_VERSION, _utcnow()),
        )

        for rule in DEFAULT_RULES:
            conn.execute(
                """
                INSERT OR IGNORE INTO rules (name, condition_json, action_json, enabled)
                VALUES (?, ?, ?, 1)
                """,
                (
                    rule["name"],
                    json.dumps(rule["condition"], sort_keys=True),
                    json.dumps(rule["action"], sort_keys=True),
                ),
            )

        conn.commit()
        conn.close()

    # ------------------------------------------------------------------ audit
    def _load_tick(self) -> int:
        conn = self._conn()
        row = conn.execute("SELECT value FROM runtime_state WHERE key='tick'").fetchone()
        conn.close()
        if row is None:
            return 0
        try:
            return max(0, int(row["value"]))
        except (TypeError, ValueError):
            return 0

    def _persist_tick(self, conn) -> None:
        conn.execute(
            """
            INSERT INTO runtime_state(key, value, updated_at)
            VALUES('tick', ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value=excluded.value,
                updated_at=excluded.updated_at
            """,
            (str(int(self.tick)), _utcnow()),
        )

    def _audit(self, conn, organ, event, payload, tick=None):
        conn.execute(
            """
            INSERT INTO audit (tick, organ, event, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                self.tick if tick is None else tick,
                organ,
                event,
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                _utcnow(),
            ),
        )

    # ------------------------------------------------------- memory primitive
    def _remember(
        self,
        conn,
        layer,
        kind,
        key,
        content,
        source,
        importance,
        trust,
        metadata,
    ):
        content = (content or "").strip()
        if not content:
            raise ValueError("memory content is empty")

        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        existing = conn.execute(
            "SELECT id FROM memories WHERE content_hash = ?", (content_hash,)
        ).fetchone()
        if existing:
            return existing["id"], False, content_hash[:16]

        if importance is None:
            hits = len(set(_terms(content)).intersection(HIGH_SIGNAL))
            importance = _clamp01(0.5 + 0.1 * hits)
        else:
            importance = _clamp01(importance)

        if trust is None:
            trust = SOURCE_TRUST.get(source, SOURCE_TRUST["unknown"])
        else:
            trust = _clamp01(trust)

        cur = conn.execute(
            """
            INSERT INTO memories (
                layer, kind, key, content, content_hash, source,
                importance, trust, status, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
            """,
            (
                layer,
                kind,
                key,
                content,
                content_hash,
                source,
                importance,
                trust,
                json.dumps(metadata or {}, ensure_ascii=False),
                _utcnow(),
            ),
        )
        memory_id = cur.lastrowid

        for term in _terms((key or "") + " " + content):
            conn.execute(
                "INSERT OR IGNORE INTO memory_terms (memory_id, term) VALUES (?, ?)",
                (memory_id, term),
            )

        self._audit(conn, layer, "memory_added", {"memory_id": memory_id, "key": key})
        return memory_id, True, content_hash[:16]

    # ------------------------------------------------------------- gen-1 face
    def register_account(self, platform, label, mode, settings=None):
        mode = (mode or "manual").strip()
        if mode not in MODE_WHITELIST:
            raise ValueError(f"invalid account mode: {mode}")
        conn = self._conn()
        cur = conn.execute(
            """
            INSERT INTO accounts (platform, label, mode, settings_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                platform,
                label,
                mode,
                json.dumps(settings or {}, ensure_ascii=False),
                _utcnow(),
            ),
        )
        account_id = cur.lastrowid
        self._audit(conn, "surface", "account_registered", {"account_id": account_id})
        conn.commit()
        conn.close()
        return account_id

    def queue_surface_action(self, account_id, kind, payload=None):
        if kind not in ACTION_WHITELIST:
            raise ValueError(f"invalid action kind: {kind}")
        conn = self._conn()
        account = conn.execute(
            "SELECT id FROM accounts WHERE id = ?", (account_id,)
        ).fetchone()
        if not account:
            conn.close()
            raise LookupError("account not found")
        cur = conn.execute(
            """
            INSERT INTO actions (account_id, kind, payload_json, status, created_at, updated_at)
            VALUES (?, ?, ?, 'proposed', ?, ?)
            """,
            (
                account_id,
                kind,
                json.dumps(payload or {}, ensure_ascii=False),
                _utcnow(),
                _utcnow(),
            ),
        )
        action_id = cur.lastrowid
        self._audit(conn, "surface", "action_queued", {"action_id": action_id})
        conn.commit()
        conn.close()
        return action_id

    def record_surface_result(self, action_id, status, result=None):
        if status not in RESULT_WHITELIST:
            raise ValueError(f"invalid result status: {status}")
        final_status = "executed_by_human" if status == "success" else status
        conn = self._conn()
        cur = conn.execute(
            """
            UPDATE actions SET status = ?, result_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                final_status,
                json.dumps(result or {}, ensure_ascii=False),
                _utcnow(),
                action_id,
            ),
        )
        if cur.rowcount == 0:
            conn.close()
            raise LookupError("action not found")
        self._audit(conn, "surface", "action_result", {"action_id": action_id, "status": final_status})
        conn.commit()
        conn.close()
        return True

    # ------------------------------------------------------------- gen-2 face
    def remember(self, content, source="manual", kind="note", metadata=None):
        conn = self._conn()
        memory_id, created, h16 = self._remember(
            conn, "input", kind, None, content, source, None, None, metadata
        )
        conn.commit()
        conn.close()
        return {"memory_id": memory_id, "created": created, "hash16": h16}

    def search(self, query, limit=20):
        query = (query or "").strip()
        if not query:
            return []
        conn = self._conn()
        terms = _terms(query)[:20]
        sql = """
            SELECT DISTINCT m.id, m.layer, m.kind, m.key, m.content,
                   m.source, m.importance, m.trust, m.created_at
            FROM memories m
            LEFT JOIN memory_terms t ON t.memory_id = m.id
            WHERE m.content LIKE ?
        """
        params = [f"%{query}%"]
        if terms:
            sql += f" OR t.term IN ({','.join(['?'] * len(terms))})"
            params.extend(terms)
        sql += " ORDER BY m.created_at DESC LIMIT ?"
        params.append(int(limit))
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def link_memories(self, conn, limit=300):
        rows = conn.execute(
            """
            SELECT a.memory_id AS x, b.memory_id AS y, COUNT(*) AS shared
            FROM memory_terms a
            JOIN memory_terms b ON a.term = b.term AND a.memory_id < b.memory_id
            GROUP BY a.memory_id, b.memory_id
            HAVING shared >= 2
            ORDER BY shared DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
        created = 0
        for row in rows:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO memory_links
                (source_id, target_id, relation, weight, created_at)
                VALUES (?, ?, 'shared_term', ?, ?)
                """,
                (row["x"], row["y"], min(1.0, row["shared"] / 5.0), _utcnow()),
            )
            created += cur.rowcount
        return created

    def compress(self, days=1.0, min_count=3):
        conn = self._conn()
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=float(days))).isoformat()
        rows = conn.execute(
            """
            SELECT id FROM memories
            WHERE created_at >= ? AND layer NOT IN ('compression', 'gestalt')
            ORDER BY id
            """,
            (cutoff,),
        ).fetchall()
        ids = [r["id"] for r in rows]
        if len(ids) < int(min_count):
            conn.close()
            return {"created": False, "memory_count": len(ids)}
        ph = ",".join(["?"] * len(ids))
        term_rows = conn.execute(
            f"""
            SELECT term, COUNT(*) AS c FROM memory_terms
            WHERE memory_id IN ({ph})
            GROUP BY term ORDER BY c DESC, term ASC LIMIT 25
            """,
            ids,
        ).fetchall()
        payload = {
            "type": "deterministic_compression",
            "window_days": float(days),
            "memory_count": len(ids),
            "memory_ids": ids[:1000],
            "top_terms": [{"term": r["term"], "count": r["c"]} for r in term_rows],
        }
        content = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        memory_id, created, _ = self._remember(
            conn, "compression", "compression", "compression/latest",
            content, "system", 0.6, 0.7, {}
        )
        self._audit(conn, "reflection", "compression", {"memory_count": len(ids)})
        conn.commit()
        conn.close()
        return {"created": created, "memory_count": len(ids), "memory_id": memory_id}

    # ------------------------------------------------------------- gen-3 face
    def add_fact(self, conn, key, value, source="system", confidence=0.6):
        content = key + " " + json.dumps(value, ensure_ascii=False, sort_keys=True)
        return self._remember(
            conn, "fact", "fact", key, content, source, None, confidence,
            {"value": value}
        )

    def apply_rules(self, conn):
        rules = conn.execute("SELECT * FROM rules WHERE enabled = 1").fetchall()
        facts = conn.execute(
            "SELECT id FROM memories WHERE layer IN ('input','fact','derived') AND status='active'"
        ).fetchall()
        term_cache = {}
        for f in facts:
            rows = conn.execute(
                "SELECT term FROM memory_terms WHERE memory_id = ?", (f["id"],)
            ).fetchall()
            term_cache[f["id"]] = {r["term"] for r in rows}

        derived = 0
        goals_activated = 0

        for rule in rules:
            cond = json.loads(rule["condition_json"])
            act = json.loads(rule["action_json"])
            all_t = cond.get("all_terms", [])
            any_t = cond.get("any_terms", [])
            if not all_t and not any_t:
                continue
            for f in facts:
                terms = term_cache.get(f["id"], set())
                if all_t and not set(all_t).issubset(terms):
                    continue
                if any_t and not any(t in terms for t in any_t):
                    continue
                if "add_fact" in act:
                    spec = act["add_fact"]
                    value = dict(spec.get("value", {}))
                    value["derived_from_rule"] = rule["name"]
                    _, created, _ = self._remember(
                        conn, "derived", "fact",
                        "derived/" + spec.get("key", rule["name"]),
                        "derived/" + spec.get("key", rule["name"]) + " " + json.dumps(value, sort_keys=True),
                        "derived", None, 0.6, {"value": value}
                    )
                    if created:
                        derived += 1
                if "activate_goal" in act:
                    spec = act["activate_goal"]
                    if self._activate_goal(
                        conn,
                        spec.get("key", rule["name"]),
                        spec.get("title", rule["name"]),
                        spec.get("priority", 0.5),
                    ):
                        goals_activated += 1

        self._audit(conn, "inference", "rules_applied",
                    {"derived": derived, "goals_activated": goals_activated})
        return {"derived_facts": derived, "goals_activated": goals_activated}

    def _activate_goal(self, conn, goal_key, title, priority):
        priority = _clamp01(priority)
        now = _utcnow()
        existing = conn.execute(
            "SELECT id, priority, status FROM goals WHERE goal_key = ?", (goal_key,)
        ).fetchone()
        if existing:
            new_p = max(existing["priority"], priority)
            changed = existing["status"] != "active" or new_p != existing["priority"]
            if changed:
                conn.execute(
                    "UPDATE goals SET status='active', title=?, priority=?, updated_at=? WHERE id=?",
                    (title, new_p, now, existing["id"]),
                )
            return changed
        conn.execute(
            """
            INSERT INTO goals (goal_key, title, priority, status, created_at, updated_at)
            VALUES (?, ?, ?, 'active', ?, ?)
            """,
            (goal_key, title, priority, now, now),
        )
        return True

    def make_plan(self, goal_key, title):
        base = [
            {"step": "review_active_facts", "mode": "human_review", "approval_required": True},
            {"step": "select_next_artifact", "mode": "human_directed", "approval_required": True},
            {"step": "execute_local_action", "mode": "explicit_execution", "approval_required": True},
        ]
        if goal_key == "advance_victor_memory":
            steps = [
                {"step": "verify_local_database", "mode": "local_check", "approval_required": False},
                {"step": "link_related_memories", "mode": "deterministic", "approval_required": False},
                {"step": "compress_recent_memory", "mode": "deterministic", "approval_required": False},
            ]
        elif goal_key == "build_cognitive_organs":
            steps = [
                {"step": "define_organ_interfaces", "mode": "deterministic", "approval_required": False},
                {"step": "wire_organ_subscriptions", "mode": "build", "approval_required": True},
                {"step": "add_executive_approval_gate", "mode": "build", "approval_required": True},
            ]
        elif goal_key == "reduce_failure_risk":
            steps = [
                {"step": "collect_error_facts", "mode": "deterministic", "approval_required": False},
                {"step": "identify_failure_source", "mode": "human_review", "approval_required": True},
            ]
        else:
            steps = base
        return {
            "goal_key": goal_key,
            "title": title,
            "execution_mode": "human_approved",
            "constraints": [
                "zero_third_party_dependencies",
                "zero_llm_cognition",
                "no_autonomous_execution",
            ],
            "steps": steps,
        }

    def update_plans(self, conn):
        goals = conn.execute(
            "SELECT goal_key, title FROM goals WHERE status='active'"
        ).fetchall()
        created = 0
        for g in goals:
            plan_json = json.dumps(self.make_plan(g["goal_key"], g["title"]), sort_keys=True)
            plan_hash = hashlib.sha256(plan_json.encode("utf-8")).hexdigest()
            exists = conn.execute(
                "SELECT id FROM plans WHERE plan_hash = ?", (plan_hash,)
            ).fetchone()
            if not exists:
                conn.execute(
                    """
                    INSERT INTO plans (goal_key, plan_json, plan_hash, status, created_at)
                    VALUES (?, ?, ?, 'proposed', ?)
                    """,
                    (g["goal_key"], plan_json, plan_hash, _utcnow()),
                )
                created += 1
        return created

    def propose_actions(self, conn):
        goals = conn.execute(
            "SELECT goal_key, title FROM goals WHERE status='active'"
        ).fetchall()
        created = 0
        for g in goals:
            payload = json.dumps(
                {"goal_key": g["goal_key"], "title": g["title"], "action": "review_and_direct"},
                sort_keys=True,
            )
            exists = conn.execute(
                "SELECT id FROM actions WHERE payload_json = ? AND status = 'proposed'",
                (payload,),
            ).fetchone()
            if not exists:
                conn.execute(
                    """
                    INSERT INTO actions (account_id, kind, payload_json, status, created_at, updated_at)
                    VALUES (NULL, 'review_goal', ?, 'proposed', ?, ?)
                    """,
                    (payload, _utcnow(), _utcnow()),
                )
                created += 1
        return created

    def approve_action(self, action_id):
        conn = self._conn()
        cur = conn.execute(
            "UPDATE actions SET status='approved', updated_at=? WHERE id=? AND status='proposed'",
            (_utcnow(), action_id),
        )
        self._audit(conn, "executive", "action_approved", {"action_id": action_id})
        conn.commit()
        conn.close()
        return cur.rowcount > 0

    # ------------------------------------------------------------- gen-4 face
    def _publish(self, conn, organ, event, concept, payload):
        c_hash = hashlib.sha256(concept.encode("utf-8")).hexdigest()
        row = conn.execute(
            "SELECT organs_json, payloads_json FROM resonance WHERE concept_hash = ?",
            (c_hash,),
        ).fetchone()
        if row:
            organs = set(json.loads(row["organs_json"]))
            payloads = json.loads(row["payloads_json"])
        else:
            organs = set()
            payloads = {}
        organs.add(organ)
        payloads[organ] = payload
        conn.execute(
            """
            INSERT INTO resonance (concept_hash, concept, organs_json, payloads_json, tick, status, updated_at)
            VALUES (?, ?, ?, ?, ?, 'live', ?)
            ON CONFLICT(concept_hash) DO UPDATE SET
                organs_json = excluded.organs_json,
                payloads_json = excluded.payloads_json,
                tick = excluded.tick,
                status = 'live',
                updated_at = excluded.updated_at
            """,
            (c_hash, concept, json.dumps(sorted(organs)), json.dumps(payloads, sort_keys=True), self.tick, _utcnow()),
        )
        self._audit(conn, organ, event, {"concept": concept, "payload": payload})

    def check_emergence(self, conn):
        rows = conn.execute(
            "SELECT * FROM resonance WHERE status = 'live'"
        ).fetchall()
        crystallized = 0
        for row in rows:
            organs = json.loads(row["organs_json"])
            if len(organs) >= EMERGENCE_THRESHOLD:
                gestalt = {
                    "type": "emergent_gestalt",
                    "concept": row["concept"],
                    "organs_aligned": organs,
                    "payloads": json.loads(row["payloads_json"]),
                    "tick": self.tick,
                }
                conn.execute(
                    """
                    INSERT INTO crystallizations
                    (concept_hash, concept, organs_json, gestalt_json, tick, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["concept_hash"],
                        row["concept"],
                        json.dumps(organs),
                        json.dumps(gestalt, ensure_ascii=False, sort_keys=True),
                        self.tick,
                        _utcnow(),
                    ),
                )
                conn.execute(
                    "UPDATE resonance SET status='crystallized', updated_at=? WHERE concept_hash=?",
                    (_utcnow(), row["concept_hash"]),
                )
                self._audit(conn, "membrane", "phase_transition", {"concept": row["concept"], "organs": organs})
                crystallized += 1
        return crystallized

    # ---------------------------------------------------------------- the wake
    def cycle(self, text=None, source="manual", tick=None):
        if tick is None:
            self.tick += 1
        else:
            tick = int(tick)
            if tick < self.tick:
                raise ValueError("external tick cannot move cognition clock backward")
            self.tick = tick
        conn = self._conn()
        self._persist_tick(conn)
        report = {"tick": self.tick, "steps": {}}

        if text:
            memory_id, created, h16 = self._remember(
                conn, "input", "note", None, text, source, None, None, {}
            )
            concept = f"focus:{h16}"
            report["steps"]["sensory"] = {"memory_id": memory_id, "created": created}
            self._publish(conn, "sensory", "sensory_input", concept, {"memory_id": memory_id})
        else:
            concept = f"tick:{self.tick}"
            self._publish(conn, "wake", "tick_open", concept, {})

        hits = len(set(_terms(text or concept)).intersection(HIGH_SIGNAL))
        score = _clamp01(0.5 + 0.1 * hits)
        self._publish(conn, "attention", "salience_detected", concept, {"score": score})

        links = self.link_memories(conn)
        self._publish(conn, "memory", "indexed_and_linked", concept, {"links": links})

        inference = self.apply_rules(conn)
        self._publish(conn, "inference", "rules_applied", concept, inference)

        plans = self.update_plans(conn)
        actions = self.propose_actions(conn)
        self._publish(conn, "goal", "goals_planned", concept, {"plans": plans, "actions": actions})

        pending = conn.execute(
            "SELECT COUNT(*) AS c FROM actions WHERE status='proposed'"
        ).fetchone()["c"]
        self._publish(conn, "executive", "gate_hold", concept, {"pending": pending})

        crystallized = self.check_emergence(conn)

        report["steps"]["attention"] = {"score": score}
        report["steps"]["association"] = {"links": links}
        report["steps"]["inference"] = inference
        report["steps"]["planning"] = {"plans": plans, "actions": actions}
        report["steps"]["executive"] = {"pending_actions": pending}
        report["steps"]["membrane"] = {"crystallized": crystallized}

        conn.commit()
        conn.close()
        return report

    # ----------------------------------------------------------- introspection
    def goals(self):
        conn = self._conn()
        rows = conn.execute("SELECT * FROM goals ORDER BY priority DESC").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def plans(self):
        conn = self._conn()
        rows = conn.execute("SELECT * FROM plans ORDER BY id DESC").fetchall()
        conn.close()
        out = []
        for r in rows:
            d = dict(r)
            d["plan"] = json.loads(d.pop("plan_json"))
            out.append(d)
        return out

    def actions(self):
        conn = self._conn()
        rows = conn.execute("SELECT * FROM actions ORDER BY id DESC").fetchall()
        conn.close()
        out = []
        for r in rows:
            d = dict(r)
            d["payload"] = json.loads(d.pop("payload_json"))
            d["result"] = json.loads(d.pop("result_json"))
            out.append(d)
        return out

    def crystallizations(self):
        conn = self._conn()
        rows = conn.execute("SELECT * FROM crystallizations ORDER BY id DESC").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def audit(self, limit=50, newest_first=False):
        conn = self._conn()
        order = "DESC" if newest_first else "ASC"
        rows = conn.execute(
            f"SELECT * FROM audit ORDER BY id {order} LIMIT ?", (int(limit),)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]


def _cli():
    parser = argparse.ArgumentParser(description=APP_NAME)
    sub = parser.add_subparsers(dest="cmd")

    p = sub.add_parser("cycle")
    p.add_argument("text", nargs="?")
    p.add_argument("--source", default="manual")
    r = sub.add_parser("remember")
    r.add_argument("text")
    s = sub.add_parser("search")
    s.add_argument("query")
    sub.add_parser("goals")
    sub.add_parser("plans")
    sub.add_parser("actions")
    sub.add_parser("cryst")
    sub.add_parser("audit")
    a = sub.add_parser("approve")
    a.add_argument("action_id", type=int)

    args = parser.parse_args()
    stack = VictorCognitionStack()

    if args.cmd == "cycle":
        print(json.dumps(stack.cycle(args.text, args.source), indent=2))
    elif args.cmd == "remember":
        print(json.dumps(stack.remember(args.text), indent=2))
    elif args.cmd == "search":
        print(json.dumps(stack.search(args.query), indent=2))
    elif args.cmd == "goals":
        print(json.dumps(stack.goals(), indent=2))
    elif args.cmd == "plans":
        print(json.dumps(stack.plans(), indent=2))
    elif args.cmd == "actions":
        print(json.dumps(stack.actions(), indent=2))
    elif args.cmd == "cryst":
        print(json.dumps(stack.crystallizations(), indent=2))
    elif args.cmd == "audit":
        print(json.dumps(stack.audit(30, newest_first=True), indent=2))
    elif args.cmd == "approve":
        print(json.dumps({"ok": stack.approve_action(args.action_id)}, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    _cli()
