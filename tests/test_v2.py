from pathlib import Path
from agent.graph import ResolutionAgent
from services.enterprise import Enterprise
from storage.database import connect, reset_database

def test_free_form_flagship_request_resolves_from_active_customer_context(tmp_path):
    db=tmp_path/"v2.db";reset_database(db,"adaptation")
    state=ResolutionAgent(Enterprise(str(db))).run(None,"My headphones arrived damaged and I want a replacement.")
    assert state.case_id=="CASE-100" and state.final_status=="RESOLVED" and state.current_resolution=="refund"
    assert {"RESOLVE_ENTITIES","GET_PAYMENT","ADAPT_PLAN","VERIFY"}.issubset({event.action for event in state.action_history})

def test_payment_state_and_refunded_amount_are_mutated_and_verified(tmp_path):
    db=tmp_path/"payment.db";reset_database(db,"adaptation")
    state=ResolutionAgent(Enterprise(str(db))).run("CASE-100","Refund my damaged headphones")
    c=connect(db);payment=c.execute("SELECT status,refunded_amount FROM payments WHERE order_id='ORD-1042'").fetchone();c.close()
    assert state.final_status=="RESOLVED"
    assert payment["status"]=="REFUNDED" and payment["refunded_amount"]==129.99

def test_unmatched_free_form_request_asks_for_targeted_clarification(tmp_path):
    db=tmp_path/"unknown.db";reset_database(db,"adaptation")
    state=ResolutionAgent(Enterprise(str(db))).run(None,"My toaster is broken")
    assert state.final_status=="NEEDS_CLARIFICATION"
    assert "order ID" in state.final_summary
