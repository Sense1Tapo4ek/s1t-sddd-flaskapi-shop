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

## Orders

### `POST /orders`

Place a customer order. Returns 201 even if Telegram dispatch fails
(notifications are best-effort).

Body:

```json
{ "name": "Иван Иванов", "phone": "+375291234567", "comment": "..." }
```

| Field | Type | Required |
|---|---|---|
| `name` | string | yes |
| `phone` | string | yes |
| `comment` | string | no |

`201`:

```json
{ "success": true, "id": 42 }
```

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
  "socials": { "instagram": "@shopname" }
}
```

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
