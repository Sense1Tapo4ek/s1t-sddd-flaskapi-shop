from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class LoginCommand:
    login: str
    password: str
    remember_me: bool = False
    csrf_token: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ChangePasswordCommand:
    admin_id: int
    new_password: str
    old_password: str | None = None
    confirmation_code: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class RegisterCustomerCommand:
    email: str
    password: str
    csrf_token: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class SendCustomerRecoveryCommand:
    email: str


@dataclass(frozen=True, slots=True, kw_only=True)
class VerifyCustomerRecoveryCommand:
    email: str
    code: str
    new_password: str
    csrf_token: str | None = None
