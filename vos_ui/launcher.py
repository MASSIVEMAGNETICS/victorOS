"""
VOS Launcher — Victor Operating System Shell
The home screen. Every feature is an App. One runtime. One audit ledger. One truth.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st

from vos_apps import load_registry
from vos_core.core_router import CORERouter

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="VictorOS v0.1.0",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global cyberpunk theme ─────────────────────────────────────────────────────
st.markdown("""
<style>
  /* Base */
  .stApp {background-color: #07070d; color: #d8d8e0;}
  * {font-family: 'Consolas', 'Courier New', monospace;}

  /* Headings */
  h1,h2,h3,h4 {color:#00ffcc; text-shadow:0 0 10px #00ffcc60;}

  /* Buttons */
  .stButton>button {
    background:#0d0d18; color:#00ffcc;
    border:1px solid #00ffcc50; border-radius:4px;
    transition: all 0.15s ease;
  }
  .stButton>button:hover {background:#00ffcc; color:#07070d; border-color:#00ffcc;}

  /* Inputs */
  .stTextInput>div>div>input,
  .stNumberInput>div>div>input,
  .stSelectbox>div>div>div {
    background:#0d0d18 !important; color:#00ffcc !important;
    border:1px solid #00ffcc30 !important;
  }

  /* Sidebar */
  section[data-testid="stSidebar"] {background:#09090f; border-right:1px solid #00ffcc20;}

  /* Metrics */
  div[data-testid="stMetric"] {
    background:#0d0d18; border:1px solid #00ffcc25;
    border-radius:4px; padding:0.5rem 0.75rem;
  }

  /* Tabs */
  .stTabs [data-baseweb="tab"] {color:#888; border-bottom:2px solid transparent;}
  .stTabs [aria-selected="true"] {color:#00ffcc !important; border-bottom:2px solid #00ffcc !important;}

  /* App tiles */
  .vos-tile {
    background:#0d0d18; border:1px solid #00ffcc25; border-radius:6px;
    padding:1.2rem; margin-bottom:0.5rem;
    transition: border-color 0.15s ease;
  }
  .vos-tile:hover {border-color:#00ffcc80;}
  .vos-tile-icon {font-size:2rem; margin-bottom:0.4rem;}
  .vos-tile-name {color:#00ffcc; font-size:1.05rem; font-weight:bold; margin-bottom:0.15rem;}
  .vos-tile-tagline {color:#888; font-size:0.8rem;}
  .vos-tile-cat {color:#00ffcc40; font-size:0.7rem; text-transform:uppercase; letter-spacing:2px;}

  /* Status bar */
  .vos-statusbar {
    position:fixed; bottom:0; left:0; right:0; z-index:999;
    background:#07070d; border-top:1px solid #00ffcc20;
    padding:0.25rem 1rem; font-size:0.72rem; color:#00ffcc60;
    display:flex; gap:2rem;
  }

  /* Divider */
  hr {border-color:#00ffcc20;}

  /* Code blocks */
  code, pre {background:#0d0d18 !important; color:#00ffcc !important;}

  /* Hide Streamlit branding */
  #MainMenu,footer,header {visibility:hidden;}
  div[data-testid="stStatusWidget"] {display:none;}
</style>
""", unsafe_allow_html=True)

# ── Singleton router (one runtime for entire OS session) ───────────────────────
@st.cache_resource
def get_router():
    return CORERouter()

router = get_router()
registry = load_registry()

# ── Session state ──────────────────────────────────────────────────────────────
if "current_app" not in st.session_state:
    st.session_state.current_app = None   # None = home screen

# ── Shared runtime metrics (computed once per render cycle) ───────────────────
audit_count = 0
if router.audit.log_path.exists():
    with open(router.audit.log_path, encoding="utf-8") as _f:
        audit_count = sum(1 for line in _f if line.strip())

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚡ VictorOS")
    st.caption(f"{router.version.version_string} · Massive Magnetics × BandoBandz")
    st.divider()

    if st.button("🏠 Home", use_container_width=True):
        st.session_state.current_app = None

    st.markdown("**Creator**")
    for app in [a for a in registry if a.category == "creator"]:
        active = st.session_state.current_app == app.id
        label = f"{'▶ ' if active else ''}{app.icon} {app.name}"
        if st.button(label, key=f"nav_{app.id}", use_container_width=True):
            st.session_state.current_app = app.id

    st.markdown("**System**")
    for app in [a for a in registry if a.category == "system"]:
        active = st.session_state.current_app == app.id
        label = f"{'▶ ' if active else ''}{app.icon} {app.name}"
        if st.button(label, key=f"nav_{app.id}", use_container_width=True):
            st.session_state.current_app = app.id

    st.divider()
    st.caption(f"📜 Audit entries: {audit_count}")
    st.caption(f"🧠 Memory: {len(router.synthetic.memory_bank)}/{router.synthetic.memory_capacity}")

# ── Home screen ────────────────────────────────────────────────────────────────
def render_home():
    st.markdown(
        "<h1 style='font-size:2.2rem; margin-bottom:0'>⚡ VictorOS</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='color:#888; margin-top:0.2rem'>"
        "Local-first AI runtime for creators · "
        "Massive Magnetics × BandoBandz · v0.1.0"
        "</p>",
        unsafe_allow_html=True,
    )
    st.divider()

    # Status row
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Runtime", router.version.version_string)
    c2.metric("Trust Threshold", f"{router.trust.threshold:.0%}")
    c3.metric("Audit Entries", audit_count)
    c4.metric("Synth Memory", f"{len(router.synthetic.memory_bank)}/{router.synthetic.memory_capacity}")

    st.divider()

    # App grid — creator row then system row
    for category, label in [("creator", "🎨 Creator Apps"), ("system", "⚙️ System Apps")]:
        st.markdown(f"### {label}")
        apps_in_cat = [a for a in registry if a.category == category]
        cols = st.columns(len(apps_in_cat))
        for col, app in zip(cols, apps_in_cat):
            with col:
                st.markdown(
                    f"""<div class="vos-tile">
                        <div class="vos-tile-icon">{app.icon}</div>
                        <div class="vos-tile-name">{app.name}</div>
                        <div class="vos-tile-tagline">{app.tagline}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )
                if st.button(f"Launch {app.name}", key=f"home_{app.id}", use_container_width=True):
                    st.session_state.current_app = app.id
                    st.rerun()
        st.markdown("")

# ── Router ─────────────────────────────────────────────────────────────────────
current_id = st.session_state.current_app

if current_id is None:
    render_home()
else:
    app = next((a for a in registry if a.id == current_id), None)
    if app is None:
        st.error(f"App '{current_id}' not found in registry.")
        st.session_state.current_app = None
    else:
        app.render(router)

# ── Status bar ─────────────────────────────────────────────────────────────────
st.markdown(
    f"""<div class="vos-statusbar">
        <span>⚡ VictorOS {router.version.version_string}</span>
        <span>📜 Audit: {audit_count} entries</span>
        <span>🧠 Synth memory: {len(router.synthetic.memory_bank)}/{router.synthetic.memory_capacity}</span>
        <span>🔒 Trust: {router.trust.threshold:.0%} threshold</span>
    </div>""",
    unsafe_allow_html=True,
)
