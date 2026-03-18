# Admin API

All admin endpoints require a JWT token. Send it as:
- **Cookie:** `token=<jwt>` (used by the admin UI automatically)
- **Header:** `Authorization: Bearer <jwt>` (for external API clients)

Swagger UI is available at `/api/docs` in dev mode. All protected endpoints are marked **(ADMIN ONLY)** in Swagger.

---

## Authentication

### POST /auth/login

Authenticate and receive a JWT token.

**Request body:**
```json
{ "login": "admin", "password": "changeme" }
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

### POST /auth/password (ADMIN ONLY)

Change the current admin's password.

**Request body:**
```json
{ "new_password": "newpass123", "old_password": "changeme" }
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

### POST /catalog (ADMIN ONLY)

Create a new product. Uses `multipart/form-data`.

**Form fields:**

| Field        | Type   | Required | Description               |
|--------------|--------|----------|---------------------------|
| `title`      | string | yes      | Product name              |
| `price`      | float  | yes      | Product price             |
| `description`| string | no       | Product description       |
| `images`     | file[] | no       | One or more image files   |

**Response** `201`: Product detail object.

---

### PUT /catalog/{product_id} (ADMIN ONLY)

Update a product. Uses `multipart/form-data`.

**Form fields:**

| Field            | Type     | Description                  |
|------------------|----------|------------------------------|
| `title`          | string   | New title                    |
| `price`          | float    | New price                    |
| `description`    | string   | New description              |
| `new_images`     | file[]   | Additional images            |
| `deleted_images` | string[] | Image paths to delete        |

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

### POST /system/settings/test-telegram (ADMIN ONLY)

Send a test message to the configured Telegram chat.

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
