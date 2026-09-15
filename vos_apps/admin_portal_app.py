"""
AdminPortal App — System health, RBAC, kill-switch, quarantine, version control.
Runs as a VOS app inside the launcher (shares the router singleton).
"""
import json
import time
import logging

import psutil
import requests
import streamlit as st
from datetime import datetime

logger = logging.getLogger(__name__)

APP_META = {
    "id": "admin_portal",
    "name": "AdminPortal",
    "icon": "🛡️",
    "tagline": "Operator controls · system health · version management",
    "category": "system",
}


def render(router) -> None:
    st.header("🛡️ AdminPortal")
    st.caption("Massive Magnetics operator interface. Kill-switch, quarantine, version control, system health.")

    trust = router.trust
    version = router.version
    audit = router.audit

    # Session state for toggle controls
    if "kill_active" not in st.session_state:
        st.session_state.kill_active = False
    if "quarantine_active" not in st.session_state:
        st.session_state.quarantine_active = False

    tab_health, tab_controls, tab_users, tab_version = st.tabs(
        ["System Health", "Constitutional Controls", "Users & Keys", "Version Control"]
    )

    # ── System Health ─────────────────────────────────────────────
    with tab_health:
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        c1, c2, c3 = st.columns(3)
        c1.metric("CPU Load", f"{cpu}%", delta="⚙️" if cpu < 80 else "⚠️ HIGH")
        c2.metric("RAM", f"{mem.percent}%",
                  delta=f"{mem.used/1024**3:.1f} / {mem.total/1024**3:.1f} GB")
        c3.metric("Disk Free", f"{disk.free/1024**3:.1f} GB",
                  delta=f"{disk.percent}% used")

        st.divider()
        ollama_status = "🔴 OFFLINE"
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=3)
            if r.status_code == 200:
                ollama_status = "🟢 ONLINE"
        except Exception as e:
            logger.warning(f"Ollama bridge check failed: {e}. Operating in local synthetic mode.")
        st.markdown(f"**Ollama Bridge:** {ollama_status} *(optional — synthetic core is active)*")

        audit_count = 0
        if audit.log_path.exists():
            with open(audit.log_path, encoding="utf-8") as f:
                audit_count = sum(1 for line in f if line.strip())
        st.markdown(f"**Audit Entries:** `{audit_count}` · **Trust Threshold:** `{trust.threshold:.0%}`")

    # ── Constitutional Controls ───────────────────────────────────
    with tab_controls:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Kill-Switch")
            if not st.session_state.kill_active:
                if st.button("🛑 ARM KILL-SWITCH", type="primary"):
                    trust.trigger_kill_switch(True)
                    st.session_state.kill_active = True
                    st.warning("KILL-SWITCH ARMED. All autonomous actions halted.")
            else:
                if st.button("✅ DISENGAGE KILL-SWITCH"):
                    trust.trigger_kill_switch(False)
                    st.session_state.kill_active = False
                    st.success("Kill-switch disengaged.")
            status = "🔴 ARMED" if st.session_state.kill_active else "🟢 SAFE"
            st.markdown(f"Status: **{status}**")

        with col2:
            st.subheader("Quarantine")
            if not st.session_state.quarantine_active:
                if st.button("⚠️ ENABLE QUARANTINE", type="secondary"):
                    trust.trigger_quarantine(True)
                    st.session_state.quarantine_active = True
                    st.info("Quarantine enabled. Low-confidence outputs held for review.")
            else:
                if st.button("🟢 DISABLE QUARANTINE"):
                    trust.trigger_quarantine(False)
                    st.session_state.quarantine_active = False
                    st.success("Quarantine disabled.")
            q_status = "🟡 ACTIVE" if st.session_state.quarantine_active else "🟢 OFF"
            st.markdown(f"Status: **{q_status}**")

        st.divider()
        st.subheader("Audit Ledger Integrity")
        if st.button("🔐 Verify Chain"):
            valid = audit.verify_integrity()
            (st.success if valid else st.error)(
                "✅ Ledger intact." if valid else "❌ Corruption detected. Manual review required."
            )

    # ── Users & Keys ─────────────────────────────────────────────
    with tab_users:
        st.caption("Local RBAC. Swap to Supabase/Postgres in v0.5.0.")
        new_user = st.text_input("Operator / Creator Handle")
        role = st.selectbox("Role", ["admin", "creator", "viewer"])
        if st.button("Generate Local Key"):
            key = f"mm-{hash(new_user + str(time.time())):x}"[:24]
            st.success(f"🔑 `{key}` (Role: {role})")
            trust.evaluate("admin_portal", "key_generated",
                           {"user": new_user, "role": role}, 0.95)

    # ── Version Control ───────────────────────────────────────────
    with tab_version:
        st.markdown(f"**Current build:** `{version.version_string}`")
        st.markdown(f"**Rollback target:** `{version.state.rollback_hash or 'none'}`")
        v_type = st.selectbox("Bump type", ["patch", "minor", "major"])
        if st.button("Apply Version Bump"):
            state = version.bump(v_type, "admin_portal")
            st.success(f"Bumped → `{version.version_string}` | rollback: `{state.rollback_hash}`")
            trust.evaluate("admin_portal", "version_bump",
                           {"type": v_type, "new": version.version_string}, 0.99)
        if version.state.rollback_hash and version.state.rollback_hash != "none":
            if st.button("↩️ Rollback"):
                restored = version.rollback()
                st.info(f"Rolled back to `{version.version_string}`")

        st.divider()
        st.subheader("System State Snapshot")
        if st.button("Export State"):
            payload = {
                "version": version.version_string,
                "threshold": trust.threshold,
                "kill_switch": st.session_state.kill_active,
                "quarantine": st.session_state.quarantine_active,
                "timestamp": datetime.utcnow().isoformat(),
            }
            st.json(payload)
