from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import streamlit as st
from agent.graph import ResolutionAgent
from demo.failures import FailureInjector
from reporting import resolution_report
from providers.llm.factory import build_provider
from services.enterprise import Enterprise
from storage.database import DEFAULT_DB,connect,ensure_database,reset_database

st.set_page_config(page_title="ResolveAI",page_icon="✦",layout="wide")
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&display=swap');
:root{--ink:#eaf2fb;--muted:#91a5bc;--canvas:#07131f;--panel:#0d2033;--panel2:#10283e;--line:#1b3b56;--accent:#38d6b0;--blue:#54a9ff;--amber:#f7b955;--danger:#ff6b73}
html,body,[class*="css"]{font-family:'Manrope',Inter,ui-sans-serif,system-ui,sans-serif}.stApp{background:var(--canvas);color:var(--ink)}[data-testid="stHeader"]{background:rgba(7,19,31,.97);border-bottom:1px solid var(--line)}[data-testid="stToolbar"]{right:1rem}[data-testid="stSidebar"]{background:#091b2c;border-right:1px solid #18354e}[data-testid="stSidebar"] *{color:var(--ink)}.block-container{max-width:1440px;padding:2.2rem 3.2rem 4rem}.brand{font-size:1.55rem;font-weight:800;color:#fff;letter-spacing:-.045em}.sub{color:var(--muted);font-size:.8rem;line-height:1.5}.casebar,.panel{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:1.15rem 1.3rem;margin:.65rem 0;box-shadow:0 8px 30px rgba(0,0,0,.12)}.chip{background:rgba(56,214,176,.14);border:1px solid rgba(56,214,176,.28);color:#78efd2;border-radius:999px;padding:.25rem .66rem;font-size:.7rem;font-weight:800;letter-spacing:.06em}.event{border:1px solid var(--line);border-left:3px solid var(--blue);background:var(--panel);padding:.9rem 1rem;margin:.5rem 0;border-radius:0 11px 11px 0}.event-adapt{border-left-color:var(--amber);background:#1c1b18}.event-fail{border-left-color:var(--danger);background:#21181c}.event small{color:var(--muted)}.metric-note{color:var(--muted);font-size:.75rem}h1,h2,h3{color:#f6f9fc;letter-spacing:-.04em}h1{font-size:2rem!important;margin-bottom:.35rem!important}h2{font-size:1.3rem!important}h3{font-size:1.05rem!important}.stCaption{color:var(--muted)!important}label,p,.stMarkdown{color:var(--ink)!important}.stTextArea textarea,.stTextInput input,[data-baseweb="select"]>div{background:#0b1d2e!important;color:var(--ink)!important;border:1px solid #30516e!important;border-radius:10px!important}.stTextArea textarea:focus,.stTextInput input:focus{border-color:var(--accent)!important;box-shadow:0 0 0 2px rgba(56,214,176,.14)!important}.stButton>button{background:var(--panel2);color:var(--ink);border:1px solid #315370;border-radius:9px;font-family:inherit;font-weight:700;padding:.58rem 1rem}.stButton>button:hover{border-color:var(--accent);color:#fff;background:#14334a}.stButton>button[kind="primary"]{background:var(--accent);color:#06231e;border-color:var(--accent)}.stButton>button[kind="primary"]:hover{background:#60e5c6;border-color:#60e5c6}.stSelectbox label,.stMultiSelect label{color:var(--muted)!important;font-size:.82rem!important;font-weight:700!important}.stRadio label{color:#b9cbe0!important}.stRadio [role="radiogroup"]{gap:.15rem}.stRadio [role="radio"]{background:transparent!important}.stRadio [data-checked="true"]{border-color:var(--accent)!important;background:var(--accent)!important}.stMetric{background:var(--panel)!important;border:1px solid var(--line);border-radius:12px;padding:.75rem .9rem}.stMetric label{color:var(--muted)!important;font-size:.72rem!important;font-weight:700!important;text-transform:uppercase;letter-spacing:.06em}.stMetric [data-testid="stMetricValue"]{color:#f3f8fc!important;font-size:1.35rem}.stTabs [data-baseweb="tab-list"]{gap:.25rem;border-bottom:1px solid var(--line)}.stTabs [data-baseweb="tab"]{color:var(--muted);font-weight:700;padding:.65rem .9rem}.stTabs [aria-selected="true"]{color:var(--accent)!important;border-bottom-color:var(--accent)!important}.stDataFrame{border:1px solid var(--line);border-radius:10px;overflow:hidden}.stAlert{border-radius:11px}.demo-hero{background:linear-gradient(135deg,#0e2940,#102139);border:1px solid #244665;border-radius:16px;padding:1.55rem 1.7rem;margin:.35rem 0 1.25rem}.demo-kicker{color:var(--accent);font-weight:800;font-size:.72rem;letter-spacing:.1em;text-transform:uppercase}.demo-card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:1rem 1.15rem;min-height:132px}.demo-card b{font-size:.95rem;color:#fff}.demo-card p{font-size:.85rem;color:var(--muted)!important;line-height:1.6}.stSpinner>div{border-top-color:var(--accent)!important}
</style>""",unsafe_allow_html=True)
if "initialized" not in st.session_state: ensure_database(DEFAULT_DB);st.session_state.initialized=True

def rows(sql,params=()):
    c=connect(DEFAULT_DB);data=[dict(row) for row in c.execute(sql,params).fetchall()];c.close();return data
def graph(state):
    labels=[event.action for event in state.action_history];unique=[]
    for item in labels:
        if item not in unique:unique.append(item)
    edges=[f'"{labels[i]}" -> "{labels[i+1]}"' for i in range(len(labels)-1)]
    colors=[]
    for node in unique:
        color="#f2b84b" if node=="ADAPT_PLAN" else "#45c99a" if node in {"VERIFY","ESCALATE"} else "#3d8ed7"
        colors.append(f'"{node}" [style=filled, fillcolor="{color}", fontcolor="white"]')
    return "digraph { rankdir=LR; bgcolor=transparent; node [shape=box, style=rounded, color=white, fontname=Arial]; "+";".join(colors+edges)+";}"
def render_graph_safe(dot_source):
    try:st.graphviz_chart(dot_source,use_container_width=True)
    except Exception:st.info("Execution path (Graphviz rendering unavailable):");st.code(dot_source,language="dot")
def run_case(request,case_id="",failures=()):
    provider=build_provider();state=ResolutionAgent(Enterprise(str(DEFAULT_DB),FailureInjector(set(failures))),provider=provider).run(case_id or None,request);st.session_state.state=state
def workspace(state):
    if state.case_id=="UNRESOLVED":st.warning(state.final_summary);return
    case=rows("SELECT * FROM cases WHERE id=?",(state.case_id,))[0];order=rows("SELECT * FROM orders WHERE id=?",(state.order_id,))[0];customer=rows("SELECT * FROM customers WHERE id=?",(state.customer_id,))[0]
    st.markdown(f"<div class='casebar'><span class='chip'>{state.final_status}</span> &nbsp; <b>{state.case_id}</b> · {case['issue_type'].replace('_',' ')}<br><span class='sub'>Customer: {customer['name']} · Order: {state.order_id} · Product: {order['product_name']}</span></div>",unsafe_allow_html=True)
    left,center,right=st.columns([1.05,1.65,1])
    with left:
        st.subheader("Case state");st.markdown(f"<div class='panel'><b>Customer objective</b><br>{state.user_request}<hr><b>Plan</b><br>{state.preferred_action.title()} → {(state.current_resolution or 'Human review').title()}<hr><b>Current status</b><br>{state.final_status}</div>",unsafe_allow_html=True)
        if state.replans: st.warning("Adaptation recorded: replacement strategy changed after a real enterprise constraint.")
    with center:
        st.subheader("Execution timeline")
        for event in state.action_history:
            css="event-adapt" if event.status in {"ADAPTED","RETRY"} else "event-fail" if event.status=="FAILED" else ""
            st.markdown(f"<div class='event {css}'><b>{event.action.replace('_',' ')}</b> <span class='sub'>· {event.status}</span><br>{event.summary}<br><small>{event.tool} · {event.timestamp[:19]}</small></div>",unsafe_allow_html=True)
    with right:
        st.subheader("Agent status");st.caption(f"Intent provider: {state.llm_provider}");metrics=[("Current outcome",(state.current_resolution or "Clarification").title()),("Actions",str(len(state.action_history))),("Tool calls",str(len(state.tool_calls))),("Adaptations",str(state.replans)),("Verifications",str(len(state.verification_results)))]
        for key,value in metrics:st.metric(key,value)
    tabs=st.tabs(["Customer view","Operations","State diff & verification","Agent graph","Audit"])
    with tabs[0]:st.success(state.final_summary or "Investigation complete.");st.download_button("Download resolution report",resolution_report(state),f"resolveai-{state.case_id}.md","text/markdown")
    with tabs[1]:st.json({"goal":state.goal.model_dump() if state.goal else {},"tool_calls":state.tool_calls,"failures":state.failures})
    with tabs[2]:
        if state.current_resolution=="refund":
            payment=rows("SELECT * FROM payments WHERE order_id=?",(state.order_id,))[0];st.markdown(f"<div class='panel'><b>Payment state</b><br>PAYMENT_CAPTURED &nbsp; → &nbsp; <b>{payment['status']}</b><br><br><b>Refunded amount</b><br>₹0.00 &nbsp; → &nbsp; <b>₹{payment['refunded_amount']:.2f}</b><br><br><b>Case state</b><br>OPEN &nbsp; → &nbsp; <b>{case['status']}</b></div>",unsafe_allow_html=True)
        if state.verification_results:st.success("Verification passed");st.json(state.verification_results[-1])
        else:st.info("No final verification was completed.")
    with tabs[3]:render_graph_safe(graph(state))
    with tabs[4]:st.dataframe(rows("SELECT created_at,action,tool,before_state,after_state,reason FROM audit_events WHERE case_id=? ORDER BY id",(state.case_id,)),use_container_width=True,hide_index=True)

with st.sidebar:
    st.markdown("<div class='brand'>✦ ResolveAI</div><div class='sub'>AUTONOMOUS RESOLUTION OPS</div>",unsafe_allow_html=True);page=st.radio("Navigation",["New case","Cases","Agent graph","Enterprise data","Demo & simulation"],label_visibility="collapsed");st.divider();st.caption("Active customer context: Alex Morgan (CUS-100)");st.success("SQLite online · Policy active");st.info(f"LLM route: {build_provider().name}")
if page=="New case":
    st.title("What can ResolveAI resolve for you?");st.caption("Describe the issue naturally. ResolveAI uses the active customer context, or an order/case ID you mention, to locate enterprise records.")
    request=st.text_area("Customer issue",placeholder="My headphones arrived damaged and I want a replacement.",height=130)
    suggestions=["Refund my damaged headphones","I want to cancel my order","My headphones arrived damaged and I want a replacement.","I need a refund for order ORD-1042"]
    chosen=st.selectbox("Try an example",["Choose an example"]+suggestions)
    if chosen!="Choose an example":request=chosen
    if st.button("Start autonomous resolution",type="primary",disabled=not request,use_container_width=True):
        with st.status("Investigating case state…",expanded=True) as status:run_case(request);status.update(label="Investigation completed",state="complete",expanded=False)
    if state:=st.session_state.get("state"):workspace(state)
    else:st.info("ResolveAI will check enterprise state, select only permitted actions, adapt to constraints, and verify the final result.")
elif page=="Cases":
    st.title("Cases");query=st.text_input("Search case, order, customer, product, or status")
    data=rows("SELECT c.id,c.status,c.issue_type,c.priority,o.id AS order_id,o.product_name,u.name,u.email FROM cases c JOIN orders o ON o.id=c.order_id JOIN customers u ON u.id=c.customer_id WHERE lower(c.id||' '||c.status||' '||o.id||' '||o.product_name||' '||u.name||' '||u.email) LIKE ? ORDER BY c.id",(f"%{query.lower()}%",));st.dataframe(data,use_container_width=True,hide_index=True)
    case_id=st.text_input("Open case by ID");
    if st.button("Open case") and case_id:run_case("Please investigate this case",case_id);workspace(st.session_state.state)
elif page=="Agent graph":
    st.title("Agent execution graph");state=st.session_state.get("state");render_graph_safe(graph(state)) if state else st.info("Run a case to view its actual traversed graph. Nodes only appear when the agent emitted their events.")
elif page=="Enterprise data":
    st.title("Enterprise data explorer");table=st.selectbox("Dataset",["customers","orders","payments","inventory","refunds","replacements","shipments","cases"]);limit=st.select_slider("Rows",options=[10,25,50,100],value=25);st.dataframe(rows(f"SELECT * FROM {table} LIMIT {limit}"),use_container_width=True,hide_index=True)
else:
    st.markdown("<div class='demo-hero'><div class='demo-kicker'>Controlled environment</div><h1>Demo & simulation</h1><p class='sub'>Create reproducible enterprise conditions without polluting the normal customer-resolution workflow. Every injected condition affects the actual service layer.</p></div>",unsafe_allow_html=True)
    a,b,c=st.columns(3)
    with a:st.markdown("<div class='demo-card'><b>01 · Seed conditions</b><p>Restore either the inventory-blocked adaptation path or a successful replacement path.</p></div>",unsafe_allow_html=True)
    with b:st.markdown("<div class='demo-card'><b>02 · Inject a real fault</b><p>Simulate a transient service outage or a verification mismatch. The agent must respond to the tool result.</p></div>",unsafe_allow_html=True)
    with c:st.markdown("<div class='demo-card'><b>03 · Inspect evidence</b><p>Run the flagship case and review its trace, state diff, graph, and persistent audit trail.</p></div>",unsafe_allow_html=True)
    st.markdown("### Configure a test run")
    left,right=st.columns(2)
    with left:scenario=st.selectbox("Seed state",["adaptation","replacement"],format_func=lambda value:"Replacement blocked → refund fallback" if value=="adaptation" else "Inventory available → successful replacement")
    with right:failures=st.multiselect("Inject one-time service failures",["refund_api_temporarily_unavailable","replacement_api_temporarily_unavailable","verification_failure"],placeholder="No fault injection")
    action1,action2,_=st.columns([1,1,2])
    with action1:
        if st.button("Reset enterprise state",use_container_width=True):reset_database(DEFAULT_DB,scenario);st.session_state.pop("state",None);st.success("Enterprise state reset.")
    with action2:
        if st.button("Run flagship case",type="primary",use_container_width=True):run_case("My headphones arrived damaged and I want a replacement.","CASE-100",failures);workspace(st.session_state.state)
