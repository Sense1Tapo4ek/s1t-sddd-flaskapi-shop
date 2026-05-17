from typing import Protocol


class IEmailSender(Protocol):
    def send(self, to: str, subject: str, body: str) -> None: ...
