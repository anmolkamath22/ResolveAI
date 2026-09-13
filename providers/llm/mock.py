from models.schemas import Goal, AgentDecision, AgentAction, TerminalDecision
from providers.llm.base import LLMProvider

class OfflineTestStubProvider(LLMProvider):
    """Deterministic unit-test stub, not a generalization-capable reasoning engine.

    If this provider appears in a demo/evaluation trace, provider configuration or
    connectivity failed. Its narrow phrase handling must never be presented as LLM
    reasoning.
    """
    def parse_goal(self, request: str) -> Goal:
        text=request.lower()
        resolution="replacement" if "replace" in text else "cancellation" if "cancel" in text else "refund"
        return Goal(issue_type="DAMAGED_ITEM" if any(x in text for x in ("damaged","broken","defect")) else "GENERAL_REQUEST",requested_resolution=resolution)
    @property
    def name(self) -> str: return "offline-demo"
    def decide(self, context: dict) -> AgentDecision:
        request=context["request"].lower(); snapshot=context.get("snapshot", {}); calls=context.get("tool_calls", [])
        succeeded={call["tool"] for call in calls if call.get("success")}
        last=calls[-1] if calls else {}
        def act(tool: str, rationale: str, **inputs: object) -> AgentDecision:
            return AgentDecision(reasoning=rationale, action=AgentAction(tool=tool,inputs=inputs,reason=rationale))
        if "SEARCH_POLICY" not in succeeded:
            return act("SEARCH_POLICY","Retrieve relevant policy before proposing any customer action.",query=context["request"])
        for tool, key in (("GET_CUSTOMER","customer_id"),("GET_ORDER","order_id"),("GET_PAYMENT","order_id"),("GET_SHIPMENT","order_id")):
            if tool not in succeeded and snapshot.get(key): return act(tool,"Gather authoritative case state before acting.",**({"customer_id":snapshot[key]} if tool=="GET_CUSTOMER" else {"order_id":snapshot[key]}))
        if context.get("pending_action"):
            return act("VERIFY","Independently verify the last successful mutation before any resolved outcome.",case_id=snapshot["case_id"],order_id=snapshot["order_id"],action=context["pending_action"])
        # Non-transient denials are observations, not instructions to retry.
        denied=last.get("error_type") in {"POLICY_DENIED","INVENTORY_UNAVAILABLE","PAYMENT_STATE_INVALID","VERIFICATION_FAILED"}
        order=context.get("order",{}); amount=float(order.get("amount",0) or 0); product=order.get("product_id")
        duplicate_attempted=any(call["tool"]=="REVERSE_DUPLICATE_CHARGE" for call in calls)
        has_duplicate=any(call["tool"]=="REVERSE_DUPLICATE_CHARGE" and call.get("success") for call in calls)
        wants_duplicate=any(word in request for word in ("charged twice","double charged","duplicate charge","duplicate payment"))
        wants_cancel=any(word in request for word in ("cancel","address change"))
        wants_damage=any(word in request for word in ("damage","broken","defect","wrong item","missing part","mis-shipped"))
        wants_replace=any(word in request for word in ("replace","replacement","wrong item","mis-shipped"))
        if wants_duplicate and not duplicate_attempted:
            return act("REVERSE_DUPLICATE_CHARGE","The request reports an additional charge, so inspect and reverse only a confirmed duplicate.",case_id=snapshot["case_id"],order_id=snapshot["order_id"])
        if wants_cancel and not denied:
            return act("CANCEL_ORDER","The customer requested cancellation; the service will enforce shipment policy.",case_id=snapshot["case_id"],order_id=snapshot["order_id"],reason="Customer requested cancellation")
        if wants_cancel and (last.get("error_type")=="POLICY_DENIED" or order.get("status") in {"SHIPPED","DELIVERED"}):
            return act("GENERATE_RETURN_LABEL","Cancellation is unavailable after dispatch; a return workflow is the safe next option.",case_id=snapshot["case_id"],order_id=snapshot["order_id"],sku=product or "UNKNOWN")
        if wants_damage and wants_replace and "GET_INVENTORY" not in succeeded and product:
            return act("GET_INVENTORY","Check actual inventory before promising a replacement.",product_id=product)
        inventory=context.get("inventory",{}).get("available_units",0)
        if wants_damage and wants_replace and "GET_INVENTORY" in succeeded and not denied:
            return act("CREATE_REPLACEMENT","Inventory and policy will be checked server-side for the requested replacement.",case_id=snapshot["case_id"],order_id=snapshot["order_id"],product_id=product,reason="Customer reports an affected item")
        if wants_damage or "refund" in request or denied:
            if amount>20000:
                return act("CREATE_APPROVAL_TASK","The requested financial remedy exceeds delegated authority and needs bounded human approval.",case_id=snapshot["case_id"],reason="Amount exceeds automated authorization threshold",amount=amount,evidence=context["request"])
            if last.get("error_type")=="POLICY_DENIED":
                return act("ESCALATE","The deterministic policy gate denied the requested remedy; preserve the evidence for human review.",case_id=snapshot["case_id"],reason=last.get("message","Policy denied a requested action"))
            return act("CREATE_REFUND","A refund is the remaining policy-gated remedy for the affected order.",case_id=snapshot["case_id"],order_id=snapshot["order_id"],reason="Customer reported a product or fulfillment problem")
        return AgentDecision(reasoning="The evidence does not identify a permitted automated remedy.",terminal=TerminalDecision(status="ESCALATED",reason="Insufficient policy-grounded evidence",summary="A specialist will review the case with the investigation evidence."))
