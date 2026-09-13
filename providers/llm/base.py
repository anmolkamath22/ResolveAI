from __future__ import annotations
from abc import ABC, abstractmethod
from models.schemas import Goal, AgentDecision

class LLMProvider(ABC):
    """Provider seam; providers may suggest intent but can never execute enterprise actions."""
    @abstractmethod
    def parse_goal(self, request: str) -> Goal: ...
    def decide(self, context: dict) -> AgentDecision:
        """Compatibility default for older intent-only providers."""
        from providers.llm.mock import OfflineTestStubProvider
        return OfflineTestStubProvider().decide(context)
    @property
    @abstractmethod
    def name(self) -> str: ...
