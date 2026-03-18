# s1t-sddd-flaskapi-shop

Universal forkable e-commerce boilerplate. Flask/APIFlask + SQLAlchemy + Dishka DI, following S-DDD (hexagonal architecture). Python 3.11+, SQLite by default.

Built for quick deployment on **CPanel** shared hosting, Docker, or any WSGI server.

---

## Features

- Admin panel with HTMX + SmartTable (dynamic filters, sorting, pagination)
- Telegram integration (order notifications, password recovery, test messages)
- JWT authentication (httpOnly cookie + Bearer header)
- Swagger/OpenAPI docs at `/api/docs`
- Declarative mock data seeding via YAML config
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

# 3. Seed the database
PYTHONPATH=src uv run data/seed.py

# 4. Run
PYTHONPATH=src FLASK_DEBUG=1 uv run src/root/entrypoints/api.py
```

Open http://localhost:5000 — admin login with `admin` / `changeme`.

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
| `CATALOG_UPLOAD_DIR`    | `media/products`        | Directory for product image uploads      |
| `SYSTEM_RECOVERY_TOKEN` | `change-me-in-production`| Secret token for password recovery URL  |
| `PORT`                  | `5000`                  | Server port                              |

> Telegram bot token and chat ID are configured through the admin UI (Settings page), not env vars.

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

SQLite by default. All tables are auto-created on app startup.

**Tables:** `products`, `product_images`, `orders`, `admins`, `settings`

See [docs/database.md](docs/database.md) for the full schema reference.

---

## Smart Filter System

Each entity exposes a `/search/schema` endpoint that describes its filterable fields. The admin SmartTable JS class fetches this schema and renders filter UI automatically.

See [docs/filters.md](docs/filters.md) for details.

---

## Adding New Entities

For every new table you need: ORM model, schema endpoint, search endpoint, SmartTable instance, and seed config entry.

See [docs/adding_new_table.md](docs/adding_new_table.md) for the full 12-step guide.

---

## Mock Data Seeding

Mock data is configured declaratively in `data/seed_config.yaml`:

```yaml
products:
  count: 10
  fields:
    title:  { type: faker, method: catch_phrase }
    price:  { type: range, min: 199.0, max: 49999.0, precision: 2 }
    images: { type: download_images, min: 1, max: 3, width: 300, height: 300 }

orders:
  count: 15
  fields:
    name:   { type: faker, method: name }
    phone:  { type: faker, method: phone_number }
    status: { type: enum, values: ["new", "processing", "done", "canceled"] }
```

Поддерживаемые типы полей: `faker`, `choice`/`enum`, `range`, `int_range`, `pattern`, `sequence`, `fixed`, `download_images`, `placeholder_images`.

Дефолтная локаль Faker — `ru_RU`. Можно переопределить: `{ type: faker, method: name, locale: en_US }`.

Run: `PYTHONPATH=src python data/seed.py`

The seed script is idempotent — it skips entities that already have data.

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
