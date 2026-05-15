# Context: shared

For contributors touching cross-cutting infrastructure. `shared` is the
**shared kernel** — every bounded context may import from it; it must
not import from any bounded context.

## Mental model

Generic plumbing that every context needs and nobody owns. SQLAlchemy
`Base` + session, request middleware (JWT parsing, CSRF), error
handlers, file storage (local FS / S3), the Telegram HTTP client, and
secret ciphering.

```
shared/
├── adapters/
│   ├── driven/
│   │   ├── db/          Base, engine, session, schema_guard, mysql opts
│   │   ├── file_storage.py     Local FS backend
│   │   ├── s3_file_storage.py  S3 backend
│   │   ├── telegram_client.py  Low-level HTTP to Bot API
│   │   └── secret_cipher.py    Fernet wrapper for stored secrets
│   └── driving/
│       ├── error_handlers.py   APIFlask error → JSON mapping
│       ├── middleware.py       JWT parsing, CSRF, request_id
│       └── htmx.py             HTMX response helpers
├── domain/              Generic value objects (paginated result, etc.)
├── generics/            Stdlib helpers, base errors
├── helpers/             Utility code
├── ports/driving/       Shared schemas (Pydantic) used across contexts
├── config.py            InfraConfig (DB URL, etc.)
└── provider.py          InfraProvider — DB engine, session factory, file storage
```

There is no `shared/ports/driven/` — `shared` has no outgoing
boundary of its own; every concrete client is in `adapters/driven/`
and consumed directly by other contexts' driven ports.

## Public surface

`InfraProvider` (in `src/shared/provider.py`) exposes:

- `Engine` and `scoped_session` for SQLAlchemy.
- `IFileStorage` resolved to local FS or S3 depending on storage settings.
- `TelegramClient` (raw Bot API HTTP client).
- `SecretCipher` for Fernet-style encryption of stored credentials.

Middleware (registered by `root/entrypoints/api.py`):

| Layer | Purpose |
|---|---|
| `error_handlers` | Maps `DomainError`, `AppError`, `PortError`, generic `Exception` to JSON responses with safe messages and proper status codes |
| `middleware` | Parses `Authorization: Bearer <jwt>` or `token=` cookie, validates CSRF on cookie-auth unsafe methods, sets a `request_id` |
| `htmx` | Helpers for HX-* response headers and partial fragment rendering |

## Invariants & gotchas

- **Single `Base` across all contexts.** Every ORM model imports from
  `shared/adapters/driven/db/base.py`. All models append
  `mysql_table_opts()` to `__table_args__` (InnoDB + utf8mb4).
- **Schema is migration-managed.** `Base.metadata.create_all` is NEVER
  called outside tests. `schema_guard.ensure_schema_present(engine)`
  refuses to boot the app when the canonical tables are missing.
- **Pool tuned for shared hosting.** `pool_pre_ping=True`,
  `pool_recycle=3600`. CPanel kills idle connections — leave these on.
- **Error handlers must not leak SQL details.** 5xx responses use a
  generic message; details go to the log only. Domain errors map to
  422, missing entities to 404, auth missing/invalid to 401,
  permission denied to 403, duplicates/constraints to 409/422.
- **CSRF middleware is wide.** It applies to every cookie-auth unsafe
  method (POST/PUT/PATCH/DELETE). Routes do not need to opt in. API
  clients with `Authorization: Bearer` are exempt — checked by the
  middleware, not the route.
- **`shared` has no business logic.** If you find yourself writing a
  `if request.json["status"] == "...":` here, the code belongs in a
  context.

## Pointers

- Base + engine: `src/shared/adapters/driven/db/`
- Middleware: `src/shared/adapters/driving/middleware.py`
- Error handlers: `src/shared/adapters/driving/error_handlers.py`
- File storage: `src/shared/adapters/driven/file_storage.py` (+ S3)
- Auth + CSRF subsystem: [../subsystems/auth-permissions.md](../subsystems/auth-permissions.md)
- DB schema reference: [../infra/mysql.md](../infra/mysql.md)
- Migrations: [../infra/migrations.md](../infra/migrations.md)
