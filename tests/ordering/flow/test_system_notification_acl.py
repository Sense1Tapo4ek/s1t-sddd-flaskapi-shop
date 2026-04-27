import pytest

from access.domain import User
from ordering.domain import Order
from ordering.ports.driven.system_notification_acl import SystemNotificationAcl


pytestmark = pytest.mark.flow


class FakeAccessFacade:
    def __init__(self, recipients: list[User]) -> None:
        self.recipients = recipients

    def order_notification_recipients(self) -> list[User]:
        return self.recipients


class FakeSystemFacade:
    def __init__(self, *, fail_for: set[str] | None = None) -> None:
        self.fail_for = fail_for or set()
        self.sent: list[dict[str, str]] = []

    def send_notification_to_chat(self, *, chat_id: str, subject: str, body: str) -> bool:
        self.sent.append({"chat_id": chat_id, "subject": subject, "body": body})
        if chat_id in self.fail_for:
            raise RuntimeError("telegram unavailable")
        return True


def _user(login: str, chat_id: str) -> User:
    return User(
        id=1,
        login=login,
        password_hash="hash",
        role="owner",
        telegram_chat_id=chat_id,
    )


def test_order_notification_uses_user_level_recipients_and_continues_on_failure():
    order = Order.create(id=42, name="Alice", phone="+375291234567", comment="")
    access = FakeAccessFacade([_user("owner", "owner-chat"), _user("super", "super-chat")])
    system = FakeSystemFacade(fail_for={"owner-chat"})
    acl = SystemNotificationAcl(_system=system, _access=access)

    acl.notify_new_order(order)

    assert [item["chat_id"] for item in system.sent] == ["owner-chat", "super-chat"]
    assert all(item["subject"] == "New order" for item in system.sent)
    assert all("Alice" in item["body"] for item in system.sent)
