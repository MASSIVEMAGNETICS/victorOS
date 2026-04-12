"""
CreativeCore — Synthetic-core-powered ad hooks, IG captions, and press pitches.
"""
import streamlit as st

APP_META = {
    "id": "creative_core",
    "name": "CreativeCore",
    "icon": "🔌",
    "tagline": "AI ad hooks · IG captions · press pitches — zero cloud",
    "category": "creator",
}


def render(router) -> None:
    st.header("🔌 CreativeCore")
    st.caption(
        "Synthetic cognitive engine generates ad hooks, captions, and press pitches. "
        "No cloud. No API key. Runs the local loop."
    )

    with st.form("creative_form"):
        c1, c2 = st.columns(2)
        title = c1.text_input("Track Title", "EXIT VELOCITY")
        artist = c2.text_input("Artist", "iambandobandz")
        genre = c1.selectbox("Genre", ["Hip-Hop/Rap", "Trap", "Drill", "R&B/Soul", "Alternative"])
        mood = c2.text_input("Mood / Energy", "Gritty, Determined")
        bpm = c1.number_input("BPM", 60, 220, 140)
        key = c2.text_input("Key", "C Minor")
        submitted = st.form_submit_button("⚡ RUN CREATIVE LOOP")

    if submitted:
        meta = router.meta_engine.parse_and_validate(
            {"title": title, "artist": artist, "genre": genre,
             "mood": mood, "bpm": bpm, "key": key}
        )
        with st.spinner("Running synthetic cognitive cycle..."):
            prompts = router._generate_prompts(meta)

        st.success("✅ Creative pack generated.")

        for key_name, label, icon in [
            ("ad_hook",     "Ad Hook (15s TikTok)",      "🎯"),
            ("caption_pack","IG Caption Pack",            "📸"),
            ("press_pitch", "Press / Playlist Pitch",    "📨"),
        ]:
            st.subheader(f"{icon} {label}")
            st.code(prompts[key_name], language="text")
            st.download_button(
                f"📥 Copy {label}",
                prompts[key_name],
                file_name=f"{title.replace(' ','_')}_{key_name}.txt",
                mime="text/plain",
                key=f"dl_{key_name}",
            )
