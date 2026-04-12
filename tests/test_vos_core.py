"""
VOS Core — Unit tests
Run: python -m pytest tests/ -v
"""
import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

from vos_core.metadata_processor import MetadataEngine
from vos_core.rollout_scheduler import RolloutScheduler
from vos_core.save3_trust import AuditLedger, SAVE3Trust
from vos_core.synthetic_core import (
    ContradictionResolver,
    FractalNode,
    PredictiveCoder,
    SymbolicRouter,
    SyntheticCognitiveCore,
)
from vos_core.version_engine import GodTierVersion


# ─────────────────────────── GodTierVersion ───────────────────────────

class TestGodTierVersion:
    def test_initial_state_written(self, tmp_path):
        v = GodTierVersion(str(tmp_path / ".vos_version.json"))
        assert v.version_string == "v0.1.0"

    def test_bump_patch(self, tmp_path):
        v = GodTierVersion(str(tmp_path / ".vos_version.json"))
        state = v.bump("patch", "test")
        assert state.patch == 1
        assert state.rollback_hash == "0.1.0"

    def test_bump_minor(self, tmp_path):
        v = GodTierVersion(str(tmp_path / ".vos_version.json"))
        state = v.bump("minor")
        assert state.minor == 2
        assert state.patch == 0

    def test_bump_major(self, tmp_path):
        v = GodTierVersion(str(tmp_path / ".vos_version.json"))
        state = v.bump("major")
        assert state.major == 1
        assert state.minor == 0
        assert state.patch == 0

    def test_rollback(self, tmp_path):
        v = GodTierVersion(str(tmp_path / ".vos_version.json"))
        v.bump("minor")
        restored = v.rollback()
        assert restored.major == 0
        assert restored.minor == 1

    def test_self_heals_on_corrupt_file(self, tmp_path):
        vf = tmp_path / ".vos_version.json"
        vf.write_text("NOT JSON AT ALL")
        v = GodTierVersion(str(vf))
        assert v.version_string == "v0.1.0"
        assert v.state.build_id == "self_healed"


# ─────────────────────────── AuditLedger / SAVE3Trust ─────────────────

class TestAuditLedger:
    def test_write_and_verify(self, tmp_path):
        ledger = AuditLedger(str(tmp_path / "audit.jsonl"))
        trust = SAVE3Trust(ledger, confidence_threshold=0.70)
        trust.evaluate("agent_a", "action_1", {"x": 1}, 0.90)
        trust.evaluate("agent_b", "action_2", {"y": 2}, 0.80)
        assert ledger.verify_integrity()

    def test_approved_above_threshold(self, tmp_path):
        ledger = AuditLedger(str(tmp_path / "audit.jsonl"))
        trust = SAVE3Trust(ledger, confidence_threshold=0.70)
        status = trust.evaluate("ag", "act", {"k": "v"}, 0.90)
        assert status == "approved"

    def test_quarantine_below_threshold(self, tmp_path):
        ledger = AuditLedger(str(tmp_path / "audit.jsonl"))
        trust = SAVE3Trust(ledger, confidence_threshold=0.70)
        status = trust.evaluate("ag", "act", {"k": "v"}, 0.50)
        assert status == "quarantined"

    def test_kill_switch_blocks_all(self, tmp_path):
        ledger = AuditLedger(str(tmp_path / "audit.jsonl"))
        trust = SAVE3Trust(ledger, confidence_threshold=0.70)
        trust.trigger_kill_switch(True)
        status = trust.evaluate("ag", "act", {"k": "v"}, 0.99)
        assert status == "killed"

    def test_handover_logged(self, tmp_path):
        ledger = AuditLedger(str(tmp_path / "audit.jsonl"))
        trust = SAVE3Trust(ledger)
        result = trust.multi_agent_handover("core_router", "synthetic_core", {"data": 1})
        assert result is True
        lines = ledger.log_path.read_text().strip().splitlines()
        assert any("handover_to_synthetic_core" in line for line in lines)


# ─────────────────────────── MetadataEngine ───────────────────────────

class TestMetadataEngine:
    def test_full_valid_input(self):
        engine = MetadataEngine()
        result = engine.parse_and_validate({
            "title": "EXIT VELOCITY",
            "artist": "iambandobandz",
            "genre": "Hip-Hop/Rap",
            "mood": "Gritty",
            "bpm": 140,
            "key": "C Minor",
        })
        assert result["valid"] is True
        assert result["bpm"] == 140
        assert result["isrc_stub"].startswith("US-VOS-")

    def test_genre_normalisation(self):
        engine = MetadataEngine()
        result = engine.parse_and_validate({
            "title": "T", "artist": "A", "genre": "rap",
            "mood": "M", "bpm": 120, "key": "D",
        })
        assert result["genre"] == "Hip-Hop/Rap"

    def test_missing_fields_get_defaults(self):
        engine = MetadataEngine()
        result = engine.parse_and_validate({})
        assert result["title"] == "Untitled_VOS_Track"
        assert result["bpm"] == 140

    def test_bpm_strips_non_digits(self):
        engine = MetadataEngine()
        result = engine.parse_and_validate({
            "title": "T", "artist": "A", "genre": "Trap",
            "mood": "M", "bpm": "~138 BPM~", "key": "F",
        })
        assert result["bpm"] == 138

    def test_export_json_is_valid(self):
        engine = MetadataEngine()
        meta = engine.parse_and_validate({
            "title": "T", "artist": "A", "genre": "Drill",
            "mood": "M", "bpm": 145, "key": "G",
        })
        parsed = json.loads(engine.export_json(meta))
        assert parsed["title"] == "T"

    def test_export_csv_two_rows(self):
        engine = MetadataEngine()
        meta = engine.parse_and_validate({
            "title": "T", "artist": "A", "genre": "R&B/Soul",
            "mood": "M", "bpm": 90, "key": "A",
        })
        csv = engine.export_csv(meta)
        rows = csv.strip().splitlines()
        assert len(rows) == 2


# ─────────────────────────── RolloutScheduler ─────────────────────────

class TestRolloutScheduler:
    def test_generates_schedule(self):
        sched = RolloutScheduler().generate("2026-05-01")
        assert len(sched) > 0

    def test_phases_present(self):
        sched = RolloutScheduler().generate("2026-05-01")
        phases = {s["phase"] for s in sched}
        assert phases == {"pre", "launch", "post"}

    def test_launch_tasks_high_priority(self):
        sched = RolloutScheduler().generate("2026-05-01")
        for item in sched:
            if item["phase"] == "launch":
                assert item["priority"] == "high"

    def test_days_are_sequential(self):
        sched = RolloutScheduler().generate("2026-05-01")
        days = [s["day"] for s in sched]
        assert days == list(range(1, len(days) + 1))

    def test_defaults_to_today(self):
        sched = RolloutScheduler().generate()
        assert len(sched) > 0


# ─────────────────────────── SyntheticCognitiveCore ───────────────────

class TestSyntheticCognitiveCore:
    def _make_core(self, tmp_path):
        ledger = AuditLedger(str(tmp_path / "audit.jsonl"))
        trust = SAVE3Trust(ledger, confidence_threshold=0.70)
        version = GodTierVersion(str(tmp_path / ".vos_version.json"))
        return SyntheticCognitiveCore(trust, ledger, version, str(tmp_path))

    def test_process_returns_expected_keys(self, tmp_path):
        core = self._make_core(tmp_path)
        out = core.process("write a hook for my trap track")
        for key in ("intent", "confidence", "trust_status", "processing_ms", "memory_slots"):
            assert key in out

    def test_processing_is_fast(self, tmp_path):
        core = self._make_core(tmp_path)
        out = core.process("metadata for hip-hop artist")
        assert out["processing_ms"] < 500  # should be well under 500ms on CPU

    def test_memory_accumulates(self, tmp_path):
        core = self._make_core(tmp_path)
        for i in range(5):
            core.process(f"prompt {i}")
        assert core.process("final")["memory_slots"] == 6

    def test_memory_cap_enforced(self, tmp_path):
        core = self._make_core(tmp_path)
        for i in range(20):
            core.process(f"prompt {i}")
        assert len(core.memory_bank) <= core.memory_capacity

    def test_hard_reset_clears_state(self, tmp_path):
        core = self._make_core(tmp_path)
        core.process("some prompt")
        core.hard_reset()
        assert len(core.memory_bank) == 0

    def test_get_synthesis_prompt_valid_domains(self, tmp_path):
        core = self._make_core(tmp_path)
        for domain in ("metadata", "rollout", "creative"):
            out = core.get_synthesis_prompt({"intent": domain})
            assert len(out) > 10

    def test_get_synthesis_prompt_unknown_domain_falls_back(self, tmp_path):
        core = self._make_core(tmp_path)
        out = core.get_synthesis_prompt({"intent": "unknown_domain"})
        assert "syllables" in out  # falls back to creative template

    def test_state_file_created(self, tmp_path):
        self._make_core(tmp_path)
        assert (tmp_path / ".synthetic_state.json").exists()

    def test_state_file_self_heals_on_corrupt(self, tmp_path):
        ledger = AuditLedger(str(tmp_path / "audit.jsonl"))
        trust = SAVE3Trust(ledger)
        version = GodTierVersion(str(tmp_path / ".vos_version.json"))
        sf = tmp_path / ".synthetic_state.json"
        sf.write_text("CORRUPTED")
        core = SyntheticCognitiveCore(trust, ledger, version, str(tmp_path))
        assert sf.exists()
        assert json.loads(sf.read_text())["memory_len"] == 0


# ─────────────────────────── Sub-components ───────────────────────────

class TestPredictiveCoder:
    def test_predict_returns_correct_shape(self):
        pc = PredictiveCoder(dim=64)
        ctx = np.random.randn(64).astype(np.float32)
        pred = pc.predict(ctx)
        assert pred.shape == (64,)

    def test_update_returns_scalar_error(self):
        pc = PredictiveCoder(dim=64)
        actual = np.ones(64, dtype=np.float32)
        predicted = np.zeros(64, dtype=np.float32)
        err = pc.update(actual, predicted)
        assert isinstance(err, float)
        assert err > 0


class TestSymbolicRouter:
    def test_routes_metadata_keywords(self):
        r = SymbolicRouter()
        result = r.route_intent("title artist genre bpm key mood")
        assert result["primary"] == "metadata"
        assert result["confidence"] > 0

    def test_routes_creative_keywords(self):
        r = SymbolicRouter()
        result = r.route_intent("write a hook lyric caption pitch")
        assert result["primary"] == "creative"

    def test_returns_scores_for_all_domains(self):
        r = SymbolicRouter()
        result = r.route_intent("anything")
        assert set(result["scores"].keys()) == {"metadata", "rollout", "creative"}


class TestContradictionResolver:
    def test_coherent_when_high_uniform_confidence(self):
        cr = ContradictionResolver(threshold=0.65)
        outputs = [{"confidence": 0.9}, {"confidence": 0.85}, {"confidence": 0.88}]
        result = cr.evaluate(outputs)
        assert result["status"] == "coherent"
        assert result["resolution"] == "accept"

    def test_contradiction_on_high_variance(self):
        cr = ContradictionResolver(threshold=0.65)
        outputs = [{"confidence": 0.0}, {"confidence": 1.0}, {"confidence": 0.5}]
        result = cr.evaluate(outputs)
        assert result["status"] == "contradiction_detected"

    def test_empty_outputs_flagged(self):
        cr = ContradictionResolver()
        result = cr.evaluate([])
        assert result["flagged"] is True
        assert result["status"] == "empty"


class TestFractalNode:
    def test_attend_returns_activation_and_vector(self):
        node = FractalNode(scale=1, weights=np.random.randn(64) * 0.2)
        inp = np.random.randn(64).astype(np.float32)
        act, vec = node.attend(inp)
        assert 0.0 <= act <= 1.0
        assert vec.shape == (64,)

    def test_compress_returns_dict(self):
        node = FractalNode(scale=2, weights=np.ones(64) * 0.1)
        d = node.compress()
        assert "scale" in d and "activation" in d and "norm" in d
