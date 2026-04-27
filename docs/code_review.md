# Code Review

Date: 2026-04-24

Scope: current Flask/APIFlask shop template after taxonomy, role/permission, superadmin, Telegram login, and demo-data changes.

Remediation update:

- Fixed: admin cookie-auth unsafe requests now require CSRF token validation.
- Fixed: Telegram/admin confirmation codes now have endpoint rate limiting in prod, DB-backed cooldown, and lockout after repeated wrong attempts.
- Fixed: password changes now require either the current password or a valid same-user Telegram confirmation code.
- Fixed: public catalog list/detail now hides inactive products; public `is_active` filters are ignored; admin edit uses an authenticated detail endpoint.
- Fixed: product swap no longer leaves images, tags, and attribute values on different product id slots.
- Fixed: DB errors returned to clients are sanitized, and DB wrappers no longer log raw SQLAlchemy tracebacks for wrapped DB failures.
- Fixed: attribute `code` conflicts are checked on update across the effective inherited chain and descendant subtree.
- Fixed: partial product updates preserve tags, attributes, images, and category data when fields are omitted.
- Fixed: taxonomy indexes are declared in the ORM for fresh databases, and the migration script keeps them for existing databases.
- Fixed: SQLite app connections enable `PRAGMA foreign_keys=ON` globally.
- Fixed: malformed route/form ids and bad taxonomy JSON are converted to validation errors instead of raw 500s.
- Fixed: owner permission flags now apply implication rules.
- Fixed: demo-data generation no longer downloads external images inside the request; it uses local placeholder bytes.
- Fixed: Telegram login HTML, chat-id HTML snippets, and Telegram client logging were tightened.
- Still open: production-default hardening, JWT/session revocation, startup default-user mutation, automated tests/quality gates, and larger-scale query/job work.

## Executive Summary

The project has a solid modular direction: bounded contexts are separated, most business operations go through use cases and facades, and the admin UI is permission-aware. The most urgent public/admin boundary, CSRF, Telegram-code, DB-error, SQLite-FK, taxonomy-integrity, and partial-update issues have been addressed. Remaining risk is mostly production hardening, session revocation, bootstrap behavior, and missing automated tests.

Quality verdict:

| Area | Current state | Main reason |
|---|---|---|
| Architecture | Good base | Context/layer separation is clear, but some facade reflection and bootstrap schema patches weaken contracts. |
| Cleanliness | Medium | Code is readable, but validation/error handling is inconsistent and legacy product admin routes still coexist with taxonomy flows. |
| Security | Improved, still needs release hardening | Public/admin boundary and several auth/input leaks are fixed; weak production defaults and JWT/session revocation remain. |
| Performance | OK for small shops | Fresh DB indexes exist now; tree/filter logic still loads full tables and demo generation is still synchronous, but no longer network-bound. |
| Scalability | Medium | Works for SQLite/CPanel, but needs Alembic, stronger DB constraints, background jobs, and test coverage to scale safely. |

## High Priority Findings

### 1. Production can accidentally run in unsafe dev mode

Evidence:

- `src/root/config.py:23` defaults `ROOT_APP_ENV` to `dev`.
- `src/root/entrypoints/api.py:114` to `src/root/entrypoints/api.py:117` creates a dev superadmin password fallback of `superadmin`.
- `src/root/entrypoints/api.py:216` to `src/root/entrypoints/api.py:223` enables broad dev CORS and a very high default limit.
- `src/root/entrypoints/api.py:167` exposes Swagger docs in dev mode.

Impact:

If deployment misses `ROOT_APP_ENV=prod`, the app exposes dev behavior, weak default credentials, broad CORS, relaxed limits, and API docs. For a reusable shop template, this is the biggest operational footgun.

Fix guide:

- Fail startup in non-local deployments when `ROOT_APP_ENV` is not explicitly set.
- In prod, fail startup if `ACCESS_JWT_SECRET`, `SYSTEM_RECOVERY_TOKEN`, `ACCESS_DEFAULT_PASSWORD`, or `ACCESS_SUPERADMIN_PASSWORD` are default/weak.
- Remove the `superadmin/superadmin` fallback from app code or guard it behind an explicit `ROOT_ALLOW_DEV_DEFAULTS=true`.
- Add a startup log line that prints `ROOT_APP_ENV`, but never prints secrets.

### 2. Public catalog can expose inactive products

Status: fixed in the current working tree.

Evidence:

- `src/catalog/app/use_cases/view_catalog_uc.py:21` builds `{"is_active": True, **(filters or {})}`, so request filters can override `is_active`.
- `src/catalog/adapters/driving/api.py:58` to `src/catalog/adapters/driving/api.py:63` accepts arbitrary query args as filters.
- `src/catalog/app/use_cases/view_catalog_uc.py:33` to `src/catalog/app/use_cases/view_catalog_uc.py:37` returns product detail by id without checking `is_active`.
- `src/catalog/templates/catalog/pages/product_form.html:107` also uses the public detail endpoint for admin edit data.

Impact:

A public user can request inactive products via filters or direct detail URLs. This breaks the expected admin/public boundary.

Fix guide:

- Make the repository public query enforce `ProductModel.is_active.is_(True)` outside user-overridable filters.
- Remove `is_active` from public dynamic filters.
- Add `get_public_detail()` that rejects inactive products.
- Add a separate authenticated admin detail endpoint for product editing.
- Add regression tests: inactive product absent from list, random, detail, and category filters.

### 3. Admin cookie writes have no explicit CSRF protection

Status: fixed in the current working tree.

Evidence:

- `src/access/adapters/driving/admin.py:18` to `src/access/adapters/driving/admin.py:25` stores auth in an httpOnly cookie.
- `static/js/api.js:3` to `static/js/api.js:13` sends mutating requests with cookie credentials and no CSRF token/header.
- HTMX forms in admin templates use cookie auth without a CSRF token.

Impact:

`SameSite=Strict` helps, but it is not a complete CSRF strategy for an admin panel, especially when there are CDN scripts, future subdomains, or any XSS bug. The template should have a deliberate CSRF layer.

Fix guide:

- Add a CSRF token cookie plus hidden form/header token.
- Require the token on all unsafe methods: `POST`, `PUT`, `PATCH`, `DELETE`.
- Make `api.js` and HTMX add `X-CSRF-Token`.
- Exempt only public order placement if it has separate anti-spam/rate controls.
- Add tests for missing, wrong, and valid CSRF tokens.

### 4. Telegram login code endpoints are not rate-limited

Status: fixed in the current working tree.

Evidence:

- `src/access/adapters/driving/admin.py:59` defines `/admin/telegram/request-code`.
- `src/access/adapters/driving/admin.py:93` defines `/admin/verify-code`.
- `src/root/entrypoints/api.py:268` to `src/root/entrypoints/api.py:275` limits only JSON login, order placement, and old recovery endpoint.
- `src/access/app/use_cases/reset_password_uc.py:48` generates a 6-digit code, but there is no attempt counter or per-login throttle.

Impact:

Attackers can spam Telegram messages and brute-force verification attempts. The code is hashed and short-lived, but a 6-digit code still needs throttling and lockout.

Fix guide:

- Apply `ROOT_RATE_LIMIT_LOGIN` or a stricter limit to both Telegram endpoints.
- Add per-login and per-IP cooldown for code generation.
- Store failed verification attempts and lock the code after 5 failures.
- Return the same generic error for unknown login, unbound Telegram, expired code, and wrong code.

### 5. Product id swap can corrupt taxonomy relations

Status: fixed in the current working tree. The current implementation swaps scalar product data and all product-owned relations through a temporary product row instead of changing primary keys directly.

Evidence:

- `src/catalog/ports/driven/sql_product_repo.py:312` to `src/catalog/ports/driven/sql_product_repo.py:325` swaps `products.id` and `product_images.product_id`.
- It does not remap `product_tags.product_id`.
- It does not remap `product_attribute_values.product_id`.

Impact:

After a swap, images follow one product while tags and attributes can follow the numeric id slot. This can silently attach the wrong classification data to products.

Fix guide:

- Prefer adding `sort_order` to products instead of swapping primary keys.
- If id swapping must stay, remap every FK table in one transaction.
- Reject swaps when either product is missing.
- Add a regression test with images, tags, and attributes on both products.

### 6. Database errors leak internal details to clients

Status: fixed in the current working tree. Client responses and wrapped DB-error logs are sanitized; duplicate/constraint responses no longer include SQLAlchemy text, SQL fragments, or constraint details.

Evidence:

- `src/shared/helpers/db.py:14` to `src/shared/helpers/db.py:16` wraps raw DB exceptions into client-visible messages.
- `src/shared/adapters/driving/error_handlers.py:56` to `src/shared/adapters/driving/error_handlers.py:61` returns that message with a 500.

Impact:

Unique constraint names, SQL fragments, table names, and other internal details can be shown to users. This is both a security and UX problem.

Fix guide:

- Log only sanitized DB operation/type metadata by default; use local debug tooling for raw SQL traces.
- Return generic messages for unknown DB errors.
- Translate known integrity errors to domain errors: duplicate slug/code as `422` or `409`, missing FK as `422`.
- Add tests that duplicate slugs do not expose SQLAlchemy messages.

## Medium Priority Findings

### 7. JWT contains a stale permission snapshot

Evidence:

- `src/access/app/use_cases/login_uc.py:15` to `src/access/app/use_cases/login_uc.py:20` embeds role and permissions into the JWT.
- `src/shared/adapters/driving/middleware.py:38` to `src/shared/adapters/driving/middleware.py:43` trusts JWT permissions for every request.

Impact:

Changing env permission flags, deactivating a user, or changing a role does not affect already issued tokens until they expire. With remember-me, this can last 30 days.

Fix guide:

- Keep only `sub`, `role`, `iat`, and `session_version` in JWT.
- Resolve current permissions server-side per request or cache them briefly.
- Store `token_version` or `session_version` on the user and increment it on password/role/status changes.
- Keep 30-day sessions only if revocation is implemented.

### 8. Startup reactivates default users

Evidence:

- `src/root/entrypoints/api.py:92` to `src/root/entrypoints/api.py:96` sets `user.role = role` and `user.is_active = True` for existing default users on every startup.

Impact:

If an admin disables the default owner or superadmin in the DB, startup silently reactivates it. This makes operational access control surprising.

Fix guide:

- Only create missing bootstrap users.
- Do not mutate existing role/status automatically.
- If bootstrap repair is needed, put it behind an explicit maintenance command.

### 9. Password change does not require the current password server-side

Status: fixed in the current working tree. Password changes now require the old password or a same-user Telegram confirmation code.

Evidence:

- `src/access/app/use_cases/change_password_uc.py:22` to `src/access/app/use_cases/change_password_uc.py:25` skips old password verification when `old_password` is omitted.
- `src/access/ports/driving/schemas.py:25` to `src/access/ports/driving/schemas.py:28` makes `old_password` optional.
- `src/system/templates/system/pages/settings.html:51` to `src/system/templates/system/pages/settings.html:71` does not ask for the old password.

Impact:

A stolen authenticated session can immediately rotate the password. There is also no server-side password length/strength validation.

Fix guide:

- Require `old_password` for normal password changes.
- Allow password reset without old password only through a separate, audited recovery flow.
- Enforce server-side length and complexity rules.
- Clear active sessions after password changes.

### 10. Attribute code conflicts can be introduced on update

Status: fixed in the current working tree.

Evidence:

- `src/catalog/app/use_cases/manage_taxonomy_uc.py:162` to `src/catalog/app/use_cases/manage_taxonomy_uc.py:164` checks duplicate effective codes only on create.
- `src/catalog/app/use_cases/manage_taxonomy_uc.py:178` to `src/catalog/app/use_cases/manage_taxonomy_uc.py:184` updates attributes without checking effective inherited conflicts.

Impact:

A category can end up with duplicate effective attribute codes across inheritance. Product form rendering and value persistence become ambiguous.

Fix guide:

- On update, load the attribute, its category, and effective chain.
- Reject a new code that conflicts with any other effective attribute in the chain.
- Add tests for parent/child duplicate update attempts.

### 11. Product partial updates can clear taxonomy data

Status: fixed in the current working tree.

Evidence:

- `src/catalog/adapters/driving/api.py:35` to `src/catalog/adapters/driving/api.py:55` always returns `tag_ids=[]` and `attribute_values={}` when those form fields are absent.
- `src/catalog/adapters/driving/api.py:262` always merges that payload into update kwargs.
- `src/catalog/app/use_cases/manage_catalog_uc.py:113` to `src/catalog/app/use_cases/manage_catalog_uc.py:116` treats non-`None` empty lists/dicts as explicit replacement.

Impact:

A partial product update that only changes title, price, description, or images can unintentionally erase tags and attributes.

Fix guide:

- For update, include taxonomy fields only if the request actually contains them.
- Keep full replace behavior for the product form, but make API semantics explicit.
- Add tests for title-only update preserving tags and attributes.

### 12. Fresh databases do not get taxonomy indexes

Status: fixed in the current working tree.

Evidence:

- `data/migrate_taxonomy.py:42` to `data/migrate_taxonomy.py:69` defines important indexes.
- `src/catalog/adapters/driven/db/models.py` defines unique constraints but no equivalent `Index(...)` declarations.
- `README.md:121` says all tables are auto-created on startup.

Impact:

Existing databases that run the migration get better indexes, but fresh databases created with `create_all()` do not. Search/filter/category operations will degrade as products/categories grow.

Fix guide:

- Move index definitions into SQLAlchemy models.
- Keep migration scripts only for changing existing databases.
- Add a verification command that checks required indexes exist.

### 13. SQLite foreign keys are not enabled globally

Status: fixed in the current working tree.

Evidence:

- `data/migrate_taxonomy.py:228` to `data/migrate_taxonomy.py:230` enables `PRAGMA foreign_keys = ON` only inside migration.
- `src/shared/adapters/driven/db/connection.py:7` to `src/shared/adapters/driven/db/connection.py:10` creates normal app engines without a SQLite foreign-key event listener.

Impact:

SQLite does not enforce FK constraints by default. App behavior can differ from declared `ondelete` rules, and orphan rows may survive some operations.

Fix guide:

- Add a SQLAlchemy `connect` event that runs `PRAGMA foreign_keys=ON` for SQLite engines.
- Add tests for deleting categories/tags/products with dependent rows.
- Avoid relying only on ORM cascade for association tables.

### 14. Some request parsing errors become 500

Status: fixed in the current working tree for catalog taxonomy/product routes covered by the review.

Evidence:

- `src/catalog/adapters/driving/api.py:35` to `src/catalog/adapters/driving/api.py:47` uses raw `int()` and `json.loads()`.
- `src/catalog/adapters/driving/admin.py:41` to `src/catalog/adapters/driving/admin.py:46` uses raw `int(category_id)`.

Impact:

Malformed form data can produce generic internal errors instead of clear `400` validation errors.

Fix guide:

- Use Pydantic or shared parsing helpers for all form inputs.
- Convert invalid category/tag ids and bad JSON to `DrivingPortError`.
- Add tests for invalid form fields.

### 15. Permission flags do not enforce implication rules

Status: fixed in the current working tree.

Evidence:

- `src/access/permissions.py:29` to `src/access/permissions.py:42` maps owner flags independently.

Impact:

Env can create inconsistent users, for example `edit_products=true` but `view_products=false`, or `edit_taxonomy=true` but `view_category_tree=false`. The UI/API then fails in secondary calls.

Fix guide:

- Enforce implication rules in `resolve_permissions()`.
- Suggested rules: `edit_products` implies `view_products` and `view_category_tree`; `edit_taxonomy` implies `view_category_tree`; `manage_orders` implies `view_orders`; `create_demo_data` implies taxonomy/product edit permissions.
- Add tests for permission resolution.

### 16. Demo-data generation blocks inside a request

Status: partially fixed in the current working tree. The request is still synchronous, but it no longer performs external image downloads and therefore cannot hang on `picsum.photos` or outbound network.

Evidence:

- `src/catalog/app/use_cases/create_demo_data_uc.py:111` to `src/catalog/app/use_cases/create_demo_data_uc.py:117` loops over leaf categories and creates products synchronously.
- `src/catalog/app/use_cases/create_demo_data_uc.py:230` to `src/catalog/app/use_cases/create_demo_data_uc.py:244` downloads images synchronously from `picsum.photos`.

Impact:

On slow network or many leaf categories, the admin request can time out. The operation also depends on external network availability.

Fix guide:

- Make demo generation a background job or split it into small chunks.
- Add `products_per_leaf` and image download flags.
- Use local placeholder images as a fallback.
- Persist a job result so the UI can poll progress.

### 17. Telegram and HTML escaping should be tightened

Status: fixed in the current working tree for the reviewed Telegram login/chat-id rendering and Telegram client logging paths.

Evidence:

- `src/system/adapters/driving/admin.py:111` to `src/system/adapters/driving/admin.py:113` injects `chat_id` into HTML without escaping.
- `src/system/adapters/driving/admin.py:172` to `src/system/adapters/driving/admin.py:175` does the same for current-user chat id.
- `src/shared/adapters/driven/telegram_client.py:27` to `src/shared/adapters/driven/telegram_client.py:29` logs Telegram HTTP exceptions; httpx exception text may include a URL containing the bot token.

Impact:

The current chat id is usually numeric, but templates should not depend on that. Logging Telegram URLs can leak bot tokens into logs.

Fix guide:

- Escape dynamic HTML with `markupsafe.escape()` or render a template partial.
- Validate chat id format.
- Log Telegram status/error category without the full bot URL.

## Low Priority Findings

### 18. `ORDER BY random()` will not scale

Evidence:

- `src/catalog/ports/driven/sql_product_repo.py:113` to `src/catalog/ports/driven/sql_product_repo.py:122` uses `func.random()`.

Impact:

Fine for small catalogs, expensive for large catalogs.

Fix guide:

- For larger catalogs, use precomputed random keys, id-window sampling, or cached featured products.

### 19. Facade reflection hides contract drift

Evidence:

- `src/catalog/ports/driving/facade.py:50` to `src/catalog/ports/driving/facade.py:61` inspects method signatures and filters kwargs dynamically.

Impact:

This makes refactors less explicit and can hide accidental argument mismatches.

Fix guide:

- Prefer explicit facade methods that match use-case signatures.
- Let tests fail when contracts drift.

### 20. The project has no automated tests or quality gates

Evidence:

- No `tests/` directory was found.
- `pyproject.toml` defines runtime dependencies but no pytest/ruff/mypy tooling.

Impact:

The template is growing in security-sensitive behavior without regression coverage.

Fix guide:

- Add pytest integration tests around public/admin boundaries, permissions, taxonomy mutations, product updates, and Telegram login.
- Add `ruff` and a minimal type-checking pass.
- Run tests in CI before releases.

## Recommended Fix Order

1. Lock production defaults and secret validation.
2. Harden JWT/session revocation so role, active status, and password changes invalidate existing sessions.
3. Stop startup from mutating/reactivating existing default users.
4. Add automated regression tests around the fixed security/data-integrity paths.
5. Convert known duplicate/constraint DB failures from generic `500` to explicit `409` or `422` domain errors.
6. Replace remaining primary-key swap UI semantics with an explicit `sort_order` column when product ordering becomes a real storefront feature.
7. Move long-running demo/catalog maintenance work to a background job or chunked progress API if datasets grow.
8. Add CI quality gates: pytest, ruff, and a lightweight type-checking pass.
