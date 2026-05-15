# Context: system

For contributors working inside `src/system/`. Store settings
(singleton), Telegram bot configuration, public store info, password
recovery dispatch, storage settings (S3/local).

## Mental model

`Settings` is a domain singleton enforced at the table level
(`CHECK (id = 1)`). It stores contact info, social links, coordinates,
the Telegram bot token, the legacy global `telegram_chat_id`, branding
fields (`app_name`, `admin_panel_title`), and `owner_can_*` runtime
permission flags consumed by `access`.

Two aggregates live in this context:

- `SettingsAgg` — contacts, branding, Telegram, owner permission flags.
- `StorageSettingsAgg` — file storage backend selection (local FS vs S3)
  and credentials. Backed by `src/system/domain/storage_settings_agg.py`.

## Public surface

Driving facade: `SystemFacade` in `ports/driving/facade.py`.

| Wire endpoint | Auth | Use case |
|---|---|---|
| `GET /system/info` | public | Public store card (contacts, hours, socials, coords) |
| `GET /system/settings` | `manage_settings` | Full settings (includes bot token) |
| `PUT /system/settings` | `manage_settings` | Partial update |
| `POST /system/settings/test-telegram` | `manage_settings` | Send legacy test message to global chat |
| `POST /system/settings/telegram/fetch-chat-id` | `manage_settings` | Poll bot updates for a chat id |
| `POST /system/settings/recover-password/{token}` | public (URL-token-gated) | Send recovery via Telegram |

Wire-level shapes: [../contract/public.md](../contract/public.md) and
[../contract/admin.md](../contract/admin.md).

## Invariants & gotchas

- **Singleton table.** The `CHECK (id = 1)` constraint enforces exactly
  one row. Repository code must `UPDATE WHERE id = 1`, never `INSERT`.
- **Public `/system/info` is the only non-admin window into settings.**
  It must never return the bot token, recovery token, owner permission
  flags, or storage credentials. Start from the output schema; if a
  field is not on the public schema, it is not exposed.
- **`telegram.chat_id` is legacy.** Order notifications and login codes
  use `admins.telegram_chat_id` per user. The global chat id is kept
  only for the `test-telegram` button. Do not add new code that reads
  it as the order recipient.
- **Recovery is URL-token gated, not session gated.** The route is
  public on purpose; `SYSTEM_RECOVERY_TOKEN` is the only secret. The
  message is dispatched to the target admin's per-user chat id.
- **Owner permission flags are read at JWT issuance** for non-runtime
  permissions, and at every request for catalog runtime permissions.
  Toggling a flag mid-session affects catalog access immediately and
  other access on next login.
- **ACL to access exists.** `ports/driven/access_acl.py` lets `system`
  ask `access` for admins by role when dispatching recovery codes. Do
  not import `access` internals from `system` use cases directly.
- **Boolean settings are typed.** APIFlask schemas coerce `"false"`
  strings to `False`. Do not branch on string truthiness in handlers.

## Pointers

- Settings aggregate: `src/system/domain/settings_agg.py`
- Storage settings aggregate: `src/system/domain/storage_settings_agg.py`
- Telegram channel: `src/system/ports/driven/telegram_channel.py`
- Access ACL: `src/system/ports/driven/access_acl.py`
- Bootstrap defaults: `src/system/ports/driven/bootstrap.py`
- Public store info schema: [../contract/public.md](../contract/public.md)
