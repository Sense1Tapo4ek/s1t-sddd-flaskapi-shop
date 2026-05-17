# s1t-sddd-flaskapi-shop

Forkable e-commerce backend/admin template built with Flask/APIFlask,
SQLAlchemy, Dishka DI, HTMX admin pages, and S-DDD/hexagonal
boundaries. Python 3.11+, MySQL 5.7+/MariaDB 10.3+ storage,
deployable on CPanel shared hosting, Docker, or any WSGI server.

## What Is Included

- Public catalog and order API with Swagger/OpenAPI at `/api/docs` in
  dev mode.
- Admin UI with HTMX, SmartTable filtering, role-aware JWT auth, CSRF
  for cookie-auth mutations, and per-user permissions.
- Catalog taxonomy: categories, tags, inherited attributes, product
  images, demo-data generation from the admin UI.
- Telegram support for order notifications, login codes, password
  confirmation, and recovery.
- MySQL via `PyMySQL`, schema managed by `yoyo-migrations`, CPanel-
  ready scripts in `scripts/` (apply / status / rollback / dump /
  restore / shell / bootstrap).
- `passenger_wsgi.py` for CPanel and Docker Compose (MySQL bundled)
  for local/container use.

## Quick Start

```bash
cp .env.example .env                  # MySQL URL inside points at docker-compose `db`
docker compose up --build             # starts MySQL + API, applies migrations, seeds
```

Or run the API natively against the bundled MySQL:

```bash
docker compose up -d db               # MySQL only
cp .env.example .env
uv sync                               # or: pip install -r requirements.txt
python scripts/db_apply.py            # apply yoyo migrations
PYTHONPATH=src FLASK_DEBUG=1 uv run src/root/entrypoints/api.py
```

Open http://localhost:5000.

- Default admin: `admin` / `changeme`
  - In dev (default), role is `owner` (limited permissions).
  - In prod, set `ACCESS_PROMOTE_TO_SUPERADMIN=true` to make it a superadmin at bootstrap.
- Customer registration: Use the `/auth/customer/register` endpoint or try the storefront UI.
- Swagger UI: http://localhost:5000/api/docs

The default admin can sign in but cannot download a database dump until its password is changed.

## Common Commands

```bash
# Run locally (MySQL must be up first)
PYTHONPATH=src FLASK_DEBUG=1 uv run src/root/entrypoints/api.py

# Run Docker on port 5000 (MySQL + API)
docker compose up --build

# Database operations
python scripts/db_apply.py     # apply yoyo migrations
python scripts/db_status.py    # show applied + pending
python scripts/db_rollback.py  # rollback last migration
python scripts/db_dump.py      # write data/dumps/<ts>.sql.gz
bash   scripts/db_shell.sh     # mysql CLI with creds from .env

# Run tests (unit + flow are stdlib-only)
PYTHONDONTWRITEBYTECODE=1 uv run --extra dev pytest -q -m "unit or flow"

# App factory smoke (assumes migrations applied)
PYTHONPATH=src uv run python3 -c "from root.entrypoints.api import create_app; app = create_app(); print('OK', len(app.url_map._rules))"
```

Docker persists the MySQL data in a named volume `mysql_data` and
uploads in `./media/`. SQL dumps land in `./data/dumps/`.

## Documentation Map

Start here when changing code:

- [CLAUDE.md](CLAUDE.md) — operational guide for human contributors
  and Claude Code: change rules, S-DDD workflow, fast navigation.
- [docs/architecture.md](docs/architecture.md) — bounded contexts,
  layers, how to add a context.
- [docs/contexts/](docs/contexts/) — one page per context (catalog,
  ordering, access, system, shared).
- [docs/subsystems/](docs/subsystems/) — auth & permissions, admin UI,
  smart filters, notifications.
- [docs/infra/](docs/infra/) — Flask, MySQL, yoyo migrations, Dishka,
  HTMX, CPanel deployment.
- [docs/dev/connecting-to-the-database.md](docs/dev/connecting-to-the-database.md)
  — step-by-step: get MySQL credentials, point your shell/IDE/app at
  the DB, run migrations.
- [docs/contract/](docs/contract/) — wire-level public and admin API.
- [docs/adr/](docs/adr/) — architectural decisions.

## Configuration

Copy `.env.example` to `.env` for local work. Important variables:

| Variable | Default | Purpose |
|---|---|---|
| `ROOT_APP_NAME` | `Shop Admin` | UI and Swagger name |
| `ROOT_APP_ENV` | `dev` | `dev` enables Swagger and dev defaults; use `prod` for deployment |
| `INFRA_DATABASE_URL` | `mysql+pymysql://shop:shop@localhost:3306/shop?charset=utf8mb4` | SQLAlchemy URL (PyMySQL driver, utf8mb4) |
| `INFRA_DB_POOL_SIZE` / `INFRA_DB_POOL_RECYCLE` / `INFRA_DB_POOL_PRE_PING` | `5` / `3600` / `true` | Pool tuning — leave `pre_ping=true` on CPanel |
| `ACCESS_JWT_SECRET` | `change-me-in-production` | JWT signing secret |
| `ACCESS_DEFAULT_LOGIN` / `ACCESS_DEFAULT_PASSWORD` | `admin` / `changeme` | Bootstrap admin credentials |
| `ACCESS_PROMOTE_TO_SUPERADMIN` | `false` | If `true`, the default admin (id=1) is a superadmin; otherwise owner role |
| `ACCESS_OWNER_CAN_*` | mostly `false` | Owner permission flags |
| `ACCESS_RECOVERY_CODE_*` | code defaults | Telegram code TTL / cooldown / attempts / lockout |
| `ACCESS_CUSTOMER_RECOVERY_CODE_*` | code defaults | Customer password recovery code settings |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM` | see `.env.example` | Email sender for customer recovery (leave `SMTP_HOST` empty for logging mode) |
| `CATALOG_UPLOAD_DIR` | `media/products` | Product image upload directory |
| `SYSTEM_RECOVERY_TOKEN` | `change-me-in-production` | URL token for Telegram password recovery |
| `ROOT_PUBLIC_CORS_ORIGINS` / `ROOT_ADMIN_CORS_ORIGINS` | unset | CORS allow-lists |
| `ROOT_RATE_LIMIT_*` | code defaults | Default / login / order / recovery rate limits |
| `PORT` | `5000` | Local server port |

Telegram bot token is stored in admin settings. Notification and login
targets are per-user `admins.telegram_chat_id` values.

## API

- Public API: [docs/contract/public.md](docs/contract/public.md)
- Admin API: [docs/contract/admin.md](docs/contract/admin.md)
- Common conventions: [docs/contract/common.md](docs/contract/common.md)
- Swagger UI: `/api/docs` in dev mode only.

## Database

MySQL 5.7+/MariaDB 10.3+ via the `PyMySQL` driver, `utf8mb4` everywhere.
Schema is owned by `migrations/*.sql` and applied with
`yoyo-migrations` — the Flask app never issues DDL. See
[docs/infra/mysql.md](docs/infra/mysql.md) and
[docs/infra/migrations.md](docs/infra/migrations.md).

For developers who need to connect (shell, IDE, scripts) — including
how to obtain the username/password — see
[docs/dev/connecting-to-the-database.md](docs/dev/connecting-to-the-database.md).

## Deployment

Docker:

```bash
docker compose up --build
```

Gunicorn:

```bash
PYTHONPATH=src gunicorn --bind 0.0.0.0:5000 --workers 2 'root.entrypoints.api:create_app()'
```

CPanel shared hosting uses `passenger_wsgi.py` and Phusion Passenger;
see [docs/infra/cpanel.md](docs/infra/cpanel.md). Set
`ROOT_APP_ENV=prod` and replace all default secrets before exposing
the app.

## License

MIT
