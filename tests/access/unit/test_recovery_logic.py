from datetime import datetime, timedelta, timezone

import pytest

from access.app.services.recovery_logic import VerifyOutcome, as_utc, should_send, verify_code


def _now() -> datetime:
    return datetime.now(timezone.utc)


class FakeRecord:
    def __init__(
        self,
        *,
        code_hash: str | None = "hashed",
        expires: datetime | None = None,
        attempts: int = 0,
        locked_until: datetime | None = None,
        last_sent_at: datetime | None = None,
    ) -> None:
        self.recovery_code_hash = code_hash
        self.recovery_code_expires = expires or (_now() + timedelta(minutes=10))
        self.recovery_code_attempts = attempts
        self.recovery_code_locked_until = locked_until
        self.recovery_code_last_sent_at = last_sent_at


def _verify_fn_match(code: str, stored: str) -> bool:
    return code == stored


def _verify_fn_no_match(code: str, stored: str) -> bool:
    return False


@pytest.mark.unit
class TestVerifyCode:
    def test_ok_when_code_matches(self) -> None:
        """
        Given a valid unexpired code,
        When verify_code is called with matching code,
        Then outcome.ok is True.
        """
        record = FakeRecord(code_hash="secret")
        outcome = verify_code(
            record,
            "secret",
            now=_now(),
            max_attempts=5,
            lockout_minutes=15,
            verify_password_fn=_verify_fn_match,
        )
        assert outcome.ok is True
        assert outcome.invalid is False
        assert outcome.locked is False
        assert outcome.expired is False

    def test_invalid_when_no_hash_stored(self) -> None:
        """
        Given no stored code hash,
        When verify_code is called,
        Then outcome.invalid is True.
        """
        record = FakeRecord(code_hash=None)
        outcome = verify_code(
            record,
            "123456",
            now=_now(),
            max_attempts=5,
            lockout_minutes=15,
            verify_password_fn=_verify_fn_match,
        )
        assert outcome.ok is False
        assert outcome.invalid is True

    def test_expired_when_past_expiry(self) -> None:
        """
        Given an expired code,
        When verify_code is called,
        Then outcome.expired is True.
        """
        record = FakeRecord(expires=_now() - timedelta(seconds=1))
        outcome = verify_code(
            record,
            "secret",
            now=_now(),
            max_attempts=5,
            lockout_minutes=15,
            verify_password_fn=_verify_fn_match,
        )
        assert outcome.ok is False
        assert outcome.expired is True

    def test_invalid_wrong_code_increments_attempts(self) -> None:
        """
        Given a valid unexpired code and wrong input,
        When verify_code is called below max_attempts,
        Then outcome.invalid is True with incremented new_attempts.
        """
        record = FakeRecord(code_hash="secret", attempts=1)
        outcome = verify_code(
            record,
            "wrong",
            now=_now(),
            max_attempts=5,
            lockout_minutes=15,
            verify_password_fn=_verify_fn_no_match,
        )
        assert outcome.ok is False
        assert outcome.invalid is True
        assert outcome.new_attempts == 2
        assert outcome.new_locked_until is None
        assert outcome.locked is False

    def test_locked_when_max_attempts_reached(self) -> None:
        """
        Given a valid unexpired code and attempts at max-1,
        When verify_code is called with wrong code,
        Then outcome.locked is True and new_locked_until is set.
        """
        now = _now()
        record = FakeRecord(code_hash="secret", attempts=4)
        outcome = verify_code(
            record,
            "wrong",
            now=now,
            max_attempts=5,
            lockout_minutes=15,
            verify_password_fn=_verify_fn_no_match,
        )
        assert outcome.ok is False
        assert outcome.locked is True
        assert outcome.invalid is True
        assert outcome.new_attempts == 5
        assert outcome.new_locked_until is not None
        assert outcome.new_locked_until >= now + timedelta(minutes=15)

    def test_locked_when_lockout_still_active(self) -> None:
        """
        Given a lockout still in effect,
        When verify_code is called,
        Then outcome.locked is True without checking hash.
        """
        record = FakeRecord(locked_until=_now() + timedelta(minutes=10))
        outcome = verify_code(
            record,
            "any",
            now=_now(),
            max_attempts=5,
            lockout_minutes=15,
            verify_password_fn=_verify_fn_match,
        )
        assert outcome.ok is False
        assert outcome.locked is True
        assert outcome.invalid is False


@pytest.mark.unit
class TestShouldSend:
    def test_can_send_when_no_last_sent(self) -> None:
        """
        Given no last_sent_at,
        When should_send is called,
        Then can_send is True and remaining is 0.
        """
        record = FakeRecord(last_sent_at=None)
        can_send, remaining = should_send(record, now=_now(), cooldown_seconds=60)
        assert can_send is True
        assert remaining == 0

    def test_cannot_send_during_cooldown(self) -> None:
        """
        Given last_sent_at 10s ago with cooldown=60s,
        When should_send is called,
        Then can_send is False and remaining > 0.
        """
        now = _now()
        record = FakeRecord(last_sent_at=now - timedelta(seconds=10))
        can_send, remaining = should_send(record, now=now, cooldown_seconds=60)
        assert can_send is False
        assert remaining > 0

    def test_can_send_after_cooldown(self) -> None:
        """
        Given last_sent_at more than cooldown ago,
        When should_send is called,
        Then can_send is True.
        """
        now = _now()
        record = FakeRecord(last_sent_at=now - timedelta(seconds=61))
        can_send, _ = should_send(record, now=now, cooldown_seconds=60)
        assert can_send is True
