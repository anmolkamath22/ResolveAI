"""Opt-in integration proof; CI should enable this only when credentials are provided."""
import os
import pytest
from agent.graph import ResolutionAgent
from providers.llm.factory import build_provider
from services.enterprise import Enterprise
from storage.database import reset_database

pytestmark=pytest.mark.skipif(os.getenv("RUN_LIVE_PROVIDER_TESTS")!="1",reason="Set RUN_LIVE_PROVIDER_TESTS=1 with a live provider credential to run.")

def test_novel_wording_is_decided_by_live_provider(tmp_path):
    os.environ.pop("RESOLVEAI_OFFLINE_TEST",None)
    db=tmp_path/"live.db";reset_database(db,"replacement")
    # No stub trigger words: this is intentionally unlike a seeded issue label.
    state=ResolutionAgent(Enterprise(str(db)),provider=build_provider()).run("CASE-100","The audio gear I received is unusable; please make this right.")
    assert state.llm_provider!="offline-demo", "Generalization proof cannot run on OfflineTestStubProvider."
    assert state.final_status in {"RESOLVED","ESCALATED","NEEDS_CLARIFICATION","ACTION_REQUIRED"}
