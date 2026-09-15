import json
import pytest

from vos_core.windows_runtime import RuntimeAlreadyActiveError, VictorWindowsRuntime

def test_restart_persists_human_stop_and_boot_count(tmp_path):
    first=VictorWindowsRuntime(str(tmp_path))
    assert first.status()["boot_count"]==1
    first.set_human_stop(True)
    first.close()
    second=VictorWindowsRuntime(str(tmp_path))
    assert second.status()["boot_count"]==2
    assert second.status()["human_stop"] is True
    assert second.status()["governance_mode"]=="BLACK"
    second.close()

def test_unfinished_thought_survives_windows_restart(tmp_path):
    first=VictorWindowsRuntime(str(tmp_path))
    ep=first.process_episode("Victor memory unfinished thought test.")
    assert ep["status"]=="EXECUTED"
    assert first.status()["cognitive_queue_pending"]==1
    tick=first.status()["scheduler_tick"]
    first.close()
    second=VictorWindowsRuntime(str(tmp_path))
    assert second.status()["cognitive_queue_pending"]==1
    assert second.status()["scheduler_tick"]==tick
    assert second.advance_cognition(1)[0]["processed"]==1
    second.close()

def test_episode_and_scheduler_receipts_verify(tmp_path):
    r=VictorWindowsRuntime(str(tmp_path))
    r.process_episode("Victor memory receipt continuity.")
    r.advance_cognition(1)
    assert r.episodes.verify_integrity()
    assert r.receipts.verify_integrity()
    assert r.scheduler.verify_receipts()
    r.close()

def test_second_live_runtime_fails_closed_without_stealing_processing_work(tmp_path):
    first=VictorWindowsRuntime(str(tmp_path))
    first.scheduler.publish_query("Claim this item exactly once.")
    claimed=first.scheduler.queue.pop_budgeted(
        first.scheduler.current_tick, max_items=1
    )
    assert len(claimed)==1
    assert first.scheduler.queue.pending_count()==0

    with pytest.raises(RuntimeAlreadyActiveError, match="already owned"):
        VictorWindowsRuntime(str(tmp_path))

    # The failed second boot must not run scheduler crash recovery against the
    # still-live owner and therefore must not requeue its PROCESSING item.
    assert first.scheduler.queue.pending_count()==0

    first.close()

    # Once the owner is gone, a new runtime may acquire the lock. Its normal
    # startup recovery can now safely recover the abandoned PROCESSING item.
    recovered=VictorWindowsRuntime(str(tmp_path))
    assert recovered.scheduler.queue.pending_count()==1
    assert recovered.scheduler.verify_receipts()
    recovered.close()

def test_episode_tamper_forces_fail_closed_mode_on_restart(tmp_path):
    r=VictorWindowsRuntime(str(tmp_path))
    r.process_episode("Create an integrity test episode.")
    path=tmp_path/"state"/"windows_episodes.jsonl"
    r.close()
    rows=path.read_text().splitlines()
    rec=json.loads(rows[0]); rec["input"]="tampered"; rows[0]=json.dumps(rec)
    path.write_text("\n".join(rows)+"\n")
    restarted=VictorWindowsRuntime(str(tmp_path))
    status=restarted.status()
    assert status["episode_chain_ok"] is False
    assert status["startup_fault"]=="episode_ledger_integrity_failure"
    assert status["governance_mode"]=="BLACK"
    restarted.close()
