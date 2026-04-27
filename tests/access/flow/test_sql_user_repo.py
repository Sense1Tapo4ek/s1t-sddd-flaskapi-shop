from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import sessionmaker

from access.adapters.driven.db.models import UserModel
from access.ports.driven.sql_user_repo import SqlUserRepo
from shared.adapters.driven.db.base import Base
from shared.adapters.driven.db.connection import create_db_engine
from shared.helpers.security import hash_password


pytestmark = pytest.mark.flow


def test_sql_user_repo_lists_active_order_notification_recipients(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'users.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(engine, expire_on_commit=False)
    with Session() as session:
        session.add_all(
            [
                UserModel(
                    login="owner",
                    password_hash=hash_password("password"),
                    role="owner",
                    telegram_chat_id="owner-chat",
                    is_active=True,
                    password_changed_at=datetime.now(timezone.utc),
                ),
                UserModel(
                    login="superadmin",
                    password_hash=hash_password("password"),
                    role="superadmin",
                    telegram_chat_id="super-chat",
                    is_active=True,
                    password_changed_at=datetime.now(timezone.utc),
                ),
                UserModel(
                    login="inactive",
                    password_hash=hash_password("password"),
                    role="owner",
                    telegram_chat_id="inactive-chat",
                    is_active=False,
                ),
                UserModel(
                    login="missing-chat",
                    password_hash=hash_password("password"),
                    role="owner",
                    telegram_chat_id=None,
                    is_active=True,
                ),
            ]
        )
        session.commit()

    repo = SqlUserRepo(_session_factory=Session)

    recipients = repo.list_order_notification_recipients()

    assert [(user.login, user.telegram_chat_id) for user in recipients] == [
        ("owner", "owner-chat"),
        ("superadmin", "super-chat"),
    ]
