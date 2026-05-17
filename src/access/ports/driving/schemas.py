from pydantic import BaseModel, ConfigDict, EmailStr, Field
from access.app.commands import (
    ChangePasswordCommand,
    LoginCommand,
    RegisterCustomerCommand,
    SendCustomerRecoveryCommand,
    VerifyCustomerRecoveryCommand,
)


class LoginIn(BaseModel):
    model_config = ConfigDict(frozen=True)
    login: str
    password: str
    remember_me: bool = False

    def to_command(self, *, csrf_token: str | None = None) -> LoginCommand:
        return LoginCommand(
            login=self.login,
            password=self.password,
            remember_me=self.remember_me,
            csrf_token=csrf_token,
        )


class LoginOut(BaseModel):
    model_config = ConfigDict(frozen=True)
    token: str
    message: str = "Login successful"


class ChangePasswordIn(BaseModel):
    model_config = ConfigDict(frozen=True)
    new_password: str
    old_password: str | None = None
    confirmation_code: str | None = None

    def to_command(self, *, admin_id: int) -> ChangePasswordCommand:
        return ChangePasswordCommand(
            admin_id=admin_id,
            new_password=self.new_password,
            old_password=self.old_password,
            confirmation_code=self.confirmation_code,
        )


class TelegramCodeRequestIn(BaseModel):
    model_config = ConfigDict(frozen=True)
    login: str


class TelegramCodeVerifyIn(BaseModel):
    model_config = ConfigDict(frozen=True)
    login: str
    code: str
    remember_me: bool = False


class TelegramBindingIn(BaseModel):
    model_config = ConfigDict(frozen=True)
    telegram_chat_id: str | None = None


class CustomerRegisterIn(BaseModel):
    model_config = ConfigDict(frozen=True)
    email: EmailStr
    password: str = Field(min_length=8)

    def to_command(self, *, csrf_token: str | None = None) -> RegisterCustomerCommand:
        return RegisterCustomerCommand(
            email=self.email,
            password=self.password,
            csrf_token=csrf_token,
        )


class CustomerRecoverIn(BaseModel):
    model_config = ConfigDict(frozen=True)
    email: EmailStr

    def to_command(self) -> SendCustomerRecoveryCommand:
        return SendCustomerRecoveryCommand(email=self.email)


class CustomerVerifyIn(BaseModel):
    model_config = ConfigDict(frozen=True)
    email: EmailStr
    code: str
    new_password: str = Field(min_length=8)

    def to_command(self, *, csrf_token: str | None = None) -> VerifyCustomerRecoveryCommand:
        return VerifyCustomerRecoveryCommand(
            email=self.email,
            code=self.code,
            new_password=self.new_password,
            csrf_token=csrf_token,
        )
