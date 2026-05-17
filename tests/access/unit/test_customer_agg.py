import pytest

from access.domain.customer_agg import Customer


@pytest.mark.unit
class TestCustomerDefaults:
    def test_required_fields_accepted(self):
        c = Customer(id=1, email="a@b.com", password_hash="hash")
        assert c.id == 1
        assert c.email == "a@b.com"
        assert c.password_hash == "hash"

    def test_is_active_default_true(self):
        c = Customer(id=1, email="a@b.com", password_hash="hash")
        assert c.is_active is True

    def test_token_version_default_zero(self):
        c = Customer(id=1, email="a@b.com", password_hash="hash")
        assert c.token_version == 0

    def test_recovery_code_attempts_default_zero(self):
        c = Customer(id=1, email="a@b.com", password_hash="hash")
        assert c.recovery_code_attempts == 0

    def test_last_login_at_default_none(self):
        c = Customer(id=1, email="a@b.com", password_hash="hash")
        assert c.last_login_at is None

    def test_created_at_default_none(self):
        c = Customer(id=1, email="a@b.com", password_hash="hash")
        assert c.created_at is None

    def test_recovery_fields_default_none(self):
        c = Customer(id=1, email="a@b.com", password_hash="hash")
        assert c.recovery_code_hash is None
        assert c.recovery_code_expires is None
        assert c.recovery_code_last_sent_at is None
        assert c.recovery_code_locked_until is None


@pytest.mark.unit
class TestCustomerSlots:
    def test_slots_prevent_arbitrary_attribute(self):
        c = Customer(id=1, email="a@b.com", password_hash="hash")
        with pytest.raises(AttributeError):
            c.nonexistent_field = "boom"  # type: ignore[attr-defined]


@pytest.mark.unit
class TestCustomerErrors:
    def test_email_already_registered_attribute(self):
        from access.domain.errors import EmailAlreadyRegisteredError

        err = EmailAlreadyRegisteredError(email="a@b.com")
        assert err.email == "a@b.com"
        assert "a@b.com" in str(err)
        assert err.code == "EMAIL_ALREADY_REGISTERED"

    def test_customer_not_found_attribute(self):
        from access.domain.errors import CustomerNotFoundError

        err = CustomerNotFoundError(customer_id=42)
        assert err.customer_id == 42
        assert "42" in str(err)
        assert err.code == "CUSTOMER_NOT_FOUND"

    def test_customer_inactive_code(self):
        from access.domain.errors import CustomerInactiveError

        err = CustomerInactiveError()
        assert err.code == "CUSTOMER_INACTIVE"
