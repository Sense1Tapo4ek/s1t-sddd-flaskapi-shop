# Database Schema

The project uses **SQLite** by default (configurable via `INFRA_DATABASE_URL`). All bounded contexts share a single database file and a single SQLAlchemy `Base` class (`src/shared/adapters/driven/db/base.py`).

Each context defines its own ORM models in `src/{context}/adapters/driven/db/models.py`.

SQLite app connections enable `PRAGMA foreign_keys=ON` through `src/shared/adapters/driven/db/connection.py`, so declared `ondelete` behavior is enforced during normal app operation.

---

## Tables

### `products` (Catalog context)

| Column       | Type         | Constraints                | Default      |
|--------------|-------------|----------------------------|--------------|
| `id`         | INTEGER     | PRIMARY KEY, AUTOINCREMENT |              |
| `category_id`| INTEGER    | FK → `categories.id`, nullable for compatibility | |
| `title`      | VARCHAR(255)| NOT NULL                   |              |
| `price`      | FLOAT       | NOT NULL                   |              |
| `description`| TEXT        |                            | `""`         |
| `is_active`  | BOOLEAN     |                            | `true`       |
| `created_at` | DATETIME    |                            | `now()`      |

**ORM model:** `src/catalog/adapters/driven/db/models.py` → `ProductModel`

---

### `product_images` (Catalog context)

| Column       | Type         | Constraints                             | Default |
|--------------|-------------|-----------------------------------------|---------|
| `id`         | INTEGER     | PRIMARY KEY, AUTOINCREMENT              |         |
| `product_id` | INTEGER     | FOREIGN KEY → `products.id`, ON DELETE CASCADE | |
| `file_path`  | VARCHAR(500)| NOT NULL                                |         |

**Relationship:** Many-to-one with `products`. Cascade delete — removing a product removes all its images.

**ORM model:** `src/catalog/adapters/driven/db/models.py` → `ProductImageModel`

---

### `categories` (Catalog context)

Hierarchical category tree. Products should be assigned to leaf categories.

| Column       | Type          | Constraints                 | Default |
|--------------|---------------|-----------------------------|---------|
| `id`         | INTEGER       | PRIMARY KEY, AUTOINCREMENT  |         |
| `parent_id`  | INTEGER       | FK → `categories.id`        | `NULL`  |
| `title`      | VARCHAR(255)  | NOT NULL                    |         |
| `slug`       | VARCHAR(255)  | UNIQUE, NOT NULL            |         |
| `description`| TEXT          |                             | `""`    |
| `sort_order` | INTEGER       |                             | `0`     |
| `is_active`  | BOOLEAN       |                             | `true`  |
| `created_at` | DATETIME      |                             | `now()` |

### `tags` and `product_tags` (Catalog context)

Tags are independent labels for products.

| Table | Purpose |
|-------|---------|
| `tags` | Tag dictionary with title, slug, color, sort order, active flag |
| `product_tags` | Many-to-many link between products and tags |

### `category_attributes`, `attribute_options`, `product_attribute_values`

Category attributes define inherited product fields.

| Table | Purpose |
|-------|---------|
| `category_attributes` | Attribute definitions owned by a category |
| `attribute_options` | Options for `select` and `multiselect` attributes |
| `product_attribute_values` | Typed product values for effective category attributes |

Supported attribute types: `text`, `number`, `boolean`, `select`,
`multiselect`, `date`, `url`, `color`, `file`, `image`.

---

### `orders` (Ordering context)

| Column       | Type         | Constraints                | Default      |
|--------------|-------------|----------------------------|--------------|
| `id`         | INTEGER     | PRIMARY KEY, AUTOINCREMENT |              |
| `name`       | VARCHAR(255)| NOT NULL                   |              |
| `phone`      | VARCHAR(50) | NOT NULL                   |              |
| `comment`    | TEXT        |                            | `""`         |
| `status`     | VARCHAR(50) |                            | `"new"`      |
| `created_at` | DATETIME    |                            | `now()`      |

**Status values:** `new`, `processing`, `done`, `canceled` (defined in `src/ordering/domain/order_status.py` → `OrderStatus` enum).

**ORM model:** `src/ordering/adapters/driven/db/models.py` → `OrderModel`

---

### `admins` (Access context)

| Column                | Type         | Constraints                | Default |
|-----------------------|-------------|----------------------------|---------|
| `id`                  | INTEGER     | PRIMARY KEY, AUTOINCREMENT |         |
| `login`               | VARCHAR(100)| UNIQUE, NOT NULL           |         |
| `password_hash`       | VARCHAR(255)| NOT NULL                   |         |
| `role`                | VARCHAR(30) | NOT NULL                   | `owner` |
| `telegram_chat_id`    | VARCHAR(100)| NULLABLE                   |         |
| `is_active`           | BOOLEAN     | NOT NULL                   | `true`  |
| `password_changed_at` | DATETIME    | NULLABLE                   |         |
| `recovery_code_hash`  | VARCHAR(255)| NULLABLE                   |         |
| `recovery_code_expires`| DATETIME   | NULLABLE                   |         |
| `recovery_code_attempts`| INTEGER    | NOT NULL                   | `0`     |
| `recovery_code_last_sent_at`| DATETIME| NULLABLE                  |         |
| `recovery_code_locked_until`| DATETIME| NULLABLE                  |         |

Roles are `owner` and `superadmin`. Owner permissions are resolved from runtime settings for catalog access and from `ACCESS_OWNER_CAN_*` env flags for other areas when JWT is issued. Superadmin always has all permissions. `password_changed_at` gates sensitive actions such as the admin SQLite dump. Recovery-code metadata is used for Telegram login/password confirmation cooldown and lockout.

**ORM model:** `src/access/adapters/driven/db/models.py` → `UserModel`

---

### `settings` (System context)

| Column              | Type         | Constraints                     | Default |
|---------------------|-------------|---------------------------------|---------|
| `id`                | INTEGER     | PRIMARY KEY, CHECK (`id = 1`)   |         |
| `phone`             | VARCHAR(50) |                                 | `""`    |
| `email`             | VARCHAR(100)|                                 | `""`    |
| `address`           | TEXT        |                                 | `""`    |
| `working_hours`     | VARCHAR(50) |                                 | `""`    |
| `coords_lat`        | FLOAT       |                                 | `0.0`   |
| `coords_lon`        | FLOAT       |                                 | `0.0`   |
| `instagram`         | VARCHAR(255)|                                 | `""`    |
| `telegram_bot_token`| VARCHAR(255)|                                 | `""`    |
| `telegram_chat_id`  | VARCHAR(100)| Legacy/global fallback only     | `""`    |
| `app_name`          | VARCHAR(100)| NOT NULL                        | `Shop Admin` |
| `admin_panel_title` | VARCHAR(100)| NOT NULL                        | `Админ панель` |
| `owner_can_view_category_tree` | BOOLEAN | NOT NULL             | `true`  |
| `owner_can_edit_taxonomy` | BOOLEAN | NOT NULL                  | `false` |
| `owner_can_view_products` | BOOLEAN | NOT NULL                  | `false` |
| `owner_can_edit_products` | BOOLEAN | NOT NULL                  | `false` |
| `owner_can_create_demo_data` | BOOLEAN | NOT NULL              | `false` |

**Singleton:** The `CHECK (id = 1)` constraint ensures only one row exists. This is a domain-level singleton pattern.

**ORM model:** `src/system/adapters/driven/db/models.py` → `SettingsModel`

Telegram bot token is global. Chat IDs for login, password confirmation, and order notifications live on `admins.telegram_chat_id`.

SQLite compatibility patches run on app startup from `src/shared/adapters/driven/db/compat.py`. They add supported missing columns for this template, including `admins.password_changed_at`. Non-SQLite schema migration is not provided by this template yet; introduce Alembic before using PostgreSQL/MySQL in production.

---

## Relationships Diagram

```
categories 1 ──── N categories
categories 1 ──── N products
products   1 ──── N product_images
products   N ──── N tags
categories 1 ──── N category_attributes
category_attributes 1 ──── N attribute_options
products 1 ──── N product_attribute_values

admins           (standalone; owner/superadmin access)
orders           (standalone)
settings         (singleton, id=1)
```

---

## Catalog Indexes

Fresh databases get taxonomy/search indexes from ORM `Index(...)` declarations. Existing SQLite databases should run `data/migrate_taxonomy.py` to create the same indexes idempotently.

| Index | Table | Columns |
|---|---|---|
| `idx_categories_parent_id` | `categories` | `parent_id` |
| `idx_categories_active_sort` | `categories` | `is_active`, `sort_order` |
| `idx_products_category_id` | `products` | `category_id` |
| `idx_products_active_id` | `products` | `is_active`, `id` |
| `idx_tags_active_sort` | `tags` | `is_active`, `sort_order` |
| `idx_product_tags_tag_id` | `product_tags` | `tag_id` |
| `idx_category_attributes_category_id` | `category_attributes` | `category_id` |
| `idx_product_attribute_values_attribute_id` | `product_attribute_values` | `attribute_id` |
| `idx_product_attribute_values_text` | `product_attribute_values` | `attribute_id`, `value_text` |
| `idx_product_attribute_values_number` | `product_attribute_values` | `attribute_id`, `value_number` |
| `idx_product_attribute_values_bool` | `product_attribute_values` | `attribute_id`, `value_bool` |

---

## Shared Base

All models inherit from the same `Base`:

```python
# src/shared/adapters/driven/db/base.py
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
```

This means `Base.metadata.create_all(engine)` creates all tables for all contexts in a single call (done in `src/root/entrypoints/api.py` → `create_app()`).

---

## Adding a New Table

See [adding_new_table.md](adding_new_table.md) for the full step-by-step guide.

Quick version:
1. Create a model in `src/{context}/adapters/driven/db/models.py` inheriting from `Base`
2. Import the model module in `src/root/entrypoints/api.py` (so it registers with `Base.metadata`)
3. Restart the app — `create_all()` will create the new table automatically
