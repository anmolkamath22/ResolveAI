from models.schemas import Goal
from providers.llm.base import LLMProvider

class MockLLMProvider(LLMProvider):
    """Offline deterministic provider used for demos/tests with no secret required."""
    def parse_goal(self, request: str) -> Goal:
        text=request.lower()
        resolution="replacement" if "replace" in text else "cancellation" if "cancel" in text else "refund"
        return Goal(issue_type="DAMAGED_ITEM" if any(x in text for x in ("damaged","broken","defect")) else "GENERAL_REQUEST",requested_resolution=resolution)
    @property
    def name(self) -> str: return "offline-demo"
