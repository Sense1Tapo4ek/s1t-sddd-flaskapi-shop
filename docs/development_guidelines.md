# Development Guidelines

These rules describe how to extend this shop template without weakening its architecture, security, or scalability.

## Architecture Rules

Keep the context boundaries:

| Context | Owns |
|---|---|
| `catalog` | Products, images, categories, tags, attributes, public catalog reads. |
| `ordering` | Orders, order status transitions, order notifications. |
| `access` | Admin users, login, JWT/session, password changes, Telegram login codes. |
| `system` | Store settings, Telegram bot settings, public store info. |
| `shared` | Generic DB/session utilities, middleware, errors, file storage, low-level clients. |
| `root` | App factory, bootstrap, DI container, blueprint registration. |

Layer rules:

| Layer | Allowed responsibility |
|---|---|
| `domain` | Pure entities, value objects, domain errors, invariants that do not need Flask/SQLAlchemy. |
| `app` | Use cases and interfaces. Coordinates domain logic and ports. |
| `ports/driving` | Facades and Pydantic schemas consumed by Flask adapters. |
| `ports/driven` | Repository/client implementations behind app interfaces. |
| `adapters/driving` | Flask/APIFlask routes, HTMX pages, request parsing, response rendering. |
| `adapters/driven` | ORM models and external APIs. |

Do not import Flask, SQLAlchemy models, or request/session objects into domain or app use cases. A use case should depend on an interface from `app/interfaces`, not on a concrete repository.

Avoid adding compatibility helpers like facade reflection unless there is a documented migration reason. Explicit method signatures are better because tests catch contract drift.

## Adding A Feature

Use this sequence for non-trivial features:

1. Define domain model/invariants/errors.
2. Add or extend an app interface if persistence/external IO is needed.
3. Implement the use case.
4. Implement repository/client methods.
5. Expose the operation through a driving facade schema.
6. Add API/admin route with explicit auth/permission checks.
7. Add UI only after the API behavior is stable.
8. Add docs and tests.

A route should be thin. It may parse request data and choose response shape, but it should not contain business decisions such as category tree validity, role rules, or product attribute validation.

## Auth And Permissions

Current permissions:

| Permission | Meaning |
|---|---|
| `view_category_tree` | Can open and read taxonomy structure; baseline for every authenticated admin. |
| `edit_taxonomy` | Can create/update/delete categories, tags, and attributes. |
| `view_products` | Can open product admin pages and product search. |
| `edit_products` | Can create/update/delete products and images. |
| `view_orders` | Can read orders. |
| `manage_orders` | Can change order status and delete/create test orders. |
| `manage_settings` | Can edit store and Telegram bot settings. |
| `create_demo_data` | Can run demo catalog generator. |

Permission implication rules that should be preserved:

| If enabled | Must also allow |
|---|---|
| Any authenticated admin | `view_category_tree` |
| `edit_products` | `view_products`, `view_category_tree` |
| `edit_taxonomy` | `view_category_tree` |
| `manage_orders` | `view_orders` |
| `create_demo_data` | `view_category_tree`, `edit_taxonomy`, `view_products`, `edit_products` |

Admin route rules:

| Route type | Required guard |
|---|---|
| Admin page read | `permission_required("view_*")` or `jwt_required` for security page. |
| Admin mutation | Specific edit/manage permission. |
| Superadmin-only action | A dedicated permission such as `create_demo_data`, or `superadmin_required` if no owner should ever get it. |
| Public API | No admin JWT, but must enforce public visibility rules in use cases/repositories. |

Do not trust UI hiding as authorization. Every protected endpoint needs a server-side guard.

Catalog runtime permissions must fail closed if settings cannot be loaded. The only exception is `superadmin`, which retains all permissions.

JWT guidance:

Keep JWT payload small and revocable. Prefer `sub`, `role`, `iat`, and a `session_version` over embedding a long-lived permission snapshot. If permissions or active status can change, the server must be able to invalidate existing sessions.

Password guidance:

Require current password or a same-user Telegram confirmation code for normal password changes. Use Telegram recovery only as a separate recovery flow. Enforce password rules on the server, not only with HTML attributes.

The admin SQLite dump is superadmin-only and additionally requires `admins.password_changed_at` to be set. The dev fallback `superadmin/superadmin` must not be enough for a dump.

Telegram guidance:

- Keep the bot token in global system settings.
- Store notification/login targets on `admins.telegram_chat_id`.
- New-order notifications go to active `owner` and `superadmin` users with a chat ID.
- Fetching a chat ID from Telegram must return a value for the account form, not silently persist a global recipient.

## Public/Admin Data Boundary

Public catalog reads must never expose inactive products, inactive categories, internal attributes, bot tokens, admin roles, recovery state, or system-only settings.

Rules:

| Area | Rule |
|---|---|
| Public product list | Always apply `is_active=true` outside user-overridable filters. |
| Public product detail | Return 404/422 for inactive products. |
| Admin product detail | Use an authenticated admin endpoint, not public detail. |
| Public filters | Whitelist allowed keys. Do not pass arbitrary query args to generic DB filters. |
| Public category tree | Include only active categories. Counts should count only active products. |
| Public tags | Include only active tags. |

When adding a public endpoint, start from the output schema. If a field is not explicitly meant for storefront users, do not include it.

## Input Validation And Errors

Validation rules:

| Input | Rule |
|---|---|
| IDs from forms | Use shared parsing helpers or Pydantic. Never raw `int()` in a route. |
| JSON in form fields | Catch parse errors and return `400`. |
| Slugs/codes | Normalize in use cases and check duplicates before hitting DB constraints. |
| Files | Validate extension, size, and preferably actual content type. |
| Telegram chat id | Validate expected format and escape when rendering. |

Error rules:

| Error source | Client response |
|---|---|
| Domain invariant | `422` with safe human message. |
| Missing entity | `404` or `422`, depending on current app convention. |
| Auth missing/invalid | `401`. |
| Permission denied | `403`. |
| Known duplicate/constraint | `409` or `422` with safe message. |
| Unknown DB/internal failure | Generic `500`; default logs should avoid raw SQL/constraint payloads. |

Do not return raw SQLAlchemy exception text to clients. Do not print raw SQLAlchemy tracebacks from wrapped repository errors in normal server logs; log the operation and exception category instead.

## Database And Migrations

The current app uses `Base.metadata.create_all()` and SQLite by default. That is acceptable for a tiny deploy, but schema evolution must be explicit.

Rules:

| Change | Required work |
|---|---|
| New table | Add ORM model, docs/database entry, indexes, repository, migration/backfill if existing DB needs it. |
| New column | Add ORM field and an idempotent migration/backfill path for existing SQLite DBs. |
| New index | Put it in the ORM model and in migration for existing DBs. |
| New relation | Enable/verify SQLite FKs and add delete/update behavior tests. |
| Production DB beyond SQLite | Introduce Alembic before the first serious deployment. |

SQLite-specific requirements:

- Enable `PRAGMA foreign_keys=ON` for every app connection through a SQLAlchemy event listener.
- Do not assume `ondelete` works unless the app connection enables FK enforcement.
- Avoid primary-key swapping; use explicit sort/order columns.
- Keep SQLite compatibility patches idempotent and isolated under infrastructure bootstrap. Do not add schema patching logic to the Flask app factory.

Index guidance:

| Query pattern | Index |
|---|---|
| Category children | `categories(parent_id)` |
| Active category tree | `categories(is_active, sort_order)` |
| Product category filter | `products(category_id)` |
| Active product list | `products(is_active, id)` or `products(is_active, created_at)` |
| Tags by active/sort | `tags(is_active, sort_order)` |
| Product tags | `product_tags(product_id, tag_id)` and `product_tags(tag_id)` |
| Attribute filters | `product_attribute_values(attribute_id, value_text/value_number/value_bool)` |

## Catalog And Taxonomy

Category rules:

- Products should be assigned only to leaf categories.
- Moving a category must reject cycles.
- Deleting a category must reject categories with children or products.
- Public tree should hide inactive categories.
- Product counts should be explicit about whether they include descendants and inactive products.

Attribute rules:

- Attribute `code` must be unique across the effective inherited chain.
- Create and update must enforce the same uniqueness rules.
- Required attributes should be validated only for products assigned to categories where they are effective.
- Select/multiselect values should be checked against options when options exist.

Tag rules:

- Tags are global, not category-scoped.
- Public endpoints should return only active tags.
- Product edit UI requires tag read access if tags are displayed.

Demo data rules:

- Demo generation must be idempotent.
- Demo rows should be identifiable by stable slugs/titles.
- Do not make demo generation depend on external network for correctness; current demo images use local placeholder bytes.
- Long-running generation should be a job or chunked operation, not one blocking request.

## Admin UI Rules

Authorization:

- Hide unavailable actions in templates, but always enforce permissions on endpoints.
- If a page makes secondary API calls, the user's permissions must cover those calls too.
- Prefer one source of truth for `CAN_*` flags in the page script.

HTMX/API:

- All mutating HTMX and `fetch()` calls must include CSRF.
- Non-2xx responses should show a toast and not replace the whole panel with raw JSON.
- Partial HTML responses must escape dynamic values or render through Jinja templates.

JavaScript:

- Use `textContent` for raw user content when possible.
- If building HTML strings, escape every dynamic value.
- Do not rely on client validation only; server must validate all fields.

## Performance Rules

For the current template, optimize for simple code first, but avoid known scaling traps.

Rules:

| Pattern | Guidance |
|---|---|
| Tree reads | Fine to load all categories for small catalogs; add recursive CTE or cached tree for large catalogs. |
| Attribute filters | Keep indexes in place and avoid joining repeatedly for many attr filters without tests. |
| Random products | `ORDER BY random()` is okay for small catalogs only. |
| Image generation/download | Do not block admin requests on slow external services. |
| Pagination | Always cap `limit` and validate `page`. |
| N+1 loads | Use `selectinload` for product images, tags, category, and attributes. |

When a query is used by SmartTable, check both the item query and the count query. Count over joined/distinct subqueries can become the slowest part.

## Security Checklist Before Release

Minimum release gate:

- `ROOT_APP_ENV=prod`.
- Strong `ACCESS_JWT_SECRET`.
- Strong `SYSTEM_RECOVERY_TOKEN`.
- Strong `ACCESS_DEFAULT_PASSWORD`.
- Strong `ACCESS_SUPERADMIN_PASSWORD`.
- Swagger disabled in prod.
- Telegram login endpoints rate-limited.
- Admin cookie-auth mutations protected by CSRF.
- No raw DB errors returned to clients.
- Public inactive products cannot be read.
- SQLite foreign keys enabled or production DB migrations configured.
- Default dev credentials unavailable in production.

## Verification Commands

Run syntax checks:

```bash
PYTHONPATH=src python3 -m py_compile $(find src data -name '*.py' -not -path '*/__pycache__/*')
```

Run app factory smoke:

```bash
PYTHONPATH=src uv run python3 -c "from root.entrypoints.api import create_app; app = create_app(); print('OK', len(app.url_map._rules))"
```

Run unit and flow tests:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --extra dev pytest -q -m "unit or flow"
```

Run diff hygiene:

```bash
git diff --check
```

Suggested tests to add first:

| Test | Expected |
|---|---|
| Public inactive product list/detail | Inactive products are not visible. |
| Owner default permissions | Can read categories, cannot mutate taxonomy/products/orders/settings. |
| Superadmin permissions | Can access every admin route. |
| Telegram code request throttling | Excess attempts are rejected. |
| Telegram code verification attempts | Wrong codes lock or throttle. |
| Product title-only update | Tags/attributes/images are preserved. |
| Product swap/order operation | Tags/images/attributes stay attached correctly. |
| Duplicate category/tag/attribute slugs | Safe 409/422, no DB internals leaked. |
| Category move cycle | Rejected. |
| Required attributes | Enforced for leaf-category products. |

## Documentation Rules

Whenever behavior changes, update docs in the same change:

| Change | Docs |
|---|---|
| API route/schema | `docs/api_public.md` or `docs/api_admin.md` |
| Table/column/index | `docs/database.md` |
| Deployment/env | `README.md` and `docs/cpanel.md` |
| New entity pattern | `docs/adding_new_table.md` |
| New security/permission behavior | `docs/development_guidelines.md` |

Docs must describe the actual code, not the intended future state. If a guide recommends a future hardening step, mark it as a requirement or TODO clearly.
