"""
SynthMind — Live monitor for the Synthetic Cognitive Core.
Shows real-time cycle stats, memory state, and exposes hard reset.
"""
import streamlit as st

APP_META = {
    "id": "synth_mind",
    "name": "SynthMind",
    "icon": "🧠",
    "tagline": "Monitor the synthetic cognitive core in real time",
    "category": "system",
}


def render(router) -> None:
    st.header("🧠 SynthMind")
    st.caption(
        "Live window into the Synthetic Cognitive Core. "
        "Run test cycles, inspect memory, arm hard reset."
    )
    core = router.synthetic

    # ── Status strip ──────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Memory Slots", f"{len(core.memory_bank)} / {core.memory_capacity}")
    c2.metric("Mesh Scales", len(core.mesh))
    c3.metric("Coder LR", f"{core.coder.learning_rate:.3f}")
    c4.metric("Resolver Threshold", f"{core.resolver.threshold:.0%}")

    st.divider()

    # ── Live test cycle ───────────────────────────────────────────
    st.subheader("Run a Cognitive Cycle")
    prompt = st.text_input("Prompt", "write a hook for my trap track")
    context = st.text_input("Context (optional)", "")

    if st.button("⚡ PROCESS"):
        with st.spinner("Running cycle..."):
            out = core.process(prompt, context or None)

        st.success(f"Cycle complete in {out['processing_ms']} ms | Trust: `{out['trust_status']}`")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Intent routing**")
            st.json({
                "intent": out["intent"],
                "intent_confidence": out["intent_confidence"],
                "contradiction": out["contradiction_status"],
                "overall_confidence": out["confidence"],
            })
        with col2:
            st.markdown("**Fractal mesh activations**")
            for i, act in enumerate(out["fractal_activation"], start=1):
                st.progress(act, text=f"Scale {i}: {act:.3f}")
            st.caption(f"Prediction error: `{out['prediction_error']}`")

        st.caption(f"Memory: {out['memory_slots']} / {core.memory_capacity} slots used")

    st.divider()

    # ── Mesh snapshot ─────────────────────────────────────────────
    st.subheader("Mesh Snapshot")
    for node in core.mesh:
        snap = node.compress()
        st.markdown(
            f"**Scale {snap['scale']}** — activation `{snap['activation']}` | "
            f"weight norm `{snap['norm']:.4f}` | updated `{snap['updated']}`"
        )

    st.divider()

    # ── Hard reset ────────────────────────────────────────────────
    st.subheader("⚠️ Hard Reset")
    st.warning(
        "Clears all memory, reinitialises mesh weights and predictive coder. "
        "Irreversible. Logged to audit ledger."
    )
    if st.button("🔴 HARD RESET SYNTHETIC CORE", type="primary"):
        core.hard_reset()
        st.success("✅ Hard reset complete. State cleared and persisted.")
