# Architecture

For contributors who need to add features or change behaviour without
breaking the bounded-context discipline of this template.

## Mental model

A Flask/APIFlask process hosts six packages under `src/`. Five are
bounded contexts; one (`root`) wires them together.

```
+-------------------------------------------------------------+
|                       root/ (entrypoint)                    |
|   create_app  ->  Dishka container  ->  blueprints          |
+----------+----------+-----------+-----------+---------------+
           |          |           |           |
        catalog    ordering    access      system
           \           |          /           /
            +--------- shared ---------------+
                  (db, middleware, telegram,
                   file storage, errors)
```

Each context owns one slice of the domain and exposes a single
**facade** (Pydantic-in, primitives/Pydantic-out). HTTP handlers and
HTMX admin pages live in `adapters/driving/` and call the facade —
they never touch domain or ORM directly.

## Bounded contexts

| Context | Owns | Reference |
|---|---|---|
| `catalog` | products, images, categories, tags, attributes, public catalog reads | [contexts/catalog.md](contexts/catalog.md) |
| `ordering` | orders, status transitions, order notifications | [contexts/ordering.md](contexts/ordering.md) |
| `access` | admin users, JWT, permissions, password/Telegram recovery | [contexts/access.md](contexts/access.md) |
| `system` | store settings (singleton), Telegram bot token, public store info | [contexts/system.md](contexts/system.md) |
| `shared` | DB session, middleware, errors, file storage, Telegram client | [contexts/shared.md](contexts/shared.md) |
| `root` | app factory, Dishka container, blueprint registration, bootstrap | — |

## Layer rules

Every business context follows the same shape:

```
src/<context>/
├── domain/            Aggregates, value objects, invariants. Pure Python.
├── app/               Use cases + interfaces. No Flask, no ORM.
│   └── interfaces/    Protocols / ABCs implemented by ports/driven/.
├── ports/
│   ├── driving/       Facade + Pydantic schemas. Public API of the context.
│   └── driven/        SQL repos, Telegram clients, ACLs to other contexts.
├── adapters/
│   ├── driving/       APIFlask blueprints (api.py) + HTMX admin (admin.py).
│   └── driven/        ORM models, raw clients.
├── config.py          Pydantic Settings; env prefix matches context name.
└── provider.py        Dishka provider.
```

Allowed import direction:

```
adapters/driving  ->  ports/driving  ->  app  ->  domain
app               ->  app/interfaces <-  ports/driven  <-  adapters/driven
```

Forbidden:

- `domain/` or `app/` importing Flask, request/session objects,
  SQLAlchemy models, Jinja templates, or static assets.
- Cross-context imports outside of `ports/driven/<other>_acl.py`
  (the anti-corruption layer). See `ordering/ports/driven/system_notification_acl.py`
  for the canonical pattern.
- Routes embedding business decisions. Routes parse input, check
  auth/permissions, call the facade, format the response.

## Wire flow (HTTP request)

1. Flask receives a request; APIFlask validates path/query/body against
   a Pydantic schema in `ports/driving/schemas.py`.
2. Middleware in `shared/adapters/driving/middleware.py` enforces JWT
   parsing and CSRF on cookie-auth mutations.
3. Route handler in `<context>/adapters/driving/api.py` (or `admin.py`)
   resolves the facade via `FromDishka[<Context>Facade]` and calls one
   method on it.
4. Facade calls the use case; the use case calls domain methods and the
   `app/interfaces/` it depends on.
5. `ports/driven/sql_*_repo.py` translates domain ↔ ORM and runs SQL
   through a shared SQLAlchemy session.
6. Errors raised by domain or use cases bubble up to
   `shared/adapters/driving/error_handlers.py`, which maps them to JSON
   responses with safe messages (see [subsystems/auth-permissions.md](subsystems/auth-permissions.md)
   for the auth error contract).

## How to add a context

Use this sequence; each step builds on the previous one.

1. **Define the domain.** Create `src/<name>/domain/<root>_agg.py` with
   the aggregate root, invariants, and `<name>/domain/errors.py`.
2. **Declare app interfaces.** In `app/interfaces/`, add Protocols for
   every persistence/external IO dependency the use cases will need.
3. **Write use cases.** `app/use_cases/<verb>_<noun>_uc.py`. They
   accept primitives or Pydantic commands and depend on interfaces.
4. **Implement driven ports.** `ports/driven/sql_<noun>_repo.py`
   (or `<target>_acl.py` for cross-context calls). Translate between
   domain and ORM/wire format.
5. **Expose the facade.** `ports/driving/facade.py` aggregates use
   cases; `ports/driving/schemas.py` holds the wire DTOs.
6. **Wire DI.** Create `provider.py` and register it in
   `src/root/container.py`.
7. **Add adapters.** `adapters/driving/api.py` (public JSON),
   `adapters/driving/admin.py` (HTMX), `adapters/driven/db/models.py`
   (ORM). In `src/root/entrypoints/api.py`:
   - register the blueprints,
   - add a side-effect import of the ORM models module
     (`import <name>.adapters.driven.db.models  # noqa: F401`) so
     SQLAlchemy's shared `Base` picks up the tables,
   - add an entry for the context's template folder in the Jinja
     `ChoiceLoader` (otherwise admin templates 404 at render).
   In `src/shared/adapters/driven/db/schema_guard.py:REQUIRED_TABLES`,
   add the context's primary table name — otherwise the app refuses
   to start with `SchemaNotReadyError`.
8. **Tests + docs.** Add `unit`/`flow` tests under `tests/<name>/` and
   create `docs/contexts/<name>.md`.

For a new entity inside an existing context, you typically skip
creating a new provider but you still add a `provide(...)` line for
every new use case / repo. Step 7's blueprint + ORM-import +
ChoiceLoader entries are already in place.

## Operational rules

| Concern | Rule | Reference |
|---|---|---|
| Auth | Every protected route declares `permission_required(...)`, `any_permission_required(...)`, or `jwt_required`. Hidden buttons are not authorization. | [subsystems/auth-permissions.md](subsystems/auth-permissions.md) |
| CSRF | Cookie-auth unsafe methods require `X-CSRF-Token`. Bearer-token clients are exempt. | [subsystems/auth-permissions.md](subsystems/auth-permissions.md) |
| Public/admin boundary | Public endpoints must never return inactive products/categories/tags, admin role data, bot tokens, recovery state, or system-only settings. | [contexts/catalog.md](contexts/catalog.md) |
| OpenAPI | JSON API blueprints expose `/api/docs` in dev only. Admin HTMX blueprints set `enable_openapi=False`. | [infra/flask.md](infra/flask.md) |
| Validation | IDs and form fields parsed via Pydantic or shared helpers. No raw `int(request.form[...])` in routes. | — |
| DB | One SQLAlchemy `Base` shared across contexts. Schema is migration-managed (`migrations/*.sql` via yoyo). The app refuses to start if required tables are absent. | [infra/mysql.md](infra/mysql.md), [infra/migrations.md](infra/migrations.md) |

## Known constraints

These shape the template intentionally; treat them as load-bearing.

- **MySQL-first.** Schema lives in `migrations/*.sql` and is applied by
  `yoyo-migrations`. The Flask app NEVER issues DDL. See
  [adr/0006-mysql-yoyo.md](adr/0006-mysql-yoyo.md).
- **HTMX admin, no SPA.** Admin pages are server-rendered Jinja plus
  HTMX partials. See [adr/0003-htmx-admin-vs-spa.md](adr/0003-htmx-admin-vs-spa.md).
- **JWT carries a permission snapshot for non-runtime permissions.**
  Runtime catalog permissions are resolved server-side per request from
  `settings`. Other permissions live in the token until logout. Plan a
  session-version field before relying on instant revocation.
- **Demo data must stay idempotent.** Generation runs in a single
  request, identified by stable slugs/titles. Do not depend on external
  network success.

## Release checklist

| Step | Where |
|---|---|
| `ROOT_APP_ENV=prod` | `.env` |
| Strong `ACCESS_JWT_SECRET`, `SYSTEM_RECOVERY_TOKEN` | `.env` |
| `SYSTEM_STORAGE_SECRETS_KEY` set if S3 backend (irrecoverable if lost after writes) | `.env` — see [infra/storage.md](infra/storage.md) |
| Strong `ACCESS_DEFAULT_PASSWORD` (single admin row) | `.env` |
| `ACCESS_PROMOTE_TO_SUPERADMIN=true` to grant full access to that admin | `.env` |
| Swagger off in prod | enforced by `app_env` |
| Telegram login/recovery rate-limited | `ROOT_RATE_LIMIT_*` |
| CSRF on cookie-auth mutations | middleware default |
| No raw DB errors leaked | error handlers |
| Public inactive entities blocked | use-case guards |
| Migrations applied (`python scripts/db_apply.py`) | deploy step |
| Dumps scheduled in CPanel cron | `scripts/db_dump.py` |
