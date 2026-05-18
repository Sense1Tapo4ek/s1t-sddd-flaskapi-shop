# Subsystem: admin UI (HTMX + Jinja)

For contributors building admin pages or panels. The admin UI is
server-rendered Jinja with HTMX partials — there is no SPA framework.

## Mental model

```
Browser ── full-page GET ───> Flask renders Jinja template
        ── HTMX request ────> Flask renders a partial (no layout)
        <── HX-* headers ───  Server tells browser to swap/push/trigger
```

Templates live under `src/<context>/templates/<context>/` with two
conventions:

- `pages/*.html` — full-page renders, extend `static/shared/_base.html`.
- `partials/*.html` — fragments returned to HTMX requests.

Admin routes register their blueprint with `enable_openapi=False` so
HTMX pages never pollute Swagger.

## Browser-served assets

Project layout (see `static/`):

```
static/
├── shared/                  Layout + common CSS used by ≥2 contexts
│   ├── _base.html
│   └── base.css
├── catalog/                 Catalog admin assets
├── ordering/
├── access/
└── system/
```

Templates reference paths relative to that root: `"catalog/pages/list.html"`,
`"shared/_base.html"`. File names inside a context folder do **not**
carry the context prefix — the folder already encodes it.

## Rules

- **Server-side permissions are mandatory.** Hiding a button via Jinja
  is UX, not authorization. The route handler must declare
  `permission_required(...)` etc.
- **CSRF on every mutation.** HTMX and `fetch()` requests using cookie
  auth send `X-CSRF-Token` automatically — see
  [auth-permissions.md](auth-permissions.md). Bearer-token clients
  are exempt.
- **Server-side validation is mandatory.** Even when the form has
  client-side validation. The use case decides; the form helps.
- **No raw JSON in error panels.** Non-2xx responses should render a
  toast or a safe error fragment, never replace the panel with the raw
  response body.
- **`textContent` for user content in JS.** Rendering user-supplied
  strings via `innerHTML` is an XSS hole — prefer Jinja or
  `element.textContent = value`.
- **Idempotent HTMX mutations or explicit confirmations.** Destructive
  actions go through a confirmation dialog (delete product, drop
  category).

## HTMX response helpers

`src/shared/adapters/driving/htmx.py` exposes helpers to set HX-*
headers consistently:

| Helper | Purpose |
|---|---|
| `hx_redirect(url)` | Set `HX-Redirect` to navigate the browser away from a partial response |
| `hx_trigger(event, payload=None)` | Set `HX-Trigger` to fire a client event after the swap |
| `hx_refresh()` | Reload the page from a partial response |

Use these instead of crafting headers by hand — the helpers normalize
JSON payloads and casing.

## Common pages

| Page | Route | Template |
|---|---|---|
| Login | `/admin/login` | `access/templates/access/pages/login.html` |
| Products list | `/admin/products/` | `catalog/templates/catalog/pages/products.html` |
| Product edit | `/admin/products/<id>` | `catalog/templates/catalog/pages/product_form.html` |
| Categories | `/admin/categories/` | `catalog/templates/catalog/pages/categories.html` |
| Tags | `/admin/tags/` | `catalog/templates/catalog/pages/tags.html` |
| Requests (inquiries + orders, two tabs) | `/admin/requests/` | `ordering/templates/ordering/pages/requests.html` |
| Settings | `/admin/settings/` | `system/templates/system/pages/settings.html` |
| Account | `/admin/account/` | `access/templates/access/pages/account.html` |

## Pointers

- HTMX helpers: `src/shared/adapters/driving/htmx.py`
- SmartTable: [smart-filters.md](smart-filters.md)
- ADR for HTMX choice: [../adr/0003-htmx-admin-vs-spa.md](../adr/0003-htmx-admin-vs-spa.md)
- HTMX docs: see [../infra/htmx.md](../infra/htmx.md)
