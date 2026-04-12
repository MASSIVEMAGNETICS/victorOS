"""
VOS Dashboard — Cyberpunk Dark Theme | Streamlit | Local-First
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st

from vos_core.core_router import CORERouter

st.set_page_config(
    page_title="VOS v0.1.0 | Massive Magnetics", page_icon="⚡", layout="wide"
)

# CYBERPUNK THEME INJECTION
st.markdown(
    """
<style>
    .stApp {background-color: #0a0a0f; color: #e0e0e0;}
    h1, h2, h3 {color: #00ffcc; text-shadow: 0 0 8px #00ffcc80;}
    .stButton>button {background: #111; color: #00ffcc; border: 1px solid #00ffcc40;}
    .stButton>button:hover {background: #00ffcc; color: #0a0a0f;}
    .stTextInput>div>div>input {background: #111; color: #00ffcc; border: 1px solid #00ffcc40;}
    .stTextArea>div>div>textarea {background: #111; color: #00ffcc; border: 1px solid #00ffcc40;}
    div[data-testid="stStatusWidget"] {display: none;}
</style>
""",
    unsafe_allow_html=True,
)

st.title("⚡ VOS v0.1.0 — Victor Operating System")
st.caption("Local-first AI runtime for creators. Massive Magnetics × BandoBandz.")

router = CORERouter()

with st.form("input_form"):
    st.subheader("📦 Ingest Raw Creative Assets")
    title = st.text_input("Track Title", "EXIT VELOCITY")
    artist = st.text_input("Artist Name", "iambandobandz")
    genre = st.selectbox(
        "Genre", ["Hip-Hop/Rap", "Trap", "Drill", "R&B/Soul", "Alternative"]
    )
    mood = st.text_input("Vibe/Mood", "Gritty, Determined, Rust Belt")
    bpm = st.number_input("BPM", 60, 200, 140)
    key = st.text_input("Musical Key", "C Minor")
    release_date = st.date_input("Target Release")
    use_ai = st.checkbox(
        "Enable Local LLM Prompt Gen (Ollama Required)", value=True
    )

    submitted = st.form_submit_button("🚀 PROCESS & EXPORT")

if submitted:
    with st.spinner("Routing through Victor core..."):
        raw = {
            "title": title,
            "artist": artist,
            "genre": genre,
            "mood": mood,
            "bpm": bpm,
            "key": key,
            "release_date": release_date.strftime("%Y-%m-%d"),
        }
        result = router.process_input(raw, generate_ai=use_ai)

    if "error" not in result:
        st.success("✅ PROCESS COMPLETE | TRUST: APPROVED")
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📊 Metadata")
            st.json(result["metadata"])
        with col2:
            st.subheader("📅 Rollout Schedule (First 7 Days)")
            for day in result["rollout_schedule"][:7]:
                st.markdown(
                    f"**Day {day['day']}** ({day['date']}) | `{day['task']}`"
                )

        st.subheader("🔌 AI Prompts / Templates")
        for k, v in result["ai_prompts"].items():
            st.markdown(f"**{k.replace('_', ' ').title()}**")
            st.code(v, language="text")

        st.info(
            f"📜 Audit Ledger: `{result['audit_log']}` | "
            f"Status: `{result['trust_status']}`"
        )
    else:
        st.error(f"⚠️ QUARANTINE TRIGGERED: {result['error']}")
