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
            "CREATE_REFUND": enterprise.refund, "CREATE_REPLACEMENT": enterprise.replacement,
            "CANCEL_ORDER": enterprise.cancel, "GENERATE_RETURN_LABEL": enterprise.return_label,
            "REVERSE_DUPLICATE_CHARGE": enterprise.duplicate_charge, "ESCALATE": enterprise.escalate, "VERIFY": enterprise.verify,
        }
    @property
    def names(self) -> tuple[str, ...]: return tuple(self._tools)
    def execute(self, name: str, **inputs: Any) -> ToolResult:
        if name not in self._tools:
            return ToolResult(success=False, error_type="INVALID_TOOL", message=f"Tool {name} is not registered")
        try:
            return self._tools[name](**inputs)
        except (KeyError, TypeError) as exc:
            return ToolResult(success=False, error_type="INVALID_INPUT", message=f"Invalid inputs for {name}: {exc}")
