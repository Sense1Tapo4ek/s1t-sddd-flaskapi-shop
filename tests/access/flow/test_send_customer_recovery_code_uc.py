from datetime import datetime, timedelta, timezone

import pytest

from access.app.commands import SendCustomerRecoveryCommand
from access.app.use_cases.send_customer_recovery_code_uc import SendCustomerRecoveryCodeUseCase
from access.config import AccessConfig
from access.domain import Customer
from access.domain.errors import EmailRecoveryFailedError


class FakeCustomerRepo:
    def __init__(self, customer: Customer | None = None) -> None:
        self._customer = customer
        self.set_calls: list[tuple[int, str, datetime]] = []
        self.clear_calls: list[int] = []

    def get_by_email(self, email: str) -> Customer | None:
        if self._customer and self._customer.email == email:
            return self._customer
        return None

    def set_recovery_code(self, customer_id: int, code_hash: str, expires: datetime) -> None:
        self.set_calls.append((customer_id, code_hash, expires))
        if self._customer and self._customer.id == customer_id:
            self._customer.recovery_code_hash = code_hash
            self._customer.recovery_code_expires = expires
            self._customer.recovery_code_last_sent_at = datetime.now(timezone.utc)

    def clear_recovery_code(self, customer_id: int) -> None:
        self.clear_calls.append(customer_id)


class FakeEmailSender:
    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail
        self.sent: list[tuple[str, str, str]] = []

    def send(self, to: str, subject: str, body: str) -> None:
        if self._fail:
            raise RuntimeError("SMTP error")
        self.sent.append((to, subject, body))


class VerifyPasswordSpy:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def __call__(self, password: str, hash_: str) -> bool:
        self.calls.append((password, hash_))
        return False


def make_customer(*, last_sent_at: datetime | None = None) -> Customer:
    return Customer(
        id=1,
        email="user@example.com",
        password_hash="hash",
        token_version=0,
        recovery_code_last_sent_at=last_sent_at,
    )


def make_config() -> AccessConfig:
    return AccessConfig(
        jwt_secret="send-recovery-test-secret-with-at-least-32-bytes!!",
        customer_recovery_code_ttl_minutes=15,
        customer_recovery_code_cooldown_seconds=60,
    )


@pytest.mark.flow
class TestSendCustomerRecoveryCodeUseCase:
    def test_happy_path_sets_code_and_sends_email(self) -> None:
        """
        Given an existing customer with no cooldown,
        When SendCustomerRecoveryCodeUseCase is called,
        Then the code is stored and email is sent.
        """
        customer = make_customer()
        repo = FakeCustomerRepo(customer)
        sender = FakeEmailSender()
        uc = SendCustomerRecoveryCodeUseCase(_repo=repo, _email_sender=sender, _config=make_config())

        uc(SendCustomerRecoveryCommand(email="user@example.com"))

        assert len(repo.set_calls) == 1
        assert len(sender.sent) == 1
        assert sender.sent[0][0] == "user@example.com"

    def test_email_send_failure_clears_code_and_raises(self) -> None:
        """
        Given email_sender.send raises an exception,
        When SendCustomerRecoveryCodeUseCase is called,
        Then clear_recovery_code is called and EmailRecoveryFailedError is raised.
        """
        customer = make_customer()
        repo = FakeCustomerRepo(customer)
        sender = FakeEmailSender(fail=True)
        uc = SendCustomerRecoveryCodeUseCase(_repo=repo, _email_sender=sender, _config=make_config())

        with pytest.raises(EmailRecoveryFailedError) as exc_info:
            uc(SendCustomerRecoveryCommand(email="user@example.com"))

        assert exc_info.value.code == "EMAIL_DELIVERY_FAILED"
        assert len(repo.clear_calls) == 1

    def test_unknown_email_returns_silently_without_sending(self) -> None:
        """
        Given an email not in the repo,
        When SendCustomerRecoveryCodeUseCase is called,
        Then it returns silently and email_sender is never called.
        """
        repo = FakeCustomerRepo(customer=None)
        sender = FakeEmailSender()
        uc = SendCustomerRecoveryCodeUseCase(_repo=repo, _email_sender=sender, _config=make_config())

        uc(SendCustomerRecoveryCommand(email="ghost@example.com"))

        assert len(sender.sent) == 0
        assert len(repo.set_calls) == 0

    def test_cooldown_active_returns_silently_without_sending(self) -> None:
        """
        Given a customer within the cooldown window,
        When SendCustomerRecoveryCodeUseCase is called,
        Then it returns silently and email_sender is never called.
        """
        customer = make_customer(last_sent_at=datetime.now(timezone.utc) - timedelta(seconds=10))
        repo = FakeCustomerRepo(customer)
        sender = FakeEmailSender()
        uc = SendCustomerRecoveryCodeUseCase(_repo=repo, _email_sender=sender, _config=make_config())

        uc(SendCustomerRecoveryCommand(email="user@example.com"))

        assert len(sender.sent) == 0
        assert len(repo.set_calls) == 0

    def test_anti_timing_verify_password_called_for_unknown_email(self, monkeypatch) -> None:
        """
        Given an email not in the repo,
        When SendCustomerRecoveryCodeUseCase is called,
        Then verify_password is invoked (anti-timing dummy hash path).
        """
        import access.app.use_cases.send_customer_recovery_code_uc as uc_module

        spy = VerifyPasswordSpy()
        monkeypatch.setattr(uc_module, "verify_password", spy)

        repo = FakeCustomerRepo(customer=None)
        sender = FakeEmailSender()
        uc = SendCustomerRecoveryCodeUseCase(_repo=repo, _email_sender=sender, _config=make_config())

        uc(SendCustomerRecoveryCommand(email="ghost@example.com"))

        assert len(spy.calls) >= 1

    def test_anti_timing_verify_password_called_during_cooldown(self, monkeypatch) -> None:
        """
        Given a customer inside the cooldown window,
        When SendCustomerRecoveryCodeUseCase is called,
        Then verify_password is invoked on the cooldown short-circuit path.
        """
        import access.app.use_cases.send_customer_recovery_code_uc as uc_module

        spy = VerifyPasswordSpy()
        monkeypatch.setattr(uc_module, "verify_password", spy)

        customer = make_customer(last_sent_at=datetime.now(timezone.utc) - timedelta(seconds=10))
        repo = FakeCustomerRepo(customer)
        sender = FakeEmailSender()
        uc = SendCustomerRecoveryCodeUseCase(_repo=repo, _email_sender=sender, _config=make_config())

        uc(SendCustomerRecoveryCommand(email="user@example.com"))

        assert len(spy.calls) >= 1
        assert len(sender.sent) == 0
