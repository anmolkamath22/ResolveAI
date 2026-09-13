import pytest
from app.api import ResolveRequest, resolve
from app.settings import settings
from storage.database import reset_database

def test_case_context_mismatch_is_rejected(tmp_path):
    db=tmp_path/"api.db";reset_database(db);old=settings.database_path;object.__setattr__(settings,"database_path",str(db))
    try:
        with pytest.raises(Exception) as exc:resolve("CASE-100",ResolveRequest(request="refund please",customer_context="CUS-200"))
        assert getattr(exc.value,"status_code",None)==403
    finally:object.__setattr__(settings,"database_path",old)
