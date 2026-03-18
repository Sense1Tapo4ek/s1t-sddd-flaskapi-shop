from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class LoginCommand:
    login: str
    password: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ChangePasswordCommand:
    admin_id: int
    new_password: str
    old_password: str | None = None
