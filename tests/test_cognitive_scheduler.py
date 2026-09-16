from vos_core.cognitive_scheduler import CognitiveScheduler
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
    assert len(pending)==1
    assert pending[0]["kind"]=="OBSERVATION"
    assert pending[0]["content"]["receipt_hash"]==executed["receipt_hash"]
    closed=s.run_until_quiescent(max_ticks=4,max_items=1)
    assert closed["quiescent"] is True
    assert closed["pending"]==0
    assert closed["ticks"]==2
    assert s.verify_receipts()
