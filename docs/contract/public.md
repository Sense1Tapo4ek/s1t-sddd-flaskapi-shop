# Contract: Public

Storefront/unauthenticated endpoints. No JWT required. Inactive
entities are never exposed; inactive products return 404 like missing.

Common conventions (auth, error model, pagination, rate limits) live
in [common.md](common.md).

---

## Catalog

### `GET /catalog`

Paginated list of active products.

Query params:

| Param | Type | Default | Description |
|---|---|---|---|
| `page` | int | `1` | Page number |
| `limit` | int | `20` | Items per page (1-100) |
| `category` | string | — | Category slug |
| `category_id` | int | — | Category id |
| `include_descendants` | bool | `false` | Include child categories |
| `tags` | string | — | Comma-separated tag slugs |
| `attr.<code>` | string | — | Attribute filter |

`is_active` query params from public clients are ignored — active
visibility is forced server-side.

`200`:

```json
{
  "items": [
    {
      "id": 1,
      "title": "Беспроводные наушники",
      "price": 49.99,
      "image": "/media/products/abc.jpg",
      "category_id": 4,
      "category": { "id": 4, "title": "Платья", "slug": "dresses" },
      "tags": []
    }
  ],
  "total": 42,
  "page": 1,
  "limit": 20
}
```

---

### `GET /catalog/random`

Random sample of active products.

Query params:

| Param | Type | Default | Bounds |
|---|---|---|---|
| `limit` | int | `4` | 1-20 |

`200`:

```json
[
  { "id": 5, "title": "...", "price": 29.99, "image": "/media/products/xyz.jpg" }
]
```

---

### `GET /catalog/{product_id}`

Active product detail.

`200`:

```json
{
  "id": 1,
  "title": "Беспроводные наушники",
  "price": 49.99,
  "description": "...",
  "images": ["/media/products/abc.jpg", "/media/products/def.jpg"],
  "category_id": 4,
  "category": { "id": 4, "title": "Платья", "slug": "dresses" },
  "category_path": ["Одежда", "Платья"],
  "tags": [],
  "attributes": [],
  "created_at": "2025-03-15"
}
```

`404` (also returned for inactive products):

```json
{ "success": false, "error": "PRODUCT_NOT_FOUND", "message": "Товар 123 не найден" }
```

---

### `GET /catalog/categories/tree`

Active categories as a nested tree.

### `GET /catalog/tags`

Active tags. Product counts count active products only.

---

## Auth

### `POST /auth/login`

Issue JWT token. Dispatch on `"@" in login`: contains `@` → customer (search email); no `@` → admin (search login).

Body: `{ "login": "...", "password": "...", "remember_me": false }`

`200`: `{ "token": "eyJ0eXAi..." }` (sets `token` and `csrf_token` cookies)

`401`: `{ "error": "INVALID_CREDENTIALS" }` or `{ "error": "ACCOUNT_INACTIVE" }`

---

### `POST /auth/customer/register`

Create customer account and issue JWT. Body: `{ "email": "...", "password": "..." }`

`201`: `{ "token": "eyJ0eXAi..." }` (same behavior as login)

`409`: `{ "error": "EMAIL_EXISTS" }`

---

### `POST /auth/customer/recover`

Request password recovery code. Always `202` (no email enumeration).
Body: `{ "email": "..." }`. Code sent via SMTP ([../infra/smtp.md](../infra/smtp.md)).

---

### `POST /auth/customer/verify`

Verify code and reset password. Body: `{ "email": "...", "code": "123456", "password": "..." }`

`200`: `{ "token": "eyJ0eXAi..." }` (same behavior as login)

`401`: `{ "error": "INVALID_CODE" }` or `{ "error": "CODE_EXPIRED" }`

---

## Inquiries

### `POST /inquiries`

Submit a guest contact inquiry. Anonymous — no JWT required. Returns
201 even if Telegram dispatch fails (notifications are best-effort).

Rate-limited: `5 per minute` per IP. `429` on excess.

Body:

```json
{ "name": "Иван Иванов", "phone": "+375291234567", "message": "Здравствуйте..." }
```

| Field | Type | Required |
|---|---|---|
| `name` | string | yes |
| `phone` | string | no |
| `contact_email` | string (email) | no |
| `message` | string | yes |

`201`:

```json
{ "success": true, "id": 42 }
```

---

## Orders

> **Feature-gated.** All `/orders*` routes exist only when
> `ORDERING_ORDERS_ENABLED=true` (default). When the flag is `false`,
> every path in this section returns `404` and is absent from the
> OpenAPI spec. See [../subsystems/feature-flags.md](../subsystems/feature-flags.md).

### `POST /orders`

Place a customer order. Requires a **customer** JWT — admin JWTs are
rejected with `403`. Returns 201 even if Telegram dispatch fails.

`customer_user_id` is sourced from JWT `sub`; it MUST NOT appear in
the request body (schema rejects it if present).

Body:

```json
{
  "items": [
    { "product_id": 5, "quantity": 2 }
  ],
  "contact_phone": "+375 29 000-00-00",
  "contact_email": "buyer@example.com",
  "delivery_method": "courier",
  "address": "ул. Примерная, 1",
  "delivery_comment": "",
  "comment": "Позвоните за час"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `items` | array | yes | Non-empty; each: `product_id` (int) + `quantity` (int ≥ 1) |
| `contact_phone` | string | **yes** | 5–30 chars, regex `^[\d\s\+\-\(\)]+$` |
| `contact_email` | string | no | Max 255 chars; empty string allowed |
| `delivery_method` | `"pickup"` \| `"courier"` | yes | |
| `address` | string | yes if courier | Required and non-empty when method is `courier` |
| `delivery_comment` | string | no | |
| `comment` | string | no | |

`201`:

```json
{ "success": true, "id": 56 }
```

`401`: missing or invalid JWT.
`403`: JWT is an admin token (not customer).
`404`: a referenced product does not exist or is inactive.
`422`: empty items list, courier delivery without address, or invalid/missing `contact_phone`.

---

## System

### `GET /system/info`

Public store card. No sensitive fields.

`200`:

```json
{
  "app_name": "Мой магазин",
  "phone": "+375 29 123-45-67",
  "address": "ул. Примерная, 123",
  "email": "info@example.com",
  "working_hours": "Пн-Пт 09:00 - 18:00",
  "coords": { "lat": 53.9, "lon": 27.56 },
  "socials": {
    "instagram": "https://instagram.com/shop",
    "telegram":  "https://t.me/shop",
    "whatsapp":  null,
    "viber":     null
  }
}
```

Each `socials.<channel>` field is independently gated by a
`SYSTEM_SOCIALS_<CHANNEL>_ENABLED` env flag (default `true`). Disabled
channels appear as `null` — clients SHOULD render only truthy values.
See [../subsystems/feature-flags.md](../subsystems/feature-flags.md).

Bot token, recovery state, owner-permission flags, and storage
credentials are NEVER returned here.

---

### `POST /system/settings/recover-password/{token}`

Trigger Telegram password recovery. `{token}` must match
`SYSTEM_RECOVERY_TOKEN`. The message is sent to the target admin's
per-user `telegram_chat_id`.

`200`:

```json
{ "success": true }
```

`404`:

```json
{ "success": false, "error": "NOT_FOUND", "message": "Неверный путь восстановления" }
```

`500`:

```json
{ "success": false, "error": "RECOVERY_FAILED", "message": "Не удалось отправить сообщение" }
```

The route is public by design; secrecy lives in the token. Rate-limit
it via `ROOT_RATE_LIMIT_RECOVERY` in production.
