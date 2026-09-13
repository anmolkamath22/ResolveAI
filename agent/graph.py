"""Bounded, observable observe → decide → execute agent loop."""
from __future__ import annotations
from collections.abc import Iterator
from uuid import uuid4
from models.schemas import ResolutionState, ToolResult
from services.enterprise import Enterprise
from providers.llm.factory import build_provider
from tools.registry import ToolRegistry
from storage.database import connect

MAX_TURNS=16; MAX_MUTATING_ACTIONS=6
MUTATING={"CREATE_REFUND","CREATE_REPLACEMENT","CANCEL_ORDER","REVERSE_DUPLICATE_CHARGE","GENERATE_RETURN_LABEL","CREATE_APPROVAL_TASK","ESCALATE","REQUEST_CUSTOMER_INFO"}
VERIFY_ACTION={"CREATE_REFUND":"refund","CREATE_REPLACEMENT":"replacement","CANCEL_ORDER":"cancellation","REVERSE_DUPLICATE_CHARGE":"duplicate_reversal","GENERATE_RETURN_LABEL":"return_label","CREATE_APPROVAL_TASK":"approval"}

class ResolutionAgent:
    def __init__(self,enterprise: Enterprise,provider=None): self.enterprise=enterprise;self.provider=provider or build_provider();self.tools=ToolRegistry(enterprise)
    def _observe(self,state,tool,inputs,result: ToolResult):
        state.tool_calls.append({"tool":tool,"inputs":inputs,"success":result.success,"error_type":result.error_type,"message":result.message,"data":result.data});state.observations.append(f"{tool}: {result.message}");state.event(tool,"ToolRegistry","SUCCESS" if result.success else "FAILED",result.message)
        if tool=="SEARCH_POLICY" and result.success:state.policy_citations.extend(result.data.get("snippets",[]))
        if not result.success:state.failures.append(result.message)
    def _execute(self,state,tool,inputs):
        result=self.tools.execute(tool,**inputs);self._observe(state,tool,inputs,result)
        if not result.success and result.error_type in {"SERVICE_UNAVAILABLE","TIMEOUT"}:
            state.event(tool,"RetryGuard","RETRY","Transient failure; one safe retry is allowed.");result=self.tools.execute(tool,**inputs);self._observe(state,tool,inputs,result)
        return result
    def _facts(self,state,case):
        values={"case_id":state.case_id,"customer_id":state.customer_id,"order_id":state.order_id,"case":case}
        for call in state.tool_calls:
            if call["success"]:
                key={"GET_ORDER":"order","GET_INVENTORY":"inventory","GET_CUSTOMER":"customer","GET_PAYMENT":"payment","GET_SHIPMENT":"shipment"}.get(call["tool"])
                if key:values[key]=call["data"]
        return values
    def _context(self,state,case):
        facts=self._facts(state,case)
        gates={action:self.enterprise.policy(state.order_id,action).data for action in ("refund","replacement","cancellation")} if state.order_id else {}
        return {"request":state.user_request,"snapshot":facts,"case":case,"order":facts.get("order",{}),"inventory":facts.get("inventory",{}),"tool_calls":state.tool_calls,"pending_action":state.pending_action,"policy_citations":state.policy_citations,"policy_gates":gates,"predicted_intent":self.enterprise.intent_classifier.classify(state.user_request,top_k=1),"available_tools":self.tools.schemas(),"error_handling":"Non-transient errors require a different action or escalation; tools are policy-gated."}
    def _terminal(self,state,status,summary,reason): state.final_status=status;state.final_summary=summary;state.event("TERMINAL","ResolutionAgent",status,reason);return state
    def _clarification(self,state,message):
        result=self._execute(state,"REQUEST_CUSTOMER_INFO",{"case_id":None if state.case_id=="UNRESOLVED" else state.case_id,"question":message,"investigation_id":state.investigation_id})
        if result.success:state.investigation_id=result.data["investigation_id"]
        return self._terminal(state,"NEEDS_CLARIFICATION",message,"Entity resolution requires a unique, authorized match.")
    def run(self,*args,**kwargs)->ResolutionState:
        final=None
        for final in self.run_streaming(*args,**kwargs): pass
        assert final is not None
        return final
    def run_streaming(self,case_id: str|None,request: str,max_actions: int=MAX_MUTATING_ACTIONS,customer_context: str|None="CUS-100",investigation_id: str|None=None)->Iterator[ResolutionState]:
        investigation_id=investigation_id or "INV-"+uuid4().hex[:8].upper();resolved_id=(case_id or "").strip().upper()
        if not resolved_id:
            temp=ResolutionState(investigation_id=investigation_id,case_id="UNRESOLVED",user_request=request);entity=self._execute(temp,"RESOLVE_CASE",{"request":request,"customer_context":customer_context})
            if not entity.success:yield self._clarification(temp,entity.message);return
            resolved_id=entity.data["case"]["id"]
        c=connect(self.enterprise.db_path);row=c.execute("SELECT * FROM cases WHERE id=?",(resolved_id,)).fetchone();c.close()
        if not row:yield self._clarification(ResolutionState(investigation_id=investigation_id,case_id=resolved_id or "UNRESOLVED",user_request=request),"That case could not be found. Please provide a valid order ID or case ID.");return
        case=dict(row);state=ResolutionState(investigation_id=investigation_id,case_id=resolved_id,user_request=request,customer_id=case["customer_id"],order_id=case["order_id"],llm_provider=self.provider.name);state.event("RESOLVE_ENTITIES","EntityResolver","SUCCESS",f"Resolved authorized case {resolved_id}.");yield state
        failures={}
        for _turn in range(MAX_TURNS):
            decision=self.provider.decide(self._context(state,case));state.llm_provider=self.provider.name
            if state.llm_provider=="offline-demo":
                state.provider_fallback_reason=getattr(self.provider,"last_error",None) or "No live provider configured"
                if not any(event.action=="PROVIDER_FALLBACK" for event in state.action_history):state.event("PROVIDER_FALLBACK","ProviderRouter","FALLBACK",state.provider_fallback_reason)
            state.event("LLM_DECISION",state.llm_provider,"SUCCESS",decision.reasoning)
            if decision.terminal:yield self._terminal(state,decision.terminal.status,decision.terminal.summary,decision.terminal.reason);return
            action=decision.action
            if not action:yield state;continue
            if action.tool not in self.tools.names:self._observe(state,action.tool,action.inputs,ToolResult(success=False,error_type="INVALID_TOOL",message="Requested tool is not available"));yield state;continue
            if action.tool in MUTATING and sum(c["tool"] in MUTATING and c["success"] for c in state.tool_calls)>=max_actions:yield self._terminal(state,"ESCALATED","A specialist will review this case.","Mutation safety limit reached.");return
            result=self._execute(state,action.tool,action.inputs)
            if not result.success:
                key=(action.tool,result.error_type);failures[key]=failures.get(key,0)+1;state.replans+=1;state.event("ADAPT_PLAN","ResolutionAgent","ADAPTED",f"{action.tool} returned {result.error_type}; provider will re-evaluate the observed state.")
                if failures[key]>=2:yield self._terminal(state,"ESCALATED","A specialist will review the blocked request.",f"Circuit breaker: {action.tool} repeated the same failure.");return
                yield state;continue
            if action.tool in VERIFY_ACTION:state.pending_action=VERIFY_ACTION[action.tool];state.current_resolution=state.pending_action;yield state;continue
            if action.tool=="VERIFY":
                state.verification_results.append(result.data);state.pending_action=None;state.event("VERIFY","VerificationService","SUCCESS","Independent verification passed.")
                status="ACTION_REQUIRED" if state.current_resolution=="return_label" else "ESCALATED" if state.current_resolution=="approval" else "RESOLVED";summary="A prepaid return label was created and verified." if status=="ACTION_REQUIRED" else "A human approval task was created and verified." if status=="ESCALATED" else f"Your {state.current_resolution} was completed and independently verified."
                combined=state.current_resolution=="duplicate_reversal" and any(word in state.user_request.lower() for word in ("damage","broken","defect","wrong item","missing part","mis-shipped"))
                if combined:state.event("CONTINUE_INVESTIGATION","ResolutionAgent","SUCCESS","The verified duplicate-charge remedy is complete; investigating the separately reported product issue.");yield state;continue
                yield self._terminal(state,status,summary,"Authoritative state transition verified.");return
            yield state
        self._execute(state,"ESCALATE",{"case_id":state.case_id,"reason":"Turn limit reached without a safe verified resolution"});yield self._terminal(state,"ESCALATED","A specialist will review the investigation.","Turn limit reached without a safe verified resolution.")
