"""Gemini-first, OpenRouter-fallback provider selection."""
from __future__ import annotations
import os
import time
from models.schemas import Goal
from models.schemas import AgentDecision
from providers.config import secret
from providers.llm.base import LLMProvider
from providers.llm.gemini import GeminiProvider, ProviderError
from providers.llm.mock import OfflineTestStubProvider
from providers.llm.openrouter import OpenRouterProvider

class ResilientProvider(LLMProvider):
    def __init__(self, providers: list[LLMProvider]):
        self.providers=providers;self.active: LLMProvider|None=None;self.last_error: str|None=None
        self._unavailable_until: dict[str,float]={};self._fallback_announced=False
    @property
    def name(self) -> str: return self.active.name if self.active else self.providers[0].name
    def parse_goal(self, request: str) -> Goal:
        for provider in self.providers:
            try:
                goal=provider.parse_goal(request);self.active=provider;return goal
            except ProviderError as exc: self.last_error=str(exc)
        fallback=OfflineTestStubProvider();self.active=fallback;return fallback.parse_goal(request)
    def decide(self, context: dict) -> AgentDecision:
        # A prior offline fallback must not become sticky: retry live providers on
        # the next turn so a transient outage cannot demote the whole case.
        active=[self.active] if self.active and self.active.name!="offline-demo" else []
        providers=active + [p for p in self.providers if p is not self.active]
        errors=[]
        for provider in providers:
            if provider is None: continue
            if time.monotonic()<self._unavailable_until.get(provider.name,0):continue
            for attempt in range(2):
                try:
                    decision=provider.decide(context); self.active=provider; self.last_error=None;self._fallback_announced=False;return decision
                except ProviderError as exc:
                    self.last_error=str(exc)
                    errors.append(f"{provider.name}: {self.last_error}")
                    # A quota response cannot be repaired by immediate repeated
                    # calls. Pause this provider for the case and let the other
                    # configured provider have one chance instead.
                    if "HTTP 429" in self.last_error or "RESOURCE_EXHAUSTED" in self.last_error:
                        self._unavailable_until[provider.name]=time.monotonic()+60
                        break
                    if attempt==0: time.sleep(0.6)
        if errors:self.last_error=" | ".join(dict.fromkeys(errors))
        fallback=OfflineTestStubProvider(); self.active=fallback
        decision=fallback.decide(context)
        if not self._fallback_announced:
            decision.reasoning=f"[FALLBACK: {self.last_error or 'no provider configured'}] {decision.reasoning}"
            self._fallback_announced=True
        return decision

def build_provider() -> LLMProvider:
    if os.getenv("RESOLVEAI_OFFLINE_TEST")=="1": return OfflineTestStubProvider()
    options: list[LLMProvider]=[]
    if key:=secret("GEMINI_API_KEY"): options.append(GeminiProvider(key,os.getenv("GEMINI_MODEL","gemini-3.6-flash")))
    if key:=secret("OPENROUTER_API_KEY"): options.append(OpenRouterProvider(key,os.getenv("OPENROUTER_MODEL","google/gemini-3.6-flash")))
    return ResilientProvider(options) if options else OfflineTestStubProvider()
