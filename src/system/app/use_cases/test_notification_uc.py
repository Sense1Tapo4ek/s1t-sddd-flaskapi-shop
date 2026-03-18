from dataclasses import dataclass

from system.app.interfaces.i_notification_channel import INotificationChannel


@dataclass(frozen=True, slots=True, kw_only=True)
class TestNotificationUseCase:
    _channel: INotificationChannel

    def __call__(self) -> bool:
        if not self._channel.is_configured():
            return False
        self._channel.send("Test", "Notification integration works!")
        return True
