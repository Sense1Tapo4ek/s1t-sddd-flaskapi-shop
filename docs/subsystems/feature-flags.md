# Feature flags

**Audience:** contributor extending the public surface or admin UI.

Single source of truth for the env-driven feature toggles. Flags are
read once at startup (`OrderingConfig`, `SystemConfig`), so flipping a
value requires a process restart. Flags are NOT stored in the database
and NOT editable from the admin UI — that is intentional: they are a
deploy-time switch, not a tenant setting.

## Mental model

```
┌───────────────────────┐
│ .env / OS environment │
└──────────┬────────────┘
           │ parsed at startup by pydantic-settings
           ▼
┌─────────────────────────────────────────────┐
│ OrderingConfig.orders_enabled               │
│ SystemConfig.socials_<channel>_enabled      │
└──────────┬──────────────────────────────────┘
           │ injected into:
           ├─► root/entrypoints/api.py        — blueprint reg, CORS
           ├─► system facade                  — InfoOut/SettingsOut
           └─► runtime_template_settings()    — Jinja `feature_flags`
```

A flag is consumed in three places: HTTP surface (blueprints + CORS),
wire payload (Pydantic `InfoOut` / `SettingsOut`), and admin templates
(nav, tabs, form fields).

## Available flags

| Env var | Default | Effect when `False` |
|---|---|---|
| `ORDERING_ORDERS_ENABLED` | `True` | `/orders*` public + admin blueprints not registered. CORS rule for `/orders*` skipped. Admin `requests` page hides Orders tab and falls back to inquiries-only view. `orders-cards-wiring.js` is not loaded. |
| `SYSTEM_SOCIALS_INSTAGRAM_ENABLED` | `True` | `socials.instagram` is `null` in `/system/info` and `/system/settings`. Admin store-form hides the Instagram input. |
| `SYSTEM_SOCIALS_TELEGRAM_ENABLED` | `True` | Same as above for `socials.telegram` (column `telegram_public_url`). |
| `SYSTEM_SOCIALS_WHATSAPP_ENABLED` | `True` | Same as above for `socials.whatsapp` (column `whatsapp_url`). |
| `SYSTEM_SOCIALS_VIBER_ENABLED` | `True` | Same as above for `socials.viber` (column `viber_url`). |

Underlying DB columns always exist (`migrations/0002_socials_extra_columns.sql`).
Flipping a flag back to `True` re-exposes the previously stored value
without any data migration.

## Where each flag is read

### `ORDERING_ORDERS_ENABLED`

- `src/ordering/config.py` — declared.
- `src/root/entrypoints/api.py` — gates `register_blueprint(orders_bp)`,
  `register_blueprint(orders_admin_bp)`, prod CORS rule `/orders*`.
- `static/templates/admin/base.html` — gates the Orders sidebar entry
  + the `/admin/orders/badge` polling block.

### `SYSTEM_SOCIALS_<CHANNEL>_ENABLED`

- `src/system/config.py` — declared (four flags).
- `src/system/ports/driving/facade.py:_socials_flags()` builds a
  `SocialsFlags` value object from the config; passes it into
  `InfoOut.from_domain` / `SettingsOut.from_domain`.
- `src/system/ports/driving/schemas.py:_build_socials()` emits the
  filtered `SocialsOut` (disabled channels become `None`).
- `src/system/ports/driving/runtime_template.py` — flags surfaced on
  Jinja context as `feature_flags`.
- `src/system/templates/system/partials/store_form.html` — conditional
  rendering of each social input.

## Wire-level behaviour

Disabled socials serialise as `null`:

```jsonc
GET /system/info
{
  "socials": {
    "instagram": "https://instagram.com/shop",
    "telegram":  null,        // SYSTEM_SOCIALS_TELEGRAM_ENABLED=false
    "whatsapp":  "https://wa.me/...",
    "viber":     null
  }
}
```

Clients SHOULD treat `null` and missing equivalently — render only
truthy values.

Disabled `/orders*` returns `404` for any public or admin path under
that prefix, because the route is not registered at all (not gated by
a runtime check). The OpenAPI spec served at `/api/docs` reflects the
same — orders endpoints are absent when the flag is off.

## How to flip a flag

```bash
# Disable orders aggregate entirely
export ORDERING_ORDERS_ENABLED=false

# Hide Telegram + Viber on the public page
export SYSTEM_SOCIALS_TELEGRAM_ENABLED=false
export SYSTEM_SOCIALS_VIBER_ENABLED=false

# Restart the process — flags are read once at startup
```

Both `false` / `0` / `no` / `off` parse as `False` (pydantic-settings
default).

## Adding a new feature flag

Flags are read **once at process startup** via pydantic-settings. Flipping
a value requires a process restart. Never store flags in the DB or expose
them through an admin endpoint.

Use `ORDERING_ORDERS_ENABLED` as the canonical reference implementation.

### Checklist

**1. Context config** — `src/<context>/config.py`

Add a field to the relevant `*Config` class:

```python
orders_enabled: bool = Field(True, description="Enable the orders aggregate.")
```

Field name matches the env var suffix (env prefix is set by the class's
`model_config`). Default `True` so existing deployments are unaffected.

**2. App factory wiring** — `src/root/entrypoints/api.py`

Resolve the config from the container, then gate blueprint registration and
CORS rules:

```python
if ordering_config.orders_enabled:
    app.register_blueprint(orders_bp)
    app.register_blueprint(orders_admin_bp)
    cors_paths.append("/orders/*")
```

**3. Facade / schema / runtime template** (if the flag changes payload shape)

- `src/<context>/ports/driving/facade.py` — pass the flag into the response
  builder (`_socials_flags()` is the pattern for the system context).
- `src/<context>/ports/driving/schemas.py` — emit `None` for disabled fields
  instead of raising or filtering at the route level.
- `src/<context>/ports/driving/runtime_template.py` — surface the flag on the
  Jinja context (`feature_flags`) so templates can branch without hitting the
  facade again.

Skip this step if the flag only gates blueprint registration with no partial
payload (i.e. the feature is fully absent when disabled, not partially
nulled).

**4. Templates** — `static/templates/`

Hide UI for the disabled feature. Mirror the context tree:
`static/templates/<context>/` for page templates,
`static/templates/admin/base.html` for nav entries.

UI hiding is **not authorization** — gate routes/blueprints first (step 2).
Templates follow; they are presentation only.

**5. Docs** — update all four homes in the same PR:

- This file (`docs/subsystems/feature-flags.md`) — add a row to
  [Available flags](#available-flags) and a subsection under
  [Where each flag is read](#where-each-flag-is-read).
- `../../CLAUDE.md` (repo root) — add a row to the feature-flags table and
  update "Affected code paths".
- `../../README.md` — add a row to the config/env-var table.
- `../architecture.md` — add the flag to the release checklist if it gates
  a major capability.

**Apply locally:** set the env var in `.env`, then restart the app:

```bash
export <ENV_VAR>=false
PYTHONPATH=src FLASK_DEBUG=1 uv run src/root/entrypoints/api.py
```

## Related

- [docs/contexts/ordering.md](../contexts/ordering.md) — orders/inquiries split
- [docs/contexts/system.md](../contexts/system.md) — settings aggregate
- [docs/contract/public.md](../contract/public.md) — wire contract for `/system/info`, `/inquiries`, `/orders`
- [docs/contract/admin.md](../contract/admin.md) — wire contract for `/system/settings`
- [docs/subsystems/admin-ui.md](./admin-ui.md) — admin nav / requests page layout
- [migrations/0002_socials_extra_columns.sql](../../migrations/0002_socials_extra_columns.sql) — adds the columns the flags expose
