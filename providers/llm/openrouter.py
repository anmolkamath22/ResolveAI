"""OpenRouter fallback provider using its OpenAI-compatible Chat Completions endpoint."""
from __future__ import annotations
import json
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen
from models.schemas import Goal
from providers.llm.base import LLMProvider
from providers.llm.gemini import GOAL_SCHEMA, SYSTEM, ProviderError

class OpenRouterProvider(LLMProvider):
    def __init__(self, api_key: str, model: str="google/gemini-3.6-flash", timeout: float=12): self.api_key=api_key;self.model=model;self.timeout=timeout
    @property
    def name(self) -> str: return f"OpenRouter · {self.model}"
    def parse_goal(self, request: str) -> Goal:
        payload={"model":self.model,"messages":[{"role":"system","content":SYSTEM},{"role":"user","content":request}],"temperature":0,"max_tokens":180,"response_format":{"type":"json_schema","json_schema":{"name":"resolveai_goal","strict":True,"schema":GOAL_SCHEMA}}}
        try:
            req=Request("https://openrouter.ai/api/v1/chat/completions",data=json.dumps(payload).encode(),headers={"Content-Type":"application/json","Authorization":f"Bearer {self.api_key}","HTTP-Referer":"https://resolveai.local","X-Title":"ResolveAI"},method="POST")
            with urlopen(req,timeout=self.timeout) as response: data=json.load(response)
            return Goal.model_validate_json(data["choices"][0]["message"]["content"])
        except (HTTPError,URLError,TimeoutError,KeyError,ValueError,json.JSONDecodeError) as exc:
            raise ProviderError(f"OpenRouter intent request failed: {type(exc).__name__}") from exc
