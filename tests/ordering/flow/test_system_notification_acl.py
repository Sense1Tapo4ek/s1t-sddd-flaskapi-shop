import pytest

from access.domain import User
from ordering.domain import Inquiry
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


def test_inquiry_notification_uses_user_level_recipients_and_continues_on_failure():
    """
    Given an inquiry and two recipients (one with a failing Telegram chat),
    When notify_inquiry_created is called,
    Then both recipients are contacted, failure on first doesn't stop second.
    """
    inquiry = Inquiry.create(id=42, name="Alice", message="Hello", phone="+375291234567")
    access = FakeAccessFacade([_user("owner", "owner-chat"), _user("super", "super-chat")])
    system = FakeSystemFacade(fail_for={"owner-chat"})
    acl = SystemNotificationAcl(_system=system, _access=access)

    acl.notify_inquiry_created(inquiry)

    assert [item["chat_id"] for item in system.sent] == ["owner-chat", "super-chat"]
    assert all(item["subject"] == "Новое обращение" for item in system.sent)
    assert all("Alice" in item["body"] for item in system.sent)


def test_order_notification_fans_out_to_all_recipients_and_continues_on_failure():
    """
    Given a placed order and two recipients (one with a failing Telegram chat),
    When notify_order_placed is called,
    Then both recipients are contacted, failure on the first doesn't stop the second.
    """
    from decimal import Decimal

    from ordering.domain import (
        DeliveryInfo,
        DeliveryMethod,
        Order,
        OrderItem,
    )

    item = OrderItem(
        product_id=10,
        title_snapshot="Mug",
        unit_price=Decimal("5.00"),
        quantity=2,
    )
    delivery = DeliveryInfo(method=DeliveryMethod.PICKUP)
    order = Order.place(
        customer_user_id=8,
        items=[item],
        delivery=delivery,
        comment="leave at door",
    )
    order.id = 56
    access = FakeAccessFacade([_user("owner", "owner-chat"), _user("super", "super-chat")])
    system = FakeSystemFacade(fail_for={"owner-chat"})
    acl = SystemNotificationAcl(_system=system, _access=access)

    acl.notify_order_placed(order, customer_email="ivan@example.com")

    assert [item["chat_id"] for item in system.sent] == ["owner-chat", "super-chat"]
    assert all(item["subject"] == "Новый заказ" for item in system.sent)
    body = system.sent[0]["body"]
    assert "#56" in body
    assert "customer=8" in body
    assert "ivan@example.com" in body
    assert "pickup" in body
