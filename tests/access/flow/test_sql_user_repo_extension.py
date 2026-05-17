from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from access.adapters.driven.db.models import UserModel
from access.domain.errors import AdminNotFoundError
from access.ports.driven.sql_user_repo import SqlUserRepo

pytestmark = pytest.mark.flow


def _make_model(**kwargs) -> UserModel:
    defaults = dict(
        id=1,
        login="admin",
        password_hash="hashed",
        role="owner",
        telegram_chat_id=None,
        is_active=True,
        password_changed_at=None,
        token_version=0,
        last_login_at=None,
        recovery_code_hash=None,
        recovery_code_expires=None,
        recovery_code_attempts=0,
        recovery_code_last_sent_at=None,
        recovery_code_locked_until=None,
    )
    defaults.update(kwargs)
    model = MagicMock(spec=UserModel)
    for k, v in defaults.items():
        setattr(model, k, v)
    return model


def _repo_with_session(session: MagicMock) -> SqlUserRepo:
    @contextmanager
    def factory():
        yield session

    return SqlUserRepo(_session_factory=factory)


class TestGetTokenVersion:
    def test_found_returns_current_value(self):
        model = _make_model(token_version=5)
        session = MagicMock()
        session.get.return_value = model
        repo = _repo_with_session(session)

        assert repo.get_token_version(1) == 5

    def test_not_found_returns_none(self):
        session = MagicMock()
        session.get.return_value = None
        repo = _repo_with_session(session)

        assert repo.get_token_version(99) is None


class TestBumpTokenVersion:
    def test_increments_and_returns_new_value(self):
        # Arrange: execute(update(...)) reports rowcount=1; re-fetch returns tv=2
        model_after = _make_model(token_version=2)
        session = MagicMock()
        session.execute.return_value.rowcount = 1
        session.get.return_value = model_after
        repo = _repo_with_session(session)

        result = repo.bump_token_version(1)

        assert result == 2
        session.execute.assert_called_once()
        session.commit.assert_called_once()
        session.get.assert_called_once()

    def test_not_found_raises_admin_not_found(self):
        session = MagicMock()
        session.execute.return_value.rowcount = 0
        repo = _repo_with_session(session)

        with pytest.raises(AdminNotFoundError):
            repo.bump_token_version(42)


class TestUpdateLastLogin:
    def test_updates_field_and_commits(self):
        model = _make_model(last_login_at=None)
        session = MagicMock()
        session.get.return_value = model
        repo = _repo_with_session(session)

        when = datetime(2025, 5, 17, tzinfo=timezone.utc)
        repo.update_last_login(1, when)

        assert model.last_login_at == when
        session.commit.assert_called_once()

    def test_no_op_when_admin_not_found(self):
        session = MagicMock()
        session.get.return_value = None
        repo = _repo_with_session(session)

        repo.update_last_login(99, datetime.now(timezone.utc))

        session.commit.assert_not_called()
