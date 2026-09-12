"""Reproducible enterprise failures for demonstrations and automated tests."""
from __future__ import annotations
from collections import Counter

class FailureInjector:
    """Inject each named transient failure once; logical constraints remain real database state."""
    transient = {"refund_api_temporarily_unavailable": "refund", "replacement_api_temporarily_unavailable": "replacement"}
    def __init__(self, enabled: set[str] | None = None):
        self.enabled = enabled or set()
        self.calls: Counter[str] = Counter()
    def consume(self, operation: str) -> str | None:
        self.calls[operation] += 1
        for scenario, target in self.transient.items():
            if scenario in self.enabled and target == operation and self.calls[operation] == 1:
                return scenario
        return None
    def verification_should_fail(self) -> bool:
        self.calls["verification"] += 1
        return "verification_failure" in self.enabled and self.calls["verification"] == 1
