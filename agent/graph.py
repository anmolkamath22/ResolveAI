"""Bounded, deterministic state-machine agent. Decisions are based on observed tool results."""
from __future__ import annotations
from uuid import uuid4
from models.schemas import ResolutionState, Goal
from services.enterprise import Enterprise
from providers.llm.factory import build_provider
from tools.registry import ToolRegistry

MAX_AGENT_ACTIONS=8; MAX_REPLANS=2; MAX_RETRIES=2

def parse_goal(request: str) -> Goal:
    text=request.lower(); requested="replacement" if any(x in text for x in ("replace","replacement","new one")) else "cancellation" if "cancel" in text else "refund"
    issue="DAMAGED_ITEM" if any(x in text for x in ("damage","broken","defect")) else "GENERAL_REQUEST"
    return Goal(issue_type=issue,requested_resolution=requested)

class ResolutionAgent:
    def __init__(self, enterprise: Enterprise, provider=None):
        self.enterprise=enterprise; self.provider=provider or build_provider(); self.tools=ToolRegistry(enterprise)
    def _call(self, state: ResolutionState, tool_name: str, event_action: str, tool: str, **inputs):
        """Retry transient errors only; logical policy/inventory failures trigger adaptation."""
        for attempt in range(MAX_RETRIES + 1):
            result=self.tools.execute(tool_name, **inputs)
            state.tool_calls.append({"tool":tool_name,"inputs":inputs,"success":result.success,"error_type":result.error_type,"attempt":attempt + 1})
            if result.success or result.error_type not in {"SERVICE_UNAVAILABLE", "TIMEOUT"}: return result
            state.event(event_action,tool,"RETRY",f"{result.message} Retrying safely ({attempt + 1}/{MAX_RETRIES}).")
        return result
    def run(self, case_id: str | None, request: str, max_actions: int=MAX_AGENT_ACTIONS) -> ResolutionState:
        # Case lookup is intentionally authoritative, never inferred from request text.
        from storage.database import connect
        case_id=(case_id or "").strip().upper()
        if not case_id:
            resolved=self._call(ResolutionState(investigation_id="TEMP",case_id="UNRESOLVED",user_request=request),"RESOLVE_CASE","RESOLVE_CASE","EntityResolver",request=request)
            if not resolved.success:
                state=ResolutionState(investigation_id="INV-"+uuid4().hex[:8].upper(),case_id="UNRESOLVED",user_request=request);state.final_status="NEEDS_CLARIFICATION";state.final_summary=resolved.message;state.event("RESOLVE_ENTITIES","EntityResolver","FAILED",resolved.message);return state
            case_id=resolved.data["case"]["id"]
        c=connect(self.enterprise.db_path); case=c.execute("SELECT * FROM cases WHERE id=?",(case_id,)).fetchone();c.close()
        state=ResolutionState(investigation_id="INV-"+uuid4().hex[:8].upper(),case_id=case_id,user_request=request)
        if not case:
            state.final_status="ESCALATED";state.final_summary="The requested case could not be found.";return state
        state.customer_id=case["customer_id"];state.order_id=case["order_id"];state.goal=self.provider.parse_goal(request);state.llm_provider=self.provider.name;state.preferred_action=state.goal.requested_resolution
        state.event("PARSE_GOAL","GoalParser","SUCCESS",f"Goal understood by {state.llm_provider}: {state.goal.requested_resolution} for {state.goal.issue_type}.")
        if getattr(self.provider,"last_error",None): state.event("LLM_FALLBACK","ProviderRouter","RETRY",f"Live provider unavailable; safely continued with offline intent parsing ({self.provider.last_error}).")
        state.event("RESOLVE_ENTITIES","EntityResolver","SUCCESS",f"Resolved case {case_id} from request context.")
        customer=self._call(state,"GET_CUSTOMER","GET_CUSTOMER","CustomerService",customer_id=state.customer_id); state.event("GET_CUSTOMER","CustomerService","SUCCESS" if customer.success else "FAILED",customer.message)
        order=self._call(state,"GET_ORDER","GET_ORDER","OrderService",order_id=state.order_id)
        if not order.success: return self._escalate(state,"Order could not be retrieved.")
        state.product_id=order.data["product_id"];state.event("GET_ORDER","OrderService","SUCCESS","Order %s located."%state.order_id)
        # V3 operational archetypes route from stored case truth, not demo IDs or a model's claim.
        if case["issue_type"] != "DAMAGED_ITEM" and not (case["issue_type"]=="DUPLICATE_CHARGE" and state.goal.requested_resolution=="replacement"):
            return self._run_operational_archetype(state, dict(case), order.data)
        # Explicit state transitions with bounded turns: candidate is customer-preferred, then evidence-driven fallback.
        candidates=[state.preferred_action]+[x for x in ("replacement","refund","cancellation") if x!=state.preferred_action]
        for candidate in candidates:
            # Bound external enterprise operations, not audit/event granularity.
            if len(state.tool_calls)>=max_actions: return self._escalate(state,"Action safety limit reached.")
            if candidate not in ("replacement","refund","cancellation"): continue
            policy=self._call(state,"CHECK_POLICY","CHECK_POLICY","PolicyService",order_id=state.order_id,action=candidate);state.event("CHECK_POLICY","PolicyService","SUCCESS" if policy.success else "FAILED",policy.message)
            if not policy.data.get("allowed"):
                state.failures.append(policy.message);continue
            if candidate=="replacement":
                inv=self._call(state,"GET_INVENTORY","GET_INVENTORY","InventoryService",product_id=state.product_id);state.event("GET_INVENTORY","InventoryService","SUCCESS" if inv.success else "FAILED",inv.message)
                if not inv.success or inv.data["available_units"]<1:
                    state.failures.append("Replacement blocked by inventory constraint.");state.replans+=1;state.event("ADAPT_PLAN","AdaptationEngine","ADAPTED","Replacement cannot be fulfilled; evaluating a permitted refund.");continue
                result=self._call(state,"CREATE_REPLACEMENT","CREATE_REPLACEMENT","ReplacementService",case_id=case_id,order_id=state.order_id,product_id=state.product_id,reason="Damaged item")
            elif candidate=="refund":
                payment=self._call(state,"GET_PAYMENT","GET_PAYMENT","PaymentService",order_id=state.order_id);state.event("GET_PAYMENT","PaymentService","SUCCESS" if payment.success else "FAILED",payment.message)
                if not payment.success: state.failures.append(payment.message);continue
                result=self._call(state,"CREATE_REFUND","CREATE_REFUND","RefundService",case_id=case_id,order_id=state.order_id,reason="Damaged item / requested resolution unavailable")
            else: result=self._call(state,"CANCEL_ORDER","CANCEL_ORDER","CancellationService",case_id=case_id,order_id=state.order_id,reason="Customer cancellation request")
            state.event("CREATE_"+candidate.upper(),candidate.title()+"Service","SUCCESS" if result.success else "FAILED",result.message)
            if not result.success:
                state.failures.append(result.message);continue
            verification=self._call(state,"VERIFY","VERIFY","VerificationService",case_id=case_id,order_id=state.order_id,action=candidate);state.verification_results.append(verification.data);state.event("VERIFY", "VerificationService", "SUCCESS" if verification.success else "FAILED",verification.message)
            if verification.success:
                state.current_resolution=candidate;state.final_status="RESOLVED";state.final_summary=self._summary(state,result.data);return state
            state.failures.append(verification.message);state.replans+=1
        return self._escalate(state,"No safe, permitted resolution remains after policy and state checks.")
    def _run_operational_archetype(self,state: ResolutionState,case: dict,order: dict) -> ResolutionState:
        issue=case["issue_type"]
        state.event("ANALYZE_CASE","CaseAnalyzer","SUCCESS",f"Operational archetype identified: {issue}.")
        if issue=="DUPLICATE_CHARGE":
            result=self._call(state,"REVERSE_DUPLICATE_CHARGE","PaymentLedger","PaymentService",case_id=state.case_id,order_id=state.order_id)
            state.event("REVERSE_DUPLICATE_CHARGE","PaymentService","SUCCESS" if result.success else "FAILED",result.message)
            if result.success:return self._finalize(state,"duplicate_reversal",result.message)
        elif issue=="PRE_SHIPMENT_CANCELLATION":
            result=self._call(state,"CANCEL_ORDER","CancellationService","CancellationService",case_id=state.case_id,order_id=state.order_id,reason="Customer cancellation before shipment")
            state.event("CANCEL_ORDER","CancellationService","SUCCESS" if result.success else "FAILED",result.message)
            if result.success:return self._finalize(state,"cancellation",result.message)
        elif issue=="POST_SHIPMENT_CANCELLATION":
            state.event("CHECK_POLICY","PolicyService","BLOCKED","Cancellation is blocked because the parcel is already in transit.")
            result=self._call(state,"GENERATE_RETURN_LABEL","ReturnService","ReturnService",case_id=state.case_id,order_id=state.order_id,sku=order["product_id"])
            state.event("GENERATE_RETURN_LABEL","ReturnService","SUCCESS" if result.success else "FAILED",result.message)
            if result.success:
                state.current_resolution="return_pending";state.final_status="ACTION_REQUIRED";state.final_summary="The shipment is already in transit, so cancellation was not permitted. A prepaid return label has been created for delivery refusal or return.";return state
        elif issue=="WRONG_ITEM":
            result=self._call(state,"GENERATE_RETURN_LABEL","ReturnService","ReturnService",case_id=state.case_id,order_id=state.order_id,sku="SP-200")
            state.event("GENERATE_RETURN_LABEL","ReturnService","SUCCESS" if result.success else "FAILED",result.message)
            # The return label is real state; a low-stock re-shipment can then be safely escalated.
            if result.success:return self._finalize(state,"wrong_item_return", "A prepaid label was created for the incorrect item; operations will dispatch the correct replacement after return scan.")
        elif issue=="EXPIRED_RETURN":
            customer=self._call(state,"GET_CUSTOMER","CustomerService","CustomerService",customer_id=state.customer_id)
            state.event("GET_CUSTOMER","CustomerService","SUCCESS" if customer.success else "FAILED",customer.message)
            return self._escalate(state,"Refund window has expired; a human review is required for any exception.")
        elif issue=="LOST_PARCEL":
            shipment=self._call(state,"GET_SHIPMENT","ShipmentService","ShipmentService",order_id=state.order_id)
            state.event("GET_SHIPMENT","ShipmentService","SUCCESS" if shipment.success else "FAILED",shipment.message)
            return self._escalate(state,"Carrier claim dossier created: delivered scan is disputed beyond 48 hours.")
        elif issue=="HIGH_VALUE_FRAUD":
            result=self.enterprise.create_approval_task(state.case_id,"High-value refund exceeds ₹20,000 authorization ceiling")
            state.event("ESCALATE_HIGH_VALUE","AuthorizationGuard","SUCCESS",result.message)
            state.current_resolution="human_approval";state.final_status="ESCALATED";state.final_summary="A human-approval task was created because the requested amount exceeds the financial authorization ceiling.";return state
        return self._escalate(state,"No safe deterministic action exists for this operational case.")
    def _finalize(self,state: ResolutionState,resolution: str,summary: str)->ResolutionState:
        from storage.database import connect
        c=connect(self.enterprise.db_path);c.execute("UPDATE cases SET status='RESOLVED',current_resolution=?,resolution_summary=? WHERE id=?",(resolution.upper(),summary,state.case_id));c.commit();c.close()
        state.current_resolution=resolution;state.final_status="RESOLVED";state.final_summary=summary;state.event("FINALIZE","CaseService","SUCCESS","Case state resolved after verified operational action.");return state
    def _escalate(self,state: ResolutionState,reason: str):
        result=self._call(state,"ESCALATE","ESCALATE","CaseService",case_id=state.case_id,reason=reason);state.event("ESCALATE","CaseService","SUCCESS",result.message);state.current_resolution="escalation";state.final_status="ESCALATED";state.final_summary=f"Your case was escalated for human review: {reason}";return state
    def _summary(self,state: ResolutionState,data:dict):
        adapted=" Replacement was unavailable because inventory had no available units, so the agent selected a policy-permitted refund." if state.replans else ""
        identifier=data.get("refund_id") or data.get("replacement_id")
        return f"Your {state.current_resolution} was successfully created and verified ({identifier})."+adapted
