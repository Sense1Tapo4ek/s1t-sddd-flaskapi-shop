# Subsystem: notifications (Telegram)

For contributors touching any Telegram-driven flow: order
notifications, login codes, password-change codes, password recovery.

## Mental model

One bot. Three flows. Per-user chat ids stored on `admins`.

```
                  ┌──────────────────────────────┐
                  │  settings.telegram_bot_token  │  global bot credential
                  └──────────────┬───────────────┘
                                 │
              ┌──────────────────┼─────────────────────────┐
              │                  │                         │
      order notifications   login/password codes   password recovery
              │                  │                         │
   active owner+superadmin   per-user code,           system facade →
   admins with chat_id       hashed at rest,          admin's chat_id
                             cooldown/lockout         via URL token
```

- The **bot token** is a global system setting
  (`settings.telegram_bot_token`).
- Every per-user destination is `admins.telegram_chat_id`. The legacy
  global `settings.telegram_chat_id` is only used by the
  `POST /system/settings/test-telegram` button.
- The raw HTTP client to the Bot API lives in
  `src/shared/adapters/driven/telegram_client.py`. Every domain-facing
  call goes through a context-owned channel/ACL.

## Order notifications

When `POST /orders` succeeds, `ordering` dispatches via
`ports/driven/system_notification_acl.py` to every active `owner` and
`superadmin` whose `telegram_chat_id` is set.

Rules:

- **Best-effort.** Network/Telegram failures are logged and swallowed;
  the order is still saved and returned `201`.
- **No global chat id is consulted.** Without per-user chat ids, no
  notification is sent. This is intentional.
- **No new-order recipient is configurable in settings.** Bind chat
  ids per admin on the account page.

## Login & password codes

Two paths share the same `recovery_code_*` columns on `admins`:

- `POST /admin/telegram/request-code` + `POST /admin/verify-code` —
  log in by Telegram code.
- `POST /admin/settings/security/password-code` +
  `POST /auth/password` (with `confirmation_code`) — change password
  by Telegram code instead of the old password.

State machine per user:

```
[idle] ──request──> [code active]
                    │
       ┌── verify ok ┴── tries < max ──> [verified] ──> token / pw change
       │
       └── tries == max ──> [locked until recovery_code_locked_until]
```

Defaults (configurable via `ACCESS_RECOVERY_CODE_*`):

| Setting | Default | Meaning |
|---|---|---|
| `_TTL_MINUTES` | 5 | Code validity window |
| `_COOLDOWN_SECONDS` | 60 | Min interval between successful sends |
| `_MAX_ATTEMPTS` | 5 | Wrong verifications before lockout |
| `_LOCKOUT_MINUTES` | 15 | Lockout duration after max attempts |

Code is hashed at rest (`recovery_code_hash`); only the digest is
compared. The raw code never appears in logs.

## Password recovery

`POST /system/settings/recover-password/{token}` — public route gated
by URL token (`SYSTEM_RECOVERY_TOKEN`). It dispatches a recovery
message to the target admin's `telegram_chat_id`. The route is public
by design; secrecy lives in the token. Rate-limit it.

## Fetching a chat id (binding flow)

`POST /system/settings/telegram/fetch-chat-id` polls the bot's
`getUpdates` for the last 15 minutes and returns any chat id that
recently sent `/start`. It does NOT persist the value to global
settings — it returns it for the account form, which the user then
saves to their own `admins.telegram_chat_id`.

## Cross-context boundary

`ordering` and `access` never import `system` internals. They go
through:

| Caller | ACL |
|---|---|
| `ordering` → bot token + admin chat ids | `src/ordering/ports/driven/system_notification_acl.py` |
| `system` → admin lookup by role | `src/system/ports/driven/access_acl.py` |

When extending a flow, add a method to the ACL, not a direct import.

## Pointers

- Bot HTTP client: `src/shared/adapters/driven/telegram_client.py`
- System Telegram channel: `src/system/ports/driven/telegram_channel.py`
- Recovery code state: `src/access/app/use_cases/recover_password_uc.py`
- Test notification UC: `src/system/app/use_cases/test_notification_uc.py`
- Auth subsystem: [auth-permissions.md](auth-permissions.md)
