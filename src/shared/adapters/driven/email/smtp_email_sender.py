import hashlib
import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from shared.config import EmailConfig
from shared.generics.errors import DrivenPortError

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True, kw_only=True)
class SmtpEmailSender:
    _config: EmailConfig

    def send(self, to: str, subject: str, body: str) -> None:
        cfg = self._config
        msg = EmailMessage()
        msg["From"] = cfg.from_addr
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)

        try:
            with smtplib.SMTP(cfg.host, cfg.port, timeout=cfg.timeout) as conn:
                if cfg.use_tls:
                    conn.starttls()
                if cfg.user and cfg.password:
                    conn.login(cfg.user, cfg.password)
                conn.send_message(msg)
        except (smtplib.SMTPException, OSError) as exc:
            raise DrivenPortError("SMTP delivery failed", code="SMTP_ERROR") from exc

        to_hash = hashlib.sha256(to.encode()).hexdigest()[:8]
        logger.info(
            "email_sent",
            extra={"to_hash": to_hash, "subject": subject},
        )
