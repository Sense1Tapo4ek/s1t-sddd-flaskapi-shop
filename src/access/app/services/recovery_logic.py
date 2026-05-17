from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Protocol


class RecoveryRecord(Protocol):
    recovery_code_hash: str | None
    recovery_code_expires: datetime | None
    recovery_code_attempts: int
    recovery_code_locked_until: datetime | None
    recovery_code_last_sent_at: datetime | None


@dataclass(frozen=True, slots=True, kw_only=True)
class VerifyOutcome:
    ok: bool
    new_attempts: int = 0
    new_locked_until: datetime | None = None
    invalid: bool = False
    locked: bool = False
    expired: bool = False


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def verify_code(
    record: RecoveryRecord,
    code: str,
    *,
    now: datetime,
    max_attempts: int,
    lockout_minutes: int,
    verify_password_fn: Callable[[str, str], bool],
) -> VerifyOutcome:
    locked_until = as_utc(record.recovery_code_locked_until)
    if locked_until and locked_until > now:
        return VerifyOutcome(ok=False, locked=True)

    if record.recovery_code_hash is None:
        return VerifyOutcome(ok=False, invalid=True)

    expires = as_utc(record.recovery_code_expires)
    if expires is None or expires < now:
        return VerifyOutcome(ok=False, expired=True)

    if not verify_password_fn(code, record.recovery_code_hash):
        attempts = (record.recovery_code_attempts or 0) + 1
        new_locked_until: datetime | None = None
        if attempts >= max_attempts:
            new_locked_until = now + timedelta(minutes=lockout_minutes)
        return VerifyOutcome(
            ok=False,
            invalid=True,
            new_attempts=attempts,
            new_locked_until=new_locked_until,
            locked=new_locked_until is not None,
        )

    return VerifyOutcome(ok=True)


def should_send(
    record: RecoveryRecord,
    *,
    now: datetime,
    cooldown_seconds: int,
) -> tuple[bool, int]:
    last_sent_at = as_utc(record.recovery_code_last_sent_at)
    if last_sent_at is None:
        return True, 0
    cooldown_until = last_sent_at + timedelta(seconds=cooldown_seconds)
    if cooldown_until > now:
        remaining = int((cooldown_until - now).total_seconds()) + 1
        return False, remaining
    return True, 0
