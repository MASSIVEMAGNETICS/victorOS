"""
AuditVault — Immutable SAVE3 audit ledger viewer with integrity verification.
"""
import json

import streamlit as st

APP_META = {
    "id": "audit_vault",
    "name": "AuditVault",
    "icon": "📜",
    "tagline": "Browse and verify the immutable SAVE3 audit ledger",
    "category": "system",
}

_STATUS_COLOR = {
    "approved": "🟢",
    "quarantined": "🟡",
    "killed": "🔴",
}


def render(router) -> None:
    st.header("📜 AuditVault")
    st.caption(
        "Every action evaluated by SAVE3 is written here. "
        "Immutable. Hash-verified. Tamper-evident."
    )

    ledger = router.audit

    # ── Integrity check ────────────────────────────────────────────
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("🔐 Verify Integrity"):
            valid = ledger.verify_integrity()
            if valid:
                st.success("✅ Ledger intact — no duplicates detected.")
            else:
                st.error("❌ Integrity check failed. Manual review required.")

    # ── Entry count ───────────────────────────────────────────────
    entries = []
    if ledger.log_path.exists():
        for line in ledger.log_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except Exception:
                entries.append({"raw": line, "status": "corrupted"})

    with col2:
        st.metric("Total Entries", len(entries))

    if not entries:
        st.info("No audit entries yet. Run any VOS app to initialise the ledger.")
        return

    # ── Filters ───────────────────────────────────────────────────
    st.divider()
    fc1, fc2 = st.columns(2)
    agents = sorted({e.get("agent_id", "?") for e in entries if "agent_id" in e})
    statuses = sorted({e.get("status", "?") for e in entries if "status" in e})
    agent_filter = fc1.multiselect("Filter by agent", agents, default=agents)
    status_filter = fc2.multiselect("Filter by status", statuses, default=statuses)

    filtered = [
        e for e in entries
        if e.get("agent_id") in agent_filter and e.get("status") in status_filter
    ]

    st.caption(f"Showing {len(filtered)} of {len(entries)} entries (newest first)")

    # ── Entry list ────────────────────────────────────────────────
    for entry in reversed(filtered[-200:]):  # cap display at 200
        if "agent_id" not in entry:
            st.code(entry.get("raw", str(entry)), language="text")
            continue
        dot = _STATUS_COLOR.get(entry["status"], "⚪")
        conf = entry.get("confidence", 0)
        bar_val = max(0.0, min(1.0, float(conf)))
        with st.expander(
            f"{dot} `{entry['timestamp']}` · **{entry['agent_id']}** → `{entry['action']}` · conf `{conf:.2f}`",
            expanded=False,
        ):
            st.progress(bar_val, text=f"Confidence: {conf:.2f}")
            st.json({k: v for k, v in entry.items() if k != "timestamp"})

    st.divider()
    raw_export = "\n".join(json.dumps(e) for e in filtered)
    st.download_button(
        "📥 Export filtered ledger",
        raw_export,
        file_name="vos_audit_export.jsonl",
        mime="application/json",
    )
