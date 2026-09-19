from unittest import mock

from vos_core.cognitive_scheduler import (
    CognitiveItem,
    CognitiveScheduler,
    ItemKind,
)
from vos_core.physiology import PhysiologyReceiptLedger, VictorPhysiologyRuntime
from vos_core.victor_cognition_stack import VictorCognitionStack

def runtime(tmp_path):
    stack=VictorCognitionStack(str(tmp_path/"victor_stack.db"))
    phys=VictorPhysiologyRuntime(
        receipt_ledger=PhysiologyReceiptLedger(str(tmp_path/"physiology.jsonl")),
        granted_authorities=("local_owner",),
    )
    return stack,phys,CognitiveScheduler(stack,phys,tmp_path/"victor_stack.db")

def test_query_enqueues_followup_instead_of_recursive_think(tmp_path):
    stack,phys,s=runtime(tmp_path)
    s.publish_query("Victor memory cognition test.")
    r=s.tick(max_items=1)
    assert r["processed"]==1
    assert r["generated_thoughts"]==1
    assert s.queue.pending_count()==1
    assert stack.tick==1

def test_pending_thought_and_tick_survive_restart(tmp_path):
    stack,phys,s=runtime(tmp_path)
    s.publish_query("Victor memory unfinished thought.")
    s.tick(max_items=1)
    tick=s.current_tick
    assert s.queue.pending_count()==1
    stack2=VictorCognitionStack(str(tmp_path/"victor_stack.db"))
    phys2=VictorPhysiologyRuntime(
        receipt_ledger=PhysiologyReceiptLedger(str(tmp_path/"physiology2.jsonl")),
        granted_authorities=("local_owner",),
    )
    s2=CognitiveScheduler(stack2,phys2,tmp_path/"victor_stack.db")
    assert s2.current_tick==tick
    assert s2.queue.pending_count()==1
    assert s2.tick(max_items=1)["processed"]==1

def test_human_stop_blocks_capability_execution(tmp_path):
    stack,phys,s=runtime(tmp_path)
    s.publish_query("Victor memory cognition build.")
    s.tick(max_items=1)
    phys.set_human_stop(True)
    r=s.tick(max_items=1)
    assert r["execution"]["status"]=="REJECTED"
    assert "human_stop_active" in r["execution"]["executed"]["reasons"]

def test_context_retrieval_uses_real_memory(tmp_path):
    stack,phys,s=runtime(tmp_path)
    stack.remember("Victor scheduler retrieves durable memory",source="manual")
    s.publish_query("scheduler durable memory")
    item=s.queue.pop_budgeted(1,max_items=1)[0]
    ctx=s._retrieve_context(item)
    assert ctx["relevant_memories"]

def test_scheduler_receipt_chain_verifies(tmp_path):
    stack,phys,s=runtime(tmp_path)
    s.publish_query("Victor memory receipt test.")
    s.tick(max_items=1)
    s.tick(max_items=1)
    assert s.verify_receipts()


def test_execution_observation_reenters_queue_and_closes_loop(tmp_path):
    stack,phys,s=runtime(tmp_path)
    s.publish_query("Victor memory closed loop proof.")
    first=s.tick(max_items=1)
    assert first["generated_thoughts"]==1
    second=s.tick(max_items=1)
    assert second["execution"]["status"]=="EXECUTED"
    executed=second["execution"]["executed"]
    assert executed["receipt_hash"]
    assert executed["observation_event_id"]
    pending=s.queue.pending_items()
    assert {item["kind"] for item in pending}=={"OBSERVATION","ACTION_CANDIDATE"}
    observation=next(item for item in pending if item["kind"]=="OBSERVATION")
    assert observation["content"]["receipt_hash"]==executed["receipt_hash"]
    closed=s.run_until_quiescent(max_ticks=6,max_items=1)
    assert closed["quiescent"] is True
    assert closed["pending"]==0
    assert closed["ticks"]==5
    assert s.verify_receipts()


def test_batched_action_candidates_are_deferred_without_false_quiescence(tmp_path):
    stack,phys,s=runtime(tmp_path)
    for index in range(2):
        assert s.queue.push(CognitiveItem(
            id=f"thought-{index}",kind=ItemKind.THOUGHT,
            content={"step":"batched-review","stack_action_ids":[]},
            priority=0.8-index*0.1,depth=1,parent_id=f"query-{index}",
            created_tick=s.current_tick,
        ))

    first=s.tick(max_items=8)
    assert first["processed"]==2
    assert first["generated_actions"]==2
    assert first["deferred_actions"]==1
    assert first["execution"]["status"]=="EXECUTED"
    assert any(item["kind"]=="ACTION_CANDIDATE" for item in s.queue.pending_items())

    closed=s.run_until_quiescent(max_ticks=8,max_items=8)
    assert closed["quiescent"] is True
    with s._conn() as conn:
        results=conn.execute(
            "SELECT observation_event_id FROM capability_results ORDER BY id"
        ).fetchall()
    assert len(results)==2
    assert len({row["observation_event_id"] for row in results})==2
    assert all(row["observation_event_id"] for row in results)


def test_result_and_observation_insert_rollback_together(tmp_path):
    stack,phys,s=runtime(tmp_path)
    candidate={
        "capability":"memory.commit_reflection",
        "payload":{"text":"atomic observation test","item_id":"source"},
        "score":0.7,"source_item_id":"source","source_depth":1,
    }
    with mock.patch.object(
        s.queue,"_insert_with_conn",side_effect=RuntimeError("forced observation failure")
    ):
        try:
            s._execute([candidate])
        except RuntimeError as exc:
            assert "forced observation failure" in str(exc)
        else:
            raise AssertionError("observation persistence failure must fail closed")

    with s._conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM capability_results").fetchone()[0]==0
        assert conn.execute(
            "SELECT COUNT(*) FROM cognitive_queue WHERE kind=?",
            (ItemKind.OBSERVATION.value,),
        ).fetchone()[0]==0


def test_restart_recovers_legacy_result_observation_exactly_once(tmp_path):
    stack,phys,s=runtime(tmp_path)
    payload={
        "capability":"memory.commit_reflection","decision_status":"EXECUTED",
        "governance_mode":"GREEN","reasons":[],"receipt_hash":"receipt-1",
        "outcome":{"memory":{"id":1}},
    }
    with s._conn() as conn:
        conn.execute("""INSERT INTO capability_results
          (tick,capability,status,payload_json,receipt_hash,created_at)
          VALUES(?,?,?,?,?,?)""",
          (3,"memory.commit_reflection","EXECUTED",
           '{"capability":"memory.commit_reflection","decision_status":"EXECUTED",'
           '"governance_mode":"GREEN","outcome":{"memory":{"id":1}},'
           '"reasons":[],"receipt_hash":"receipt-1"}',
           "receipt-1","2026-09-19T00:00:00+00:00"))

    stack2=VictorCognitionStack(str(tmp_path/"victor_stack.db"))
    phys2=VictorPhysiologyRuntime(
        receipt_ledger=PhysiologyReceiptLedger(str(tmp_path/"physiology2.jsonl")),
        granted_authorities=("local_owner",),
    )
    recovered=CognitiveScheduler(stack2,phys2,tmp_path/"victor_stack.db")
    observations=[
        item for item in recovered.queue.pending_items()
        if item["kind"]==ItemKind.OBSERVATION.value
    ]
    assert len(observations)==1
    assert observations[0]["content"]["recovered"] is True

    stack3=VictorCognitionStack(str(tmp_path/"victor_stack.db"))
    phys3=VictorPhysiologyRuntime(
        receipt_ledger=PhysiologyReceiptLedger(str(tmp_path/"physiology3.jsonl")),
        granted_authorities=("local_owner",),
    )
    restarted=CognitiveScheduler(stack3,phys3,tmp_path/"victor_stack.db")
    observations=[
        item for item in restarted.queue.pending_items()
        if item["kind"]==ItemKind.OBSERVATION.value
    ]
    assert len(observations)==1
    with restarted._conn() as conn:
        row=conn.execute("SELECT observation_event_id FROM capability_results").fetchone()
    assert row["observation_event_id"]==observations[0]["id"]
