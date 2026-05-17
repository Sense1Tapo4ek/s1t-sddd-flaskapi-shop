from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from access.adapters.driven.db.models import CustomerModel
from access.domain.errors import CustomerNotFoundError, EmailAlreadyRegisteredError
from access.ports.driven.sql_customer_repo import SqlCustomerRepo

pytestmark = pytest.mark.flow


def _make_model(**kwargs) -> CustomerModel:
    defaults = dict(
        id=1,
        email="user@example.com",
        password_hash="hashed",
        is_active=True,
        created_at=datetime(2024, 1, 1),
        token_version=0,
        last_login_at=None,
        recovery_code_hash=None,
        recovery_code_expires=None,
        recovery_code_attempts=0,
        recovery_code_last_sent_at=None,
        recovery_code_locked_until=None,
    )
    defaults.update(kwargs)
    model = MagicMock(spec=CustomerModel)
    for k, v in defaults.items():
        setattr(model, k, v)
    return model


def _repo_with_session(session: MagicMock) -> SqlCustomerRepo:
    @contextmanager
    def factory():
        yield session

    return SqlCustomerRepo(_session_factory=factory)


class TestGetByEmail:
    def test_found(self):
        model = _make_model()
        session = MagicMock()
        session.execute.return_value.scalar_one_or_none.return_value = model
        repo = _repo_with_session(session)

        result = repo.get_by_email("user@example.com")

        assert result is not None
        assert result.email == "user@example.com"

    def test_not_found(self):
        session = MagicMock()
        session.execute.return_value.scalar_one_or_none.return_value = None
        repo = _repo_with_session(session)

        assert repo.get_by_email("missing@example.com") is None


class TestGetById:
    def test_found(self):
        model = _make_model(id=7)
        session = MagicMock()
        session.get.return_value = model
        repo = _repo_with_session(session)

        result = repo.get_by_id(7)

        assert result is not None
        assert result.id == 7

    def test_not_found(self):
        session = MagicMock()
        session.get.return_value = None
        repo = _repo_with_session(session)

        assert repo.get_by_id(99) is None


class TestCreate:
    def _session_factory(self, session):
        @contextmanager
        def factory():
            yield session
        return factory

    def test_success(self):
        session = MagicMock()

        def fake_add(m):
            m.id = 5
            m.email = "new@example.com"
            m.password_hash = "hash"
            m.is_active = True
            m.created_at = datetime(2024, 1, 1)
            m.token_version = 0
            m.last_login_at = None
            m.recovery_code_hash = None
            m.recovery_code_expires = None
            m.recovery_code_attempts = 0
            m.recovery_code_last_sent_at = None
            m.recovery_code_locked_until = None

        session.add = fake_add
        session.commit = MagicMock()
        session.refresh = MagicMock()

        repo = SqlCustomerRepo(_session_factory=self._session_factory(session))
        result = repo.create(email="new@example.com", password_hash="hash")

        session.commit.assert_called_once()
        assert result.email == "new@example.com"

    def test_duplicate_email_raises(self):
        session = MagicMock()
        session.add = MagicMock()
        session.commit.side_effect = IntegrityError("Duplicate", None, None)
        session.rollback = MagicMock()

        repo = SqlCustomerRepo(_session_factory=self._session_factory(session))

        with pytest.raises(EmailAlreadyRegisteredError) as exc_info:
            repo.create(email="dup@example.com", password_hash="hash")

        assert exc_info.value.email == "dup@example.com"
        session.rollback.assert_called_once()


class TestGetTokenVersion:
    def test_found(self):
        model = _make_model(token_version=3)
        session = MagicMock()
        session.get.return_value = model
        repo = _repo_with_session(session)

        assert repo.get_token_version(1) == 3

    def test_not_found_returns_none(self):
        session = MagicMock()
        session.get.return_value = None
        repo = _repo_with_session(session)

        assert repo.get_token_version(99) is None


class TestBumpTokenVersion:
    def test_increments_and_returns_new_value(self):
        # Arrange: execute(update(...)) reports rowcount=1; re-fetch returns tv=3
        model_after = _make_model(token_version=3)
        session = MagicMock()
        session.execute.return_value.rowcount = 1
        session.get.return_value = model_after
        repo = _repo_with_session(session)

        result = repo.bump_token_version(1)

        assert result == 3
        session.execute.assert_called_once()
        session.commit.assert_called_once()
        session.get.assert_called_once()

    def test_not_found_raises(self):
        session = MagicMock()
        session.execute.return_value.rowcount = 0
        repo = _repo_with_session(session)

        with pytest.raises(CustomerNotFoundError):
            repo.bump_token_version(99)


class TestUpdateLastLogin:
    def test_updates_field(self):
        model = _make_model(last_login_at=None)
        session = MagicMock()
        session.get.return_value = model
        repo = _repo_with_session(session)

        when = datetime(2025, 6, 1, tzinfo=timezone.utc)
        repo.update_last_login(1, when)

        assert model.last_login_at == when
        session.commit.assert_called_once()

    def test_no_op_when_not_found(self):
        session = MagicMock()
        session.get.return_value = None
        repo = _repo_with_session(session)

        repo.update_last_login(99, datetime.now(timezone.utc))

        session.commit.assert_not_called()
