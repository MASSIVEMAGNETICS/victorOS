"""VictorOS Windows Prototype — persistent cognitive scheduler interface."""
from pathlib import Path
import sys
import streamlit as st

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from vos_core.windows_runtime import VictorWindowsRuntime

st.set_page_config(page_title="VictorOS Windows Cognitive Prototype",page_icon="⚡",layout="wide")
st.markdown("""<style>.stApp{background:#07090d;color:#e8eef3}h1,h2,h3{color:#55ffd6}
div[data-testid="stMetric"]{background:#0d1117;border:1px solid #203036;padding:12px;border-radius:8px}</style>""",unsafe_allow_html=True)

@st.cache_resource
def runtime():
    return VictorWindowsRuntime(str(ROOT))

victor=runtime()
status=victor.status()
st.title("⚡ VictorOS — Windows Cognitive Prototype")
st.caption("event → persistent queue → macrotick → cognition → Choice → physiology/lease → bounded capability → receipt")

if status["startup_fault"]:
    st.error(f"FAIL-CLOSED STARTUP FAULT: {status['startup_fault']}")

cols=st.columns(6)
for col,(name,value) in zip(cols,[
    ("Governance",status["governance_mode"]),
    ("Human STOP","ACTIVE" if status["human_stop"] else "CLEAR"),
    ("Episodes",status["episode_count"]),
    ("Queue",status["cognitive_queue_pending"]),
    ("Scheduler Tick",status["scheduler_tick"]),
    ("Stack Tick",status["stack_tick"]),
]): col.metric(name,value)

with st.sidebar:
    st.header("Owner Control")
    st.write(f"Physiology receipts: **{'OK' if status['receipt_chain_ok'] else 'BROKEN'}**")
    st.write(f"Episode chain: **{'OK' if status['episode_chain_ok'] else 'BROKEN'}**")
    st.write(f"Scheduler receipts: **{'OK' if status['scheduler_receipt_chain_ok'] else 'BROKEN'}**")
    if not status["human_stop"]:
        if st.button("🛑 ACTIVATE HUMAN STOP",type="primary",use_container_width=True):
            victor.set_human_stop(True); st.rerun()
    else:
        st.error("HUMAN STOP ACTIVE. Governed capability execution is blocked.")
        if st.button("Reset Human STOP",use_container_width=True,disabled=bool(status["startup_fault"])):
            victor.set_human_stop(False); st.rerun()

st.subheader("Owner Query → Persistent Cognition")
st.caption("Submitting runs exactly one macrotick. Follow-up thoughts stay durable for later ticks; no recursive think().")
owner_input=st.text_area("Input",height=140,placeholder="Ask Victor something worth thinking through…",
    disabled=status["human_stop"] or bool(status["startup_fault"]))
if st.button("Submit Query + Run 1 Tick",use_container_width=True,
    disabled=status["human_stop"] or bool(status["startup_fault"])):
    try:
        ep=victor.process_episode(owner_input)
        if ep["status"]=="EXECUTED":
            tr=ep.get("scheduler_tick_receipt") or {}
            st.success(f"Query accepted. Tick {tr.get('tick')} ran; {tr.get('queue_size_end',0)} item(s) remain.")
            st.json(tr)
        else: st.warning(f"Query {ep['status']} · {', '.join(ep['reasons'])}")
    except Exception as exc: st.exception(exc)

st.divider()
st.subheader("Cognitive Clock")
a,b,c=st.columns(3)
if a.button("Advance 1 Tick",use_container_width=True):
    st.json(victor.advance_cognition(1)[0]); st.rerun()
if b.button("Advance 5 Ticks",use_container_width=True):
    st.json(victor.advance_cognition(5)); st.rerun()
if c.button("Refresh State",use_container_width=True): st.rerun()

pending=victor.pending_cognition(25)
st.markdown("### Pending Cognitive Work")
if not pending: st.info("Cognitive queue is empty.")
for item in pending:
    with st.expander(f"{item['kind']} · priority {item['priority']:.2f} · depth {item['depth']} · {item['id'][:10]}…"):
        st.json(item)

actions=victor.proposed_actions()
if actions:
    st.markdown("### Human-Approval Actions")
    st.caption("Scheduler may prepare these for review; it never silently approves stack actions.")
    for action in actions[:20]: st.json(action)

st.divider()
st.subheader("Recent Episodes")
for ep in victor.recent_episodes(12):
    with st.expander(f"{ep['timestamp']} · {ep['status']} · {ep['event_hash'][:10]}…"):
        st.write(ep["input"])
        if ep.get("scheduler_tick_receipt"): st.json(ep["scheduler_tick_receipt"])
