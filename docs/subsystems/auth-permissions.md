# Subsystem: auth & permissions

For contributors adding routes or changing auth/permission behaviour
across contexts. End-to-end coverage: JWT issuance, cookie/header
transport, CSRF, server-side permission checks, public/admin boundary.

## Mental model

```
        login                       request
    user ────> POST /auth/login ─┐  ─────> Flask
                                 │             │
            password OR TG code  │             ├─ middleware: parse JWT
                                 │             │   (Authorization: Bearer
                                 ▼             │    OR token=<jwt> cookie)
            access.AccessFacade  │             │
                  resolve_perms ─┘             ├─ middleware: CSRF on
                                               │   cookie-auth POST/PUT/
            JWT { sub, role,                   │   PATCH/DELETE
                  permissions[non_runtime],    │
                  exp }                        ├─ route decorator:
                                               │   @permission_required
                                               │   @any_permission_required
                                               │   @jwt_required
                                               │
                                               ▼
                                          facade.method(...)
```

## Tokens

- **Algorithm:** HS256.
- **Secret:** `ACCESS_JWT_SECRET`. Must be a strong random value in
  production. Default `change-me-in-production` is a deployment smell.
- **Claims:**
  - `sub` — admin id
  - `role` — `owner` or `superadmin`
  - `permissions` — snapshot of non-runtime permissions at login time
  - `exp` — expiry (longer when `remember_me=true`)
- **Transport:**
  - Admin UI: `token=<jwt>` cookie, set by login response.
  - External API: `Authorization: Bearer <jwt>` header.

## Permission set

The eight permissions enforced server-side:

| Permission | Meaning |
|---|---|
| `view_category_tree` | Read taxonomy structure (baseline for any authenticated admin) |
| `edit_taxonomy` | Create/update/delete categories, tags, attributes |
| `view_products` | Open product admin pages and product search |
| `edit_products` | Create/update/delete products and images |
| `view_orders` | Read orders |
| `manage_orders` | Change order status, create/delete test orders |
| `manage_settings` | Edit store and Telegram settings |
| `create_demo_data` | Run demo catalog generator |

### Implication rules (enforced in `resolve_permissions`)

| If allowed | Must also allow |
|---|---|
| Any authenticated admin | `view_category_tree` |
| `edit_products` | `view_products`, `view_category_tree` |
| `edit_taxonomy` | `view_category_tree` |
| `manage_orders` | `view_orders` |
| `create_demo_data` | `view_category_tree`, `edit_taxonomy`, `view_products`, `edit_products` |

### Runtime vs snapshot permissions

- **Runtime** (re-resolved per request from `settings`):
  `view_category_tree`, `edit_taxonomy`, `view_products`,
  `edit_products`, `create_demo_data`. Toggling a flag takes effect
  immediately.
- **Snapshot** (frozen in JWT until next login):
  `view_orders`, `manage_orders`, `manage_settings`. Toggling these
  requires logout/login.

`superadmin` always gets every permission; flags do not apply.

## Route guard rules

| Route type | Decorator |
|---|---|
| Admin page read | `permission_required("view_*")`, `any_permission_required(...)`, or `jwt_required` for security/account pages |
| Admin mutation | Specific edit/manage permission |
| Superadmin-only | Dedicated permission (`create_demo_data`) or `superadmin_required` when owners must never reach the action |
| Public API | No JWT; visibility enforced inside the use case / repository |

UI hiding (omitting a button when `permission` is false) is a UX nicety,
not authorization. Every protected endpoint must declare a server-side
guard.

## CSRF model

CSRF protection lives in `shared/adapters/driving/middleware.py`. The
rules are:

- Cookie-auth unsafe methods (POST/PUT/PATCH/DELETE) require
  `X-CSRF-Token` matching the `csrf_token` cookie.
- The admin UI fetches `csrf_token` from the cookie and sends it on
  every HTMX/`fetch` mutation automatically.
- `Authorization: Bearer <jwt>` clients are exempt — the middleware
  checks the transport, not the route.
- GET/HEAD/OPTIONS never require CSRF.

## Telegram code flow

Two flows share the same `recovery_code_*` columns on `admins`:

1. **Admin UI login** — `POST /admin/telegram/request-code` →
   `POST /admin/verify-code`. Code is generated, hashed, and sent to
   the user's `telegram_chat_id`. Verifying a correct code issues a JWT.
2. **Password change** — `POST /admin/settings/security/password-code`
   → `POST /auth/password` with `confirmation_code`. Same hash + TTL
   pipeline.

Defaults: 60s send cooldown, 5-minute TTL, 5 attempts before lockout,
15-minute lockout window. All configurable via `ACCESS_RECOVERY_CODE_*`
env vars.

## Public/admin data boundary

| Area | Rule |
|---|---|
| Public product list/random | Force `is_active=true` outside user-overridable filters |
| Public product detail | Inactive returns 404 like missing |
| Public filters | Whitelisted keys only; never pass arbitrary query params to a generic DB filter helper |
| Public category tree | Active only; counts must count active products only |
| Public tags | Active only |
| Public store info | Only fields on the public schema; bot token / recovery / owner flags never exposed |

Start any new public endpoint by defining its **output** schema. If a
field is not on the schema, do not include it.

## Pointers

- Permission resolver: `src/access/permissions.py`
- Runtime perms (catalog): `src/access/app/runtime_permissions.py`
- Middleware: `src/shared/adapters/driving/middleware.py`
- Error handlers: `src/shared/adapters/driving/error_handlers.py`
- Recovery flow code: `src/access/app/use_cases/`
- Admin contract: [../contract/admin.md](../contract/admin.md)
- Public contract: [../contract/public.md](../contract/public.md)
