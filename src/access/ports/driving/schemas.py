from pydantic import BaseModel, ConfigDict
from access.app.commands import LoginCommand


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
