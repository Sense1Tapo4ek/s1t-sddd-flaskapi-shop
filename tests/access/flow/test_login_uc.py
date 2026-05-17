from datetime import datetime, timedelta, timezone

import pytest

from access.app.commands import LoginCommand
from access.app.use_cases.login_uc import LoginUseCase
from access.config import AccessConfig
from access.domain import AdminInactiveError, InvalidPasswordError, User
from shared.helpers.security import hash_password, verify_jwt


class FakeAdminRepo:
    def __init__(self, users: list[User] | None = None) -> None:
        self.users = {user.id: user for user in users or []}
        self.last_login_updated: dict[int, datetime] = {}

    def get_by_login(self, login: str) -> User | None:
        return next((u for u in self.users.values() if u.login == login), None)

    def get_by_id(self, user_id: int) -> User | None:
        return self.users.get(user_id)

    def update_password(self, user_id: int, password_hash: str, password_changed_at=None) -> User | None:
        user = self.users.get(user_id)
        if user is None:
            return None
        user.password_hash = password_hash
        user.password_changed_at = password_changed_at
        return user

    def update_telegram_chat_id(self, user_id: int, chat_id: str | None) -> User | None:
        user = self.users.get(user_id)
        if user is None:
            return None
        user.telegram_chat_id = chat_id or None
        return user

    def set_recovery_code(self, user_id: int, code_hash: str, expires) -> None:
        user = self.users.get(user_id)
        if user:
            user.recovery_code_hash = code_hash
            user.recovery_code_expires = expires
            user.recovery_code_attempts = 0

    def record_recovery_failure(self, user_id: int, attempts: int, locked_until) -> None:
        user = self.users.get(user_id)
        if user:
            user.recovery_code_attempts = attempts
            user.recovery_code_locked_until = locked_until

    def clear_recovery_code(self, user_id: int) -> None:
        user = self.users.get(user_id)
        if user:
            user.recovery_code_hash = None
            user.recovery_code_expires = None
            user.recovery_code_attempts = 0
            user.recovery_code_locked_until = None

    def get_token_version(self, admin_id: int) -> int | None:
        user = self.users.get(admin_id)
        return user.token_version if user else None

    def bump_token_version(self, admin_id: int) -> int:
        user = self.users.get(admin_id)
        if user:
            user.token_version += 1
            return user.token_version
        return 0

    def update_last_login(self, admin_id: int, when: datetime) -> None:
        self.last_login_updated[admin_id] = when

    def list_order_notification_recipients(self) -> list[User]:
        return []


class FakeCustomerRepo:
    def __init__(self, customers=None) -> None:
        from access.domain.customer_agg import Customer
        self.customers: dict[int, Customer] = {c.id: c for c in (customers or [])}
        self.last_login_updated: dict[int, datetime] = {}

    def get_by_email(self, email: str):
        return next((c for c in self.customers.values() if c.email == email), None)

    def get_by_id(self, customer_id: int):
        return self.customers.get(customer_id)

    def create(self, *, email: str, password_hash: str):
        from access.domain.customer_agg import Customer
        new_id = max(self.customers.keys(), default=0) + 1
        c = Customer(id=new_id, email=email, password_hash=password_hash)
        self.customers[new_id] = c
        return c

    def update_password(self, customer_id: int, password_hash: str) -> None:
        c = self.customers.get(customer_id)
        if c:
            c.password_hash = password_hash

    def set_recovery_code(self, customer_id: int, code_hash: str, expires) -> None:
        pass

    def clear_recovery_code(self, customer_id: int) -> None:
        pass

    def record_recovery_failure(self, customer_id: int, attempts: int, locked_until) -> None:
        pass

    def get_token_version(self, customer_id: int) -> int | None:
        c = self.customers.get(customer_id)
        return c.token_version if c else None

    def bump_token_version(self, customer_id: int) -> int:
        c = self.customers.get(customer_id)
        if c:
            c.token_version += 1
            return c.token_version
        return 0

    def update_last_login(self, customer_id: int, when: datetime) -> None:
        self.last_login_updated[customer_id] = when


def make_user(*, user_id: int = 1, login: str = "admin", password: str = "correct-password", role: str = "owner", is_active: bool = True, token_version: int = 3) -> User:
    return User(id=user_id, login=login, password_hash=hash_password(password), role=role, is_active=is_active, token_version=token_version)


def make_customer(*, customer_id: int = 10, email: str = "user@example.com", password: str = "cust-pass", is_active: bool = True, token_version: int = 7):
    from access.domain.customer_agg import Customer
    return Customer(id=customer_id, email=email, password_hash=hash_password(password), is_active=is_active, token_version=token_version)


def make_config() -> AccessConfig:
    return AccessConfig(
        jwt_secret="login-flow-secret-with-at-least-32-bytes",
        owner_can_view_category_tree=False,
        owner_can_edit_taxonomy=False,
        owner_can_view_products=False,
        owner_can_edit_products=True,
        owner_can_view_orders=False,
        owner_can_manage_orders=True,
        owner_can_manage_settings=False,
        owner_can_create_demo_data=False,
    )


def make_use_case(admin_repo=None, customer_repo=None, config=None) -> LoginUseCase:
    return LoginUseCase(
        _admin_repo=admin_repo or FakeAdminRepo(),
        _customer_repo=customer_repo or FakeCustomerRepo(),
        _config=config or make_config(),
    )


@pytest.mark.flow
class TestLoginUseCase:
    @pytest.mark.parametrize(
        ("login", "password"),
        [
            ("admin", "wrong-password"),
            ("missing", "correct-password"),
        ],
    )
    def test_wrong_password_or_missing_user_raises_invalid_password(self, login, password) -> None:
        """
        Given an existing admin and a login attempt with bad credentials,
        When the login use case is executed,
        Then authentication fails with InvalidPasswordError.
        """
        # Arrange
        admin_repo = FakeAdminRepo([make_user()])
        use_case = make_use_case(admin_repo=admin_repo)

        # Act / Assert
        with pytest.raises(InvalidPasswordError) as exc_info:
            use_case(LoginCommand(login=login, password=password))
        assert exc_info.value.code == "INVALID_PASSWORD"

    def test_inactive_user_raises_admin_inactive(self) -> None:
        """
        Given an inactive admin with a valid password,
        When the login use case is executed,
        Then login is blocked with AdminInactiveError.
        """
        # Arrange
        admin_repo = FakeAdminRepo([make_user(is_active=False)])
        use_case = make_use_case(admin_repo=admin_repo)

        # Act / Assert
        with pytest.raises(AdminInactiveError) as exc_info:
            use_case(LoginCommand(login="admin", password="correct-password"))
        assert exc_info.value.code == "ADMIN_INACTIVE"

    def test_valid_login_returns_jwt_with_csrf_and_role_permissions(self) -> None:
        """
        Given an active owner with configured role permissions,
        When the login use case succeeds with a CSRF token,
        Then the returned JWT contains identity, CSRF, and resolved permissions.
        """
        # Arrange
        config = make_config()
        admin_repo = FakeAdminRepo([make_user()])
        use_case = make_use_case(admin_repo=admin_repo, config=config)

        # Act
        token = use_case(LoginCommand(login="admin", password="correct-password", csrf_token="csrf-token-1"))

        # Assert
        payload = verify_jwt(token, config.jwt_secret)
        assert payload is not None
        assert payload["sub"] == 1
        assert payload["login"] == "admin"
        assert payload["role"] == "owner"
        assert payload["csrf"] == "csrf-token-1"
        assert payload["account_type"] == "admin"
        assert payload["tv"] == 3
        assert payload["permissions"] == {
            "view_category_tree": True,
            "edit_taxonomy": False,
            "view_products": True,
            "edit_products": True,
            "view_orders": True,
            "manage_orders": True,
            "manage_settings": False,
            "create_demo_data": False,
        }

    @pytest.mark.parametrize(
        ("remember_me", "expected_hours"),
        [(False, 24), (True, 24 * 30)],
    )
    def test_valid_login_sets_expected_expiration_window(self, remember_me, expected_hours) -> None:
        """
        Given an active admin and a remember-me choice,
        When the login use case issues a JWT,
        Then the token expiration matches the selected session lifetime.
        """
        # Arrange
        config = make_config()
        admin_repo = FakeAdminRepo([make_user()])
        use_case = make_use_case(admin_repo=admin_repo, config=config)
        before = datetime.now(timezone.utc)

        # Act
        token = use_case(LoginCommand(login="admin", password="correct-password", remember_me=remember_me))
        after = datetime.now(timezone.utc)

        # Assert
        payload = verify_jwt(token, config.jwt_secret)
        assert payload is not None
        expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        assert before + timedelta(hours=expected_hours, seconds=-2) <= expires_at
        assert expires_at <= after + timedelta(hours=expected_hours)
