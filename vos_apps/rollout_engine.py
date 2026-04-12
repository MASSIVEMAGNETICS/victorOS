"""
RolloutEngine — 30-day priority-scored rollout calendar generator + export.
"""
import json
from datetime import date

import streamlit as st

APP_META = {
    "id": "rollout_engine",
    "name": "RolloutEngine",
    "icon": "📅",
    "tagline": "Generate a 30-day priority rollout calendar",
    "category": "creator",
}


def render(router) -> None:
    st.header("📅 RolloutEngine")
    st.caption("Generate a priority-scored pre/launch/post rollout plan. Export as JSON or copy to your calendar.")

    release_date = st.date_input("Target Release Date", value=date.today())
    track_name = st.text_input("Track / Project Name", "EXIT VELOCITY")

    if st.button("⚡ GENERATE ROLLOUT"):
        schedule = router.rollout.generate(release_date.strftime("%Y-%m-%d"))
        router.trust.evaluate("rollout_engine", "calendar_generated",
                              {"days": len(schedule), "track": track_name}, 0.92)

        st.success(f"✅ {len(schedule)}-event rollout calendar generated.")

        # Phase summary
        phases = {"pre": [], "launch": [], "post": []}
        for item in schedule:
            phases[item["phase"]].append(item)

        tabs = st.tabs(["🟡 Pre-Launch", "🔴 Launch", "🟢 Post-Launch", "📋 Full Schedule"])

        for tab, phase_key, label in zip(
            tabs[:3],
            ["pre", "launch", "post"],
            ["Pre-Launch", "Launch", "Post-Launch"]
        ):
            with tab:
                for item in phases[phase_key]:
                    badge = "🔴 HIGH" if item["priority"] == "high" else "🟡 MED"
                    st.markdown(
                        f"**Day {item['day']}** · `{item['date']}` · {badge}  \n{item['task']}"
                    )

        with tabs[3]:
            st.dataframe(
                [{k: v for k, v in s.items()} for s in schedule],
                use_container_width=True,
            )
            st.download_button(
                "📥 Export JSON",
                json.dumps(schedule, indent=2),
                file_name=f"{track_name.replace(' ','_')}_rollout.json",
                mime="application/json",
            )
