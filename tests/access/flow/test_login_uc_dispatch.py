"""
Flow tests for LoginUseCase dispatch logic (Phase 5).

Covers:
- Dispatch by "@" — admin vs customer path.
- JWT payload shape per account_type.
- Error cases: wrong password, inactive account.
- update_last_login called on success.
"""
from datetime import datetime, timezone

import pytest

from access.app.commands import LoginCommand
from access.app.use_cases.login_uc import LoginUseCase
from access.config import AccessConfig
from access.domain import AdminInactiveError, InvalidPasswordError, User
from access.domain.customer_agg import Customer
from access.domain.errors import CustomerInactiveError
from shared.helpers.security import hash_password, verify_jwt


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeAdminRepo:
    def __init__(self, users: list[User] | None = None) -> None:
        self.users = {u.id: u for u in (users or [])}
        self.get_by_login_calls: list[str] = []
        self.last_login_updated: dict[int, datetime] = {}

    def get_by_login(self, login: str) -> User | None:
        self.get_by_login_calls.append(login)
        return next((u for u in self.users.values() if u.login == login), None)

    def get_by_id(self, user_id: int) -> User | None:
        return self.users.get(user_id)

    def update_password(self, user_id, password_hash, password_changed_at=None):
        return None

    def update_telegram_chat_id(self, user_id, chat_id):
        return None

    def set_recovery_code(self, user_id, code_hash, expires):
        pass

    def record_recovery_failure(self, user_id, attempts, locked_until):
        pass

    def clear_recovery_code(self, user_id):
        pass

    def get_token_version(self, admin_id):
        u = self.users.get(admin_id)
        return u.token_version if u else None

    def bump_token_version(self, admin_id):
        u = self.users.get(admin_id)
        if u:
            u.token_version += 1
            return u.token_version
        return 0

    def update_last_login(self, admin_id: int, when: datetime) -> None:
        self.last_login_updated[admin_id] = when

    def list_order_notification_recipients(self):
        return []


class FakeCustomerRepo:
    def __init__(self, customers: list[Customer] | None = None) -> None:
        self.customers = {c.id: c for c in (customers or [])}
        self.get_by_email_calls: list[str] = []
        self.last_login_updated: dict[int, datetime] = {}

    def get_by_email(self, email: str) -> Customer | None:
        self.get_by_email_calls.append(email)
        return next((c for c in self.customers.values() if c.email == email), None)

    def get_by_id(self, customer_id: int) -> Customer | None:
        return self.customers.get(customer_id)

    def create(self, *, email, password_hash):
        new_id = max(self.customers.keys(), default=0) + 1
        c = Customer(id=new_id, email=email, password_hash=password_hash)
        self.customers[new_id] = c
        return c

    def update_password(self, customer_id, password_hash):
        pass

    def set_recovery_code(self, customer_id, code_hash, expires):
        pass

    def clear_recovery_code(self, customer_id):
        pass

    def record_recovery_failure(self, customer_id, attempts, locked_until):
        pass

    def get_token_version(self, customer_id):
        c = self.customers.get(customer_id)
        return c.token_version if c else None

    def bump_token_version(self, customer_id):
        c = self.customers.get(customer_id)
        if c:
            c.token_version += 1
            return c.token_version
        return 0

    def update_last_login(self, customer_id: int, when: datetime) -> None:
        self.last_login_updated[customer_id] = when


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_admin(*, token_version: int = 3, is_active: bool = True) -> User:
    return User(
        id=1,
        login="admin",
        password_hash=hash_password("admin-pass"),
        role="owner",
        is_active=is_active,
        token_version=token_version,
    )


def make_customer(*, token_version: int = 7, is_active: bool = True) -> Customer:
    return Customer(
        id=10,
        email="user@example.com",
        password_hash=hash_password("cust-pass"),
        is_active=is_active,
        token_version=token_version,
    )


def make_config() -> AccessConfig:
    return AccessConfig(
        jwt_secret="dispatch-test-secret-at-least-32-bytes-x",
        owner_can_edit_products=True,
        owner_can_manage_orders=True,
    )


def make_uc(admin_repo=None, customer_repo=None) -> LoginUseCase:
    return LoginUseCase(
        _admin_repo=admin_repo or FakeAdminRepo(),
        _customer_repo=customer_repo or FakeCustomerRepo(),
        _config=make_config(),
    )


# ---------------------------------------------------------------------------
# Dispatch routing
# ---------------------------------------------------------------------------

@pytest.mark.flow
class TestLoginDispatch:
    def test_login_without_at_routes_to_admin_repo(self) -> None:
        """
        Given login with no "@",
        When LoginUseCase is called,
        Then admin_repo.get_by_login is called and customer_repo is not touched.
        """
        # Arrange
        admin_repo = FakeAdminRepo([make_admin()])
        customer_repo = FakeCustomerRepo()
        uc = make_uc(admin_repo=admin_repo, customer_repo=customer_repo)

        # Act
        uc(LoginCommand(login="admin", password="admin-pass"))

        # Assert
        assert admin_repo.get_by_login_calls == ["admin"]
        assert customer_repo.get_by_email_calls == []

    def test_login_with_at_routes_to_customer_repo(self) -> None:
        """
        Given login containing "@",
        When LoginUseCase is called,
        Then customer_repo.get_by_email is called and admin_repo is not touched.
        """
        # Arrange
        admin_repo = FakeAdminRepo()
        customer_repo = FakeCustomerRepo([make_customer()])
        uc = make_uc(admin_repo=admin_repo, customer_repo=customer_repo)

        # Act
        uc(LoginCommand(login="user@example.com", password="cust-pass"))

        # Assert
        assert customer_repo.get_by_email_calls == ["user@example.com"]
        assert admin_repo.get_by_login_calls == []


# ---------------------------------------------------------------------------
# Admin happy path — JWT payload
# ---------------------------------------------------------------------------

@pytest.mark.flow
class TestAdminLoginJwt:
    def test_jwt_contains_admin_account_type_and_tv(self) -> None:
        """
        Given a valid admin login,
        When a JWT is issued,
        Then it contains account_type=admin, tv=token_version, role, permissions.
        """
        # Arrange
        config = make_config()
        admin_repo = FakeAdminRepo([make_admin(token_version=3)])
        uc = LoginUseCase(_admin_repo=admin_repo, _customer_repo=FakeCustomerRepo(), _config=config)

        # Act
        token = uc(LoginCommand(login="admin", password="admin-pass"))

        # Assert
        payload = verify_jwt(token, config.jwt_secret)
        assert payload is not None
        assert payload["account_type"] == "admin"
        assert payload["tv"] == 3
        assert payload["role"] == "owner"
        assert "permissions" in payload
        assert "email" not in payload

    def test_update_last_login_called_on_admin_success(self) -> None:
        """
        Given a valid admin login,
        When the use case succeeds,
        Then update_last_login is recorded for the admin.
        """
        # Arrange
        admin_repo = FakeAdminRepo([make_admin()])
        uc = make_uc(admin_repo=admin_repo)

        # Act
        uc(LoginCommand(login="admin", password="admin-pass"))

        # Assert
        assert 1 in admin_repo.last_login_updated
        assert admin_repo.last_login_updated[1].tzinfo is not None


# ---------------------------------------------------------------------------
# Customer happy path — JWT payload
# ---------------------------------------------------------------------------

@pytest.mark.flow
class TestCustomerLoginJwt:
    def test_jwt_contains_customer_account_type_and_tv(self) -> None:
        """
        Given a valid customer login,
        When a JWT is issued,
        Then it contains account_type=customer, tv=token_version, email; no role/permissions.
        """
        # Arrange
        config = make_config()
        customer_repo = FakeCustomerRepo([make_customer(token_version=7)])
        uc = LoginUseCase(_admin_repo=FakeAdminRepo(), _customer_repo=customer_repo, _config=config)

        # Act
        token = uc(LoginCommand(login="user@example.com", password="cust-pass"))

        # Assert
        payload = verify_jwt(token, config.jwt_secret)
        assert payload is not None
        assert payload["account_type"] == "customer"
        assert payload["tv"] == 7
        assert payload["email"] == "user@example.com"
        assert "role" not in payload
        assert "permissions" not in payload

    def test_update_last_login_called_on_customer_success(self) -> None:
        """
        Given a valid customer login,
        When the use case succeeds,
        Then update_last_login is recorded for the customer.
        """
        # Arrange
        customer_repo = FakeCustomerRepo([make_customer()])
        uc = make_uc(customer_repo=customer_repo)

        # Act
        uc(LoginCommand(login="user@example.com", password="cust-pass"))

        # Assert
        assert 10 in customer_repo.last_login_updated
        assert customer_repo.last_login_updated[10].tzinfo is not None


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

@pytest.mark.flow
class TestLoginErrors:
    def test_admin_wrong_password_raises(self) -> None:
        """
        Given wrong admin password,
        When login is attempted,
        Then InvalidPasswordError is raised.
        """
        # Arrange
        admin_repo = FakeAdminRepo([make_admin()])
        uc = make_uc(admin_repo=admin_repo)

        # Act / Assert
        with pytest.raises(InvalidPasswordError):
            uc(LoginCommand(login="admin", password="wrong"))

    def test_admin_inactive_raises(self) -> None:
        """
        Given an inactive admin with correct password,
        When login is attempted,
        Then AdminInactiveError is raised.
        """
        # Arrange
        admin_repo = FakeAdminRepo([make_admin(is_active=False)])
        uc = make_uc(admin_repo=admin_repo)

        # Act / Assert
        with pytest.raises(AdminInactiveError):
            uc(LoginCommand(login="admin", password="admin-pass"))

    def test_customer_not_found_raises_invalid_password(self) -> None:
        """
        Given a login email that does not exist,
        When login is attempted,
        Then InvalidPasswordError is raised (no enumeration).
        """
        # Arrange
        uc = make_uc(customer_repo=FakeCustomerRepo())

        # Act / Assert
        with pytest.raises(InvalidPasswordError):
            uc(LoginCommand(login="ghost@example.com", password="any"))

    def test_customer_wrong_password_raises(self) -> None:
        """
        Given existing customer but wrong password,
        When login is attempted,
        Then InvalidPasswordError is raised.
        """
        # Arrange
        customer_repo = FakeCustomerRepo([make_customer()])
        uc = make_uc(customer_repo=customer_repo)

        # Act / Assert
        with pytest.raises(InvalidPasswordError):
            uc(LoginCommand(login="user@example.com", password="wrong"))

    def test_customer_inactive_raises(self) -> None:
        """
        Given an inactive customer with correct password,
        When login is attempted,
        Then CustomerInactiveError is raised.
        """
        # Arrange
        customer_repo = FakeCustomerRepo([make_customer(is_active=False)])
        uc = make_uc(customer_repo=customer_repo)

        # Act / Assert
        with pytest.raises(CustomerInactiveError):
            uc(LoginCommand(login="user@example.com", password="cust-pass"))
