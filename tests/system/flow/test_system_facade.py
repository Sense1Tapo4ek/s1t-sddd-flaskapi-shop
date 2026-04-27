from __future__ import annotations

import pytest

from system.config import SystemConfig
from system.domain import SiteSettings
from system.ports.driving.facade import SystemFacade


pytestmark = pytest.mark.flow


class FakeTelegramClient:
    def __init__(self) -> None:
        self.sent_messages: list[dict[str, str]] = []

    def send_message(self, *, token: str, chat_id: str, text: str) -> bool:
        self.sent_messages.append({"token": token, "chat_id": chat_id, "text": text})
        return True


def _settings() -> SiteSettings:
    return SiteSettings(
        id=1,
        phone="+375291234567",
        email="shop@example.com",
        address="Minsk",
        working_hours="10:00-20:00",
        coords_lat=53.9,
        coords_lon=27.56,
        instagram="@shop",
        telegram_bot_token="bot-token",
        telegram_chat_id="chat-42",
    )


def test_send_login_code_uses_configured_ttl_in_telegram_message():
    """
    Given the recovery code TTL is configurable,
    When a Telegram login code is sent,
    Then the Telegram message uses the provided TTL instead of a hard-coded hint.
    """
    # Arrange
    telegram_client = FakeTelegramClient()
    facade = SystemFacade(
        _config=SystemConfig(),
        _get_query=_settings,
        _manage_uc=object(),
        _test_notify_uc=object(),
        _recover_password_uc=object(),
        _fetch_chat_id_uc=object(),
        _notification_channel=object(),
        _telegram_client=telegram_client,
    )

    # Act
    result = facade.send_login_code(
        chat_id="chat-42",
        login="owner",
        code="123456",
        ttl_minutes=17,
    )

    # Assert
    assert result is True
    assert len(telegram_client.sent_messages) == 1
    text = telegram_client.sent_messages[0]["text"]
    assert "Valid for 17 minutes." in text
    assert "Valid for 5 minutes." not in text
