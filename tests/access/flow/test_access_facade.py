"""
Flow tests for the three split facades: AccessFacade, AdminFacade, CustomerFacade.

Covers:
- AccessFacade.login dispatches to LoginUseCase for both admin and customer paths.
- CustomerFacade.register / send_recovery_code / verify_and_reset / get_customer.
- AdminFacade unchanged-behaviour smoke tests.
"""
from unittest.mock import MagicMock, create_autospec

import pytest

from access.app import (
    IAdminRepo,
    ICustomerRepo,
    LoginUseCase,
    RegisterCustomerUseCase,
    SendCustomerRecoveryCodeUseCase,
    VerifyCustomerRecoveryUseCase,
)
from access.config import AccessConfig
from access.domain import Customer, CustomerNotFoundError
from access.ports.driving.access_facade import AccessFacade
from access.ports.driving.admin_facade import AdminFacade
from access.ports.driving.customer_facade import CustomerFacade
from access.ports.driving.schemas import (
    CustomerRecoverIn,
    CustomerRegisterIn,
    CustomerVerifyIn,
    LoginIn,
)
from shared.helpers.security import hash_password


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config() -> AccessConfig:
    return AccessConfig(
        jwt_secret="facade-split-test-secret-at-least-32-bytes",
        owner_can_edit_products=True,
        owner_can_manage_orders=True,
    )


def _make_customer(customer_id: int = 99) -> Customer:
    return Customer(
        id=customer_id,
        email="cust@example.com",
        password_hash=hash_password("password123"),
        is_active=True,
        token_version=1,
    )


# ---------------------------------------------------------------------------
# AccessFacade — login-only dispatch
# ---------------------------------------------------------------------------

@pytest.mark.flow
class TestAccessFacadeLogin:
    def test_login_calls_login_uc_and_returns_login_out(self) -> None:
        """
        Given a LoginUseCase mock that returns a token string,
        When AccessFacade.login is called,
        Then it returns a LoginOut with that token.
        """
        # Arrange
        mock_login_uc = MagicMock(spec=LoginUseCase)
        mock_login_uc.return_value = "jwt-token-abc"
        facade = AccessFacade(_login_uc=mock_login_uc)
        schema = LoginIn(login="admin", password="pass")

        # Act
        result = facade.login(schema)

        # Assert
        assert result.token == "jwt-token-abc"
        mock_login_uc.assert_called_once()

    def test_login_passes_csrf_token_to_command(self) -> None:
        """
        Given a csrf_token kwarg,
        When AccessFacade.login is called,
        Then the command forwarded to LoginUseCase carries the csrf_token.
        """
        # Arrange
        mock_login_uc = MagicMock(spec=LoginUseCase)
        mock_login_uc.return_value = "tok"
        facade = AccessFacade(_login_uc=mock_login_uc)
        schema = LoginIn(login="user@example.com", password="pass123")

        # Act
        facade.login(schema, csrf_token="csrf-xyz")

        # Assert
        call_args = mock_login_uc.call_args
        cmd = call_args[0][0]
        assert cmd.csrf_token == "csrf-xyz"

    def test_login_admin_path_no_at_in_login(self) -> None:
        """
        Given login without "@",
        When AccessFacade.login is called (real LoginUseCase with fake repos),
        Then admin path executes and returns a JWT string.
        """
        # Arrange
        from access.domain import User

        class _AdminRepo:
            def __init__(self, user):
                self._user = user

            def get_by_login(self, login):
                return self._user if self._user.login == login else None

            def update_last_login(self, uid, when):
                pass

            def get_by_id(self, uid):
                return self._user

        class _CustomerRepo:
            def get_by_email(self, e):
                return None

            def update_last_login(self, cid, when):
                pass

        config = _make_config()
        admin = User(
            id=1,
            login="admin",
            password_hash=hash_password("admin-pass"),
            role="owner",
            is_active=True,
            token_version=3,
        )
        login_uc = LoginUseCase(
            _admin_repo=_AdminRepo(admin),
            _customer_repo=_CustomerRepo(),
            _config=config,
        )
        facade = AccessFacade(_login_uc=login_uc)
        schema = LoginIn(login="admin", password="admin-pass")

        # Act
        result = facade.login(schema, csrf_token="csrf1")

        # Assert
        assert isinstance(result.token, str)
        assert len(result.token) > 20

    def test_login_customer_path_at_in_login(self) -> None:
        """
        Given login containing "@",
        When AccessFacade.login is called (real LoginUseCase with fake repos),
        Then customer path executes and returns a JWT string.
        """
        # Arrange
        class _AdminRepo:
            def get_by_login(self, login):
                return None

        class _CustomerRepo:
            def __init__(self, customer):
                self._customer = customer

            def get_by_email(self, email):
                return self._customer if self._customer.email == email else None

            def update_last_login(self, cid, when):
                pass

        config = _make_config()
        customer = Customer(
            id=10,
            email="user@example.com",
            password_hash=hash_password("cust-pass"),
            is_active=True,
            token_version=7,
        )
        login_uc = LoginUseCase(
            _admin_repo=_AdminRepo(),
            _customer_repo=_CustomerRepo(customer),
            _config=config,
        )
        facade = AccessFacade(_login_uc=login_uc)
        schema = LoginIn(login="user@example.com", password="cust-pass")

        # Act
        result = facade.login(schema)

        # Assert
        assert isinstance(result.token, str)
        assert len(result.token) > 20


# ---------------------------------------------------------------------------
# CustomerFacade
# ---------------------------------------------------------------------------

@pytest.mark.flow
class TestCustomerFacadeRegister:
    def test_register_returns_login_out_with_token(self) -> None:
        """
        Given RegisterCustomerUseCase mock that returns a token,
        When CustomerFacade.register is called,
        Then LoginOut with that token is returned.
        """
        # Arrange
        mock_repo = create_autospec(ICustomerRepo, instance=True)
        mock_register_uc = MagicMock(spec=RegisterCustomerUseCase)
        mock_register_uc.return_value = "register-token"
        mock_send_uc = MagicMock(spec=SendCustomerRecoveryCodeUseCase)
        mock_verify_uc = MagicMock(spec=VerifyCustomerRecoveryUseCase)

        facade = CustomerFacade(
            _repo=mock_repo,
            _register_uc=mock_register_uc,
            _send_code_uc=mock_send_uc,
            _verify_uc=mock_verify_uc,
        )
        schema = CustomerRegisterIn(email="new@example.com", password="password123")

        # Act
        result = facade.register(schema, csrf_token="csrf-reg")

        # Assert
        assert result.token == "register-token"
        mock_register_uc.assert_called_once()
        cmd = mock_register_uc.call_args[0][0]
        assert cmd.email == "new@example.com"
        assert cmd.password == "password123"
        assert cmd.csrf_token == "csrf-reg"

    def test_register_forwards_none_csrf_by_default(self) -> None:
        """
        Given no csrf_token kwarg,
        When CustomerFacade.register is called,
        Then command carries csrf_token=None.
        """
        # Arrange
        mock_repo = create_autospec(ICustomerRepo, instance=True)
        mock_register_uc = MagicMock(spec=RegisterCustomerUseCase)
        mock_register_uc.return_value = "tok"
        facade = CustomerFacade(
            _repo=mock_repo,
            _register_uc=mock_register_uc,
            _send_code_uc=MagicMock(),
            _verify_uc=MagicMock(),
        )
        schema = CustomerRegisterIn(email="a@b.com", password="password123")

        # Act
        facade.register(schema)

        # Assert
        cmd = mock_register_uc.call_args[0][0]
        assert cmd.csrf_token is None


@pytest.mark.flow
class TestCustomerFacadeSendRecoveryCode:
    def test_send_recovery_code_calls_uc_and_returns_none(self) -> None:
        """
        Given SendCustomerRecoveryCodeUseCase mock,
        When CustomerFacade.send_recovery_code is called,
        Then the use case is called and None is returned (silent on unknown email).
        """
        # Arrange
        mock_repo = create_autospec(ICustomerRepo, instance=True)
        mock_send_uc = MagicMock(spec=SendCustomerRecoveryCodeUseCase)
        mock_send_uc.return_value = None
        facade = CustomerFacade(
            _repo=mock_repo,
            _register_uc=MagicMock(),
            _send_code_uc=mock_send_uc,
            _verify_uc=MagicMock(),
        )
        schema = CustomerRecoverIn(email="recover@example.com")

        # Act
        result = facade.send_recovery_code(schema)

        # Assert
        assert result is None
        mock_send_uc.assert_called_once()
        cmd = mock_send_uc.call_args[0][0]
        assert cmd.email == "recover@example.com"

    def test_send_recovery_code_returns_none_for_unknown_email(self) -> None:
        """
        Given SendCustomerRecoveryCodeUseCase that returns None (unknown email, silent),
        When CustomerFacade.send_recovery_code is called,
        Then None is returned without exception.
        """
        # Arrange
        mock_repo = create_autospec(ICustomerRepo, instance=True)
        mock_send_uc = MagicMock(spec=SendCustomerRecoveryCodeUseCase)
        mock_send_uc.return_value = None
        facade = CustomerFacade(
            _repo=mock_repo,
            _register_uc=MagicMock(),
            _send_code_uc=mock_send_uc,
            _verify_uc=MagicMock(),
        )

        # Act — no exception expected
        result = facade.send_recovery_code(CustomerRecoverIn(email="ghost@nowhere.com"))

        # Assert
        assert result is None


@pytest.mark.flow
class TestCustomerFacadeVerifyAndReset:
    def test_verify_and_reset_returns_login_out(self) -> None:
        """
        Given VerifyCustomerRecoveryUseCase mock returning a token,
        When CustomerFacade.verify_and_reset is called,
        Then LoginOut with that token is returned.
        """
        # Arrange
        mock_repo = create_autospec(ICustomerRepo, instance=True)
        mock_verify_uc = MagicMock(spec=VerifyCustomerRecoveryUseCase)
        mock_verify_uc.return_value = "reset-token"
        facade = CustomerFacade(
            _repo=mock_repo,
            _register_uc=MagicMock(),
            _send_code_uc=MagicMock(),
            _verify_uc=mock_verify_uc,
        )
        schema = CustomerVerifyIn(
            email="r@example.com",
            code="123456",
            new_password="newpassword1",
        )

        # Act
        result = facade.verify_and_reset(schema, csrf_token="csrf-vfy")

        # Assert
        assert result.token == "reset-token"
        cmd = mock_verify_uc.call_args[0][0]
        assert cmd.email == "r@example.com"
        assert cmd.code == "123456"
        assert cmd.new_password == "newpassword1"
        assert cmd.csrf_token == "csrf-vfy"


@pytest.mark.flow
class TestCustomerFacadeGetCustomer:
    def test_get_customer_returns_customer_when_found(self) -> None:
        """
        Given a repo returning a Customer,
        When CustomerFacade.get_customer is called,
        Then the Customer is returned.
        """
        # Arrange
        customer = _make_customer(customer_id=5)
        mock_repo = create_autospec(ICustomerRepo, instance=True)
        mock_repo.get_by_id.return_value = customer
        facade = CustomerFacade(
            _repo=mock_repo,
            _register_uc=MagicMock(),
            _send_code_uc=MagicMock(),
            _verify_uc=MagicMock(),
        )

        # Act
        result = facade.get_customer(5)

        # Assert
        assert result is customer
        mock_repo.get_by_id.assert_called_once_with(5)

    def test_get_customer_raises_not_found_when_missing(self) -> None:
        """
        Given a repo returning None,
        When CustomerFacade.get_customer is called,
        Then CustomerNotFoundError is raised.
        """
        # Arrange
        mock_repo = create_autospec(ICustomerRepo, instance=True)
        mock_repo.get_by_id.return_value = None
        facade = CustomerFacade(
            _repo=mock_repo,
            _register_uc=MagicMock(),
            _send_code_uc=MagicMock(),
            _verify_uc=MagicMock(),
        )

        # Act / Assert
        with pytest.raises(CustomerNotFoundError):
            facade.get_customer(999)


# ---------------------------------------------------------------------------
# AdminFacade smoke — ensure login() is gone and get_user() works
# ---------------------------------------------------------------------------

@pytest.mark.flow
class TestAdminFacadeSmoke:
    def test_admin_facade_has_no_login_method(self) -> None:
        """
        Given AdminFacade,
        When checking for a login attribute,
        Then it does not exist (login moved to AccessFacade).
        """
        assert not hasattr(AdminFacade, "login")

    def test_access_facade_has_login_method(self) -> None:
        """
        Given AccessFacade,
        When checking for a login attribute,
        Then it exists.
        """
        assert hasattr(AccessFacade, "login")

    def test_admin_facade_get_user_raises_when_not_found(self) -> None:
        """
        Given AdminFacade with a repo returning None,
        When get_user is called,
        Then AdminNotFoundError is raised.
        """
        # Arrange
        from access.app import IAdminRepo, ChangePasswordUseCase, ResetPasswordUseCase
        from access.app import GenerateRecoveryCodeUseCase, VerifyRecoveryCodeUseCase
        from access.domain import AdminNotFoundError

        mock_repo = create_autospec(IAdminRepo, instance=True)
        mock_repo.get_by_id.return_value = None
        facade = AdminFacade(
            _repo=mock_repo,
            _change_password_uc=MagicMock(spec=ChangePasswordUseCase),
            _reset_password_uc=MagicMock(spec=ResetPasswordUseCase),
            _generate_code_uc=MagicMock(spec=GenerateRecoveryCodeUseCase),
            _verify_code_uc=MagicMock(spec=VerifyRecoveryCodeUseCase),
        )

        # Act / Assert
        with pytest.raises(AdminNotFoundError):
            facade.get_user(42)
