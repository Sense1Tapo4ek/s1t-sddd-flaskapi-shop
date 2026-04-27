# Admin API

All admin endpoints require a JWT token. Send it as:
- **Cookie:** `token=<jwt>` (used by the admin UI automatically)
- **Header:** `Authorization: Bearer <jwt>` (for external API clients)

Swagger UI is available at `/api/docs` in dev mode. Protected endpoints require both authentication and the relevant JWT permission. Superadmin has all permissions.

When authenticating through the admin UI cookie, unsafe requests (`POST`, `PUT`, `PATCH`, `DELETE`) also require CSRF protection. The admin UI sends `X-CSRF-Token` automatically from the `csrf_token` cookie. External API clients using `Authorization: Bearer <jwt>` do not need CSRF.

---

## Authentication

### POST /auth/login

Authenticate and receive a JWT token.

**Request body:**
```json
{ "login": "admin", "password": "changeme", "remember_me": false }
```

**Response** `200`:
```json
{ "token": "eyJhbGciOi...", "message": "Login successful" }
```

**Response** `401`:
```json
{ "error": "Invalid login or password" }
```

---

### Admin UI Telegram Login

The admin UI supports login by per-user Telegram code:

```text
POST /admin/telegram/request-code
POST /admin/verify-code
```

The code is sent only to the `telegram_chat_id` bound to that user. New-order notifications also use per-user chat IDs for active `owner` and `superadmin` accounts; global settings do not define an order recipient.
Code generation has cooldown protection, and repeated wrong verification attempts temporarily lock the code.

---

### POST /auth/password (ADMIN ONLY)

Change the current admin's password. The request must include either the current password or a valid Telegram confirmation code for the same user.

Admin UI can request a confirmation code with:

```text
POST /admin/settings/security/password-code
```

**Request body:**
```json
{ "new_password": "newpass123", "old_password": "changeme" }
```

Alternative:

```json
{ "new_password": "newpass123", "confirmation_code": "123456" }
```

**Response** `200`:
```json
{ "success": true }
```

---

## Catalog Management

### GET /catalog/admin/search (ADMIN ONLY)

Search products with dynamic filters, sorting, and pagination.

**Query params:**

| Param     | Type   | Default | Description                |
|-----------|--------|---------|----------------------------|
| `q`       | string | ""      | Full-text search query     |
| `page`    | int    | 1       | Page number                |
| `limit`   | int    | 20      | Items per page (1-100)     |
| `sort_by` | string | null    | Sort column name           |
| `sort_dir`| string | "asc"   | `asc` or `desc`            |
| `*`       | string |         | Dynamic filters: `field__op=value` |

**Filter examples:** `title__ilike=phone`, `price__gte=100`, `price__lte=500`
Taxonomy filters are also supported: `category_id=4`,
`include_descendants=true`, `tags=sale,new`, `attr.size=M`,
`attr.weight__gte=10`.

**Response** `200`:
```json
{
  "items": [
    {
      "id": 1, "title": "Headphones", "price": 49.99,
      "description": "...", "images": [...], "created_at": "2025-03-15"
    }
  ],
  "total": 5
}
```

---

### GET /catalog/admin/search/schema (ADMIN ONLY)

Returns the filter schema for the products smart table.

**Response** `200`:
```json
{
  "fields": [
    { "key": "id", "label": "ID", "type": "number", "operators": ["eq"] },
    { "key": "title", "label": "Название", "type": "string", "operators": ["ilike", "eq"] },
    { "key": "price", "label": "Цена", "type": "number", "operators": ["eq", "gte", "lte"] },
    { "key": "created_at", "label": "Дата", "type": "date", "operators": ["eq", "gte", "lte"] }
  ]
}
```

---

### GET /catalog/admin/products/{product_id} (ADMIN ONLY)

Return product detail for admin editing. Unlike public `GET /catalog/{product_id}`, this endpoint can return inactive products and is protected by `view_products`.

**Response** `200`: Product detail object.

---

### POST /catalog (ADMIN ONLY)

Create a new product. Uses `multipart/form-data`.

**Form fields:**

| Field        | Type   | Required | Description               |
|--------------|--------|----------|---------------------------|
| `title`      | string | yes      | Product name              |
| `price`      | float  | yes      | Product price             |
| `description`| string | no       | Product description       |
| `images`     | file[] | no       | One or more image files   |
| `category_id`| int    | no       | Leaf category id          |
| `tag_ids`    | string | no       | Comma-separated tag ids   |
| `attribute_values` | JSON string | no | Attribute values by code |

**Response** `201`: Product detail object.

---

### PUT /catalog/{product_id} (ADMIN ONLY)

Update a product. Uses `multipart/form-data`.
Omitted taxonomy fields are preserved. Send `tag_ids` or `attribute_values` only when you intend to replace those sets.

**Form fields:**

| Field            | Type     | Description                  |
|------------------|----------|------------------------------|
| `title`          | string   | New title                    |
| `price`          | float    | New price                    |
| `description`    | string   | New description              |
| `new_images`     | file[]   | Additional images            |
| `deleted_images` | string[] | Image paths to delete        |
| `category_id`    | int      | Leaf category id             |
| `tag_ids`        | string   | Comma-separated tag ids      |
| `attribute_values` | JSON string | Attribute values by code |

**Response** `200`: Updated product detail object.

---

### DELETE /catalog/{product_id} (ADMIN ONLY)

Permanently delete a product and all its images.

**Response** `200`:
```json
{ "success": true }
```

---

### DELETE /catalog/{product_id}/images (ADMIN ONLY)

Delete a specific product image.

**Request body:**
```json
{ "image_path": "/media/products/abc.jpg" }
```

**Response** `200`: Updated product detail object.

---

## Catalog Taxonomy

Read endpoints require `view_category_tree`; all authenticated admin users receive that read permission as a baseline. Mutations require `edit_taxonomy`.

### Categories

Admin category endpoints:

```text
GET    /catalog/admin/categories/tree
GET    /catalog/admin/categories/{id}
POST   /catalog/admin/categories
PUT    /catalog/admin/categories/{id}
DELETE /catalog/admin/categories/{id}
POST   /catalog/admin/categories/{id}/move
GET    /catalog/admin/categories/{id}/products
```

### Category attributes

```text
GET    /catalog/admin/categories/{id}/attributes
POST   /catalog/admin/categories/{id}/attributes
PUT    /catalog/admin/categories/{id}/attributes/{attribute_id}
DELETE /catalog/admin/categories/{id}/attributes/{attribute_id}
```

### Tags

```text
GET    /catalog/admin/tags
GET    /catalog/admin/tags/search/schema
POST   /catalog/admin/tags
PUT    /catalog/admin/tags/{id}
DELETE /catalog/admin/tags/{id}
```

### Demo data

```text
POST /catalog/admin/demo-data
```

Requires `create_demo_data`. Superadmin can use it from `/admin/categories/` to idempotently create missing demo categories, tags, attributes, and products for active leaf categories.
Demo product images are generated from a local placeholder, not downloaded from external services during the request.

---

## Order Management

### GET /orders (ADMIN ONLY)

List orders with filters, sorting, and pagination.

**Query params:** Same pattern as catalog search — `page`, `limit`, `sort_by`, `sort_dir`, plus dynamic filters.

**Filter examples:** `status=new`, `name__ilike=alice`, `created_at__gte=2025-01-01`

**Response** `200`:
```json
{
  "items": [
    {
      "id": 1, "name": "Alice", "phone": "+375...",
      "status": "new", "comment": "...", "created_at": "2025-03-15 14:30"
    }
  ],
  "total": 15
}
```

---

### GET /orders/search/schema (ADMIN ONLY)

Returns the filter schema for the orders smart table.

**Response** `200`:
```json
{
  "fields": [
    { "key": "id", "label": "ID", "type": "number", "operators": ["eq"] },
    { "key": "name", "label": "Имя", "type": "string", "operators": ["ilike", "eq"] },
    { "key": "phone", "label": "Телефон", "type": "string", "operators": ["ilike", "eq"] },
    { "key": "created_at", "label": "Дата", "type": "date", "operators": ["eq", "gte", "lte"] },
    {
      "key": "status", "label": "Статус", "type": "enum", "operators": ["eq"],
      "options": [
        { "value": "new", "label": "Новый" },
        { "value": "processing", "label": "В обработке" },
        { "value": "done", "label": "Выполнен" },
        { "value": "canceled", "label": "Отменён" }
      ]
    }
  ]
}
```

---

### PATCH /orders/{order_id}/status (ADMIN ONLY)

Update an order's status.

**Request body:**
```json
{ "status": "processing" }
```

**Valid statuses:** `new`, `processing`, `done`, `canceled`

**Response** `200`:
```json
{ "success": true }
```

**Response** `404`:
```json
{ "error": "Order not found" }
```

**Response** `422`:
```json
{ "error": "Invalid status transition" }
```

---

## System Settings

### GET /system/settings (ADMIN ONLY)

Get all system settings including Telegram credentials.

**Response** `200`:
```json
{
  "contacts": { "phone": "...", "email": "...", "working_hours": "...", "address": "..." },
  "telegram": { "bot_token": "...", "chat_id": "..." },
  "coords": { "lat": 53.9, "lon": 27.56 },
  "socials": { "instagram": "..." }
}
```

---

### PUT /system/settings (ADMIN ONLY)

Update system settings (partial update supported).

**Request body:**
```json
{
  "contacts": { "phone": "+375...", "email": "new@example.com" },
  "telegram": { "bot_token": "123:ABC..." },
  "coords": { "lat": 53.9, "lon": 27.56 },
  "socials": { "instagram": "@newhandle" }
}
```

**Response** `200`: Full settings object.

---

`telegram.bot_token` is the global bot credential. `telegram.chat_id` is retained only as a legacy setting; order notifications, login codes, and password-confirmation codes target `admins.telegram_chat_id`.

Boolean settings are typed by the API schema. For example, `"false"` is parsed as `false`, not as a truthy string.

### POST /system/settings/test-telegram (ADMIN ONLY)

Send a legacy test message to the configured global Telegram chat, if present. Normal order and login notifications do not use this global chat.

**Response** `200`:
```json
{ "success": true }
```

---

### POST /system/settings/telegram/fetch-chat-id (ADMIN ONLY)

Fetch the Telegram chat ID by polling bot updates. The user must have sent `/start` to the bot within the last 15 minutes.

**Request body:**
```json
{ "bot_token": "123456:ABC-DEF..." }
```

**Response** `200`:
```json
{ "success": true, "chat_id": "123456789" }
```

The fetch operation returns the discovered chat ID only. It does not save `telegram_chat_id` into global settings; account binding is saved through the current user's account page.

---

### GET /admin/settings/database-dump (ADMIN UI)

Downloads a SQLite snapshot through the admin UI. Requirements:

- authenticated superadmin;
- `admins.password_changed_at` is set for that superadmin;
- `INFRA_DATABASE_URL` points to a file-backed SQLite database.

The response uses `Cache-Control: no-store`. The dev fallback `superadmin/superadmin` account is blocked until its password is changed.
