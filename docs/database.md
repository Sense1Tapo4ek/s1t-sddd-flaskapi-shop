# Database Schema

The project uses **SQLite** by default (configurable via `INFRA_DATABASE_URL`). All bounded contexts share a single database file and a single SQLAlchemy `Base` class (`src/shared/adapters/driven/db/base.py`).

Each context defines its own ORM models in `src/{context}/adapters/driven/db/models.py`.

---

## Tables

### `products` (Catalog context)

| Column       | Type         | Constraints                | Default      |
|--------------|-------------|----------------------------|--------------|
| `id`         | INTEGER     | PRIMARY KEY, AUTOINCREMENT |              |
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
| `recovery_code_hash`  | VARCHAR(255)| NULLABLE                   |         |
| `recovery_code_expires`| DATETIME   | NULLABLE                   |         |

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
| `telegram_chat_id`  | VARCHAR(100)|                                 | `""`    |

**Singleton:** The `CHECK (id = 1)` constraint ensures only one row exists. This is a domain-level singleton pattern.

**ORM model:** `src/system/adapters/driven/db/models.py` → `SettingsModel`

---

## Relationships Diagram

```
products  1 ──── N  product_images
   │                    │
   └── product_id ──────┘ (FK, CASCADE)

admins           (standalone)
orders           (standalone)
settings         (singleton, id=1)
```

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
