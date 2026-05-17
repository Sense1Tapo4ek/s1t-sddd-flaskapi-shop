import hashlib
import logging
import smtplib
from email.message import EmailMessage
from unittest.mock import MagicMock, patch

import pytest

from shared.adapters.driven.email.logging_email_sender import LoggingEmailSender
from shared.adapters.driven.email.smtp_email_sender import SmtpEmailSender
from shared.config import EmailConfig
from shared.generics.errors import DrivenPortError


def _make_smtp_sender(**overrides) -> SmtpEmailSender:
    cfg = EmailConfig(
        host=overrides.get("host", "smtp.example.com"),
        port=overrides.get("port", 587),
        user=overrides.get("user", "user@example.com"),
        password=overrides.get("password", "secret"),
        from_addr=overrides.get("from_addr", "noreply@example.com"),
        use_tls=overrides.get("use_tls", True),
        timeout=overrides.get("timeout", 5),
    )
    return SmtpEmailSender(_config=cfg)


@pytest.mark.flow
class TestSmtpEmailSender:
    def test_sends_message_with_starttls(self):
        """
        Given SMTP config with use_tls=True and credentials,
        When send() is called,
        Then SMTP is constructed, starttls/login/send_message are called.
        """
        sender = _make_smtp_sender()
        mock_smtp = MagicMock()
        mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp.__exit__ = MagicMock(return_value=False)
        mock_smtp_cls = MagicMock(return_value=mock_smtp)

        with patch(
            "shared.adapters.driven.email.smtp_email_sender.smtplib.SMTP",
            mock_smtp_cls,
        ):
            sender.send("to@example.com", "Subject", "Body text")

        mock_smtp_cls.assert_called_once_with(
            "smtp.example.com", 587, timeout=5
        )
        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once_with("user@example.com", "secret")
        mock_smtp.send_message.assert_called_once()
        msg_arg = mock_smtp.send_message.call_args[0][0]
        assert isinstance(msg_arg, EmailMessage)

    def _patched_smtp(self, mock_smtp):
        mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp.__exit__ = MagicMock(return_value=False)
        return patch(
            "shared.adapters.driven.email.smtp_email_sender.smtplib.SMTP",
            MagicMock(return_value=mock_smtp),
        )

    def test_no_starttls_when_disabled(self):
        """
        Given use_tls=False,
        When send() is called,
        Then starttls is NOT called.
        """
        sender = _make_smtp_sender(use_tls=False)
        mock_smtp = MagicMock()
        with self._patched_smtp(mock_smtp):
            sender.send("to@example.com", "Sub", "Body")
        mock_smtp.starttls.assert_not_called()

    def test_no_login_when_no_credentials(self):
        """
        Given empty user/password,
        When send() is called,
        Then login is NOT called.
        """
        sender = _make_smtp_sender(user="", password="")
        mock_smtp = MagicMock()
        with self._patched_smtp(mock_smtp):
            sender.send("to@example.com", "Sub", "Body")
        mock_smtp.login.assert_not_called()

    def test_smtp_exception_raises_driven_port_error(self):
        """
        Given SMTP raises SMTPException,
        When send() is called,
        Then DrivenPortError is raised with original exc as __cause__.
        """
        sender = _make_smtp_sender()
        original = smtplib.SMTPException("connection refused")
        with patch(
            "shared.adapters.driven.email.smtp_email_sender.smtplib.SMTP",
            side_effect=original,
        ):
            with pytest.raises(DrivenPortError) as exc_info:
                sender.send("to@example.com", "Sub", "Body")

        assert exc_info.value.__cause__ is original

    def test_os_error_raises_driven_port_error(self):
        """
        Given SMTP raises OSError (host unreachable),
        When send() is called,
        Then DrivenPortError is raised.
        """
        sender = _make_smtp_sender()
        with patch(
            "shared.adapters.driven.email.smtp_email_sender.smtplib.SMTP",
            side_effect=OSError("connection refused"),
        ):
            with pytest.raises(DrivenPortError):
                sender.send("to@example.com", "Sub", "Body")

    def test_body_not_in_logs(self, caplog):
        """
        Given a message with sensitive body,
        When send() completes,
        Then body text does NOT appear in any log record.
        """
        sender = _make_smtp_sender()
        mock_smtp = MagicMock()
        body = "SUPER_SECRET_BODY_CONTENT"

        with self._patched_smtp(mock_smtp):
            with caplog.at_level(logging.DEBUG):
                sender.send("to@example.com", "Sub", body)

        for record in caplog.records:
            assert body not in record.getMessage()


@pytest.mark.flow
class TestLoggingEmailSender:
    def test_dev_logs_body(self, caplog):
        """
        Given app_env=dev,
        When send() is called,
        Then body appears in log output.
        """
        sender = LoggingEmailSender(_app_env="dev")
        body = "Your recovery code is 123456"

        with caplog.at_level(logging.DEBUG):
            sender.send("to@example.com", "Reset", body)

        full_log = " ".join(r.getMessage() for r in caplog.records)
        assert body in full_log

    def test_prod_suppresses_body(self, caplog):
        """
        Given app_env=prod,
        When send() is called,
        Then body is NOT in logs; suppression marker IS in logs.
        """
        sender = LoggingEmailSender(_app_env="prod")
        body = "Your recovery code is 654321"

        with caplog.at_level(logging.WARNING):
            sender.send("to@example.com", "Reset", body)

        full_log = " ".join(r.getMessage() for r in caplog.records)
        assert body not in full_log
        assert "RECOVERY CODE SUPPRESSED" in full_log

    def test_logs_to_hash_not_plain_email(self, caplog):
        """
        Given any app_env,
        When send() is called,
        Then plain email is NOT in logs; its SHA-256 prefix IS.
        """
        to = "target@example.com"
        expected_hash = hashlib.sha256(to.encode()).hexdigest()[:8]

        for env in ("dev", "prod"):
            caplog.clear()
            sender = LoggingEmailSender(_app_env=env)
            with caplog.at_level(logging.DEBUG):
                sender.send(to, "MySubject", "body")

            full_log = " ".join(r.getMessage() for r in caplog.records)
            assert to not in full_log, f"Plain email leaked in env={env}"
            assert expected_hash in full_log, f"Hash missing in env={env}"
            assert "MySubject" in full_log

    def test_dev_uses_debug_level(self, caplog):
        """
        Given app_env=dev,
        When send() is called,
        Then log level is DEBUG.
        """
        sender = LoggingEmailSender(_app_env="dev")
        with caplog.at_level(logging.DEBUG):
            sender.send("a@b.com", "Sub", "body")
        assert any(r.levelno == logging.DEBUG for r in caplog.records)

    def test_prod_uses_warning_level(self, caplog):
        """
        Given app_env=prod,
        When send() is called,
        Then log level is WARNING.
        """
        sender = LoggingEmailSender(_app_env="prod")
        with caplog.at_level(logging.DEBUG):
            sender.send("a@b.com", "Sub", "body")
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    def test_prod_body_not_in_logs(self, caplog):
        """
        Given LoggingEmailSender in prod mode,
        When send() is called with a sensitive body,
        Then body text does NOT appear in any log record.
        """
        sender = LoggingEmailSender(_app_env="prod")
        body = "PROD_SENSITIVE_BODY_12345"
        with caplog.at_level(logging.DEBUG):
            sender.send("x@example.com", "Sub", body)
        for record in caplog.records:
            assert body not in record.getMessage()
