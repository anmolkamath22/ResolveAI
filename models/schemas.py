"""Typed contracts shared by the agent and simulated enterprise services."""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

class Action(str, Enum):
    GET_CUSTOMER="GET_CUSTOMER"; GET_ORDER="GET_ORDER"; CHECK_POLICY="CHECK_POLICY"
    GET_INVENTORY="GET_INVENTORY"; CREATE_REPLACEMENT="CREATE_REPLACEMENT"
    CREATE_REFUND="CREATE_REFUND"; CANCEL_ORDER="CANCEL_ORDER"; ESCALATE="ESCALATE"; VERIFY="VERIFY"
    GET_PAYMENT="GET_PAYMENT"; GET_SHIPMENT="GET_SHIPMENT"; GENERATE_RETURN_LABEL="GENERATE_RETURN_LABEL"
    REVERSE_DUPLICATE_CHARGE="REVERSE_DUPLICATE_CHARGE"; ESCALATE_HIGH_VALUE="ESCALATE_HIGH_VALUE"

class ToolCall(BaseModel):
    """Validated audit-safe tool contract; the registry accepts no arbitrary executable action."""
    action: Action
    inputs: dict[str, Any] = Field(default_factory=dict)

class ToolResult(BaseModel):
    success: bool
    data: dict[str, Any] = Field(default_factory=dict)
    error_type: str | None = None
    message: str = ""

class Goal(BaseModel):
    issue_type: str
    requested_resolution: str
    urgency: str = "NORMAL"

class ActionRecord(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    action: str; tool: str; status: str; summary: str
    inputs_summary: str = ""; result_summary: str = ""

class ResolutionState(BaseModel):
    investigation_id: str; case_id: str; user_request: str
    customer_id: str | None = None; order_id: str | None = None; product_id: str | None = None
    goal: Goal | None = None; preferred_action: str | None = None
    current_resolution: str | None = None; final_status: str = "IN_PROGRESS"
    action_history: list[ActionRecord] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    observations: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    replans: int = 0; verification_results: list[dict[str, Any]] = Field(default_factory=list)
    final_summary: str | None = None
    llm_provider: str = "offline-demo"

    def event(self, action: str, tool: str, status: str, summary: str, **kwargs: str) -> None:
        self.action_history.append(ActionRecord(action=action, tool=tool, status=status, summary=summary, **kwargs))
