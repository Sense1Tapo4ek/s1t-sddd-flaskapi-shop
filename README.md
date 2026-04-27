# s1t-sddd-flaskapi-shop

Universal forkable e-commerce boilerplate. Flask/APIFlask + SQLAlchemy + Dishka DI, following S-DDD (hexagonal architecture). Python 3.11+, SQLite by default.

Built for quick deployment on **CPanel** shared hosting, Docker, or any WSGI server.

---

## Features

- Admin panel with HTMX + SmartTable (dynamic filters, sorting, pagination)
- Catalog taxonomy: category tree, tags, inherited category attributes
- Telegram integration (order notifications to per-user chat IDs, per-user login codes)
- Role-aware JWT authentication (httpOnly cookie + Bearer header)
- Swagger/OpenAPI docs at `/api/docs`
- Superadmin demo-data generator from the admin UI
- CPanel-ready (`passenger_wsgi.py` included)

---

## Quick Start

```bash
# 1. Clone and configure
git clone <repo-url>
cd s1t-sddd-flaskapi-shop
cp .env.example .env       # edit secrets!

# 2. Install dependencies
pip install -r requirements.txt
# or with uv:
uv sync

# 3. Run
PYTHONPATH=src FLASK_DEBUG=1 uv run src/root/entrypoints/api.py
```

Open http://localhost:5000:

- Owner login: `admin` / `changeme`
- Dev superadmin login: `superadmin` / `superadmin`

The dev superadmin can sign in with the fallback password, but cannot download a database dump until that password is changed.

Swagger docs: http://localhost:5000/api/docs

---

## Docker

```bash
docker compose up --build
```

Runs on port 5000. Database is persisted in `./data/shop.db`, uploads in `./media/`.

---

## Environment Variables

| Variable                | Default                 | Description                              |
|-------------------------|-------------------------|------------------------------------------|
| `ROOT_APP_NAME`         | `Shop Admin`            | App name (shown in UI and Swagger)       |
| `ROOT_APP_ENV`          | `dev`                   | `dev` or `prod`                          |
| `INFRA_DATABASE_URL`    | `sqlite:///data/shop.db`| SQLAlchemy database URL                  |
| `ACCESS_JWT_SECRET`     | `change-me-in-production`| JWT signing secret                      |
| `ACCESS_DEFAULT_LOGIN`  | `admin`                 | Default admin username                   |
| `ACCESS_DEFAULT_PASSWORD`| `changeme`             | Default admin password                   |
| `ACCESS_DEFAULT_TELEGRAM_CHAT_ID`| ``          | Initial per-user Telegram chat for default owner |
| `ACCESS_SUPERADMIN_LOGIN`| `superadmin`           | Developer superadmin login               |
| `ACCESS_SUPERADMIN_PASSWORD`| dev fallback only     | Superadmin password; required in prod    |
| `ACCESS_SUPERADMIN_TELEGRAM_CHAT_ID`| ``       | Initial per-user Telegram chat for superadmin |
| `ACCESS_RECOVERY_CODE_TTL_MINUTES`| `5`        | Telegram code lifetime                    |
| `ACCESS_RECOVERY_CODE_COOLDOWN_SECONDS`| `60`  | Minimum seconds between code sends        |
| `ACCESS_RECOVERY_CODE_MAX_ATTEMPTS`| `5`       | Wrong code attempts before lockout        |
| `ACCESS_RECOVERY_CODE_LOCKOUT_MINUTES`| `15`   | Lockout duration after too many failures  |
| `ACCESS_OWNER_CAN_VIEW_CATEGORY_TREE`| `true`  | Legacy flag; category structure read is always allowed for authenticated admins |
| `ACCESS_OWNER_CAN_EDIT_TAXONOMY`| `false`      | Owner can edit categories/tags/attributes|
| `ACCESS_OWNER_CAN_VIEW_PRODUCTS`| `false`      | Owner can view product admin             |
| `ACCESS_OWNER_CAN_EDIT_PRODUCTS`| `false`      | Owner can mutate products                |
| `ACCESS_OWNER_CAN_VIEW_ORDERS`| `false`        | Owner can view orders                    |
| `ACCESS_OWNER_CAN_MANAGE_ORDERS`| `false`      | Owner can update/delete orders           |
| `ACCESS_OWNER_CAN_MANAGE_SETTINGS`| `false`    | Owner can edit store/system settings     |
| `ACCESS_OWNER_CAN_CREATE_DEMO_DATA`| `false`   | Owner can run demo-data generator        |
| `CATALOG_UPLOAD_DIR`    | `media/products`        | Directory for product image uploads      |
| `SYSTEM_RECOVERY_TOKEN` | `change-me-in-production`| Secret token for password recovery URL  |
| `PORT`                  | `5000`                  | Server port                              |

> Telegram bot token is global and configured by superadmin in Settings → Оповещения. Each user binds their own Telegram Chat ID on the account page. New-order notifications are sent to active owners and superadmins with a bound chat ID.

---

## Architecture

S-DDD hexagonal architecture with 4 bounded contexts:

```
src/
├── catalog/     Products, images, search
├── ordering/    Orders, status transitions, Telegram notifications
├── access/      Admin authentication, JWT, password management
├── system/      Store settings, Telegram config, password recovery
├── shared/      DB base, middleware, error handling, file storage
└── root/        App factory, DI container, blueprints registration
```

Each context follows the same layer structure:

```
src/{context}/
├── domain/           Pure business logic (aggregates, value objects, errors)
├── app/              Use cases + abstract interfaces
├── ports/
│   ├── driving/      Facade + Pydantic schemas
│   └── driven/       Repository implementations
├── adapters/
│   ├── driving/      Flask blueprints (api.py, admin.py)
│   └── driven/       ORM models, external clients
├── config.py         Pydantic Settings
└── provider.py       Dishka DI Provider
```

---

## Database

SQLite by default. All tables are auto-created on app startup, and SQLite compatibility patches add supported missing columns for existing template databases.

**Tables:** `products`, `product_images`, `categories`, `tags`, `product_tags`,
`category_attributes`, `attribute_options`, `product_attribute_values`,
`orders`, `admins`, `settings`

The admin UI database dump is SQLite-only and requires a superadmin account whose password has been changed after bootstrap. The fallback `superadmin/superadmin` dev account is intentionally blocked from this action.

See [docs/database.md](docs/database.md) for the full schema reference.

---

## Smart Filter System

Each entity exposes a `/search/schema` endpoint that describes its filterable fields. The admin SmartTable JS class fetches this schema and renders filter UI automatically.

See [docs/filters.md](docs/filters.md) for details.

---

## Adding New Entities

For every new table you need: ORM model, schema endpoint, search endpoint, SmartTable instance, admin UI route, and docs.

See [docs/adding_new_table.md](docs/adding_new_table.md) for the full 12-step guide.

For broader engineering rules, see [docs/development_guidelines.md](docs/development_guidelines.md). The current review and remediation priorities are in [docs/code_review.md](docs/code_review.md).

---

## Demo Data

CLI seeding was removed. Superadmin can create demo catalog data from `/admin/categories/` with the “Создать демо-данные” button. It idempotently creates missing demo categories, tags, attributes, and a small product set for every active leaf category.

For existing SQLite databases created before taxonomy support, run:

```bash
PYTHONPATH=src uv run data/migrate_taxonomy.py
```

---

## API Documentation

- [Public API](docs/api_public.md) — catalog, orders, public info
- [Admin API](docs/api_admin.md) — management, settings, auth

Swagger UI: `/api/docs` (dev mode only)

---

## Deployment

### Docker

```bash
docker compose up --build
```

### CPanel (Shared Hosting)

The project includes `passenger_wsgi.py` for Phusion Passenger. See [docs/cpanel.md](docs/cpanel.md) for the full deployment guide.

### Gunicorn (VPS)

```bash
PYTHONPATH=src gunicorn --bind 0.0.0.0:5000 --workers 2 'root.entrypoints.api:create_app()'
```

---

## License

MIT
