"""A narrow, validated boundary between agent decisions and enterprise operations."""
from __future__ import annotations
from typing import Callable, Any
from models.schemas import ToolResult
from services.enterprise import Enterprise

class ToolRegistry:
    def __init__(self, enterprise: Enterprise):
        self.enterprise = enterprise
        self._tools: dict[str, Callable[..., ToolResult]] = {
            "GET_CUSTOMER": enterprise.customer, "GET_ORDER": enterprise.order,
            "SEARCH_CUSTOMER": enterprise.search_customer, "RESOLVE_CASE": enterprise.resolve_case_request,
            "GET_INVENTORY": enterprise.inventory, "CHECK_POLICY": enterprise.policy, "GET_PAYMENT": enterprise.payment, "GET_SHIPMENT": enterprise.shipment,
            "GET_CASE_HISTORY": enterprise.case_history, "SEARCH_POLICY": enterprise.search_policy,
            "CREATE_REFUND": enterprise.refund, "CREATE_REPLACEMENT": enterprise.replacement,
            "CANCEL_ORDER": enterprise.cancel, "GENERATE_RETURN_LABEL": enterprise.return_label,
            "REVERSE_DUPLICATE_CHARGE": enterprise.duplicate_charge, "ESCALATE": enterprise.escalate,
            "CREATE_APPROVAL_TASK": enterprise.create_approval_task, "REQUEST_CUSTOMER_INFO": enterprise.request_customer_info, "VERIFY": enterprise.verify,
        }
    @property
    def names(self) -> tuple[str, ...]: return tuple(self._tools)
    def schemas(self) -> list[dict[str, Any]]:
        """Compact function-calling contracts supplied to every decision turn."""
        fields={
            "GET_CUSTOMER":["customer_id"],"GET_ORDER":["order_id"],"GET_PAYMENT":["order_id"],"GET_SHIPMENT":["order_id"],"GET_INVENTORY":["product_id","warehouse_id"],"SEARCH_CUSTOMER":["identifier"],"GET_CASE_HISTORY":["case_id"],"SEARCH_POLICY":["query","limit"],"RESOLVE_CASE":["request","customer_context"],"CHECK_POLICY":["order_id","action"],
            "CREATE_REFUND":["case_id","order_id","reason","amount","item_id","quantity"],"CREATE_REPLACEMENT":["case_id","order_id","product_id","reason"],"CANCEL_ORDER":["case_id","order_id","reason"],"REVERSE_DUPLICATE_CHARGE":["case_id","order_id"],"GENERATE_RETURN_LABEL":["case_id","order_id","sku"],"CREATE_APPROVAL_TASK":["case_id","reason","amount","evidence"],"ESCALATE":["case_id","reason"],"REQUEST_CUSTOMER_INFO":["case_id","question","investigation_id"],"VERIFY":["case_id","order_id","action"]}
        return [{"name": name, "input_schema": {"type":"object", "properties":{field:{"type":"number" if field in {"amount","quantity","limit"} else "string"} for field in fields.get(name,[])},"additionalProperties": False},
                 "description": "Mutating calls are policy-gated and idempotent." if name.startswith(("CREATE_","CANCEL","REVERSE","ESCALATE","GENERATE","REQUEST")) else "Read-only enterprise query."}
                for name in self.names]
    def execute(self, name: str, **inputs: Any) -> ToolResult:
        if name not in self._tools:
            return ToolResult(success=False, error_type="INVALID_TOOL", message=f"Tool {name} is not registered")
        try:
            return self._tools[name](**inputs)
        except (KeyError, TypeError) as exc:
            return ToolResult(success=False, error_type="INVALID_INPUT", message=f"Invalid inputs for {name}: {exc}")
