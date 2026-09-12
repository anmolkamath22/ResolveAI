from models.schemas import Goal
from providers.llm.base import LLMProvider
from providers.llm.factory import ResilientProvider
from providers.llm.gemini import ProviderError

class FailingProvider(LLMProvider):
    @property
    def name(self): return "failing"
    def parse_goal(self, request): raise ProviderError("temporary provider failure")

class WorkingProvider(LLMProvider):
    @property
    def name(self): return "working"
    def parse_goal(self, request): return Goal(issue_type="DAMAGED_ITEM",requested_resolution="refund")

def test_provider_router_falls_back_without_exposing_error_as_goal():
    router=ResilientProvider([FailingProvider(),WorkingProvider()])
    goal=router.parse_goal("refund my damaged item")
    assert goal.requested_resolution=="refund"
    assert router.name=="working" and router.last_error
