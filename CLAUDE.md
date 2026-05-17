# CLAUDE.md

Canonical operational guide for Claude Code and human contributors.
This file is the single source of operating rules — there is no
separate AGENTS.md. Detailed contracts live in `docs/`.

## First Links

| Need | Read |
|---|---|
| Product overview, run/deploy commands | [README.md](README.md) |
| Architecture, contexts, layer rules, release checklist | [docs/architecture.md](docs/architecture.md) |
| One bounded context (catalog / ordering / access / system / shared) | [docs/contexts/](docs/contexts/) |
| Auth & permissions (JWT, CSRF, runtime vs snapshot perms) | [docs/subsystems/auth-permissions.md](docs/subsystems/auth-permissions.md) |
| Admin UI conventions (HTMX, partials, CSRF on mutations) | [docs/subsystems/admin-ui.md](docs/subsystems/admin-ui.md) |
| SmartTable filter schema and operators | [docs/subsystems/smart-filters.md](docs/subsystems/smart-filters.md) |
| Telegram flows (orders, login codes, recovery) | [docs/subsystems/notifications.md](docs/subsystems/notifications.md) |
| Public storefront contract | [docs/contract/public.md](docs/contract/public.md) |
| Admin API contract | [docs/contract/admin.md](docs/contract/admin.md) |
| Common wire conventions (auth, errors, pagination) | [docs/contract/common.md](docs/contract/common.md) |
| MySQL backend (driver, charset, pool, tables) | [docs/infra/mysql.md](docs/infra/mysql.md) |
| Schema migrations (yoyo: add / apply / rollback) | [docs/infra/migrations.md](docs/infra/migrations.md) |
| How to connect to the DB (creds, IDE, CPanel) | [docs/dev/connecting-to-the-database.md](docs/dev/connecting-to-the-database.md) |
| Flask/APIFlask app factory and OpenAPI rules | [docs/infra/flask.md](docs/infra/flask.md) |
| Dishka providers and DI conventions | [docs/infra/dishka.md](docs/infra/dishka.md) |
| HTMX conventions | [docs/infra/htmx.md](docs/infra/htmx.md) |
| CPanel/Passenger deployment | [docs/infra/cpanel.md](docs/infra/cpanel.md) |
| Architectural decisions | [docs/adr/](docs/adr/) |

## Project Shape

Flask/APIFlask shop template with SQLAlchemy, Dishka DI, HTMX admin
pages, S-DDD/hexagonal boundaries.

Bounded contexts under `src/`:

| Context | Owns |
|---|---|
| `catalog` | Products, images, categories, tags, attributes, public catalog reads |
| `ordering` | Orders, status transitions, notifications |
| `access` | Admin users, login, JWT/session, permissions, password flows |
| `system` | Store settings (singleton), Telegram bot token, public store info |
| `shared` | Generic infrastructure (DB/session, middleware, errors, file storage) |
| `root` | App factory, bootstrap, container, blueprint registration |

Each business context follows the S-DDD layer shape (see
[docs/architecture.md](docs/architecture.md) for the full description):

```
src/<context>/
├── domain/            Aggregates, value objects, invariants. Pure Python.
├── app/               Use cases + interfaces. No Flask, no ORM.
├── ports/
│   ├── driving/       Facade (single per context) + Pydantic schemas.
│   └── driven/        SQL repos, external clients, cross-context ACLs.
├── adapters/
│   ├── driving/       APIFlask blueprints (api.py) + HTMX admin (admin.py).
│   └── driven/        ORM models, raw clients.
├── config.py          Pydantic Settings (env prefix matches context).
└── provider.py        Dishka provider.
```

Layer direction is strict — enforced by import discipline:

```
adapters/driving -> ports/driving -> app -> domain
app -> app/interfaces <- ports/driven <- adapters/driven
```

`domain/` and `app/` MUST NOT import Flask, request/session objects,
SQLAlchemy models, Jinja templates, or static assets. Cross-context
imports are allowed ONLY through ACLs in `ports/driven/<target>_acl.py`
(see `ordering/ports/driven/system_notification_acl.py`).

## Common Commands

```bash
# Install
uv sync
# or: pip install -r requirements.txt

# Start MySQL (compose ships mysql:5.7) and apply migrations
docker compose up -d db
python scripts/db_apply.py

# Run local app (MySQL must be up + migrated)
PYTHONPATH=src FLASK_DEBUG=1 uv run src/root/entrypoints/api.py

# Full stack via Docker
docker compose up --build

# DB operations
python scripts/db_apply.py     # yoyo apply (idempotent)
python scripts/db_status.py    # applied + pending
python scripts/db_rollback.py  # rollback last migration
python scripts/db_dump.py      # data/dumps/<ts>.sql.gz
bash   scripts/db_shell.sh     # mysql CLI from .env

# Unit + flow tests (fast, no DB)
PYTHONDONTWRITEBYTECODE=1 uv run --extra dev pytest -q -m "unit or flow"

# App-factory smoke (assumes migrations applied + DB reachable)
PYTHONPATH=src uv run python3 -c "from root.entrypoints.api import create_app; app = create_app(); print('OK', len(app.url_map._rules))"

# Diff hygiene
git diff --check
```

## Change Rules

- Prefer existing context and layer patterns over new abstractions.
- Routes stay thin: parse input, check auth/permissions, call facade,
  format response. Business decisions belong in use cases/domain.
- Expose driving operations through the context facade with Pydantic
  schemas. Facades return primitives or Pydantic, not domain objects.
- Every protected route declares `permission_required(...)`,
  `any_permission_required(...)`, or `jwt_required`. UI hiding is not
  authorization.
- Cookie-auth unsafe requests require CSRF; bearer-token clients are
  exempt (enforced in `shared/adapters/driving/middleware.py`).
- Public endpoints must never expose inactive catalog data, admin
  data, bot tokens, recovery state, or internal settings.
- Cross-context calls go through ACLs in `ports/driven/`. Never import
  another context's `app/` or `adapters/` directly.
- Test markers: `unit`, `flow`, `integration`, `e2e` (configured in
  `pyproject.toml`).
- Update the matching doc page in the same change when API routes,
  schemas, env vars, DB schema, permissions, or deployment steps
  change. Doc drift is treated as a bug.

## Feature Workflow (S-DDD order)

For any non-trivial behaviour, work in this sequence:

1. **Domain.** Add aggregate/VO/invariants in `<ctx>/domain/`. Errors
   in `<ctx>/domain/errors.py`.
2. **App interface.** Declare a Protocol in `<ctx>/app/interfaces/`
   for every persistence/external IO need.
3. **Use case.** `<ctx>/app/use_cases/<verb>_<noun>_uc.py`. Depends on
   interfaces; accepts primitives or Pydantic commands.
4. **Driven port.** `<ctx>/ports/driven/sql_<noun>_repo.py` (or
   `<target>_acl.py`). Translates domain ↔ ORM/wire.
5. **Facade method + schema.** `<ctx>/ports/driving/facade.py` and
   `<ctx>/ports/driving/schemas.py`.
6. **Driving adapter.** Route in `<ctx>/adapters/driving/api.py` or
   `admin.py` with explicit auth/permission decorators.
7. **DI wiring.** Add `provide(...)` in `<ctx>/provider.py`. The
   provider is the ONLY place mapping concrete → interface.
8. **Tests + docs.** Add `unit`/`flow` tests; update the relevant
   `docs/contexts/<name>.md` or `docs/contract/*.md` in the same PR.

For a new entity in an existing context, skip the DI wiring step (the
provider already exists) and add only the new repo/use case/facade
method/route/template.

## Permissions

**Account type gate (first check):** `account_type` claim is checked before role/permissions. Customer JWTs are rejected by `admin_required`, `permission_required(...)`, and `superadmin_required` decorators.

The eight server-side permissions (admin only):

`view_category_tree`, `edit_taxonomy`, `view_products`,
`edit_products`, `view_orders`, `manage_orders`, `manage_settings`,
`create_demo_data`.

`superadmin` has every permission. Owner permissions are constrained
by runtime settings (catalog scope) and `ACCESS_OWNER_CAN_*` env flags
(other scopes). Customers have no permissions field. Implication rules and runtime-vs-snapshot semantics:
[docs/subsystems/auth-permissions.md](docs/subsystems/auth-permissions.md).

## Errors

Each context defines its own error hierarchy. Adapters catch them in
`shared/adapters/driving/error_handlers.py`:

| Error type | HTTP | Log level |
|---|---|---|
| `DomainError` (invariant violation) | 409 / 422 | warning |
| `AppError` (missing entity, orchestration) | 404 / 422 | warning |
| `PortError` (infra failure) | 503 | error + traceback |
| Unknown `Exception` | 500 | exception + traceback |

5xx responses NEVER expose SQL errors, tracebacks, or internal field
names. Domain code never logs; only adapters do.

## Documentation Hygiene

Eight kinds of docs, eight homes. Do not mix kinds.

| Change | Update |
|---|---|
| Architecture / context boundary / cross-context flow | `docs/architecture.md`, `docs/contexts/<name>.md` |
| Cross-cutting capability (auth, UI, filters, Telegram) | `docs/subsystems/<name>.md` |
| External library/tool usage | `docs/infra/<tool>.md` |
| Wire protocol (HTTP route/schema/status code) | `docs/contract/{public,admin,common}.md` |
| Architectural decision | New `docs/adr/NNNN-<kebab>.md` (≤40 lines) |
| Run/install/deploy commands and env vars | `README.md` |

Line budgets (hard caps):

| Page | Max lines |
|---|---|
| README | 200 |
| `architecture.md` | 300 |
| `contexts/*.md` | 250 |
| `subsystems/*.md` | 200 |
| `infra/*.md` | 150 |
| `contract/*.md` | 300 |
| ADR | 40 |

Anti-patterns (always wrong):

- Restating code in prose; documenting field types that the schema
  already encodes.
- Tutorials inside reference pages.
- Implementation diaries ("we tried X but…"); use ADRs or commits.
- Marketing voice ("powerful, flexible").
- Stale TODOs / "coming soon"; land it or delete the line.

## Claude-Specific Notes

- Keep edits scoped to the user's requested area. This repo may have
  unrelated local changes; do not revert them.
- Prefer the existing bounded-context and layer patterns before adding
  abstractions.
- For code changes, run the narrowest relevant tests first
  (`pytest -m "unit or flow"`), then broader checks if the change
  crosses contexts.
- For documentation-only changes, verify links and run `git diff --check`.
- Do not duplicate architecture / API / database reference here;
  update `docs/<area>/<page>.md` instead.
