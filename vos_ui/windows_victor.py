"""VictorOS Windows Prototype — governed local owner interface."""
from pathlib import Path
import sys

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vos_core.windows_runtime import VictorWindowsRuntime

st.set_page_config(page_title="VictorOS Windows Prototype", page_icon="⚡", layout="wide")

st.markdown(
    """
<style>
.stApp { background:#07090d; color:#e8eef3; }
h1,h2,h3 { color:#55ffd6; }
code { color:#55ffd6 !important; }
div[data-testid="stMetric"] { background:#0d1117; border:1px solid #203036; padding:12px; border-radius:8px; }
</style>
""",
    unsafe_allow_html=True,
)

@st.cache_resource
def runtime() -> VictorWindowsRuntime:
    return VictorWindowsRuntime(str(ROOT))

victor = runtime()
status = victor.status()

st.title("⚡ VictorOS — Windows Prototype")
st.caption("Local-first governed runtime · persistent episodes · hash-linked receipts · explicit Human STOP")

if status["startup_fault"]:
    st.error(f"FAIL-CLOSED STARTUP FAULT: {status['startup_fault']}")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Governance", status["governance_mode"])
c2.metric("Human STOP", "ACTIVE" if status["human_stop"] else "CLEAR")
c3.metric("Episodes", status["episode_count"])
c4.metric("Boots", status["boot_count"])

with st.sidebar:
    st.header("Owner Control")
    st.write(f"Receipt chain: **{'OK' if status['receipt_chain_ok'] else 'BROKEN'}**")
    st.write(f"Episode chain: **{'OK' if status['episode_chain_ok'] else 'BROKEN'}**")
    st.code(status["last_receipt"][:24] + "…" if len(status["last_receipt"]) > 24 else status["last_receipt"])
    st.divider()

    if not status["human_stop"]:
        if st.button("🛑 ACTIVATE HUMAN STOP", type="primary", use_container_width=True):
            victor.set_human_stop(True)
            st.rerun()
    else:
        st.error("HUMAN STOP IS ACTIVE. Governed execution is blocked.")
        if st.button("Reset Human STOP", use_container_width=True, disabled=bool(status["startup_fault"])):
            try:
                victor.set_human_stop(False)
                st.rerun()
            except RuntimeError as exc:
                st.error(str(exc))

st.subheader("Owner Input → Episode")
owner_input = st.text_area(
    "Input",
    height=150,
    placeholder="Give Victor an observation, intent, question, or local reasoning task…",
    disabled=status["human_stop"] or bool(status["startup_fault"]),
)

if st.button(
    "Commit Episode",
    use_container_width=True,
    disabled=status["human_stop"] or bool(status["startup_fault"]),
):
    try:
        episode = victor.process_episode(owner_input)
        if episode["status"] == "EXECUTED":
            st.success(f"Episode committed · receipt {episode['receipt_hash'][:16]}…")
        else:
            st.warning(f"Episode {episode['status']} · {', '.join(episode['reasons'])}")
        if episode.get("cognitive"):
            st.json(episode["cognitive"])
    except Exception as exc:
        st.exception(exc)

st.divider()
st.subheader("Recent Episodes")
recent = victor.recent_episodes(12)
if not recent:
    st.info("No Windows episodes yet.")
else:
    for episode in recent:
        with st.expander(
            f"{episode['timestamp']} · {episode['status']} · {episode['event_hash'][:10]}…",
            expanded=False,
        ):
            st.write(episode["input"])
            st.caption(
                f"Governance: {episode['governance_mode']} · Receipt: {episode['receipt_hash']}"
            )
            if episode.get("reasons"):
                st.write("Reasons:", episode["reasons"])
            if episode.get("cognitive"):
                st.json(episode["cognitive"])
