from pathlib import Path
from storage.database import reset_database, connect
from services.enterprise import Enterprise
from agent.graph import ResolutionAgent
from demo.failures import FailureInjector
from reporting import resolution_report
from tools.registry import ToolRegistry

def run(tmp_path: Path, scenario: str, case: str, text: str):
    db=tmp_path/"demo.db";reset_database(db,scenario);return ResolutionAgent(Enterprise(str(db))).run(case,text),db

def test_inventory_blocked_adapts_to_verified_refund(tmp_path):
    state,db=run(tmp_path,"adaptation","CASE-100","My headphones arrived damaged. I want a replacement.")
    assert state.final_status=="RESOLVED" and state.current_resolution=="refund"
    assert state.replans==1 and any(x.action=="ADAPT_PLAN" for x in state.action_history)
    assert any(x.action=="CREATE_REFUND" and x.status=="SUCCESS" for x in state.action_history)
    assert state.verification_results
    c=connect(db);assert c.execute("SELECT payment_status FROM orders WHERE id='ORD-1042'").fetchone()[0]=="REFUNDED";c.close()

def test_available_inventory_creates_replacement(tmp_path):
    state,_=run(tmp_path,"replacement","CASE-200","My speaker arrived damaged. I want a replacement.")
    assert state.final_status=="RESOLVED" and state.current_resolution=="replacement"
    assert any(x.action=="CREATE_REPLACEMENT" for x in state.action_history)

def test_refund_is_idempotent(tmp_path):
    db=tmp_path/"demo.db";reset_database(db,"adaptation");e=Enterprise(str(db))
    first=e.refund("CASE-100","ORD-1042","test"); second=e.refund("CASE-100","ORD-1042","test")
    assert first.success and second.success
    assert first.data["refund_id"] == second.data["id"]

def test_policy_blocks_expired_refund(tmp_path):
    state,_=run(tmp_path,"adaptation","CASE-300","I want a refund for my damaged headphones")
    assert state.final_status=="ESCALATED"

def test_transient_refund_outage_is_retried_then_verified(tmp_path):
    db=tmp_path/"retry.db";reset_database(db,"adaptation")
    state=ResolutionAgent(Enterprise(str(db),FailureInjector({"refund_api_temporarily_unavailable"}))).run("CASE-100","My headphones arrived damaged. I want a replacement.")
    assert state.final_status=="RESOLVED"
    assert any(event.status=="RETRY" and event.action=="CREATE_REFUND" for event in state.action_history)

def test_registry_rejects_unregistered_tool_and_report_is_customer_safe(tmp_path):
    db=tmp_path/"registry.db";reset_database(db,"adaptation")
    assert ToolRegistry(Enterprise(str(db))).execute("DROP_DATABASE").error_type=="INVALID_TOOL"
    state=ResolutionAgent(Enterprise(str(db))).run("CASE-100","My headphones arrived damaged. I want a replacement.")
    report=resolution_report(state)
    assert "ResolveAI Resolution Report" in report and "prompt" not in report.lower()
