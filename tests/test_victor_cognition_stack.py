#!/usr/bin/env python3
# =============================================================================
# SAVE3 STANDARD
# artifact: victor_cognition_stack/test_victor_stack.py
# version: 1.0.0
# purpose: drift gate. zero third-party deps. zero LLMs. stdlib unittest only.
# =============================================================================

import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "victor_cognition_stack", HERE / "victor_cognition_stack.py"
)
STACK_MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STACK_MOD)
VictorCognitionStack = STACK_MOD.VictorCognitionStack

STDLIB_ALLOWED = {
    "argparse", "hashlib", "json", "re", "sqlite3", "datetime", "pathlib"
}


class TestVictorCognitionStack(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "t.db"
        self.stack = VictorCognitionStack(db_path=self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def test_00_zero_third_party_imports(self):
        src = (HERE / "victor_cognition_stack.py").read_text(encoding="utf-8")
        mods = set()
        for m in re.finditer(r"^\s*import\s+([a-zA-Z_][a-zA-Z0-9_]*)", src, re.M):
            mods.add(m.group(1))
        for m in re.finditer(r"^\s*from\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+import", src, re.M):
            mods.add(m.group(1))
        self.assertTrue(
            mods <= STDLIB_ALLOWED,
            f"NON-STDLIB IMPORT DETECTED: {mods - STDLIB_ALLOWED}"
        )

    def test_01_memory_dedup_and_search(self):
        r1 = self.stack.remember("Victor local memory weld test line.")
        r2 = self.stack.remember("Victor local memory weld test line.")
        self.assertTrue(r1["created"])
        self.assertFalse(r2["created"])
        self.assertEqual(r1["memory_id"], r2["memory_id"])
        hits = self.stack.search("weld test")
        self.assertTrue(any(h["id"] == r1["memory_id"] for h in hits))

    def test_02_cycle_activates_goals_and_plans(self):
        rep = self.stack.cycle(
            "Victor needs local memory organs and a membrane for sovereign cognition."
        )
        self.assertTrue(rep["steps"]["sensory"]["created"])
        keys = {g["goal_key"] for g in self.stack.goals()}
        self.assertTrue({"advance_victor_memory", "build_cognitive_organs"} <= keys)
        self.assertGreaterEqual(len(self.stack.plans()), 1)
        self.assertGreaterEqual(len(self.stack.actions()), 1)

    def test_03_provenance_layers_separate_observed_from_inferred(self):
        self.stack.cycle("Victor memory provenance check.")
        conn = self.stack._conn()
        layers = {
            r["layer"]
            for r in conn.execute("SELECT DISTINCT layer FROM memories").fetchall()
        }
        conn.close()
        self.assertIn("input", layers)
        self.assertTrue(layers & {"fact", "derived"})

    def test_04_membrane_emergence_crystallizes(self):
        self.stack.cycle("Victor membrane emergence weld test.")
        cryst = self.stack.crystallizations()
        self.assertGreaterEqual(len(cryst), 1)
        organs = json.loads(cryst[0]["organs_json"])
        self.assertGreaterEqual(len(organs), 3)

    def test_05_executive_gate_requires_approval(self):
        self.stack.cycle("Victor memory executive gate test.")
        actions = self.stack.actions()
        self.assertTrue(all(a["status"] == "proposed" for a in actions))
        target = actions[0]["id"]
        self.assertTrue(self.stack.approve_action(target))
        after = {a["id"]: a["status"] for a in self.stack.actions()}
        self.assertEqual(after[target], "approved")
        others = [s for i, s in after.items() if i != target]
        self.assertTrue(all(s == "proposed" for s in others))

    def test_06_surface_account_lifecycle(self):
        acc = self.stack.register_account(
            "openai_web", "Bando ChatGPT Web", "web_bridge", {"host": "chatgpt.com"}
        )
        aid = self.stack.queue_surface_action(acc, "inject_text", {"text": "bridge test"})
        with self.assertRaises(ValueError):
            self.stack.queue_surface_action(acc, "autonomous_hack", {})
        with self.assertRaises(ValueError):
            self.stack.register_account("x", "y", "cloud_magic")
        self.assertTrue(self.stack.approve_action(aid))
        self.stack.record_surface_result(aid, "success", {"injected": True})
        final = {a["id"]: a["status"] for a in self.stack.actions()}[aid]
        self.assertEqual(final, "executed_by_human")

    def test_07_persistence_across_reopen(self):
        self.stack.remember("persistence weld check bando.")
        reopened = VictorCognitionStack(db_path=self.db)
        hits = reopened.search("persistence weld check")
        self.assertGreaterEqual(len(hits), 1)

    def test_08_audit_ledger_monotonic(self):
        self.stack.cycle("audit monotonic check one.")
        self.stack.cycle("audit monotonic check two.")
        rows = self.stack.audit(200, newest_first=False)
        self.assertGreater(len(rows), 0)
        ticks = [r["tick"] for r in rows]
        self.assertEqual(ticks, sorted(ticks))


    def test_09_tick_persists_across_reopen(self):
        self.stack.cycle("Victor memory tick persistence.")
        tick=self.stack.tick
        reopened=VictorCognitionStack(str(self.db_path))
        self.assertEqual(reopened.tick,tick)

    def test_10_external_tick_cannot_move_backward(self):
        self.stack.cycle("Victor memory external clock.", tick=7)
        self.assertEqual(self.stack.tick,7)
        with self.assertRaises(ValueError):
            self.stack.cycle("backward", tick=6)

if __name__ == "__main__":
    unittest.main(verbosity=2)
