from storage.database import connect, reset_database
from services.enterprise import Enterprise
from agent.graph import ResolutionAgent

def test_v3_golden_suite_is_seeded(tmp_path):
    db=tmp_path/"v3.db";reset_database(db)
    c=connect(db);assert c.execute("SELECT count(*) FROM cases WHERE id BETWEEN 'CASE-100' AND 'CASE-800'").fetchone()[0]==8
    assert c.execute("SELECT count(*) FROM warehouses").fetchone()[0]==2;c.close()

def test_duplicate_charge_is_reversed_from_real_payment_ledger(tmp_path):
    db=tmp_path/"duplicate.db";reset_database(db)
    state=ResolutionAgent(Enterprise(str(db))).run("CASE-200","I was charged twice")
    c=connect(db);count=c.execute("SELECT count(*) FROM payments WHERE order_id='ORD-2042' AND status='REVERSED'").fetchone()[0];c.close()
    assert state.final_status=="RESOLVED" and state.current_resolution=="duplicate_reversal" and count==1

def test_post_shipment_cancellation_creates_real_return_label(tmp_path):
    db=tmp_path/"return.db";reset_database(db)
    state=ResolutionAgent(Enterprise(str(db))).run("CASE-500","Please cancel my order")
    c=connect(db);label=c.execute("SELECT status FROM return_labels WHERE order_id='ORD-5042'").fetchone();c.close()
    assert state.final_status=="ACTION_REQUIRED" and label["status"]=="ACTIVE"

def test_high_value_refund_creates_human_approval_task(tmp_path):
    db=tmp_path/"approval.db";reset_database(db)
    state=ResolutionAgent(Enterprise(str(db))).run("CASE-800","Refund my laptop")
    c=connect(db);task=c.execute("SELECT status FROM approval_tasks WHERE case_id='CASE-800'").fetchone();c.close()
    assert state.final_status=="ESCALATED" and task["status"]=="PENDING"
