"""
MetaForge — Asset ingestion + DSP-ready metadata normalization + JSON/CSV export.
"""
import json

import streamlit as st

APP_META = {
    "id": "meta_forge",
    "name": "MetaForge",
    "icon": "🎵",
    "tagline": "Ingest raw assets → structured DSP metadata",
    "category": "creator",
}


def render(router) -> None:
    st.header("🎵 MetaForge")
    st.caption("Ingest raw creative assets and generate DSP-ready metadata for DistroKid, TuneCore, and CD Baby.")

    with st.form("meta_form"):
        c1, c2 = st.columns(2)
        title = c1.text_input("Track Title", "EXIT VELOCITY")
        artist = c2.text_input("Artist Name", "iambandobandz")
        genre = c1.selectbox("Genre", ["Hip-Hop/Rap", "Trap", "Drill", "R&B/Soul", "Alternative", "Rock"])
        mood = c2.text_input("Vibe / Mood", "Gritty, Determined, Rust Belt")
        bpm = c1.number_input("BPM", 60, 220, 140)
        key = c2.text_input("Musical Key", "C Minor")
        submitted = st.form_submit_button("⚡ FORGE METADATA")

    if submitted:
        raw = {"title": title, "artist": artist, "genre": genre,
               "mood": mood, "bpm": bpm, "key": key}
        meta = router.meta_engine.parse_and_validate(raw)
        router.trust.evaluate("meta_forge", "metadata_generated", {"title": title}, 0.95)

        st.success("✅ Metadata forged and validated.")
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Structured Output")
            st.json(meta)
        with col2:
            st.subheader("Export")
            json_out = router.meta_engine.export_json(meta)
            csv_out = router.meta_engine.export_csv(meta)
            st.download_button("📥 Download JSON", json_out,
                               file_name=f"{title.replace(' ','_')}_meta.json",
                               mime="application/json")
            st.download_button("📥 Download CSV", csv_out,
                               file_name=f"{title.replace(' ','_')}_meta.csv",
                               mime="text/csv")
            st.code(f"ISRC Stub: {meta['isrc_stub']}", language="text")
