"""Held-out, language-varied checks: none route on the stored issue_type."""
from agent.graph import ResolutionAgent
from services.enterprise import Enterprise
from storage.database import connect, reset_database
from services.policy_rag import PolicyRAG

def test_policy_search_is_similarity_retrieval_not_case_lookup():
    results=PolicyRAG().search("my card was charged twice for the same purchase")
    assert results and results[0]["id"]=="duplicate-charge"

def test_combined_request_sequences_verified_payment_and_product_remedies(tmp_path):
    db=tmp_path/"combined.db";reset_database(db,"replacement")
    state=ResolutionAgent(Enterprise(str(db))).run("CASE-200","My speaker arrived damaged and I was charged twice")
    tools=[call["tool"] for call in state.tool_calls]
    assert state.final_status=="RESOLVED"
    assert tools.index("REVERSE_DUPLICATE_CHARGE") < tools.index("CREATE_REFUND")
    c=connect(db)
    assert c.execute("SELECT count(*) FROM payments WHERE order_id='ORD-2042' AND status='REVERSED'").fetchone()[0]==1
    assert c.execute("SELECT count(*) FROM refunds WHERE order_id='ORD-2042'").fetchone()[0]==1
    c.close()

def test_vague_request_without_authenticated_scope_never_selects_customer(tmp_path):
    db=tmp_path/"isolation.db";reset_database(db)
    state=ResolutionAgent(Enterprise(str(db))).run(None,"My headphones are broken",customer_context=None)
    assert state.final_status=="NEEDS_CLARIFICATION"
    assert state.case_id=="UNRESOLVED"

def test_partial_refund_preserves_remaining_order_state(tmp_path):
    db=tmp_path/"partial.db";reset_database(db)
    result=Enterprise(str(db)).refund("CASE-100","ORD-1042","One unit is damaged",amount=40,item_id="ITEM-1042",quantity=1)
    c=connect(db);order=c.execute("SELECT status,payment_status FROM orders WHERE id='ORD-1042'").fetchone();payment=c.execute("SELECT refunded_amount FROM payments WHERE order_id='ORD-1042'").fetchone();c.close()
    assert result.success and result.data["status"]=="PARTIALLY_REFUNDED"
    assert order["status"]=="DELIVERED" and order["payment_status"]=="PAID" and payment["refunded_amount"]==40
