# Bulk actions

**Audience:** contributor adding a bulk-action surface (SmartTable page).
**Spec:** `docs/superpowers/specs/2026-05-15-bulk-actions-design.md`.

## 1. Mental model

Selection lives in `SmartTable`. The `BulkActionBar` reacts to changes
and runs handlers. Three selection states:

```
empty            bar hidden
ids              explicit Set<id> (page select, manual ticks, range)
all_by_filter    "everything matching current filter snapshot"
```

`all_by_filter` survives pagination but resets on filter/sort/limit
change (with a toast) and on HTMX rebuild (with a one-shot hint).

## 2. Frontend wiring

### 2.1 Enable selection on a SmartTable

```js
const table = new SmartTable({
  instanceName: "productsTable",
  endpoint: "/catalog/admin/search",
  schemaEndpoint: "/catalog/admin/search/schema",
  containerId: "productsTable",
  columns,
  selectable: true,           // ← turns on the checkbox column + master menu
  rowIdKey: "id",             // optional, defaults to "id"
  getRowName: it => it.title, // optional; used in the failures-detail table
});
```

`SmartTable` exposes:

| Method | Purpose |
|---|---|
| `getSelection()` | `{ mode, ids?, filter?, total }` snapshot |
| `clearSelection()` | switch to `empty` and fire `onSelectionChange` |
| `selectPage()` | mark every id on the current page |
| `selectAllByFilter()` | switch to filter-mode |
| `markFailedRows(ids)` | flash `is-flashing-failed` for ~1.5 s |
| `buildFailureRows(failed)` | enrich `{id, reason}` with row names |
| `destroy()` | remove listeners; idempotent |

`selectable: false` (default) keeps existing pages bit-for-bit identical.

### 2.2 Mount a BulkActionBar

```js
new BulkActionBar({
  table,
  actions: [
    { id: "activate",   label: "Активировать",   icon: "check-circle",
      confirm: "soft",
      handler: payload => api.post("/admin/products/bulk/activate",
                                   { ...payload, active: true }) },
    { id: "deactivate", label: "Деактивировать", icon: "circle-off",
      confirm: "soft",
      handler: payload => api.post("/admin/products/bulk/activate",
                                   { ...payload, active: false }) },
    { id: "delete",     label: "Удалить",        icon: "trash-2",
      variant: "danger", confirm: "type-to-confirm",
      typeWord: "удалить",
      handler: payload => api.post("/admin/products/bulk/delete", payload) },
  ],
});
```

The bar:
- Subscribes to `table.onSelectionChange` (composable — your own callback
  is preserved).
- Renders a floating capsule (`position: fixed; bottom: 24px;`).
- Slides up with overshoot when selection becomes non-empty.
- Adds `padding-bottom: 72px` on `<body>` so the bar does not cover
  the last rows.

### 2.3 Action contract

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | stable handle (used by DOM `data-action`) |
| `label` | yes | Russian, ≤16 chars |
| `icon` | yes | Lucide symbol name (`check-circle`, `tag`, …) |
| `variant` | no | `"danger"` separates the button to the right of the divider |
| `confirm` | no | `"soft"` · `"modal"` · `"type-to-confirm"` |
| `typeWord` | only for `type-to-confirm` | overrides default `удалить` |
| `confirmTitle` / `confirmText(sel)` | no | overrides defaults |
| `handler(payload, sel)` | yes | receives `{ target: BulkTarget }` envelope |

Handler MUST resolve to `{ total, ok, failed[] }` (see backend
contract). Returning anything else still works — the bar treats the
result as a no-failures success.

## 3. UI strings & icons

- All Russian strings live in `static/js/bulk-i18n.js`. Use `bulkT(key, {…})`.
- All reason codes are mapped to RU labels by `bulkReason(code)`. Add new
  codes to `REASONS` map in the same file.
- Icons come from `static/img/lucide.svg` — referenced via
  `<use href="/static/img/lucide.svg#icon-NAME"/>`. Currently shipped:
  `check-circle`, `circle-off`, `folder`, `tag`, `trash-2`,
  `arrow-right-circle`, `alert-triangle`, `x`, `chevron-down`.

## 4. Backend contract (Phase 2)

`POST /admin/<context>/bulk/<action>` (cookie-auth → CSRF mandatory).

Request:

```jsonc
// ids-mode
{ "target": { "kind": "ids", "ids": ["uuid", ...] }, /* extra fields */ }

// filter-mode (server replays the snapshot)
{ "target": { "kind": "filter", "filter": { ... } }, /* extra fields */ }
```

Response — ALWAYS 200 on a syntactically valid request:

```json
{ "total": 234, "ok": 230, "failed": [
  { "id": "uuid", "reason": "product_in_use_by_active_order" }
] }
```

| 422 code | Meaning |
|---|---|
| `bulk_target_empty` | `ids` was an empty list |
| `bulk_target_too_large` | more than 1000 ids |

Partial success is never a 4xx. Infrastructure failures stay 5xx.

Schemas/runner live in `src/shared/ports/driving/bulk_schemas.py` and
`src/shared/app/bulk_runner.py`. See
`tests/shared/flow/test_bulk_runner.py` for behaviour.

## 5. Pitfalls

- **HTMX re-renders that destroy the table** must call
  `table.destroy()` before recreating, otherwise listeners leak. The
  built-in `resetInteractionState` clears selection and emits the
  one-shot hint toast.
- **Modals over the bar.** Confirm modals raise `aria-hidden="true"`
  on the bar via `_setAriaHiddenWhileModal()`. The overlay lives at
  `z-index: 50+`, the bar at `40`.
- **`beforeunload` while a handler is in flight** asks the user to
  confirm tab close. It's lifted as soon as the handler resolves or
  rejects.
- **Failures detail.** The modal shows `name | id | reason`. `name` is
  pulled from the last page payload via `getRowName(item)`; if the
  failed row is not on the current page, the cell shows `—`.

## 6. Where to look

| Concern | File |
|---|---|
| Selection state machine | `static/js/smart-table.js` |
| Bar / soft / modal / type-to-confirm | `static/js/bulk-action-bar.js` |
| RU strings & reason codes | `static/js/bulk-i18n.js` |
| Capsule + master dropdown CSS | `static/css/components/bulk-bar.css` |
| `tr.is-selected`, checkbox column, flash | `static/css/components/smart-table.css` |
| Warning toast | `static/css/components/toasts.css` |
| Icons | `static/img/lucide.svg` |
| Backend schemas | `src/shared/ports/driving/bulk_schemas.py` |
| Backend runner | `src/shared/app/bulk_runner.py` |
