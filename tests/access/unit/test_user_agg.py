import pytest

from access.domain.user_agg import User


@pytest.mark.unit
class TestUserNewFields:
    def test_token_version_default_zero(self):
        u = User(id=1, login="admin", password_hash="hash")
        assert u.token_version == 0

    def test_last_login_at_default_none(self):
        u = User(id=1, login="admin", password_hash="hash")
        assert u.last_login_at is None

    def test_existing_fields_unaffected(self):
        u = User(id=1, login="admin", password_hash="hash")
        assert u.role == "owner"
        assert u.is_active is True
        assert u.recovery_code_attempts == 0

    def test_slots_prevent_arbitrary_attribute(self):
        u = User(id=1, login="admin", password_hash="hash")
        with pytest.raises(AttributeError):
            u.unknown_attribute = "x"
