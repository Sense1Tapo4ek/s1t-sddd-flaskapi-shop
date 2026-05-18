# Contract: Admin

JWT-protected endpoints. Permission column lists the server-side guard
— `superadmin` bypasses every guard. Common conventions (auth
transport, CSRF, error model, pagination, sorting/filtering, rate
limits) live in [common.md](common.md). Permission semantics:
[../subsystems/auth-permissions.md](../subsystems/auth-permissions.md).

---

## Authentication

### `POST /auth/login`

```json
{ "login": "admin", "password": "changeme", "remember_me": false }
```

`200`:

```json
{ "token": "eyJhbGciOi...", "message": "Login successful" }
```

`401`:

```json
{ "success": false, "error": "INVALID_CREDENTIALS", "message": "Неверный логин или пароль" }
```

### Telegram login (admin UI)

```
POST /admin/telegram/request-code
POST /admin/verify-code
```

Code is sent to the `telegram_chat_id` bound to the requested user.
Cooldown, TTL, and lockout: [../subsystems/notifications.md](../subsystems/notifications.md).

### `POST /auth/password` (`jwt_required`)

Change the current admin's password. Provide the current password OR a
valid Telegram confirmation code:

```json
{ "new_password": "newpass123", "old_password": "changeme" }
```

```json
{ "new_password": "newpass123", "confirmation_code": "123456" }
```

Code request: `POST /admin/settings/security/password-code`.

`200`: `{ "success": true }`.

---

## Catalog Management

### `GET /catalog/admin/search` (`view_products`)

SmartTable products endpoint. Query params: `q`, `page`, `limit`,
`sort_by`, `sort_dir`, plus dynamic `field__op=value` filters.

Taxonomy filters: `category_id`, `category` (slug),
`include_descendants`, `tags` (comma-separated slugs), `attr.<code>`,
`attr.<code>__gte`.

Examples: `title__ilike=phone`, `price__gte=100`, `price__lte=500`,
`category_id=4&include_descendants=true&tags=sale,new&attr.size=M`.

`200`:

```json
{
  "items": [
    { "id": 1, "title": "...", "price": 49.99,
      "description": "...", "images": [...], "created_at": "2025-03-15" }
  ],
  "total": 5
}
```

### `GET /catalog/admin/search/schema` (`view_products`)

Returns the SmartTable filter schema. Format:
[../subsystems/smart-filters.md](../subsystems/smart-filters.md).

### `GET /catalog/admin/products/{product_id}` (`view_products`)

Admin product detail. Returns inactive products too.

### `POST /catalog` (`edit_products`)

Multipart create.

| Field | Type | Required |
|---|---|---|
| `title` | string | yes |
| `price` | float | yes |
| `description` | string | no |
| `images` | file[] | no |
| `category_id` | int | no (leaf only) |
| `tag_ids` | string | no (comma-separated) |
| `attribute_values` | JSON string | no (`{code: value}`) |

`201`: full product detail.

### `PUT /catalog/{product_id}` (`edit_products`)

Multipart update. Omitted taxonomy fields are preserved. Send
`tag_ids` or `attribute_values` only when replacing the set.

Additional fields: `new_images` (file[]), `deleted_images` (string[]).

### `DELETE /catalog/{product_id}` (`edit_products`)

Permanently deletes the product and cascades image files.

```json
{ "success": true }
```

### `DELETE /catalog/{product_id}/images` (`edit_products`)

```json
{ "image_path": "/media/products/abc.jpg" }
```

Returns updated product detail.

---

## Catalog Taxonomy

Reads require `view_category_tree` (baseline for any authenticated
admin). Mutations require `edit_taxonomy`.

### Categories

```
GET    /catalog/admin/categories/tree
GET    /catalog/admin/categories/{id}
POST   /catalog/admin/categories
PUT    /catalog/admin/categories/{id}
DELETE /catalog/admin/categories/{id}
POST   /catalog/admin/categories/{id}/move
GET    /catalog/admin/categories/{id}/products
```

`move` rejects cycles and rejects targets that would orphan products
on a non-leaf node.

### Category attributes

```
GET    /catalog/admin/categories/{id}/attributes
POST   /catalog/admin/categories/{id}/attributes
PUT    /catalog/admin/categories/{id}/attributes/{attribute_id}
DELETE /catalog/admin/categories/{id}/attributes/{attribute_id}
```

`code` must be unique across the effective inherited chain.

### Tags

```
GET    /catalog/admin/tags
GET    /catalog/admin/tags/search/schema
POST   /catalog/admin/tags
PUT    /catalog/admin/tags/{id}
DELETE /catalog/admin/tags/{id}
```

### Demo data

`POST /catalog/admin/demo-data` (`create_demo_data`). Idempotent —
re-running adds only what is missing. Product images are generated
from a local placeholder (no external network).

---

## Requests & Inquiries & Orders

Both entity groups use `view_orders` (read) and `manage_orders` (write)
permissions. Separate `view_inquiries`/`manage_inquiries` are deferred
(see [../adr/0010-inquiries-vs-orders-split.md](../adr/0010-inquiries-vs-orders-split.md)).

> **Orders are feature-gated.** All `/admin/orders/*` endpoints (and the
> public `/orders*`) exist only when `ORDERING_ORDERS_ENABLED=true`
> (default). When the flag is `false`, the Orders tab is removed from
> `/admin/requests/` and the inquiries-only view is shown. See
> [../subsystems/feature-flags.md](../subsystems/feature-flags.md).

### Unified page

| Route | Auth | Notes |
|---|---|---|
| `GET /admin/requests/` | `view_orders` | HTMX page, two tabs (Заказы / Обращения) |
| `GET /admin/requests/badge` | `view_orders` | `{ "count": N }` — sum of `new` for both types |
| `GET /admin/inquiries/` | `view_orders` | 302 → `/admin/requests/` |
| `GET /admin/orders/` | `view_orders` | 302 → `/admin/requests/` |

### Inquiry endpoints

| Route | Auth | Request | Success |
|---|---|---|---|
| `GET /admin/inquiries/search` | `view_orders` | `q`, `page`, `limit`, `sort_by`, `sort_dir`, `field__op=value` | `{ "items": [...], "total": N }` |
| `GET /admin/inquiries/search/schema` | `view_orders` | — | filter schema |
| `PATCH /admin/inquiries/<id>/status` | `manage_orders` | `{ "status": "in_progress" }` | `{ "success": true }` |
| `POST /admin/inquiries/<id>/archive` | `manage_orders` | — | `{ "success": true }` |
| `POST /admin/inquiries/bulk/status` | `manage_orders` | `{ "ids": [...], "status": "closed" }` | `{ "updated": N, "skipped": M }` |
| `POST /admin/inquiries/bulk/archive` | `manage_orders` | `{ "ids": [...] }` | `{ "updated": N, "skipped": M }` |

Inquiry statuses: `new`, `in_progress`, `closed`, `archived`.

Inquiry search item shape: `{ id, name, phone, contact_email, message, status, created_at }`.

### Order endpoints

Same route conventions as inquiries under `/admin/orders/`.

| Route | Auth | Request | Success |
|---|---|---|---|
| `GET /admin/orders/search` | `view_orders` | same params as inquiries | `{ "items": [...], "total": N }` |
| `GET /admin/orders/search/schema` | `view_orders` | — | filter schema |
| `PATCH /admin/orders/<id>/status` | `manage_orders` | `{ "status": "confirmed" }` | `{ "success": true }` |
| `POST /admin/orders/<id>/archive` | `manage_orders` | — | `{ "success": true }` |
| `POST /admin/orders/bulk/status` | `manage_orders` | `{ "ids": [...], "status": "confirmed" }` | `{ "updated": N, "skipped": M }` |
| `POST /admin/orders/bulk/archive` | `manage_orders` | `{ "ids": [...] }` | `{ "updated": N, "skipped": M }` |

Order statuses: `new`, `confirmed`, `completed`, `canceled`, `archived`.
`archived` is reachable from any terminal state (`completed`, `canceled`).

Order search item shape: `{ id, customer_user_id, total, delivery_method, delivery_address, status, created_at, items: [{product_id, title_snapshot, unit_price, quantity}] }`.

Error codes: `404` entity not found; `422` illegal status transition.

---

## System Settings

### `GET /system/settings` (`manage_settings`)

```json
{
  "branding": { "app_name": "...", "admin_panel_title": "..." },
  "contacts": { "phone": "...", "email": "...", "working_hours": "...", "address": "..." },
  "telegram": { "bot_token": "...", "chat_id": "..." },
  "coords": { "lat": 53.9, "lon": 27.56 },
  "socials": {
    "instagram": "https://instagram.com/shop",
    "telegram":  null,
    "whatsapp":  "https://wa.me/...",
    "viber":     null
  },
  "catalog_access": { "owner_can_view_category_tree": true, ... }
}
```

Each `socials.<channel>` is gated by a `SYSTEM_SOCIALS_<CHANNEL>_ENABLED`
env flag (see [../subsystems/feature-flags.md](../subsystems/feature-flags.md)).
Disabled channels are returned as `null` and are NOT writable via `PUT`
— the admin form does not even render the input.

### `PUT /system/settings` (`manage_settings`)

Partial update; any subset of the response body is accepted.

The `socials` payload uses field names `instagram` / `telegram` /
`whatsapp` / `viber`. They map to DB columns `instagram`,
`telegram_public_url`, `whatsapp_url`, `viber_url` respectively.

`telegram.bot_token` is the global bot credential.
`telegram.chat_id` is a legacy global fallback; orders, login codes,
and password codes use `admins.telegram_chat_id`.

Boolean settings are typed — `"false"` is parsed as `false`.

### `POST /system/settings/test-telegram` (`manage_settings`)

Sends a legacy test message to the configured global Telegram chat.
Order/login notifications do not use this global chat.

### `POST /system/settings/telegram/fetch-chat-id` (`manage_settings`)

Polls bot updates for a chat id (user must have sent `/start` within
the last 15 minutes).

```json
{ "bot_token": "123456:ABC-DEF..." }
```

`200`:

```json
{ "success": true, "chat_id": "123456789" }
```

Returns the discovered chat id only — it does NOT save it to global
settings. The user binds it on their account form.

### `GET /admin/settings/database-dump` (admin UI; superadmin)

Returns the newest MySQL dump produced by `scripts/db_dump.py` (lives
under `data/dumps/`). Requirements:

- Authenticated superadmin.
- `admins.password_changed_at` is set for that superadmin.
- At least one dump file exists in `data/dumps/`.

Response sets `Cache-Control: no-store` and `Content-Type:
application/gzip` (or `application/sql` for plain `.sql`). Dump
creation is out-of-process: schedule `python scripts/db_dump.py`
from CPanel cron (see [../infra/cpanel.md](../infra/cpanel.md)).
