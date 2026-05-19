from typing import Protocol


class INotificationChannel(Protocol):
    def send(self, subject: str, body: str) -> None: ...

    def is_configured(self) -> bool: ...
