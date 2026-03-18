# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

s1t-sddd-flaskapi-shop — universal forkable e-commerce boilerplate. Flask/APIFlask + SQLAlchemy + Dishka DI, following S-DDD (hexagonal architecture). Python 3.11+, SQLite by default.

## Commands

```bash
# Setup
cp .env.example .env
pip install -r requirements.txt
uv sync

PYTHONPATH=src FLASK_DEBUG=1 uv run src/root/entrypoints/api.py

# Seed admin user + system settings
PYTHONPATH=src uv run data/seed.py

# Docker
docker compose up --build    # runs on port 5000

# Swagger docs available at /api/docs when running
```

No test suite exists yet. No linter/formatter is configured in project files.

## Architecture

S-DDD hexagonal architecture with 4 bounded contexts under `src/`:

```
src/{context}/
├── domain/          # Aggregates, value objects, domain errors (pure Python, no imports from outer layers)
├── app/             # Use cases + interfaces (abstract repos/gateways)
│   ├── interfaces/  # ABC definitions: IProductRepo, IFileStorage, etc.
│   └── use_cases/   # Business logic orchestration
├── ports/
│   ├── driving/     # Facade (entry point) + Pydantic schemas (DTOs)
│   └── driven/      # Concrete repo/gateway implementations (SqlProductRepo, etc.)
├── adapters/
│   ├── driving/     # Flask blueprints (api.py) — call Facade methods
│   └── driven/      # ORM models (db/models.py), external API clients
├── config.py        # Pydantic Settings with context-specific env prefix
└── provider.py      # Dishka DI Provider — wires interfaces to implementations
```

### Bounded Contexts

| Context    | Prefix    | Domain Aggregates       | Key Facade          |
|------------|-----------|-------------------------|---------------------|
| `catalog`  | CATALOG_  | Product, ProductImage   | CatalogFacade       |
| `ordering` | ORDERING_ | Order, OrderStatus      | OrderingFacade      |
| `access`   | ACCESS_   | User                    | AccessFacade        |
| `system`   | SYSTEM_   | SiteSettings (singleton)| SystemFacade        |

### Shared kernel (`src/shared/`)

- `config.py` — `InfraConfig` (INFRA_ prefix, provides `database_url`)
- `provider.py` — `InfraProvider` (DB session factory)
- `domain/value_objects.py` — `Money`, `PhoneNumber`
- `generics/errors.py` — Error hierarchy: `LayerError` → `DomainError`, `ApplicationError`, `DrivingPortError`, `DrivenPortError`, `DrivingAdapterError`, `DrivenAdapterError`
- `generics/pagination.py` — Pagination helper
- `helpers/security.py` — JWT create/verify
- `adapters/driving/middleware.py` — `@jwt_required` decorator (cookie-first, then Authorization header; stores payload in `request.admin_payload`)
- `adapters/driving/error_handlers.py` — Maps error types to HTTP status codes; HTMX-aware (sends `HX-Trigger` / `HX-Redirect` headers for HTMX requests)
- `adapters/driving/htmx.py` — `is_htmx()`, `render_partial_or_full()` helpers
- `adapters/driven/db/` — SQLAlchemy session factory + `SqlBaseRepo`
- `adapters/driven/file_storage.py` — `LocalFileStorage` (implements `IFileStorage`)
- `adapters/driven/telegram_client.py` — `TelegramClient` (sync httpx, stateless)

### Composition Root (`src/root/`)

- `container.py` — Builds Dishka container from all 5 providers (InfraProvider + 4 context providers)
- `entrypoints/api.py` — `create_app()` factory: loads .env, creates tables, registers blueprints, serves admin UI via Jinja2 + HTMX

### Dependency flow (strict)

`adapters/driving` → `ports/driving` (Facade) → `app` (use cases) → `domain`
`app` → `app/interfaces` (abstractions) ← `ports/driven` (implementations) ← `adapters/driven` (ORM/infra)

Domain and app layers must NEVER import from adapters, ports, or Flask.

### Adding a new bounded context

1. Create `src/{context}/` with the layer structure above
2. Add `config.py` with Pydantic Settings (unique env prefix)
3. Add `provider.py` with Dishka Provider
4. Register the provider in `src/root/container.py`
5. Create blueprint in `adapters/driving/api.py`, register in `src/root/entrypoints/api.py`
6. Create ORM models in `adapters/driven/db/models.py`, add `Base.metadata.create_all()` in `create_app()`

### Key conventions

- Each context has exactly one **Facade** (frozen dataclass) as the sole entry point for driving adapters
- Facades accept/return **Pydantic schemas** (defined in `ports/driving/schemas.py`), never domain objects
- Use cases live in `app/use_cases/` and depend on abstract interfaces from `app/interfaces/`
- ORM models share a single SQLAlchemy `Base` from `shared/adapters/driven/db/base.py`
- Config classes use `pydantic-settings` with env prefix matching context name (CATALOG_, ORDERING_, etc.)
- All DI is APP-scoped via Dishka providers; use `@inject` + `FromDishka[T]` in blueprint route handlers
- JWT is stored in an httpOnly cookie (`token`) for admin UI; API clients may use Authorization Bearer header
- JWT secret is stored on `flask.current_app.config["JWT_SECRET"]` via `init_middleware(app, jwt_secret)` at startup; `@jwt_required` reads it from there

### DI pattern (Dishka Flask integration)

```python
from dishka.integrations.flask import inject, FromDishka
from catalog.ports.driving.facade import CatalogFacade

@catalog_bp.get("/catalog")
@inject
def list_products(facade: FromDishka[CatalogFacade]):
    return facade.list_products(...)
```

## API Routes

- Public: `GET /catalog`, `GET /catalog/random`, `GET /catalog/<id>`, `GET /system/info`, `POST /orders`
- Admin (JWT): `GET/POST/PUT/DELETE /catalog/...`, `GET/PATCH /orders/...`, `GET/PUT /system/settings`, `POST /auth/login`, `POST /auth/change-password`
- Admin UI (HTMX): `/admin/` — Jinja2 templates with HTMX partial rendering; auth via httpOnly cookie
- Swagger: `/api/docs`

## Docs

- `docs/api_public.md` — Public API contract
- `docs/api_admin.md` — Admin API contract
- `docs/database.md` — Database schema reference
- `docs/filters.md` — Smart filter system (schemas, SmartTable, operators)
- `docs/adding_new_table.md` — Step-by-step guide for adding new entities
- `docs/cpanel.md` — CPanel deployment guide
