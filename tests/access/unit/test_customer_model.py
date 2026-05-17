"""
Smoke tests for CustomerModel ORM declaration.
No DB required — declarative metadata is resolved at import time.
"""
import pytest
from access.adapters.driven.db.models import CustomerModel


EXPECTED_COLUMNS = {
    "id",
    "email",
    "password_hash",
    "is_active",
    "created_at",
    "token_version",
    "last_login_at",
    "recovery_code_hash",
    "recovery_code_expires",
    "recovery_code_attempts",
    "recovery_code_last_sent_at",
    "recovery_code_locked_until",
}


@pytest.mark.unit
def test_tablename():
    assert CustomerModel.__tablename__ == "customers"


@pytest.mark.unit
def test_all_columns_declared():
    actual = set(CustomerModel.__table__.columns.keys())
    missing = EXPECTED_COLUMNS - actual
    assert not missing, f"Missing columns: {missing}"


@pytest.mark.unit
def test_email_is_unique():
    col = CustomerModel.__table__.columns["email"]
    assert col.unique


@pytest.mark.unit
def test_token_version_default_zero():
    col = CustomerModel.__table__.columns["token_version"]
    assert col.default.arg == 0
    assert not col.nullable


@pytest.mark.unit
def test_last_login_at_nullable():
    col = CustomerModel.__table__.columns["last_login_at"]
    assert col.nullable


@pytest.mark.unit
def test_created_at_not_nullable():
    col = CustomerModel.__table__.columns["created_at"]
    assert not col.nullable
    assert col.default is not None
