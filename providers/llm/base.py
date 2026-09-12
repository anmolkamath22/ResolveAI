from __future__ import annotations
from abc import ABC, abstractmethod
from models.schemas import Goal

class LLMProvider(ABC):
    """Provider seam; providers may suggest intent but can never execute enterprise actions."""
    @abstractmethod
    def parse_goal(self, request: str) -> Goal: ...
    @property
    @abstractmethod
    def name(self) -> str: ...
