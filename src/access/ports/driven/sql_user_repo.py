from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from access.adapters.driven import UserModel
from access.app.interfaces import IAdminRepo
from access.domain import User
from shared.generics.errors import DrivenPortError


@dataclass(frozen=True, slots=True, kw_only=True)
class SqlUserRepo(IAdminRepo):
    _session_factory: Callable[[], Session]

    def _to_domain(self, model: UserModel) -> User:
        return User(
            id=model.id,
            login=model.login,
            password_hash=model.password_hash,
            recovery_code_hash=model.recovery_code_hash,
            recovery_code_expires=model.recovery_code_expires,
        )

    def get_by_login(self, login: str) -> User | None:
        try:
            with self._session_factory() as session:
                model = session.execute(
                    select(UserModel).where(UserModel.login == login)
                ).scalar_one_or_none()
                return self._to_domain(model) if model else None
        except Exception as e:
            raise DrivenPortError(f"DB Error loading user by login: {e}")

    def get_by_id(self, user_id: int) -> User | None:
        try:
            with self._session_factory() as session:
                model = session.get(UserModel, user_id)
                return self._to_domain(model) if model else None
        except Exception as e:
            raise DrivenPortError(f"DB Error loading user by id: {e}")

    def update_password(self, user_id: int, password_hash: str) -> User | None:
        try:
            with self._session_factory() as session:
                model = session.get(UserModel, user_id)
                if not model:
                    return None
                model.password_hash = password_hash
                session.commit()
                session.refresh(model)
                return self._to_domain(model)
        except Exception as e:
            raise DrivenPortError(f"DB Error updating password: {e}")

    def set_recovery_code(self, user_id: int, code_hash: str, expires: datetime) -> None:
        try:
            with self._session_factory() as session:
                model = session.get(UserModel, user_id)
                if model:
                    model.recovery_code_hash = code_hash
                    model.recovery_code_expires = expires
                    session.commit()
        except Exception as e:
            raise DrivenPortError(f"DB Error setting recovery code: {e}")

    def clear_recovery_code(self, user_id: int) -> None:
        try:
            with self._session_factory() as session:
                model = session.get(UserModel, user_id)
                if model:
                    model.recovery_code_hash = None
                    model.recovery_code_expires = None
                    session.commit()
        except Exception as e:
            raise DrivenPortError(f"DB Error clearing recovery code: {e}")
