"""Authoritative business services. Natural-language input never mutates storage directly."""
from __future__ import annotations
from uuid import uuid4
from storage.database import connect
from models.schemas import ToolResult
from demo.failures import FailureInjector

class Enterprise:
    def __init__(self, db_path: str, failures: FailureInjector | None = None):
        self.db_path=db_path; self.failures=failures or FailureInjector()
    def _transient(self, operation: str) -> ToolResult | None:
        scenario=self.failures.consume(operation)
        if scenario:
            return ToolResult(success=False,error_type="SERVICE_UNAVAILABLE",message=f"Simulated transient failure: {scenario}.")
        return None
    def _one(self, sql: str, args: tuple=()):
        c=connect(self.db_path); r=c.execute(sql,args).fetchone(); c.close(); return dict(r) if r else None
    def customer(self, customer_id: str):
        row=self._one("SELECT * FROM customers WHERE id=?",(customer_id,)); return ToolResult(success=bool(row),data=row or {},error_type=None if row else "NOT_FOUND",message="Customer identified" if row else "Customer not found")
    def search_customer(self, identifier: str):
        needle=f"%{identifier.strip().lower()}%";c=connect(self.db_path)
        rows=c.execute("SELECT * FROM customers WHERE lower(id) LIKE ? OR lower(name) LIKE ? OR lower(email) LIKE ? LIMIT 6",(needle,needle,needle)).fetchall();c.close()
        data=[dict(row) for row in rows]
        return ToolResult(success=bool(data),data={"matches":data},error_type=None if data else "NOT_FOUND",message=f"Found {len(data)} customer match(es)")
    def order(self, order_id: str):
        row=self._one("SELECT * FROM orders WHERE id=?",(order_id,)); return ToolResult(success=bool(row),data=row or {},error_type=None if row else "NOT_FOUND",message="Order located" if row else "Order not found")
    def payment(self, order_id: str):
        row=self._one("SELECT * FROM payments WHERE order_id=?",(order_id,));return ToolResult(success=bool(row),data=row or {},error_type=None if row else "NOT_FOUND",message="Payment record located" if row else "Payment record not found")
    def shipment(self, order_id: str):
        row=self._one("SELECT * FROM shipments WHERE order_id=?",(order_id,));return ToolResult(success=bool(row),data=row or {},error_type=None if row else "NOT_FOUND",message="Shipment record located" if row else "Shipment record not found")
    def resolve_case_request(self, request: str, customer_context: str = "CUS-100"):
        """Resolve explicit IDs first, otherwise match a uniquely-described open customer case."""
        import re
        text=request.lower(); c=connect(self.db_path)
        case_id=re.search(r"case[- ]?(\d+)",text)
        order_id=re.search(r"ord[- ]?(\d+)",text)
        if case_id:
            row=c.execute("SELECT * FROM cases WHERE lower(id)=?",(f"case-{case_id.group(1)}",)).fetchone();c.close();return ToolResult(success=bool(row),data={"case":dict(row)} if row else {},error_type=None if row else "NOT_FOUND",message="Case resolved from request" if row else "Case identifier not found")
        if order_id:
            row=c.execute("SELECT c.* FROM cases c WHERE lower(c.order_id)=?",(f"ord-{order_id.group(1)}",)).fetchone();c.close();return ToolResult(success=bool(row),data={"case":dict(row)} if row else {},error_type=None if row else "NOT_FOUND",message="Order resolved to case" if row else "Order identifier not found")
        rows=c.execute("SELECT c.* FROM cases c JOIN orders o ON c.order_id=o.id JOIN customers u ON c.customer_id=u.id WHERE c.status IN ('OPEN','INVESTIGATING') AND (lower(o.product_name) LIKE ? OR lower(c.description) LIKE ? OR lower(u.name) LIKE ? OR lower(u.email) LIKE ?) LIMIT 3",(f"%{text}%",f"%{text}%",f"%{text}%",f"%{text}%")).fetchall()
        if not rows:
            # Product-token matching supports conversational forms such as “my headphones”.
            candidates=c.execute("SELECT c.*,o.product_name FROM cases c JOIN orders o ON c.order_id=o.id WHERE c.status='OPEN' AND c.customer_id=?",(customer_context,)).fetchall()
            if not candidates:
                candidates=c.execute("SELECT c.*,o.product_name FROM cases c JOIN orders o ON c.order_id=o.id WHERE c.status='OPEN'").fetchall()
            request_terms={term for term in re.findall(r"[a-z]{4,}",text) if term not in {"want","need","refund","replace","replacement","damaged","order","item"}}
            rows=[row for row in candidates if request_terms & set(re.findall(r"[a-z]{4,}",row["product_name"].lower()))][:3]
        c.close();matches=[dict(row) for row in rows]
        if len(matches)==1:return ToolResult(success=True,data={"case":matches[0]},message="Case resolved from product/customer context")
        if len(matches)>1:return ToolResult(success=False,data={"matches":matches},error_type="AMBIGUOUS_ENTITY",message="More than one open case matches; provide an order ID, email, or case ID.")
        return ToolResult(success=False,error_type="MISSING_ENTITY",message="I could not match this request to one case. Include an order ID, customer email, or product.")
    def inventory(self, product_id: str, warehouse_id: str | None = None):
        c=connect(self.db_path)
        query="SELECT * FROM inventory WHERE product_id=?"+(" AND warehouse_id=?" if warehouse_id else "")
        rows=c.execute(query,(product_id,warehouse_id) if warehouse_id else (product_id,)).fetchall();c.close()
        records=[dict(row) for row in rows];available=sum(row["available_units"] for row in records)
        return ToolResult(success=bool(records),data={"product_id":product_id,"warehouses":records,"available_units":available},error_type=None if records else "NOT_FOUND",message=(f"{available} eligible units across {len(records)} warehouse(s)" if records else "Inventory not found"))
    def policy(self, order_id: str, action: str):
        o=self._one("SELECT * FROM orders WHERE id=?",(order_id,))
        if not o: return ToolResult(success=False,error_type="NOT_FOUND",message="Order not found")
        key={"replacement":"eligible_replacement","refund":"eligible_refund","cancellation":"cancellation_allowed"}[action]
        allowed=bool(o[key]) and o["payment_status"]=="PAID" and o["status"] not in ("REFUNDED","REPLACED","CANCELLED")
        reason=(f"{action.title()} is permitted by deterministic policy" if allowed else f"{action.title()} is not permitted for this order")
        return ToolResult(success=True,data={"allowed":allowed,"action":action,"reason":reason,"amount":o["amount"]},message=reason)
    def _audit(self,c,case_id,action,before,after,reason,verification="PENDING"): c.execute("INSERT INTO audit_events(case_id,action,tool,before_state,after_state,reason,verification_status) VALUES(?,?,?,?,?,?,?)",(case_id,action,"Enterprise",before,after,reason,verification))
    def refund(self, case_id: str, order_id: str, reason: str):
        if transient:=self._transient("refund"): return transient
        existing=self._one("SELECT * FROM refunds WHERE order_id=?",(order_id,))
        if existing: return ToolResult(success=True,data=existing,message="Existing refund returned (idempotent)")
        p=self.policy(order_id,"refund")
        if not p.data.get("allowed"): return ToolResult(success=False,error_type="POLICY_DENIED",message=p.message)
        c=connect(self.db_path); o=c.execute("SELECT * FROM orders WHERE id=?",(order_id,)).fetchone();payment=c.execute("SELECT * FROM payments WHERE order_id=? ORDER BY id LIMIT 1",(order_id,)).fetchone();rid="REF-"+uuid4().hex[:8].upper()
        if not payment or payment["status"]!="PAYMENT_CAPTURED":c.close();return ToolResult(success=False,error_type="PAYMENT_STATE_INVALID",message="Payment is not in a refundable captured state")
        if o["amount"]>20000:c.close();return self.create_approval_task(case_id,"Refund exceeds ₹20,000 authorization ceiling")
        c.execute("INSERT INTO refunds(id,order_id,case_id,amount,status,reason,payment_id,idempotency_key) VALUES(?,?,?,?,?,?,?,?)",(rid,order_id,case_id,o["amount"],"REFUNDED",reason,payment["id"],f"{case_id}:CREATE_REFUND"));c.execute("UPDATE payments SET status='REFUNDED',refunded_amount=? WHERE order_id=?",(o["amount"],order_id));c.execute("UPDATE orders SET payment_status='REFUNDED',status='REFUNDED' WHERE id=?",(order_id,));self._audit(c,case_id,"CREATE_REFUND","PAYMENT_CAPTURED","REFUNDED",reason);c.commit();c.close()
        return ToolResult(success=True,data={"refund_id":rid,"payment_id":payment["id"],"status":"REFUNDED","amount":o["amount"],"before_state":"PAYMENT_CAPTURED","after_state":"REFUNDED"},message="Refund created and payment state updated")
    def replacement(self, case_id: str, order_id: str, product_id: str, reason: str):
        if transient:=self._transient("replacement"): return transient
        existing=self._one("SELECT * FROM replacements WHERE order_id=?",(order_id,))
        if existing:return ToolResult(success=True,data=existing,message="Existing replacement returned (idempotent)")
        p=self.policy(order_id,"replacement"); inv=self.inventory(product_id)
        if not p.data.get("allowed"):return ToolResult(success=False,error_type="POLICY_DENIED",message=p.message)
        if not inv.success or inv.data["available_units"] < 1:return ToolResult(success=False,error_type="INVENTORY_UNAVAILABLE",message="No replacement inventory is available")
        warehouse=next(record for record in inv.data["warehouses"] if record["available_units"]>0)["warehouse_id"]
        c=connect(self.db_path);rid="REP-"+uuid4().hex[:8].upper();c.execute("UPDATE inventory SET available_units=available_units-1,reserved_units=reserved_units+1 WHERE product_id=? AND warehouse_id=?",(product_id,warehouse));c.execute("INSERT INTO replacements(id,order_id,case_id,product_id,warehouse_id,status,tracking_number) VALUES(?,?,?,?,?,?,?)",(rid,order_id,case_id,product_id,warehouse,"CONFIRMED",f"RPL-{rid[-8:]}"));c.execute("UPDATE orders SET status='REPLACED' WHERE id=?",(order_id,));self._audit(c,case_id,"CREATE_REPLACEMENT","DELIVERED","REPLACED",reason);c.commit();c.close();return ToolResult(success=True,data={"replacement_id":rid,"warehouse_id":warehouse,"status":"CONFIRMED"},message="Replacement created and stock reserved")
    def cancel(self, case_id: str, order_id: str, reason: str):
        """Idempotent cancellation guarded by the authoritative policy service."""
        o=self.order(order_id).data
        if o.get("status")=="CANCELLED": return ToolResult(success=True,data={"status":"CANCELLED"},message="Order was already cancelled (idempotent)")
        p=self.policy(order_id,"cancellation")
        if not p.data.get("allowed"): return ToolResult(success=False,error_type="POLICY_DENIED",message=p.message)
        c=connect(self.db_path);c.execute("UPDATE orders SET status='CANCELLED' WHERE id=?",(order_id,));self._audit(c,case_id,"CANCEL_ORDER",o["status"],"CANCELLED",reason);c.commit();c.close()
        return ToolResult(success=True,data={"status":"CANCELLED"},message="Order cancelled")
    def escalate(self,case_id: str,reason: str):
        c=connect(self.db_path); c.execute("UPDATE cases SET status='ESCALATED',current_resolution='ESCALATION' WHERE id=?",(case_id,)); self._audit(c,case_id,"ESCALATE","OPEN","ESCALATED",reason);c.commit();c.close();return ToolResult(success=True,data={"status":"ESCALATED"},message=reason)
    def return_label(self,case_id: str,order_id: str,sku: str):
        existing=self._one("SELECT * FROM return_labels WHERE order_id=?",(order_id,))
        if existing:return ToolResult(success=True,data=existing,message="Existing return label returned (idempotent)")
        c=connect(self.db_path);label="RMA-"+uuid4().hex[:8].upper();c.execute("INSERT INTO return_labels VALUES(?,?,?,?,?)",(label,order_id,sku,f"https://returns.resolveai.test/{label}","ACTIVE"));c.execute("UPDATE cases SET status='ACTION_REQUIRED',current_resolution='RETURN_PENDING' WHERE id=?",(case_id,));self._audit(c,case_id,"GENERATE_RETURN_LABEL","SHIPPED","RETURN_PENDING","Prepaid return label generated");c.commit();c.close();return ToolResult(success=True,data={"label_id":label,"status":"RETURN_PENDING"},message="Prepaid return label generated")
    def create_approval_task(self,case_id: str,reason: str):
        existing=self._one("SELECT * FROM approval_tasks WHERE case_id=?",(case_id,))
        if existing:return ToolResult(success=True,data=existing,message="Existing human approval task returned")
        c=connect(self.db_path);task="APR-"+uuid4().hex[:8].upper();c.execute("INSERT INTO approval_tasks VALUES(?,?,?,?,?)",(task,case_id,reason,"PENDING","financial threshold guard"));c.execute("UPDATE cases SET status='ESCALATED',current_resolution='HUMAN_APPROVAL' WHERE id=?",(case_id,));self._audit(c,case_id,"ESCALATE_HIGH_VALUE","ACTION_REQUIRED","ESCALATED",reason);c.commit();c.close();return ToolResult(success=True,data={"approval_id":task,"status":"PENDING"},message=reason)
    def duplicate_charge(self,case_id: str,order_id: str):
        c=connect(self.db_path);payments=c.execute("SELECT * FROM payments WHERE order_id=?",(order_id,)).fetchall()
        if len(payments)<2:c.close();return ToolResult(success=False,error_type="NO_DUPLICATE",message="No duplicate authorization found")
        duplicate=payments[-1];c.execute("UPDATE payments SET status='REVERSED',refunded_amount=amount WHERE id=?",(duplicate["id"],));c.execute("UPDATE cases SET status='RESOLVED',current_resolution='DUPLICATE_REVERSAL' WHERE id=?",(case_id,));self._audit(c,case_id,"REVERSE_DUPLICATE_CHARGE","PAYMENT_CAPTURED","REVERSED","Duplicate authorization token reversed","PASSED");c.commit();c.close();return ToolResult(success=True,data={"payment_id":duplicate["id"],"amount":duplicate["amount"],"status":"REVERSED"},message="Duplicate authorization reversed")
    def verify(self,case_id: str,order_id: str,action: str):
        if self.failures.verification_should_fail():
            return ToolResult(success=False,error_type="VERIFICATION_FAILED",message="Simulated verification mismatch; state was not marked resolved.")
        o=self.order(order_id).data; c=connect(self.db_path)
        if action=="refund":
            payment=c.execute("SELECT * FROM payments WHERE order_id=?",(order_id,)).fetchone();ok=o.get("payment_status")=="REFUNDED" and payment and payment["status"]=="REFUNDED" and c.execute("SELECT 1 FROM refunds WHERE order_id=?",(order_id,)).fetchone()
        else: ok=o.get("status")=="REPLACED" and c.execute("SELECT 1 FROM replacements WHERE order_id=?",(order_id,)).fetchone()
        if ok:c.execute("UPDATE cases SET status='RESOLVED',current_resolution=? WHERE id=?",(action.upper(),case_id));c.commit()
        c.close(); return ToolResult(success=bool(ok),data={"expected":action.upper(),"actual_payment_status":o.get("payment_status"),"actual_order_status":o.get("status"),"payment_state":"REFUNDED" if action=="refund" and ok else None},error_type=None if ok else "VERIFICATION_FAILED",message="State transition verified" if ok else "Expected state was not reached")
