import hashlib
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_SUPPRESSED = "[RECOVERY CODE SUPPRESSED]"


@dataclass(frozen=True, slots=True, kw_only=True)
class LoggingEmailSender:
    _app_env: str

    def send(self, to: str, subject: str, body: str) -> None:
        to_hash = hashlib.sha256(to.encode()).hexdigest()[:8]
        logged_body = body if self._app_env != "prod" else _SUPPRESSED
        level = logging.WARNING if self._app_env == "prod" else logging.DEBUG
        logger.log(
            level,
            "EMAIL_FAKE_SEND to_hash=%s subject=%s body=%s",
            to_hash,
            subject,
            logged_body,
        )
