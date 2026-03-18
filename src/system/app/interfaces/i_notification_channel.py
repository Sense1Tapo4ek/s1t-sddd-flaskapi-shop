from abc import ABC, abstractmethod


class INotificationChannel(ABC):
    @abstractmethod
    def send(self, subject: str, body: str) -> None: ...

    @abstractmethod
    def is_configured(self) -> bool: ...
