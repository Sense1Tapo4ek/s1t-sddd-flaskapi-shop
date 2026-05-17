from datetime import datetime, timedelta, timezone

import pytest

from access.app.commands import VerifyCustomerRecoveryCommand
from access.app.services.session_cache import SessionCache
from access.app.use_cases.verify_customer_recovery_uc import VerifyCustomerRecoveryUseCase
from access.config import AccessConfig
from access.domain import Customer, CustomerInactiveError, RecoveryCodeLockedError
from access.domain.errors import InvalidRecoveryCodeError, WeakPasswordError
from shared.helpers.security import hash_password, verify_jwt


class FakeCustomerRepo:
    def __init__(self, customer: Customer | None = None) -> None:
        self._customer = customer
        self.update_password_calls: list[tuple[int, str]] = []
        self.clear_calls: list[int] = []
        self.record_failure_calls: list[tuple[int, int, datetime | None]] = []
        self.bump_calls: list[int] = []
        self._token_version = customer.token_version if customer else 0

    def get_by_email(self, email: str) -> Customer | None:
        if self._customer and self._customer.email == email:
            return self._customer
        return None

    def update_password(self, customer_id: int, password_hash: str) -> None:
        self.update_password_calls.append((customer_id, password_hash))

    def clear_recovery_code(self, customer_id: int) -> None:
        self.clear_calls.append(customer_id)
        if self._customer and self._customer.id == customer_id:
            self._customer.recovery_code_hash = None
            self._customer.recovery_code_expires = None

    def record_recovery_failure(
        self, customer_id: int, attempts: int, locked_until: datetime | None
    ) -> None:
        self.record_failure_calls.append((customer_id, attempts, locked_until))
        if self._customer and self._customer.id == customer_id:
            self._customer.recovery_code_attempts = attempts
            self._customer.recovery_code_locked_until = locked_until

    def bump_token_version(self, customer_id: int) -> int:
        self.bump_calls.append(customer_id)
        self._token_version += 1
        return self._token_version

    def update_last_login(self, customer_id: int, when: datetime) -> None:
        pass


def make_customer(
    *,
    is_active: bool = True,
    code: str | None = "123456",
    attempts: int = 0,
    locked_until: datetime | None = None,
    expires: datetime | None = None,
) -> Customer:
    if expires is None and code is not None:
        expires = datetime.now(timezone.utc) + timedelta(minutes=15)
    return Customer(
        id=1,
        email="user@example.com",
        password_hash=hash_password("oldpassword"),
        is_active=is_active,
        token_version=0,
        recovery_code_hash=hash_password(code) if code is not None else None,
        recovery_code_expires=expires,
        recovery_code_attempts=attempts,
        recovery_code_locked_until=locked_until,
    )


def make_config() -> AccessConfig:
    return AccessConfig(
        jwt_secret="verify-customer-recovery-test-secret-32bytes!!",
        customer_recovery_code_max_attempts=5,
        customer_recovery_code_lockout_minutes=15,
    )


def make_uc(repo: FakeCustomerRepo, cache: SessionCache | None = None) -> VerifyCustomerRecoveryUseCase:
    return VerifyCustomerRecoveryUseCase(
        _repo=repo,
        _config=make_config(),
        _cache=cache or SessionCache(),
    )


@pytest.mark.flow
class TestVerifyCustomerRecoveryUseCase:
    def test_happy_path_resets_password_and_returns_jwt(self) -> None:
        """
        Given a valid recovery code for an active customer,
        When VerifyCustomerRecoveryUseCase is called with correct code and new password,
        Then password is updated, code cleared, token_version bumped, cache invalidated, JWT returned.
        """
        customer = make_customer()
        repo = FakeCustomerRepo(customer)
        cache = SessionCache()
        cache.put("customer", 1, 0)
        uc = make_uc(repo, cache)

        token = uc(VerifyCustomerRecoveryCommand(
            email="user@example.com", code="123456", new_password="newpassword123"
        ))

        payload = verify_jwt(token, make_config().jwt_secret)
        assert payload is not None
        assert payload["account_type"] == "customer"
        assert len(repo.update_password_calls) == 1
        assert len(repo.clear_calls) == 1
        assert len(repo.bump_calls) == 1
        assert cache.get("customer", 1) is None

    def test_short_new_password_raises_weak_password_error(self) -> None:
        """
        Given a new password shorter than 8 characters,
        When VerifyCustomerRecoveryUseCase is called,
        Then WeakPasswordError is raised before any repo calls.
        """
        repo = FakeCustomerRepo(make_customer())
        uc = make_uc(repo)

        with pytest.raises(WeakPasswordError) as exc_info:
            uc(VerifyCustomerRecoveryCommand(
                email="user@example.com", code="123456", new_password="short"
            ))

        assert exc_info.value.code == "WEAK_PASSWORD"
        assert len(repo.update_password_calls) == 0

    def test_unknown_email_raises_invalid_recovery_code_error(self) -> None:
        """
        Given an email not in the repo,
        When VerifyCustomerRecoveryUseCase is called,
        Then InvalidRecoveryCodeError is raised.
        """
        repo = FakeCustomerRepo(customer=None)
        uc = make_uc(repo)

        with pytest.raises(InvalidRecoveryCodeError):
            uc(VerifyCustomerRecoveryCommand(
                email="ghost@example.com", code="123456", new_password="newpassword123"
            ))

    def test_inactive_customer_raises_customer_inactive_error(self) -> None:
        """
        Given an inactive customer,
        When VerifyCustomerRecoveryUseCase is called,
        Then CustomerInactiveError is raised.
        """
        repo = FakeCustomerRepo(make_customer(is_active=False))
        uc = make_uc(repo)

        with pytest.raises(CustomerInactiveError) as exc_info:
            uc(VerifyCustomerRecoveryCommand(
                email="user@example.com", code="123456", new_password="newpassword123"
            ))

        assert exc_info.value.code == "CUSTOMER_INACTIVE"

    def test_wrong_code_records_failure_and_raises_invalid(self) -> None:
        """
        Given a valid code but wrong input below max attempts,
        When VerifyCustomerRecoveryUseCase is called,
        Then record_recovery_failure is called and InvalidRecoveryCodeError is raised.
        """
        repo = FakeCustomerRepo(make_customer())
        uc = make_uc(repo)

        with pytest.raises(InvalidRecoveryCodeError):
            uc(VerifyCustomerRecoveryCommand(
                email="user@example.com", code="000000", new_password="newpassword123"
            ))

        assert len(repo.record_failure_calls) == 1
        assert repo.record_failure_calls[0][1] == 1  # attempts incremented

    def test_max_attempts_records_failure_and_raises_locked(self) -> None:
        """
        Given a customer one attempt away from lockout,
        When a wrong code is submitted,
        Then record_recovery_failure is called and RecoveryCodeLockedError is raised.
        """
        config = make_config()
        customer = make_customer(attempts=config.customer_recovery_code_max_attempts - 1)
        repo = FakeCustomerRepo(customer)
        uc = make_uc(repo)

        with pytest.raises(RecoveryCodeLockedError) as exc_info:
            uc(VerifyCustomerRecoveryCommand(
                email="user@example.com", code="000000", new_password="newpassword123"
            ))

        assert exc_info.value.code == "RECOVERY_CODE_LOCKED"
        assert len(repo.record_failure_calls) == 1
        assert repo.record_failure_calls[0][2] is not None  # locked_until set

    def test_already_locked_raises_locked_without_recording(self) -> None:
        """
        Given a customer whose lockout is still active,
        When VerifyCustomerRecoveryUseCase is called,
        Then RecoveryCodeLockedError is raised without recording another failure.
        """
        customer = make_customer(locked_until=datetime.now(timezone.utc) + timedelta(minutes=5))
        repo = FakeCustomerRepo(customer)
        uc = make_uc(repo)

        with pytest.raises(RecoveryCodeLockedError):
            uc(VerifyCustomerRecoveryCommand(
                email="user@example.com", code="000000", new_password="newpassword123"
            ))

        assert len(repo.record_failure_calls) == 0

    def test_expired_code_clears_and_raises_invalid(self) -> None:
        """
        Given a customer with an expired recovery code,
        When VerifyCustomerRecoveryUseCase is called,
        Then clear_recovery_code is called and InvalidRecoveryCodeError is raised.
        """
        customer = make_customer(expires=datetime.now(timezone.utc) - timedelta(seconds=1))
        repo = FakeCustomerRepo(customer)
        uc = make_uc(repo)

        with pytest.raises(InvalidRecoveryCodeError):
            uc(VerifyCustomerRecoveryCommand(
                email="user@example.com", code="123456", new_password="newpassword123"
            ))

        assert len(repo.clear_calls) == 1
        assert len(repo.update_password_calls) == 0
