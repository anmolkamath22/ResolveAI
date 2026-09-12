"""Gemini-first, OpenRouter-fallback provider selection."""
from __future__ import annotations
import os
from models.schemas import Goal
from providers.config import secret
from providers.llm.base import LLMProvider
from providers.llm.gemini import GeminiProvider, ProviderError
from providers.llm.mock import MockLLMProvider
from providers.llm.openrouter import OpenRouterProvider

class ResilientProvider(LLMProvider):
    def __init__(self, providers: list[LLMProvider]): self.providers=providers;self.active: LLMProvider|None=None;self.last_error: str|None=None
    @property
    def name(self) -> str: return self.active.name if self.active else self.providers[0].name
    def parse_goal(self, request: str) -> Goal:
        for provider in self.providers:
            try:
                goal=provider.parse_goal(request);self.active=provider;return goal
            except ProviderError as exc: self.last_error=str(exc)
        fallback=MockLLMProvider();self.active=fallback;return fallback.parse_goal(request)

def build_provider() -> LLMProvider:
    options: list[LLMProvider]=[]
    if key:=secret("GEMINI_API_KEY"): options.append(GeminiProvider(key,os.getenv("GEMINI_MODEL","gemini-3.6-flash")))
    if key:=secret("OPENROUTER_API_KEY"): options.append(OpenRouterProvider(key,os.getenv("OPENROUTER_MODEL","google/gemini-3.6-flash")))
    return ResilientProvider(options) if options else MockLLMProvider()
