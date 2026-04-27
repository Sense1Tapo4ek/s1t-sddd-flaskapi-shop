from datetime import datetime, timedelta, timezone

import pytest

from system.app import FetchTelegramChatIdUseCase
from system.domain import SiteSettings
from system.domain.errors import (
    SettingsNotFoundError,
    TelegramBotNotStartedError,
    TelegramStartNotFoundError,
    TelegramTokenInvalidError,
)


pytestmark = pytest.mark.flow


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


class FakeTelegramClient:
    def __init__(self, *, updates: list[dict] | None = None) -> None:
        self.updates = updates or []
        self.tokens: list[str] = []

    def get_updates(self, token: str) -> list[dict]:
        self.tokens.append(token)
        return self.updates


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
        telegram_bot_token="",
        telegram_chat_id="",
    )


def _start_update(*, chat_id: int, age: timedelta) -> dict:
    started_at = datetime.now(timezone.utc) - age
    return {
        "message": {
            "text": "/start",
            "date": int(started_at.timestamp()),
            "chat": {"id": chat_id},
        }
    }


class TestFetchTelegramChatIdUseCase:
    def test_rejects_missing_token_without_fetching_updates(self):
        """
        Given an empty Telegram bot token,
        When fetching a Telegram chat id,
        Then the use case rejects the token without calling Telegram.
        """
        # Arrange
        repo = InMemorySettingsRepo(_settings())
        telegram_client = FakeTelegramClient()
        use_case = FetchTelegramChatIdUseCase(_repo=repo, _client=telegram_client)

        # Act
        with pytest.raises(TelegramTokenInvalidError) as exc_info:
            use_case("")

        # Assert
        assert exc_info.value.code == "INVALID_TELEGRAM_TOKEN"
        assert telegram_client.tokens == []
        assert repo.saved == []

    def test_rejects_when_no_updates_exist(self):
        """
        Given a Telegram bot token with no updates,
        When fetching a Telegram chat id,
        Then the use case asks the user to start the bot and does not save settings.
        """
        # Arrange
        repo = InMemorySettingsRepo(_settings())
        telegram_client = FakeTelegramClient(updates=[])
        use_case = FetchTelegramChatIdUseCase(_repo=repo, _client=telegram_client)

        # Act
        with pytest.raises(TelegramBotNotStartedError) as exc_info:
            use_case("bot-token")

        # Assert
        assert exc_info.value.code == "BOT_NOT_STARTED"
        assert telegram_client.tokens == ["bot-token"]
        assert repo.saved == []

    def test_rejects_stale_start_message(self):
        """
        Given only an old /start Telegram update,
        When fetching a Telegram chat id,
        Then the use case rejects the stale update and does not save settings.
        """
        # Arrange
        repo = InMemorySettingsRepo(_settings())
        telegram_client = FakeTelegramClient(
            updates=[_start_update(chat_id=123, age=timedelta(minutes=16))]
        )
        use_case = FetchTelegramChatIdUseCase(_repo=repo, _client=telegram_client)

        # Act
        with pytest.raises(TelegramStartNotFoundError) as exc_info:
            use_case("bot-token")

        # Assert
        assert exc_info.value.code == "START_MESSAGE_NOT_FOUND"
        assert telegram_client.tokens == ["bot-token"]
        assert repo.saved == []

    def test_returns_fresh_start_chat_id_without_saving_global_settings(self):
        """
        Given a fresh /start Telegram update and existing settings,
        When fetching a Telegram chat id,
        Then the use case returns it for the current user field without mutating global settings.
        """
        # Arrange
        settings = _settings()
        repo = InMemorySettingsRepo(settings)
        telegram_client = FakeTelegramClient(
            updates=[
                _start_update(chat_id=111, age=timedelta(minutes=16)),
                _start_update(chat_id=777, age=timedelta(minutes=1)),
            ]
        )
        use_case = FetchTelegramChatIdUseCase(_repo=repo, _client=telegram_client)

        # Act
        chat_id = use_case("fresh-token")

        # Assert
        assert chat_id == "777"
        assert settings.telegram_bot_token == ""
        assert settings.telegram_chat_id == ""
        assert repo.saved == []
        assert telegram_client.tokens == ["fresh-token"]

    def test_missing_settings_raises_not_found_without_fetching_updates(self):
        """
        Given no settings aggregate,
        When fetching a Telegram chat id,
        Then the use case raises SettingsNotFoundError without calling Telegram.
        """
        # Arrange
        repo = InMemorySettingsRepo(None)
        telegram_client = FakeTelegramClient(
            updates=[_start_update(chat_id=777, age=timedelta(minutes=1))]
        )
        use_case = FetchTelegramChatIdUseCase(_repo=repo, _client=telegram_client)

        # Act
        with pytest.raises(SettingsNotFoundError) as exc_info:
            use_case("fresh-token")

        # Assert
        assert exc_info.value.code == "SETTINGS_NOT_FOUND"
        assert repo.saved == []
        assert telegram_client.tokens == []
