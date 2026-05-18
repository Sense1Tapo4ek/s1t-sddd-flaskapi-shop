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

## Account type gate (first authorization check)

`account_type` claim is checked BEFORE any role/permission rules:

| Guard | Accepts | Rejects |
|---|---|---|
| `admin_required` | `account_type=admin` | `account_type=customer` |
| `customer_required` | `account_type=customer` | `account_type=admin` |
| `permission_required(...)` | `account_type=admin` + permission | `account_type=customer` (no permissions field) |
| `superadmin_required` | `account_type=admin` + role=superadmin | `account_type=customer` + other roles |

Customer JWTs carry no `role` or `permissions` fields. If a customer somehow
obtains an admin JWT, role/permission checks still apply (defense in depth).

## Tokens

- **Algorithm:** HS256.
- **Secret:** `ACCESS_JWT_SECRET`. Must be a strong random value in
  production. Default `change-me-in-production` is a deployment smell.
- **Claims (admin):**
  - `sub` — user id
  - `account_type` — `admin`
  - `login` — login name
  - `role` — `owner` or `superadmin`
  - `permissions` — snapshot of non-runtime permissions at login time
  - `tv` — token version for cache invalidation
  - `csrf` — CSRF token (if supplied at login)
  - `exp` — expiry (longer when `remember_me=true`)
- **Claims (customer):**
  - `sub` — customer id
  - `account_type` — `customer`
  - `email` — customer email
  - `tv` — token version for cache invalidation
  - `csrf` — CSRF token (if supplied at login)
  - `exp` — expiry (longer when `remember_me=true`)
- **Transport:**
  - Admin UI: `token=<jwt>` cookie, set by login response.
  - External API: `Authorization: Bearer <jwt>` header.
  - Customers: same as admin (cookie or bearer header).

## Permission set

The eight permissions enforced server-side:

| Permission | Meaning |
|---|---|
| `view_category_tree` | Read taxonomy structure (baseline for any authenticated admin) |
| `edit_taxonomy` | Create/update/delete categories, tags, attributes |
| `view_products` | Open product admin pages and product search |
| `edit_products` | Create/update/delete products and images |
| `view_orders` | Read orders **and inquiries** (D2 deferred — see below) |
| `manage_orders` | Change status of orders **and inquiries** (D2 deferred) |
| `manage_settings` | Edit store and Telegram settings |
| `create_demo_data` | Run demo catalog generator |

**D2 deferred:** separate `view_inquiries`/`manage_inquiries` permissions
are planned but not yet implemented. Currently `view_orders` and
`manage_orders` guard both the orders and inquiries admin endpoints.
When D2 lands, the permission set grows to ten and a new implication
rule `manage_inquiries → view_inquiries` is added.

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
| Admin page read | `permission_required("view_*")`, `any_permission_required(...)`, or `admin_required` for security/account pages |
| Admin mutation | Specific edit/manage permission via `permission_required(...)` |
| Superadmin-only | `superadmin_required` (enforces role=superadmin + account_type=admin) |
| Customer-only | `customer_required` (enforces account_type=customer) |
| Public API | No JWT; visibility enforced inside the use case / repository |

The `admin_required`, `customer_required`, and `permission_required(...)` decorators all check `account_type` FIRST.

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
