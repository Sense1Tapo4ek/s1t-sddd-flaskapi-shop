# Context: access

For contributors working inside `src/access/`. Admin users, JWT
issuance, permission resolution, password changes, Telegram login
codes, and password recovery.

## Mental model

`User` (table `admins`) has a role of `owner` or `superadmin`, an
optional `telegram_chat_id`, a password hash, and recovery-code state
(hash, expiry, attempt counter, lockout-until, last-sent-at).

Permission resolution:

- **`superadmin`** receives every permission unconditionally.
- **`owner`** receives a deterministic subset:
  - `view_category_tree` is baseline for any authenticated admin.
  - Other permissions come from `AccessConfig.owner_can_*` env flags
    AND, for runtime catalog permissions (`edit_taxonomy`,
    `view_products`, `edit_products`, `create_demo_data`,
    `view_category_tree`), the current `settings` row at request time.
  - Implication rules (enforced in `permissions.resolve_permissions`):
    `edit_products` → `view_products`, `view_category_tree`;
    `edit_taxonomy` → `view_category_tree`;
    `manage_orders` → `view_orders`;
    `create_demo_data` → taxonomy + products read/edit.

JWT carries a permission snapshot for non-runtime permissions. Runtime
catalog permissions are re-resolved per request from settings, so they
take effect immediately without re-login.

## Public surface

Driving facade: `AccessFacade` in `ports/driving/facade.py`.

| Wire endpoint | Auth | Use case |
|---|---|---|
| `POST /auth/login` | public (rate-limited) | Issue JWT |
| `POST /auth/password` | `jwt_required` | Change own password (old pw OR Telegram code) |
| `POST /admin/telegram/request-code` | UI | Request login code to bound chat |
| `POST /admin/verify-code` | UI | Verify code and issue JWT |
| `POST /admin/settings/security/password-code` | `jwt_required` | Request password-change code |

Routes live in `adapters/driving/api.py` and `adapters/driving/admin.py`.
Wire-level shapes: [../contract/admin.md](../contract/admin.md).

## Invariants & gotchas

- **Bootstrap defaults are weak by design** (`admin/changeme`,
  `superadmin/superadmin`). Production must override
  `ACCESS_DEFAULT_PASSWORD` and `ACCESS_SUPERADMIN_PASSWORD`. The
  DB-dump endpoint additionally requires `password_changed_at` to be
  set on the calling superadmin — the dev fallback can sign in but
  cannot download a dump.
- **Bootstrap reactivates seeded users on startup.** A known finding:
  `bootstrap_access_defaults` re-asserts `role` and `is_active` on the
  seeded `admin`/`superadmin`. Plan a maintenance flag before relying
  on disabling them.
- **JWT permission snapshot is sticky for non-runtime perms.** Changes
  to `owner_can_manage_orders` / `owner_can_manage_settings` env flags
  only land on next login. Add a session-version field before relying
  on instant revocation.
- **Telegram codes are hashed at rest.** `recovery_code_hash`,
  `recovery_code_expires`, `recovery_code_attempts`,
  `recovery_code_last_sent_at`, `recovery_code_locked_until` form the
  rate-limit + lockout state. Cooldown defaults: 60s send cooldown,
  5-minute TTL, 5 attempts, 15-minute lockout.
- **CSRF is enforced in middleware**, not per route. Cookie-auth
  unsafe methods must carry `X-CSRF-Token` (from the `csrf_token`
  cookie). Bearer-token API clients are exempt.
- **`telegram_chat_id` binding is per user.** Fetching the chat id by
  polling bot updates returns the value to the account form; it does
  NOT silently overwrite `settings.telegram_chat_id` (which is legacy).

## Pointers

- Permission resolver: `src/access/permissions.py`
- Runtime perms: `src/access/app/runtime_permissions.py`
- Bootstrap: `src/access/ports/driven/bootstrap.py`
- User aggregate: `src/access/domain/user_agg.py`
- Auth + permissions subsystem: [../subsystems/auth-permissions.md](../subsystems/auth-permissions.md)
- Telegram code flow: [../subsystems/notifications.md](../subsystems/notifications.md)
