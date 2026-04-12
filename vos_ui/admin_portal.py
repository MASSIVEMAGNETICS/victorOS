"""
VOS Admin Portal — Massive Magnetics Operator Interface
Version: 0.1.0 | SAVE3: Active | Cyberpunk Dark Theme
Role: System admin, project routing, trust oversight, MRR tracking
"""
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import psutil
import requests
import streamlit as st
from datetime import datetime

from vos_core.core_router import CORERouter

logging.basicConfig(level=logging.INFO, format="[ADMIN] %(message)s")
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="MM ADMIN | VOS v0.1.0", page_icon="🛡️", layout="wide"
)

# CYBERPUNK ENTERPRISE THEME
st.markdown(
    """
<style>
    .stApp {background-color: #0b0b10; color: #d0d0d0; font-family: 'Consolas', monospace;}
    h1, h2, h3, h4 {color: #00ffcc; text-shadow: 0 0 6px #00ffcc60; margin-top: 1rem;}
    .sidebar .sidebar-content {background-color: #0a0a0e; color: #00ffcc;}
    .stButton>button {background: #111; color: #00ffcc; border: 1px solid #00ffcc40; font-family: 'Consolas', monospace;}
    .stButton>button:hover {background: #00ffcc; color: #000;}
    .stMetric {background: #0f0f14; border: 1px solid #00ffcc30; border-radius: 4px; padding: 0.5rem;}
    .status-dot {height: 10px; width: 10px; border-radius: 50%; display: inline-block; margin-right: 6px;}
    .green {background-color: #00ff88;}
    .yellow {background-color: #ffcc00;}
    .red {background-color: #ff3366;}
    table {width: 100%; border-collapse: collapse; background: #0f0f14;}
    th, td {border: 1px solid #00ffcc30; padding: 8px; text-align: left;}
    th {color: #00ffcc;}
</style>
""",
    unsafe_allow_html=True,
)

# INIT CORE COMPONENTS
router = CORERouter()
audit = router.audit
trust = router.trust
version = router.version

# SESSION STATE INIT
if "kill_active" not in st.session_state:
    st.session_state.kill_active = False
if "quarantine_active" not in st.session_state:
    st.session_state.quarantine_active = False

# SIDEBAR NAV
st.sidebar.title("🛡️ MASSIVE MAGNETICS")
st.sidebar.caption(f"VOS {version.version_string} | Admin Portal")
nav = st.sidebar.radio(
    "Module",
    ["Dashboard", "System Health", "Projects", "Users & Keys", "Analytics", "Settings"],
)

# ================= DASHBOARD =================
if nav == "Dashboard":
    st.title("⚡ Operator Dashboard")
    col1, col2, col3, col4 = st.columns(4)

    audit_count = 0
    if audit.log_path.exists():
        with open(audit.log_path, encoding="utf-8") as f:
            audit_count = sum(1 for line in f if line.strip())

    col1.metric(
        "System Status",
        "ONLINE" if not st.session_state.kill_active else "KILLED",
        delta=version.version_string,
    )
    col2.metric("Trust Threshold", f"{trust.threshold * 100:.0f}%")
    col3.metric("Audit Entries", audit_count)
    col4.metric(
        "Active Mode",
        "QUARANTINE" if st.session_state.quarantine_active else "NORMAL",
    )

    st.subheader("📜 Recent Audit Log")
    if audit.log_path.exists():
        lines = audit.log_path.read_text(encoding="utf-8").strip().splitlines()[-5:]
        for line in lines:
            try:
                d = json.loads(line)
                st.markdown(
                    f"`{d['timestamp']}` | `{d['agent_id']}` → `{d['action']}` | "
                    f"**{d['status']}** | conf: `{d['confidence']:.2f}`"
                )
            except Exception:
                st.markdown("`[CORRUPTED ENTRY]`")
    else:
        st.info("No audit entries yet. Run a core process to initialize.")

# ================= SYSTEM HEALTH =================
elif nav == "System Health":
    st.title("🔍 System Health & Oversight")
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    st.subheader("Host Metrics")
    c1, c2, c3 = st.columns(3)
    c1.metric("CPU Load", f"{cpu}%", delta="⚙️" if cpu < 80 else "⚠️ HIGH")
    c2.metric(
        "RAM Usage",
        f"{mem.percent}%",
        delta=f"{mem.used / 1024**3:.1f}GB / {mem.total / 1024**3:.1f}GB",
    )
    c3.metric("Disk Free", f"{disk.free / 1024**3:.1f}GB", delta=f"{disk.percent}% used")

    st.subheader("AI Runtime Status")
    ollama_url = "http://localhost:11434/api/tags"
    try:
        resp = requests.get(ollama_url, timeout=3)
        status = "🟢 ONLINE" if resp.status_code == 200 else "🔴 OFFLINE"
    except Exception:
        status = "🔴 OFFLINE"
    st.markdown(f"**Ollama Bridge:** {status}")

    st.subheader("Constitutional Controls")
    if st.button(
        "🛑 ARM KILL-SWITCH", type="primary", disabled=st.session_state.kill_active
    ):
        trust.trigger_kill_switch(True)
        st.session_state.kill_active = True
        st.warning("KILL-SWITCH ARMED. All autonomous actions halted.")
    if st.button("✅ DISENGAGE KILL-SWITCH", disabled=not st.session_state.kill_active):
        trust.trigger_kill_switch(False)
        st.session_state.kill_active = False
        st.success("Kill-switch disengaged.")

    if st.button(
        "⚠️ ENABLE QUARANTINE",
        type="secondary",
        disabled=st.session_state.quarantine_active,
    ):
        trust.trigger_quarantine(True)
        st.session_state.quarantine_active = True
        st.info("Quarantine enabled. Low-confidence outputs routed to manual review.")
    if st.button(
        "🟢 DISABLE QUARANTINE", disabled=not st.session_state.quarantine_active
    ):
        trust.trigger_quarantine(False)
        st.session_state.quarantine_active = False
        st.success("Quarantine disabled.")

# ================= PROJECTS =================
elif nav == "Projects":
    st.title("📁 Active Creator Projects")
    st.info(
        "Projects populate as creators run VOS core processes. "
        "Audit ledger tracks all state changes."
    )
    st.dataframe(
        {
            "Project ID": ["P-001", "P-002", "P-003"],
            "Artist": ["iambandobandz", "Creator_Alpha", "Indie_West"],
            "Status": ["Processing", "Rollout Active", "Queued"],
            "Trust Score": ["0.88", "0.74", "0.91"],
            "Last Updated": [datetime.now().strftime("%Y-%m-%d %H:%M")] * 3,
        },
        use_container_width=True,
    )

# ================= USERS & KEYS =================
elif nav == "Users & Keys":
    st.title("👤 Users & API Routing")
    st.caption(
        "Role-based access control. Keys route to local endpoints. "
        "Swap to Postgres/Supabase in v0.5.0."
    )
    new_user = st.text_input("Add Operator / Creator Handle")
    role = st.selectbox("Assign Role", ["admin", "creator", "viewer"])
    if st.button("Generate Local Key"):
        key = f"mm-{hash(new_user + str(time.time())):x}"[:24]
        st.success(f"🔑 Local Key Generated: `{key}` (Role: {role})")
        trust.evaluate(
            "admin_portal",
            "key_generated",
            {"user": new_user, "role": role},
            0.95,
        )

# ================= ANALYTICS =================
elif nav == "Analytics":
    st.title("📈 Operator Analytics (MRR & Conversion)")
    st.caption(
        "Placeholder structure wired for real DB ingestion. "
        "Swap in Stripe/Supabase at Phase 2."
    )
    col1, col2, col3 = st.columns(3)
    col1.metric("Monthly Active Users", "142")
    col2.metric("MRR Run-Rate", "$4,260")
    col3.metric("Conversion Rate", "6.8%")

    st.subheader("Funnel Tracking")
    st.bar_chart(
        {"Visitors": [5000], "Signups": [320], "Free Tier": [280], "Paid Tier": [40]}
    )

# ================= SETTINGS =================
elif nav == "Settings":
    st.title("⚙️ System Settings & Version Control")
    st.subheader(f"Current Build: `{version.version_string}`")

    st.subheader("God-Tier Version Control")
    v_type = st.selectbox("Bump Version", ["patch", "minor", "major"])
    if st.button("Apply Version Bump"):
        state = version.bump(v_type, f"admin_portal_{v_type}")
        st.success(
            f"Updated to {version.version_string} | Rollback target: {state.rollback_hash}"
        )
        trust.evaluate(
            "admin_portal",
            "version_bump",
            {"type": v_type, "new": version.version_string},
            0.99,
        )

    st.subheader("Audit Ledger Integrity")
    if st.button("Verify Chain"):
        valid = audit.verify_integrity()
        st.success(
            "✅ Ledger intact." if valid else "❌ Ledger corrupted. Manual review required."
        )

    st.subheader("Export Configuration")
    if st.button("Download Full System State"):
        payload = {
            "version": version.version_string,
            "threshold": trust.threshold,
            "kill_switch": st.session_state.kill_active,
            "quarantine": st.session_state.quarantine_active,
            "timestamp": datetime.utcnow().isoformat(),
        }
        st.json(payload)
