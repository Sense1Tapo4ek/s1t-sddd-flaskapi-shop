# Infra: HTMX

For contributors writing admin partials. Vendor docs at
<https://htmx.org/> are authoritative; this page lists project usage
only.

## Usage in the template

HTMX is loaded once from `static/shared/_base.html`. Every admin page
extends that base and gets HTMX globally without per-page script tags.

Admin blueprints declare `enable_openapi=False` so HTMX endpoints
never pollute Swagger.

## Conventions

- **Partial routes return fragments**, not full pages. They render
  templates from `<context>/templates/<context>/partials/`.
- **Full-page routes return pages** that extend `shared/_base.html`.
- **CSRF on every mutation.** The admin UI bootstrap reads the
  `csrf_token` cookie and sets it as the `X-CSRF-Token` request header
  on every HTMX/`fetch` call automatically. Routes do not need to opt
  in — see [../subsystems/auth-permissions.md](../subsystems/auth-permissions.md).
- **HX-* response headers** are set through helpers in
  `src/shared/adapters/driving/htmx.py`. Use `hx_redirect`,
  `hx_trigger`, `hx_refresh` instead of hand-crafting headers.
- **Error toasts, not raw JSON.** Non-2xx responses should render a
  toast or a safe error fragment. Replacing the panel with raw
  response text is forbidden.

## Common headers

| Header | When to set |
|---|---|
| `HX-Redirect` | Navigate the browser away from a partial response (e.g., logout) |
| `HX-Trigger` | Fire a client event after the swap (toast, refresh another panel) |
| `HX-Refresh` | Force a full page reload from a partial response |
| `HX-Reswap` / `HX-Retarget` | Override the original swap target/strategy |

## Pointers

- Helpers: `src/shared/adapters/driving/htmx.py`
- Base layout: `static/shared/_base.html`
- Admin UI subsystem: [../subsystems/admin-ui.md](../subsystems/admin-ui.md)
- SmartTable (driven by HTMX + JSON): [../subsystems/smart-filters.md](../subsystems/smart-filters.md)
