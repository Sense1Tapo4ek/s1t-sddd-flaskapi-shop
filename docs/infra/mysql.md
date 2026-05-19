# Infra: MySQL & SQLAlchemy

For contributors changing the schema or working with the ORM.
The project targets **MySQL 5.7+** / **MariaDB 10.3+**, using the
`PyMySQL` pure-Python driver and `utf8mb4` everywhere.

## Configuration

`INFRA_DATABASE_URL` (default
`mysql+pymysql://shop:shop@localhost:3306/shop?charset=utf8mb4`).
Read by `InfraConfig` in `src/shared/config.py`. Pool tuning knobs:

| Env var | Default | Purpose |
|---|---|---|
| `INFRA_DB_POOL_SIZE` | `5` | Open connections per worker |
| `INFRA_DB_POOL_RECYCLE` | `3600` (s) | Force reconnect before MySQL `wait_timeout` |
| `INFRA_DB_POOL_PRE_PING` | `true` | Validate handle before checkout — mandatory on CPanel |

## Shared `Base` and table options

```python
# src/shared/adapters/driven/db/base.py
class Base(DeclarativeBase): pass

def mysql_table_opts() -> dict[str, str]:
    return {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }
```

Every ORM model appends `mysql_table_opts()` to its `__table_args__`.
This is enforced by review — `Base.metadata.create_all` is NEVER called
outside tests.

## Schema ownership

Schema is owned by `migrations/*.sql` (yoyo). See
[migrations.md](./migrations.md). On startup `ensure_schema_present()`
checks the canonical tables exist and refuses to boot otherwise.

## Tables

| Table | Owner | Model | Notes |
|---|---|---|---|
| `products` | catalog | `ProductModel` | `is_active`, `category_id` (leaf), `created_at` |
| `product_images` | catalog | `ProductImageModel` | FK → `products`, ON DELETE CASCADE |
| `categories` | catalog | `CategoryModel` | Self-FK tree; `slug` UNIQUE; leaf-only assignment |
| `tags`, `product_tags` | catalog | `TagModel`, `ProductTagModel` | Global tags, M:N |
| `category_attributes` | catalog | `CategoryAttributeModel` | Inherited by descendants |
| `attribute_options` | catalog | `AttributeOptionModel` | For `select`/`multiselect` |
| `product_attribute_values` | catalog | `ProductAttributeValueModel` | Typed: `value_text`, `value_number`, `value_bool`, `value_json` |
| `inquiries` | ordering | `InquiryModel` | Public contact form submissions; `status` ∈ {`new`, `in_progress`, `closed`, `archived`} |
| `orders` | ordering | `OrderModel` | `status` ∈ {`new`, `confirmed`, `completed`, `canceled`, `archived`}; `contact_phone`, `contact_email` |
| `order_items` | ordering | `OrderItemModel` | FK → `orders`, ON DELETE CASCADE; snapshots `title`, `price_at_order` |
| `customers` | access | `CustomerModel` | Storefront accounts (separate from admins); recovery via email |
| `admins` | access | `UserModel` | `role`, `telegram_chat_id`, `password_changed_at`, `recovery_code_*` |
| `settings` | system | `SettingsModel` | Singleton, `CHECK (id = 1)` |
| `storage_settings` | system | `StorageSettingsModel` | Singleton, encrypted secrets |
| `_yoyo_migration` | yoyo | — | Bookkeeping; do not touch |

## Gotchas

- **`utf8mb4` index limit.** A `VARCHAR(255)` is 1020 bytes under
  utf8mb4; InnoDB allows ≤3072 bytes per index by default. Composite
  indexes on long varchars need explicit prefix lengths
  (`KEY idx (col(64))`).
- **`JSON` type.** Requires MySQL ≥ 5.7.8. MariaDB ≥ 10.2 emulates JSON
  as `LONGTEXT` — fine because we read/write whole values via
  SQLAlchemy `JSON`, never `JSON_*` functions in SQL.
- **`pool_pre_ping`.** CPanel kills idle connections silently. Without
  pre-ping the first request after idle returns a dead handle.
- **Time zones.** All `DateTime` columns store naive UTC. The app does
  not depend on `time_zone` session variable; do not change it.
- **Random ordering.** `ORDER BY rand()` is fine at template scale; for
  larger catalogs add a precomputed shuffle column.

## Relationships

```
categories 1 ── N categories
categories 1 ── N products
products   1 ── N product_images   (cascade delete)
products   N ── N tags             (product_tags)
categories 1 ── N category_attributes
category_attributes 1 ── N attribute_options
products   1 ── N product_attribute_values

admins              (standalone)
orders              (standalone)
settings            (singleton, id=1)
storage_settings    (singleton, id=1)
```

## Performance

| Pattern | Guidance |
|---|---|
| Tree reads | Loading all categories is fine at template scale; cache or use a recursive CTE for very large trees |
| Attribute filters | Keep indexes; profile count queries before adding many joins |
| Random products | `ORDER BY rand()` — OK at template scale |
| N+1 | `selectinload(...)` for images, tags, category, attributes |
| Pagination | Cap `limit`; validate `page >= 1` |

For SmartTable endpoints, profile BOTH the items query and the count
query.

## Pointers

- Base + connection: `src/shared/adapters/driven/db/`
- Schema guard: `src/shared/adapters/driven/db/schema_guard.py`
- Per-context models: `src/<context>/adapters/driven/db/models.py`
- Migrations: [migrations.md](./migrations.md)
- ADR: [../adr/0006-mysql-yoyo.md](../adr/0006-mysql-yoyo.md)
