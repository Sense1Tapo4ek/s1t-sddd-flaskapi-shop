# Infra: Flask / APIFlask

For contributors configuring routes, OpenAPI, error handlers, or
middleware. Vendor docs are authoritative; this page captures only
project-specific usage.

## Version

APIFlask (which extends Flask with Pydantic-based input/output
schemas + Swagger). Pinned via `pyproject.toml`.

## App factory

`src/root/entrypoints/api.py` exposes `create_app()`. It:

1. Loads `RootConfig` (`ROOT_*` env vars).
2. Builds the Dishka container (`src/root/container.py`).
3. Instantiates `APIFlask(...)` with the app name and `docs_path`
   conditional on `app_env == "dev"`.
4. Registers middleware, error handlers, blueprints, and the bootstrap
   hook that verifies the schema via `ensure_schema_present(engine)`
   (refuses to start if migrations are unapplied) and seeds default
   users/settings.

CPanel Passenger and Docker both call `create_app()`.

## Blueprint registration

JSON API blueprints under `src/<context>/adapters/driving/api.py`.
Admin HTMX blueprints under `src/<context>/adapters/driving/admin.py`.
Both are registered in `create_app()`:

```python
app.register_blueprint(catalog_bp)
app.register_blueprint(ordering_bp)
app.register_blueprint(access_bp)
app.register_blueprint(system_bp)

app.register_blueprint(catalog_admin_bp)
app.register_blueprint(taxonomy_admin_bp)
app.register_blueprint(ordering_admin_bp)
app.register_blueprint(access_admin_bp)
app.register_blueprint(system_admin_bp)
app.register_blueprint(account_admin_bp)
```

## OpenAPI hygiene

- JSON API blueprints expose `/api/docs` (Swagger UI) **only when
  `ROOT_APP_ENV=dev`**.
- Admin HTMX blueprints set `enable_openapi=False` so HTMX pages never
  appear in Swagger.
- Utility/template routes that should not be in Swagger use
  `@bp.doc(hide=True)`.

## Schemas

Every JSON route validates input through a Pydantic schema in
`ports/driving/schemas.py` of the owning context, and declares its
response shape with `@bp.output`:

```python
@bp.post("/")
@bp.input(CreateInquiryIn)
@bp.output(CreatedIdResponse, status_code=201)
@bp.doc(summary="Create inquiry (Public)")
@inject
def create(json_data: CreateInquiryIn,
           facade: FromDishka[InquiriesFacade]):
    return {"success": True, "id": facade.create_inquiry(json_data)}
```

Rules:

- Always pair `@bp.input` with `@bp.output` so Swagger UI shows both
  request and response shapes. Endpoints that return `201` must pass
  `status_code=201` to `@bp.output` — otherwise the spec lies (claims
  200).
- Generic envelopes live in `shared/ports/driving/schemas.py`:
  `SuccessResponse` (`{success: true}`), `CreatedIdResponse`
  (`{success: true, id: int}`).
- No raw `int(request.form["x"])` in handlers — declare it in the
  schema and let APIFlask raise 422 on failure.
- Multipart uploads (`POST/PUT /catalog`) use a marshmallow `Schema`
  with `apiflask.fields.File` in
  `<context>/ports/driving/multipart_schemas.py` and
  `@bp.input(Schema, location="form_and_files", arg_name="_form")`.
  The handler accepts `_form: dict` and ignores it — schemas exist
  for the OpenAPI requestBody, the handler reads `request.form`
  and `request.files` directly.

## Middleware

Registered in `create_app()` from `src/shared/adapters/driving/middleware.py`:

| Order | Responsibility |
|---|---|
| 1 | Set `request_id` |
| 2 | Parse JWT from `Authorization: Bearer` or `token=` cookie |
| 3 | Enforce CSRF on cookie-auth unsafe methods |
| 4 | Apply rate limits (`ROOT_RATE_LIMIT_*`) when `app_env == "prod"` |

## Error handlers

Centralized in `src/shared/adapters/driving/error_handlers.py`. They
map domain/app/port errors to JSON status codes with safe messages.
See [../subsystems/auth-permissions.md](../subsystems/auth-permissions.md)
for the auth error shape.

## CORS

`ROOT_PUBLIC_CORS_ORIGINS` and `ROOT_ADMIN_CORS_ORIGINS` are
JSON-array env vars. They are enforced only in `prod`. In `dev`, CORS
is wide open by design.

## Smoke check

```bash
PYTHONPATH=src uv run python3 -c "from root.entrypoints.api import create_app; app = create_app(); print('OK', len(app.url_map._rules))"
```

This runs the full bootstrap path (schema-present check, default
users/settings) and prints the route count. Migrations must be
applied first (`python scripts/db_apply.py`).

## Pointers

- App factory: `src/root/entrypoints/api.py`
- Container: `src/root/container.py`
- Config: `src/root/config.py`
- Middleware: `src/shared/adapters/driving/middleware.py`
- Error handlers: `src/shared/adapters/driving/error_handlers.py`
