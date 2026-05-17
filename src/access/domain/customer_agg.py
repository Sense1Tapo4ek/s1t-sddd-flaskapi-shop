from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class Customer:
    id: int
    email: str
    password_hash: str
    is_active: bool = True
    created_at: datetime | None = field(default=None)
    token_version: int = 0
    last_login_at: datetime | None = field(default=None)
    recovery_code_hash: str | None = field(default=None)
    recovery_code_expires: datetime | None = field(default=None)
    recovery_code_attempts: int = 0
    recovery_code_last_sent_at: datetime | None = field(default=None)
    recovery_code_locked_until: datetime | None = field(default=None)
