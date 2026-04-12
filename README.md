# ⚡ VictorOS (VOS) v0.1.0

**Local-first AI runtime for creators. Massive Magnetics × BandoBandz.**

> Solve the indie artist paralysis problem — promo, metadata, rollout, ad hooks — without touching the cloud.  
> Every feature is a first-class App running inside the VOS shell.

---

## What It Is

VOS ingests raw creative assets (lyrics, stems, notes, hooks) and outputs:

- **Structured DSP metadata** — DistroKid / TuneCore / CD Baby ready
- **30-day rollout calendars** — pre-launch, launch, post-launch, priority-scored
- **Ad-creative packs** — TikTok hooks, IG captions, press pitches
- **SAVE3 audit ledger** — every action is logged, hashed, verified

Runs on **Windows 10**. No cloud dependency. No API keys. No stochastic parrots.

---

## Architecture

```
VOS/
├── vos_core/              # Core runtime (no UI dependency)
│   ├── version_engine.py  # God-Tier versioning — self-healing, rollback-safe
│   ├── save3_trust.py     # Bayesian trust scoring + immutable audit ledger
│   ├── metadata_processor.py  # DSP metadata normalisation + JSON/CSV export
│   ├── rollout_scheduler.py   # 30-day priority-scored rollout calendar
│   ├── synthetic_core.py  # Synthetic cognitive core (replaces LLM/Ollama)
│   └── core_router.py     # Central dispatch — wires all subsystems together
│
├── vos_apps/              # App Registry — every feature is a discrete App
│   ├── meta_forge.py      # 🎵 MetaForge — asset ingestion + metadata export
│   ├── rollout_engine.py  # 📅 RolloutEngine — rollout calendar generator
│   ├── creative_core.py   # 🔌 CreativeCore — ad hooks, captions, pitches
│   ├── synth_mind.py      # 🧠 SynthMind — synthetic core live monitor
│   ├── audit_vault.py     # 📜 AuditVault — immutable ledger viewer
│   └── admin_portal_app.py # 🛡️ AdminPortal — kill-switch, health, RBAC
│
├── vos_ui/
│   ├── launcher.py        # ⚡ VOS OS Shell — unified home screen (START HERE)
│   ├── dashboard.py       # Creator dashboard (standalone)
│   └── admin_portal.py    # Operator portal (standalone)
│
├── main.py                # CLI entry point
├── requirements.txt
└── setup_windows.bat      # Windows 10 one-click setup + launch
```

---

## Apps

| App | Category | What it does |
|-----|----------|--------------|
| 🎵 **MetaForge** | Creator | Ingest raw assets → DSP-ready metadata (JSON + CSV export) |
| 📅 **RolloutEngine** | Creator | Generate 30-day priority rollout calendars (JSON export) |
| 🔌 **CreativeCore** | Creator | Synthetic-core ad hooks, IG captions, press pitches |
| 🧠 **SynthMind** | System | Live synthetic cognitive core monitor + hard reset |
| 📜 **AuditVault** | System | Browse, filter, and verify the immutable SAVE3 audit ledger |
| 🛡️ **AdminPortal** | System | Kill-switch, quarantine, system health, RBAC, version control |

---

## Synthetic Cognitive Core

The LLM/Ollama bridge has been replaced with a **local synthetic cognitive loop**:

- **Predictive Coding** — top-down expectation vs. bottom-up signal; minimises prediction error
- **Fractal Attention Mesh** — 3-scale hierarchical routing; activations compress to fixed vectors
- **Symbolic Router** — deterministic intent parsing; zero hallucination
- **Contradiction Resolver** — multi-path confidence voting; SAVE3 quarantines low-trust states
- **Memory Bank** — fixed-slot compression (12 slots); auto-purges oldest

~0.5–2ms per cycle on CPU. Zero external API calls.

---

## Quickstart

### Windows 10 (GUI)
```bat
setup_windows.bat
# Choose option 1: VictorOS Shell
# Open http://localhost:8500
```

### Any platform (GUI)
```bash
pip install -r requirements.txt
streamlit run vos_ui/launcher.py --server.port 8500
```

### CLI
```bash
pip install -r requirements.txt
python main.py --title "EXIT VELOCITY" --artist "iambandobandz" --genre "Hip-Hop/Rap" --mood "Gritty" --bpm 140 --key "C Minor" --no-ai
```

---

## Ports

| Interface | Port | Command |
|-----------|------|---------|
| **VOS Shell** (all apps) | 8500 | `streamlit run vos_ui/launcher.py` |
| Creator Dashboard | 8501 | `streamlit run vos_ui/dashboard.py` |
| Admin Portal | 8502 | `streamlit run vos_ui/admin_portal.py` |

---

## Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

41 tests covering: `GodTierVersion`, `SAVE3Trust`, `AuditLedger`, `MetadataEngine`, `RolloutScheduler`, `SyntheticCognitiveCore`, `PredictiveCoder`, `SymbolicRouter`, `ContradictionResolver`, `FractalNode`.

---

## SAVE3 Audit Ledger

Every action evaluated by the trust engine is written to `vos_audit.jsonl`:

```jsonl
{"timestamp":"...","agent_id":"core_router","action":"process_complete","confidence":0.88,"status":"approved","payload_hash":"..."}
```

Check it: **AuditVault app → Verify Integrity button**.

---

## Roadmap

| Version | Focus |
|---------|-------|
| v0.1.0 | ✅ Core runtime, 6 apps, VOS shell, synthetic core, SAVE3 |
| v0.5.0 | Stripe/MRR engine, Supabase integration, ad-spend simulation |
| v1.0.0 | GPU tensor acceleration, long-term memory pipeline, multi-node sync |
