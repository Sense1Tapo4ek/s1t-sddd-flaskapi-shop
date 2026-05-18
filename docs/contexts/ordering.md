# Context: ordering

For contributors working inside `src/ordering/`. Guest contact
inquiries and authenticated customer orders, admin management,
status transitions, and Telegram notifications.

## Mental model

Two aggregates in one context, sharing notification infrastructure.

```
Inquiry (guest)                   Order (customer)
───────────────                   ────────────────
name / phone? / email? / message  customer_user_id (from JWT)
                                  items[] (price snapshot)
                                  delivery: pickup | courier+address
                                  total (computed)

new → in_progress → closed        new → confirmed → completed / canceled
          ↓ (any state)                         ↓ (any terminal)
       archived                             archived
```

- `Inquiry` originates from anonymous `POST /inquiries`.
- `Order` originates from customer-authenticated `POST /orders`.
  `customer_user_id` is sourced from JWT `sub`, never from the body.
- Status transitions validated in domain; routes pass the target
  string, use case raises 422 on illegal moves.
- Notifications are best-effort. Telegram failures are logged and
  swallowed; the aggregate is still saved and 201 returned.

## Aggregates

| | Inquiry | Order |
|---|---|---|
| Source file | `domain/inquiry_agg.py` | `domain/order_agg.py` |
| Status enum | `InquiryStatus` | `OrderStatus` |
| Key fields | name, phone?, contact_email?, message | items, total, delivery, comment |
| Auth | anonymous | `@customer_required` |
| Table | `inquiries` | `orders` + `order_items` |

## Public surface

Two driving facades:

- `InquiriesFacade` — `ports/driving/inquiries_facade.py`
- `OrdersFacade` — `ports/driving/orders_facade.py`

Wire-level endpoint map:

| Endpoint | Auth | Notes |
|---|---|---|
| `POST /inquiries` | public | rate-limited `5/min` (IP) |
| `POST /orders` | `customer_required` | items + delivery in body |
| `GET /admin/requests/` | `view_orders` | unified two-tab UI page |
| `GET /admin/requests/badge` | `view_orders` | combined new-count |
| `GET /admin/inquiries/search` | `view_orders` | paginated JSON |
| `GET /admin/inquiries/search/schema` | `view_orders` | filter schema |
| `PATCH /admin/inquiries/<id>/status` | `manage_orders` | |
| `POST /admin/inquiries/<id>/archive` | `manage_orders` | |
| `POST /admin/inquiries/bulk/status` | `manage_orders` | |
| `POST /admin/inquiries/bulk/archive` | `manage_orders` | |
| `GET /admin/orders/search` | `view_orders` | paginated JSON |
| `GET /admin/orders/search/schema` | `view_orders` | filter schema |
| `PATCH /admin/orders/<id>/status` | `manage_orders` | |
| `POST /admin/orders/<id>/archive` | `manage_orders` | |
| `POST /admin/orders/bulk/status` | `manage_orders` | |
| `POST /admin/orders/bulk/archive` | `manage_orders` | |

`GET /admin/inquiries/` and `GET /admin/orders/` redirect 302 → `/admin/requests/`.

Wire-level shapes: [../contract/public.md](../contract/public.md)
and [../contract/admin.md](../contract/admin.md).

## Cross-context calls

| Need | ACL file |
|---|---|
| Telegram bot token + admin chat ids | `ports/driven/system_notification_acl.py` |
| Product title+price snapshot at order time | `ports/driven/catalog_product_lookup_acl.py` |

Admin notification recipients are resolved via `system_notification_acl`
→ `SystemFacade` → active `owner`/`superadmin` admins with a bound
`telegram_chat_id`.

Product snapshot happens inside `PlaceOrderUseCase`: for each item,
the ACL calls `catalog` to fetch current title and price, which are
then frozen on `OrderItem`. The order total is computed from snapshots,
not live prices.

## Invariants & gotchas

- `courier` delivery requires a non-empty `address`. The VO
  `DeliveryInfo.__post_init__` raises `CourierAddressRequiredError`.
- `items` list must not be empty — `EmptyOrderError` from domain.
- `customer_user_id` comes from `g.customer_user_id` (set by
  `@customer_required`), NEVER from the request body.
- Permissions: `view_orders`/`manage_orders` currently guard BOTH
  inquiries and orders admin endpoints (D2 deferred — see
  [../adr/0010-inquiries-vs-orders-split.md](../adr/0010-inquiries-vs-orders-split.md)).
- Orders aggregate is **feature-gated** by `ORDERING_ORDERS_ENABLED`
  (default `true`). When `false`, `/orders*` and `/admin/orders/*`
  blueprints are not registered, CORS rule for `/orders*` is skipped,
  and the admin requests page collapses to inquiries-only. Inquiries
  remain available regardless. See
  [../subsystems/feature-flags.md](../subsystems/feature-flags.md).

## Pointers

- Domain: `src/ordering/domain/`
- App use cases: `src/ordering/app/use_cases/`
- Driven ports: `src/ordering/ports/driven/`
- Admin HTMX: `src/ordering/adapters/driving/admin.py`
- Public API: `src/ordering/adapters/driving/api.py`
- Admin UI (two-tab): `static/ordering/requests.html`
- CardsFeed component: `static/js/cards-feed.js`
- Notifications subsystem: [../subsystems/notifications.md](../subsystems/notifications.md)
- Filters subsystem: [../subsystems/smart-filters.md](../subsystems/smart-filters.md)
