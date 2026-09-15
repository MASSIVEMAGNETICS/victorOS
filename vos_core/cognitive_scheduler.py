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

class ItemStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
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
    
    # For PriorityQueue sorting: highest priority first, then oldest first
    def __lt__(self, other: 'CognitiveItem') -> bool:
        if self.priority != other.priority:
            return self.priority > other.priority
        return self.created_tick < other.created_tick


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False)

def _hash_payload(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()

class PersistentCognitiveQueue:
    """SQLite-backed priority queue. Pending thoughts survive process death/reboot."""
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
        # Crash recovery: items claimed before a process died become pending again.
        with self._conn() as conn:
            conn.execute(
                "UPDATE cognitive_queue SET status=?, updated_at=? WHERE status=?",
                (ItemStatus.PENDING.value, _utcnow(), ItemStatus.PROCESSING.value),
            )

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
                created_at TEXT NOT NULL
            );
            """)

    def push(self, item: CognitiveItem) -> bool:
        if item.depth > MAX_DEPTH:
            item.status=ItemStatus.DROPPED_DEPTH
            return False
        now=_utcnow()
        with self._conn() as conn:
            conn.execute("""
              INSERT OR IGNORE INTO cognitive_queue
              (id,kind,content_json,priority,depth,parent_id,created_tick,ttl,status,created_at,updated_at)
              VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,(item.id,item.kind.value,_canonical_json(item.content),float(item.priority),
                 int(item.depth),item.parent_id,int(item.created_tick),int(item.ttl),
                 ItemStatus.PENDING.value,now,now))
        return True

    def pop_budgeted(self,current_tick:int,max_items:int=8,max_ms:int=300)->List[CognitiveItem]:
        start=time.perf_counter(); out=[]
        while len(out)<max_items and (time.perf_counter()-start)*1000<max_ms:
            with self._conn() as conn:
                row=conn.execute("""
                  SELECT * FROM cognitive_queue WHERE status=?
                  ORDER BY priority DESC, created_tick ASC LIMIT 1
                """,(ItemStatus.PENDING.value,)).fetchone()
                if row is None: break
                if current_tick-int(row["created_tick"])>int(row["ttl"]):
                    conn.execute("UPDATE cognitive_queue SET status=?,updated_at=? WHERE id=?",
                                 (ItemStatus.DROPPED_TTL.value,_utcnow(),row["id"]))
                    continue
                changed=conn.execute("""
                  UPDATE cognitive_queue SET status=?,updated_at=?
                  WHERE id=? AND status=?
                """,(ItemStatus.PROCESSING.value,_utcnow(),row["id"],ItemStatus.PENDING.value)).rowcount
                if not changed: continue
            out.append(self._row(row,ItemStatus.PROCESSING))
        return out

    def mark(self,item_id:str,status:ItemStatus):
        with self._conn() as conn:
            conn.execute("UPDATE cognitive_queue SET status=?,updated_at=? WHERE id=?",
                         (status.value,_utcnow(),item_id))

    def pending_count(self)->int:
        with self._conn() as conn:
            return int(conn.execute("SELECT COUNT(*) c FROM cognitive_queue WHERE status=?",
                                    (ItemStatus.PENDING.value,)).fetchone()["c"])

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
        return CognitiveItem(id=r["id"],kind=ItemKind(r["kind"]),content=json.loads(r["content_json"]),
          priority=float(r["priority"]),depth=int(r["depth"]),parent_id=r["parent_id"],
          created_tick=int(r["created_tick"]),ttl=int(r["ttl"]),status=status)

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
    def execute(self,capability,payload):
        if capability not in self.handlers: raise KeyError("unregistered capability: "+capability)
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
        self.queue=PersistentCognitiveQueue(self.db_path)
        self.registry=WindowsCapabilityRegistry(stack)
        self.bus=CognitiveEventBus(); self.bus.subscribe(self._ingest_event)
        self.current_tick=max(self._load_tick(),int(self.stack.tick))

    def _conn(self):
        conn=sqlite3.connect(self.db_path,timeout=30); conn.row_factory=sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;"); return conn

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
          "sensor_change":ItemKind.THOUGHT}
        self.queue.push(CognitiveItem(
          id=payload.get("event_id") or uuid.uuid4().hex,
          kind=mapping.get(event_type,ItemKind.THOUGHT),
          content={"event_type":event_type,**payload},
          priority=max(0.0,min(1.0,float(payload.get("priority",0.5)))),
          depth=0,parent_id=None,created_tick=self.current_tick))

    def _retrieve_context(self,item):
        query=str(item.content.get("text") or item.content.get("step") or item.content.get("event_type") or _canonical_json(item.content))
        return {
          "relevant_memories":self.stack.search(query,limit=8),
          "active_goals":[g for g in self.stack.goals() if g.get("status")=="active"][:12],
        }

    def _reason(self,item,context):
        out={"followup_thoughts":[],"candidate_actions":[]}
        if item.kind in (ItemKind.QUERY,ItemKind.GOAL,ItemKind.CONFLICT,ItemKind.PREDICTION):
            text=str(item.content.get("text") or item.content.get("message") or _canonical_json(item.content))
            before={a["id"] for a in self.stack.actions()}
            report=self.stack.cycle(text,source="scheduler",tick=self.current_tick)
            after=[a for a in self.stack.actions() if a["id"] not in before]
            out["followup_thoughts"].append({
              "kind":ItemKind.THOUGHT,
              "content":{"step":"review_cognition_cycle","origin_item_id":item.id,"text":text,
                         "stack_tick":report["tick"],"stack_action_ids":[a["id"] for a in after]},
              "priority":max(0.05,item.priority-0.05)})
            return out

        if item.kind==ItemKind.THOUGHT:
            action_ids=[int(x) for x in item.content.get("stack_action_ids",[])]
            actions={a["id"]:a for a in self.stack.actions()}
            for aid in action_ids:
                action=actions.get(aid)
                if action and action["status"]=="proposed":
                    out["candidate_actions"].append({
                      "capability":"cognition.queue_human_review",
                      "payload":{"stack_action_id":aid},"score":0.8,
                      "source_item_id":item.id})
            reflection=(f"Scheduler reflection for item {item.id}: "
                        f"{len(context['relevant_memories'])} relevant memories, "
                        f"{len(context['active_goals'])} active goals, "
                        f"{len(action_ids)} new proposed actions.")
            out["candidate_actions"].append({
              "capability":"memory.commit_reflection",
              "payload":{"text":reflection,"item_id":item.id},
              "score":max(0.1,item.priority-0.15),"source_item_id":item.id})
        return out

    @staticmethod
    def _choice_rank(candidates):
        valid=[dict(c) for c in candidates if c.get("capability") and 0<=float(c.get("score",0))<=1]
        return sorted(valid,key=lambda c:(float(c.get("score",0)),str(c["capability"]),str(c.get("source_item_id",""))),reverse=True)

    def _execute(self,ranked):
        if not ranked: return {"executed":None,"status":"NO_ACTION"}
        c=ranked[0]; capability=str(c["capability"])
        if not self.registry.contains(capability):
            return {"executed":None,"status":"BLOCKED_UNREGISTERED_CAPABILITY","capability":capability}
        proposal=ActionProposal(
          name=capability,capability=capability,provenance="victor-cognitive-scheduler",
          required_authorities=("local_owner",),consequence=.08,irreversibility=.05,
          uncertainty=max(0.0,1.0-float(c.get("score",.5))),novelty=.10,arousal=0,
          urgency=0,capability_power=.10,
          metadata={"scheduler_tick":self.current_tick,"source_item_id":c.get("source_item_id")})
        d=self.physiology.execute(proposal,lambda:self.registry.execute(capability,dict(c.get("payload",{}))))
        result={"capability":capability,"decision_status":d.status.value,
          "governance_mode":d.governance_mode.value,"reasons":list(d.reasons),
          "receipt_hash":d.receipt_hash,"outcome":d.actual_outcome}
        with self._conn() as conn:
            conn.execute("""INSERT INTO capability_results
              (tick,capability,status,payload_json,receipt_hash,created_at) VALUES(?,?,?,?,?,?)""",
              (self.current_tick,capability,d.status.value,_canonical_json(result),d.receipt_hash,_utcnow()))
        return {"executed":result,"status":d.status.value}

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

    def tick(self,max_items:int=8,max_ms:int=300):
        self.current_tick+=1; self._save_tick()
        receipt={"tick":self.current_tick,"queue_size_start":self.queue.pending_count(),
          "processed":0,"generated_thoughts":0,"generated_actions":0,"execution":None}
        work=self.queue.pop_budgeted(self.current_tick,max_items,max_ms)
        receipt["processed"]=len(work); candidates=[]
        for item in work:
            try:
                reasoned=self._reason(item,self._retrieve_context(item))
                for f in reasoned["followup_thoughts"]:
                    child=CognitiveItem(id=uuid.uuid4().hex,kind=f["kind"],content=dict(f["content"]),
                      priority=max(0,min(1,float(f.get("priority",.5)))),depth=item.depth+1,
                      parent_id=item.id,created_tick=self.current_tick)
                    if self.queue.push(child): receipt["generated_thoughts"]+=1
                candidates.extend(reasoned["candidate_actions"])
                receipt["generated_actions"]+=len(reasoned["candidate_actions"])
                self.queue.mark(item.id,ItemStatus.COMPLETED)
            except Exception as exc:
                self.queue.mark(item.id,ItemStatus.FAILED)
                receipt.setdefault("errors",[]).append(f"{type(exc).__name__}: {exc}")
        receipt["execution"]=self._execute(self._choice_rank(candidates))
        receipt["queue_size_end"]=self.queue.pending_count()
        receipt["receipt_hash"]=self._write_tick_receipt({k:v for k,v in receipt.items() if k!="receipt_hash"})
        return receipt
