from pydantic import BaseModel, ConfigDict
from access.app.commands import LoginCommand


class LoginIn(BaseModel):
    model_config = ConfigDict(frozen=True)
    login: str
    password: str

    def to_command(self) -> LoginCommand:
        return LoginCommand(login=self.login, password=self.password)


class LoginOut(BaseModel):
    model_config = ConfigDict(frozen=True)
    token: str
    message: str = "Login successful"


class ChangePasswordIn(BaseModel):
    model_config = ConfigDict(frozen=True)
    new_password: str
    old_password: str | None = None
