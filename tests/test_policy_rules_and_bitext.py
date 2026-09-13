import pytest
from services.enterprise import Enterprise
from services.intent_classifier import IntentClassifier
from storage.database import connect, reset_database

@pytest.fixture
def enterprise(tmp_path):
    path=tmp_path/"bitext.db";reset_database(path)
    return Enterprise(str(path))

def test_expired_case_is_denied_by_computed_date_not_seed_flag(enterprise):
    result=enterprise.policy("ORD-3042","refund")
    assert result.success and not result.data["allowed"]
    assert "days ago" in result.message and result.data["policy_ref"]=="refund-window"

def test_computed_policy_ignores_deprecated_seed_boolean(enterprise):
    c=connect(enterprise.db_path);c.execute("UPDATE orders SET eligible_refund=0 WHERE id='ORD-1042'");c.commit();c.close()
    assert enterprise.policy("ORD-1042","refund").data["allowed"]

def test_bitext_intent_classifier_handles_support_paraphrase():
    result=IntentClassifier().classify("there is an extra card charge on my purchase")
    assert result and result[0]["intent"]=="payment_issue"

PARAPHRASES=[
    ("CASE-100","hey my headphones came in broken, can you send new ones"),
    ("CASE-100","the wireless headphones i got are damaged, want a replacement please"),
    ("CASE-200","i think i got billed twice for the same speaker order"),
    ("CASE-400","can you stop my cable order before it ships"),
    ("CASE-600","i ordered headphones but a speaker showed up instead"),
]
@pytest.mark.parametrize("expected_case,phrasing",PARAPHRASES)
def test_bitext_style_paraphrase_never_resolves_wrong_case(enterprise,expected_case,phrasing):
    result=enterprise.resolve_case_request(phrasing,customer_context=None)
    if result.success:assert result.data["case"]["id"]==expected_case
    else:assert result.error_type in {"AMBIGUOUS_ENTITY","MISSING_ENTITY"}
