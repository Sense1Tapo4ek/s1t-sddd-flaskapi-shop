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

## Customer accounts

**Aggregate:** `Customer` (table `customers`). Email, password hash, and
recovery-code state (hash, expiry, attempt counter, lockout-until).

**Dispatch:** `LoginUseCase` routes on `"@" in login`:
- Contains `@` → customer path (`ICustomerRepo.get_by_email`).
- No `@` → admin path (`IAdminRepo.get_by_login`).

**Facades (three by actor):**
- `AccessFacade`: `login(schema)` → JWT. Public entry point.
- `CustomerFacade`: `register(schema)`, `send_recovery_code(schema)`,
  `verify_and_reset(schema)` → JWT on success. Driven port for recovery
  code verification.
- `AdminFacade`: admin operations (change password, reset, Telegram codes).

**JWT payload** by `account_type`:
- **admin:** `sub`, `login`, `role`, `permissions[non_runtime]`, `account_type=admin`, `tv`.
- **customer:** `sub`, `email`, `account_type=customer`, `tv`.

Both carry `csrf` (if CSRF token supplied) and follow the same TTL logic
(`remember_me=true` extends expiry).

**SessionCache (in-memory TTL=60s):** Caches `token_version` per account
to short-circuit costly recovery-code hash validations. On password change
or logout, the cache is invalidated, forcing next login.

**Invariants:**
- Recovery code cooldown: 60s (configurable via
  `ACCESS_CUSTOMER_RECOVERY_CODE_COOLDOWN_SECONDS`).
- Recovery code TTL: 15 minutes (configurable via
  `ACCESS_CUSTOMER_RECOVERY_CODE_TTL_MINUTES`).
- Constant-time failures: Both customer and admin login paths burn time
  on failed email/password lookup to avoid username enumeration.

## Public surface

Three driving facades in `ports/driving/`:

- `AccessFacade`: `login(schema)` → JWT (dispatch by `"@"`).
- `AdminFacade`: admin operations.
- `CustomerFacade`: customer self-service (register, recover, verify).

| Wire endpoint | Auth | Facade / Use case |
|---|---|---|
| `POST /auth/login` | public (rate-limited) | AccessFacade.login |
| `POST /auth/customer/register` | public | CustomerFacade.register |
| `POST /auth/customer/recover` | public (always 202) | CustomerFacade.send_recovery_code |
| `POST /auth/customer/verify` | public | CustomerFacade.verify_and_reset |
| `POST /auth/password` | `admin_required` | AdminFacade.change_password |
| `POST /admin/telegram/request-code` | UI | AdminFacade.generate_recovery_code / for_login |
| `POST /admin/verify-code` | UI | AdminFacade.verify_recovery_code / for_login |
| `POST /admin/settings/security/password-code` | `admin_required` | AdminFacade.generate_recovery_code / for_user_id |

Routes live in `adapters/driving/api.py` and `adapters/driving/admin.py`.
Wire-level shapes: [../contract/admin.md](../contract/admin.md) (admin
routes) and [../contract/public.md](../contract/public.md) (customer auth).

## Invariants & gotchas

- **Single superadmin via env flag.** `ACCESS_PROMOTE_TO_SUPERADMIN=true`
  makes the default admin (id=1) a superadmin at bootstrap. Otherwise,
  role is `owner` and permissions come from env flags. Production must
  either set this flag + change the password, or use the web form to
  promote an admin after first login.
- **Bootstrap defaults are weak by design** (`admin/changeme`).
  Production must override `ACCESS_DEFAULT_PASSWORD`. The DB-dump
  endpoint additionally requires `password_changed_at` to be set on the
  calling admin — the dev fallback can sign in but cannot download a
  dump.
- **Bootstrap reactivates seeded users on startup.** A known finding:
  `bootstrap_access_defaults` re-asserts `role` and `is_active` on the
  seeded admin (id=1). Plan a maintenance flag before relying on disabling
  it.
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
- Customer aggregate: `src/access/domain/customer_agg.py`
- Session token cache: `src/access/app/services/session_cache.py`
- Auth + permissions subsystem: [../subsystems/auth-permissions.md](../subsystems/auth-permissions.md)
- Telegram code flow: [../subsystems/notifications.md](../subsystems/notifications.md)
- SMTP email: [../infra/smtp.md](../infra/smtp.md)
