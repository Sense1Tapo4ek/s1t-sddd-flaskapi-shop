# Infra: SMTP

Outbound transactional email via SMTP. Currently used only for customer
password recovery codes. Falling back to log-only mode in development.

## Configuration

| Env var | Type | Default | Description |
|---|---|---|---|
| `SMTP_HOST` | string | `""` | SMTP server hostname |
| `SMTP_PORT` | int | `587` | SMTP port |
| `SMTP_USER` | string | `""` | Auth username (empty = no auth) |
| `SMTP_PASSWORD` | string | `""` | Auth password |
| `SMTP_FROM` | string | `noreply@shop.local` | `From` address on all messages |
| `SMTP_USE_TLS` | bool | `true` | Enable STARTTLS |
| `SMTP_TIMEOUT` | int | `10` | Socket timeout in seconds |

Defined in `src/shared/config.py:EmailConfig` with env prefix `SMTP_`.

## Implementations

### SmtpEmailSender (Production)

Sends messages via `smtplib.SMTP`. Built-in TLS support.

- **Logging:** recipient email is hashed (sha256[:8]) for privacy; subject
  is logged as-is; body and recovery code are never logged.
- **Error handling:** `smtplib.SMTPException` and `OSError` are caught and
  wrapped in `DrivenPortError(code="SMTP_ERROR")`, surfacing as **503
  Service Unavailable** to the client.

File: `src/shared/adapters/driven/email/smtp_email_sender.py`.

### LoggingEmailSender (Development fallback)

Logs messages instead of sending. Useful for testing without a real SMTP
server.

- **Log level:** WARNING in production, DEBUG otherwise.
- **Body visibility:** suppressed in production (logged as `[RECOVERY CODE
  SUPPRESSED]`), printed in dev.
- **Recipient:** hashed for privacy (sha256[:8]).

File: `src/shared/adapters/driven/email/logging_email_sender.py`.

## Local Development

To test without a real SMTP server:

1. Keep `SMTP_HOST=""` (empty). The app will wire `LoggingEmailSender` instead.
2. Run the app and watch logs when a customer requests password recovery:
   ```
   DEBUG:access... EMAIL_FAKE_SEND to_hash=abc123 subject=Восстановление пароля body=Ваш код: 123456...
   ```

To test with a real SMTP server (e.g., mailpit on localhost):

1. Set `SMTP_HOST=localhost`, `SMTP_PORT=1025` (mailpit SMTP port), `SMTP_USE_TLS=false`.
2. Run mailpit: `docker run --rm -d -p 1025:1025 -p 8025:8025 axllent/mailpit`.
3. Send a recovery email from the UI. Check http://localhost:8025 for the message.

## Sender Selection

In `src/access/provider.py`, the DI container chooses:

- If `SMTP_HOST` is empty → `LoggingEmailSender`.
- Otherwise → `SmtpEmailSender`.

## Related

- Customer password recovery: `src/access/app/use_cases/send_customer_recovery_code_uc.py`.
- Use case catches exceptions and raises `EmailRecoveryFailedError`.
- Facade (`ports/driving/`) returns HTTP 202 regardless, suppressing delivery
  errors from the client (to avoid leaking whether a customer email exists).
