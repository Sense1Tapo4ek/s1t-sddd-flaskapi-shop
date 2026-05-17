import pytest

from access.app.commands import RegisterCustomerCommand
from access.app.use_cases.register_customer_uc import RegisterCustomerUseCase
from access.config import AccessConfig
from access.domain import Customer, EmailAlreadyRegisteredError
from access.domain.errors import WeakPasswordError
from shared.helpers.security import verify_jwt


class FakeCustomerRepo:
    def __init__(self, existing_emails: set[str] | None = None) -> None:
        self._emails = existing_emails or set()
        self._next_id = 1

    def create(self, *, email: str, password_hash: str) -> Customer:
        if email in self._emails:
            raise EmailAlreadyRegisteredError(email)
        customer = Customer(
            id=self._next_id,
            email=email,
            password_hash=password_hash,
            token_version=0,
        )
        self._next_id += 1
        self._emails.add(email)
        return customer

    def get_by_email(self, email: str) -> Customer | None:
        return None

    def get_by_id(self, customer_id: int) -> Customer | None:
        return None


def make_config() -> AccessConfig:
    return AccessConfig(jwt_secret="register-customer-test-secret-with-32-bytes!!")


@pytest.mark.flow
class TestRegisterCustomerUseCase:
    def test_happy_path_returns_jwt_with_customer_account_type(self) -> None:
        """
        Given a new email and strong password,
        When RegisterCustomerUseCase is called,
        Then a JWT with account_type=customer is returned.
        """
        repo = FakeCustomerRepo()
        config = make_config()
        uc = RegisterCustomerUseCase(_repo=repo, _config=config)

        token = uc(RegisterCustomerCommand(email="user@example.com", password="strongpass"))

        payload = verify_jwt(token, config.jwt_secret)
        assert payload is not None
        assert payload["account_type"] == "customer"
        assert payload["email"] == "user@example.com"

    def test_short_password_raises_weak_password_error(self) -> None:
        """
        Given a password shorter than 8 characters,
        When RegisterCustomerUseCase is called,
        Then WeakPasswordError is raised.
        """
        repo = FakeCustomerRepo()
        uc = RegisterCustomerUseCase(_repo=repo, _config=make_config())

        with pytest.raises(WeakPasswordError) as exc_info:
            uc(RegisterCustomerCommand(email="user@example.com", password="short"))

        assert exc_info.value.code == "WEAK_PASSWORD"

    def test_duplicate_email_propagates_email_already_registered_error(self) -> None:
        """
        Given an email already in the repo,
        When RegisterCustomerUseCase is called,
        Then EmailAlreadyRegisteredError propagates from the repo.
        """
        repo = FakeCustomerRepo(existing_emails={"taken@example.com"})
        uc = RegisterCustomerUseCase(_repo=repo, _config=make_config())

        with pytest.raises(EmailAlreadyRegisteredError) as exc_info:
            uc(RegisterCustomerCommand(email="taken@example.com", password="strongpass"))

        assert exc_info.value.code == "EMAIL_ALREADY_REGISTERED"
