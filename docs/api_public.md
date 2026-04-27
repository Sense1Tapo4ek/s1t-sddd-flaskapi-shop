# Public API

Base URL: `http://localhost:5000` (dev) or your production domain.

All public endpoints are available without authentication.

---

## Catalog

### GET /catalog

Get a paginated list of active products. Public catalog reads always enforce active product visibility server-side; `is_active` query params are ignored.

**Query params:**

| Param  | Type | Default | Description       |
|--------|------|---------|-------------------|
| `page` | int  | 1       | Page number (≥1)  |
| `limit`| int  | 20      | Items per page (1-100) |
| `category` | string | | Category slug |
| `category_id` | int | | Category id |
| `include_descendants` | bool | false | Include child categories |
| `tags` | string | | Comma-separated tag slugs |
| `attr.<code>` | string | | Attribute filter |

Inactive products are not returned through category, tag, attribute, or dynamic filters.

**Response** `200`:
```json
{
  "items": [
    {
      "id": 1,
      "title": "Wireless Headphones",
      "price": 49.99,
      "image": "/media/products/abc.jpg",
      "category_id": 4,
      "category": { "id": 4, "title": "Dresses", "slug": "dresses" },
      "tags": []
    }
  ],
  "total": 42,
  "page": 1,
  "limit": 20
}
```

---

### GET /catalog/random

Get random active products.

**Query params:**

| Param  | Type | Default | Description          |
|--------|------|---------|----------------------|
| `limit`| int  | 4       | Number of items (1-20) |

**Response** `200`:
```json
[
  { "id": 5, "title": "LED Desk Lamp", "price": 29.99, "image": "/media/products/xyz.jpg" }
]
```

---

### GET /catalog/{product_id}

Get full product details including all images. Inactive products return the same not-found response as missing products.

**Response** `200`:
```json
{
  "id": 1,
  "title": "Wireless Headphones",
  "price": 49.99,
  "description": "High quality product with warranty.",
  "images": ["/media/products/abc.jpg", "/media/products/def.jpg"],
  "category_id": 4,
  "category": { "id": 4, "title": "Dresses", "slug": "dresses" },
  "category_path": ["Clothing", "Dresses"],
  "tags": [],
  "attributes": [],
  "created_at": "2025-03-15"
}
```

**Response** `404`:
```json
{ "error": "Product not found" }
```

---

## Catalog Taxonomy

### GET /catalog/categories/tree

Return active categories as a nested tree.

### GET /catalog/tags

Return active catalog tags. Public product counts count active products only.

---

## Orders

### POST /orders

Place a new customer order. If a Telegram bot token is configured, notifications are sent to active owner/superadmin users with a bound `telegram_chat_id`. Notification delivery failures do not fail order placement.

**Request body:**
```json
{
  "name": "John Doe",
  "phone": "+375291234567",
  "comment": "Please call before delivery"
}
```

| Field    | Type   | Required | Description    |
|----------|--------|----------|----------------|
| `name`   | string | yes      | Customer name  |
| `phone`  | string | yes      | Phone number   |
| `comment`| string | no       | Order comment  |

**Response** `201`:
```json
{ "success": true, "id": 42 }
```

---

## System

### GET /system/info

Get public store information (contacts, working hours, social links). No sensitive data is returned.

**Response** `200`:
```json
{
  "phone": "+1 555 000-0000",
  "address": "123 Main St",
  "email": "info@example.com",
  "working_hours": "Mon-Fri 09:00 - 18:00",
  "coords": { "lat": 53.9, "lon": 27.56 },
  "socials": { "instagram": "@shopname" }
}
```

---

### POST /system/settings/recover-password/{token}

Trigger password recovery via Telegram. The `{token}` must match the `SYSTEM_RECOVERY_TOKEN` env var. The message is sent to the target admin user's `telegram_chat_id`; global settings only provide the bot token.

**Response** `200`:
```json
{ "success": true }
```

**Response** `404`:
```json
{ "error": "NOT_FOUND", "message": "Invalid recovery path" }
```

**Response** `500`:
```json
{ "error": "RECOVERY_FAILED", "message": "Failed to send message" }
```
