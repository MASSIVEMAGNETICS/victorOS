import json

from vos_core.windows_runtime import VictorWindowsRuntime


def test_restart_persists_human_stop_and_boot_count(tmp_path):
    first = VictorWindowsRuntime(str(tmp_path))
    assert first.status()["boot_count"] == 1
    first.set_human_stop(True)

    second = VictorWindowsRuntime(str(tmp_path))
    status = second.status()
    assert status["boot_count"] == 2
    assert status["human_stop"] is True
    assert status["governance_mode"] == "BLACK"


def test_human_stop_blocks_episode(tmp_path):
    runtime = VictorWindowsRuntime(str(tmp_path))
    runtime.set_human_stop(True)
    episode = runtime.process_episode("This must not execute.")
    assert episode["status"] == "REJECTED"
    assert "human_stop_active" in episode["reasons"]
    assert runtime.status()["episode_count"] == 1


def test_episode_creates_receipt_and_verifiable_chain(tmp_path):
    runtime = VictorWindowsRuntime(str(tmp_path))
    episode = runtime.process_episode("Observe the current local runtime state.")
    assert episode["status"] == "EXECUTED"
    assert episode["receipt_hash"] != "GENESIS"
    assert runtime.episodes.verify_integrity() is True
    assert runtime.receipts.verify_integrity() is True
    assert runtime.status()["episode_count"] == 1


def test_episode_tamper_forces_fail_closed_mode_on_restart(tmp_path):
    runtime = VictorWindowsRuntime(str(tmp_path))
    runtime.process_episode("Create an integrity test episode.")

    path = tmp_path / "state" / "windows_episodes.jsonl"
    rows = path.read_text(encoding="utf-8").splitlines()
    record = json.loads(rows[0])
    record["input"] = "tampered"
    rows[0] = json.dumps(record)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    restarted = VictorWindowsRuntime(str(tmp_path))
    status = restarted.status()
    assert status["episode_chain_ok"] is False
    assert status["startup_fault"] == "episode_ledger_integrity_failure"
    assert status["governance_mode"] == "BLACK"
