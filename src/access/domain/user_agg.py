from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class User:
    """
    Aggregate Root for a system user (Staff/Admin).
    """

    id: int
    login: str
    password_hash: str
    role: str = "owner"
    telegram_chat_id: str | None = None
    is_active: bool = True
    password_changed_at: datetime | None = field(default=None)
    recovery_code_hash: str | None = field(default=None)
    recovery_code_expires: datetime | None = field(default=None)
    recovery_code_attempts: int = 0
    recovery_code_last_sent_at: datetime | None = field(default=None)
    recovery_code_locked_until: datetime | None = field(default=None)
