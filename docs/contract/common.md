# Contract: Common

Cross-cutting wire conventions. Read this before [public.md](public.md)
or [admin.md](admin.md); every endpoint inherits the rules below.

## Authentication

Two transports for the same JWT:

| Transport | Used by |
|---|---|
| `Authorization: Bearer <jwt>` header | External admin clients, SDKs |
| `token=<jwt>` cookie | Admin UI (set by login response) |

JWT claims:

| Claim | Type | Meaning |
|---|---|---|
| `sub` | int | User/customer id |
| `account_type` | string | `admin` or `customer` (backward-compat: missing → `admin`) |
| `role` | string | `owner` or `superadmin` (admin only) |
| `permissions` | object | Non-runtime permission snapshot (admin only; see auth subsystem) |
| `login` | string | Login name (admin only) |
| `email` | string | Email address (customer only) |
| `csrf` | string | CSRF token (if supplied at login) |
| `tv` | int | Token version (for invalidation cache) |
| `exp` | int | Expiry (longer if `remember_me` was true at login) |

`account_type` is the FIRST gate before role/permission checks. Customer
JWTs are rejected by `admin_required`, `permission_required`, and
`superadmin_required` decorators.

Public endpoints take no auth. Recovery uses a URL token, not a JWT.

## CSRF

Cookie-auth unsafe methods (POST/PUT/PATCH/DELETE) MUST include the
`X-CSRF-Token` request header. The value must match the `csrf_token`
cookie set on login.

Bearer-token clients (the `Authorization` header) are exempt from
CSRF — the middleware checks the transport, not the route.

## Error model

Failure responses follow this shape:

```json
{
  "success": false,
  "error": "ERROR_CODE",
  "message": "Human-readable Russian message"
}
```

Status code mapping:

| Status | Meaning |
|---|---|
| `400` | Malformed request (bad JSON, missing required field) |
| `401` | Auth missing or invalid |
| `403` | Authenticated but no required permission, or CSRF failed |
| `404` | Entity not found (or inactive on public catalog endpoints) |
| `409` | Conflict (duplicate slug, conflicting status transition, etc.) |
| `422` | Domain/validation rule violated |
| `429` | Rate limit exceeded |
| `500` | Internal failure; details only in server logs |
| `503` | Infrastructure unavailable (rare) |

5xx responses NEVER expose SQL errors, tracebacks, or internal field
names. Treat the `message` as opaque text.

## Pagination

List endpoints accept:

| Param | Type | Default | Bounds |
|---|---|---|---|
| `page` | int | `1` | `≥ 1` |
| `limit` | int | `20` | `1 .. 100` |

Public-facing list responses include the page envelope:

```json
{ "items": [...], "total": 42, "page": 1, "limit": 20 }
```

Admin search responses include `items` and `total` only — `page` and
`limit` are echoed in the query and not re-emitted.

## Sorting

Admin search endpoints accept:

| Param | Type | Default |
|---|---|---|
| `sort_by` | string (column key) | endpoint-defined |
| `sort_dir` | `asc` or `desc` | `asc` |

Allowed sort columns are whitelisted per endpoint.

## Filtering

Admin search endpoints accept dynamic `field__operator=value` filters.
See [../subsystems/smart-filters.md](../subsystems/smart-filters.md)
for the full schema/operator reference.

## Rate limits

Defaults (configurable via `ROOT_RATE_LIMIT_*`, only enforced when
`ROOT_APP_ENV=prod`):

| Scope | Default |
|---|---|
| Default route | `200 per minute` |
| `POST /auth/login` | `5 per minute` |
| `POST /orders` | `10 per minute` |
| Recovery / Telegram codes | `3 per minute` |

Rate-limit failures return `429`.

## Localization

Error messages are Russian by default. The wire is not localized
beyond that — UI labels are owned by clients.
