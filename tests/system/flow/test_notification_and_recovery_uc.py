import pytest

from system.app import RecoverPasswordUseCase
from system.app import TestNotificationUseCase as NotificationTestUseCase
from system.app.use_cases.recover_password_uc import TelegramNotConfiguredError
from system.domain import SettingsNotFoundError, SiteSettings


pytestmark = pytest.mark.flow


class FakeNotificationChannel:
    def __init__(self, *, configured: bool) -> None:
        self.configured = configured
        self.sent: list[tuple[str, str]] = []

    def is_configured(self) -> bool:
        return self.configured

    def send(self, subject: str, body: str) -> None:
        self.sent.append((subject, body))


class InMemorySettingsRepo:
    def __init__(self, settings: SiteSettings | None) -> None:
        self.settings = settings
        self.saved: list[SiteSettings] = []
        self.get_calls = 0

    def get(self) -> SiteSettings | None:
        self.get_calls += 1
        return self.settings

    def save(self, settings: SiteSettings) -> None:
        self.saved.append(settings)
        self.settings = settings


class FakeAccessAcl:
    def __init__(self, *, code: str = "123456", chat_id: str = "user-chat") -> None:
        self.code = code
        self.chat_id = chat_id
        self.generate_calls = 0
        self.clear_calls = 0

    def generate_recovery_code(self) -> str:
        self.generate_calls += 1
        return self.code

    def request_recovery_code(self) -> tuple[str, str, str]:
        self.generate_calls += 1
        return "admin", self.chat_id, self.code

    def clear_recovery_code(self) -> None:
        self.clear_calls += 1

    def reset_admin_password(self) -> str:
        raise AssertionError("reset_admin_password should not be used in this flow")


class FakeTelegramClient:
    def __init__(self, *, result: bool = True) -> None:
        self.result = result
        self.sent_messages: list[dict[str, str]] = []

    def send_message(self, *, token: str, chat_id: str, text: str) -> bool:
        self.sent_messages.append({"token": token, "chat_id": chat_id, "text": text})
        return self.result


def _settings(
    *,
    telegram_bot_token: str = "bot-token",
    telegram_chat_id: str = "chat-42",
) -> SiteSettings:
    return SiteSettings(
        id=1,
        phone="+375291234567",
        email="shop@example.com",
        address="Minsk",
        working_hours="10:00-20:00",
        coords_lat=53.9,
        coords_lon=27.56,
        instagram="@shop",
        telegram_bot_token=telegram_bot_token,
        telegram_chat_id=telegram_chat_id,
    )


class TestTestNotificationUseCase:
    def test_returns_false_when_channel_not_configured_and_does_not_send(self):
        """
        Given a notification channel without configuration,
        When testing notification delivery,
        Then the use case returns False and does not send a message.
        """
        # Arrange
        channel = FakeNotificationChannel(configured=False)
        use_case = NotificationTestUseCase(_channel=channel)

        # Act
        result = use_case()

        # Assert
        assert result is False
        assert channel.sent == []

    def test_sends_when_channel_is_configured(self):
        """
        Given a configured notification channel,
        When testing notification delivery,
        Then the use case sends a test notification and returns True.
        """
        # Arrange
        channel = FakeNotificationChannel(configured=True)
        use_case = NotificationTestUseCase(_channel=channel)

        # Act
        result = use_case()

        # Assert
        assert result is True
        assert channel.sent == [("Test", "Notification integration works!")]


class TestRecoverPasswordUseCase:
    def test_rejects_missing_settings(self):
        """
        Given no settings aggregate exists,
        When recovering the password,
        Then the use case raises SettingsNotFoundError without generating a code.
        """
        # Arrange
        repo = InMemorySettingsRepo(None)
        access_acl = FakeAccessAcl()
        telegram_client = FakeTelegramClient()
        use_case = RecoverPasswordUseCase(
            _repo=repo,
            _client=telegram_client,
            _access_acl=access_acl,
        )

        # Act
        with pytest.raises(SettingsNotFoundError) as exc_info:
            use_case()

        # Assert
        assert exc_info.value.code == "SETTINGS_NOT_FOUND"
        assert access_acl.generate_calls == 0
        assert telegram_client.sent_messages == []

    def test_rejects_unconfigured_bot_token(self):
        """
        Given settings without a Telegram bot token,
        When recovering the password,
        Then the use case raises TelegramNotConfiguredError without sending anything.
        """
        # Arrange
        repo = InMemorySettingsRepo(
            _settings(telegram_bot_token="", telegram_chat_id="legacy-global")
        )
        access_acl = FakeAccessAcl()
        telegram_client = FakeTelegramClient()
        use_case = RecoverPasswordUseCase(
            _repo=repo,
            _client=telegram_client,
            _access_acl=access_acl,
        )

        # Act
        with pytest.raises(TelegramNotConfiguredError) as exc_info:
            use_case()

        # Assert
        assert exc_info.value.code == "TELEGRAM_NOT_CONFIGURED"
        assert access_acl.generate_calls == 0
        assert telegram_client.sent_messages == []

    def test_rejects_missing_user_chat_id(self):
        """
        Given a Telegram bot token but the target user has no chat id,
        When recovering the password,
        Then the use case clears the code and reports Telegram as unconfigured.
        """
        # Arrange
        repo = InMemorySettingsRepo(_settings(telegram_bot_token="bot-token", telegram_chat_id=""))
        access_acl = FakeAccessAcl(chat_id="")
        telegram_client = FakeTelegramClient()
        use_case = RecoverPasswordUseCase(
            _repo=repo,
            _client=telegram_client,
            _access_acl=access_acl,
        )

        # Act
        with pytest.raises(TelegramNotConfiguredError) as exc_info:
            use_case()

        # Assert
        assert exc_info.value.code == "TELEGRAM_NOT_CONFIGURED"
        assert access_acl.generate_calls == 1
        assert access_acl.clear_calls == 1
        assert telegram_client.sent_messages == []

    def test_generates_recovery_code_and_sends_telegram_message(self):
        """
        Given configured Telegram settings and an access ACL,
        When recovering the password,
        Then the use case generates a recovery code and sends it through Telegram.
        """
        # Arrange
        repo = InMemorySettingsRepo(_settings())
        access_acl = FakeAccessAcl(code="654321")
        telegram_client = FakeTelegramClient(result=True)
        use_case = RecoverPasswordUseCase(
            _repo=repo,
            _client=telegram_client,
            _access_acl=access_acl,
        )

        # Act
        result = use_case()

        # Assert
        assert result is True
        assert access_acl.generate_calls == 1
        assert telegram_client.sent_messages == [
            {
                "token": "bot-token",
                "chat_id": "user-chat",
                "text": (
                    "<b>Login Code</b>\n\n"
                    "Account: <code>admin</code>\n"
                    "Your one-time code:\n"
                    "<code>654321</code>\n\n"
                    "Valid for 5 minutes."
                ),
            }
        ]

    def test_returns_false_when_telegram_send_fails(self):
        """
        Given configured Telegram settings and a Telegram client that cannot send,
        When recovering the password,
        Then the use case clears the unusable code and returns the send result.
        """
        # Arrange
        repo = InMemorySettingsRepo(_settings())
        access_acl = FakeAccessAcl(code="654321")
        telegram_client = FakeTelegramClient(result=False)
        use_case = RecoverPasswordUseCase(
            _repo=repo,
            _client=telegram_client,
            _access_acl=access_acl,
        )

        # Act
        result = use_case()

        # Assert
        assert result is False
        assert access_acl.generate_calls == 1
        assert access_acl.clear_calls == 1
        assert len(telegram_client.sent_messages) == 1
