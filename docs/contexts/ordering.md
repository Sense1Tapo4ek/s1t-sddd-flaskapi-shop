# Context: ordering

For contributors working inside `src/ordering/`. Customer order
placement, admin order listing, status transitions, and order
notifications via Telegram.

## Mental model

An `Order` is created from public input (name, phone, comment).
Status transitions through a fixed lifecycle. Notification of new
orders is a side effect dispatched to active `owner` and `superadmin`
admins who have a bound `telegram_chat_id`. Failures to notify never
fail order placement.

```
new ─> processing ─> done
   \─> canceled       \─> canceled
```

`OrderStatus` is the source of truth (`src/ordering/domain/order_status.py`).

## Public surface

Driving facade: `OrderingFacade` in `ports/driving/facade.py`.

| Wire endpoint | Auth | Use case |
|---|---|---|
| `POST /orders` | public | Place order; fire-and-forget Telegram notify |
| `GET /orders` | `view_orders` | Admin list with SmartTable filters |
| `GET /orders/search/schema` | `view_orders` | SmartTable filter schema |
| `PATCH /orders/{id}/status` | `manage_orders` | Status transition |

Wire-level shapes live in [../contract/public.md](../contract/public.md)
and [../contract/admin.md](../contract/admin.md).

## Invariants & gotchas

- **Status transitions are validated in the domain.** Routes must not
  let arbitrary status strings through; the use case returns a 422 if
  the target is invalid or unreachable from the current state.
- **Notification target is per-user, not global.** New-order
  notifications go to every active `owner`/`superadmin` whose
  `admins.telegram_chat_id` is set. The legacy global
  `settings.telegram_chat_id` is not used for order notifications.
- **Notification is best-effort.** Telegram errors are logged and
  swallowed inside the system-notification ACL; the order is still
  saved and returned 201.
- **Cross-context calls go through ACL.** Talking to `system` for the
  Telegram bot token and admin chat IDs happens via
  `ports/driven/system_notification_acl.py`. Do not import `system`
  internals from `ordering` use cases.

## Pointers

- Aggregate + status enum: `src/ordering/domain/`
- ACL to system: `src/ordering/ports/driven/system_notification_acl.py`
- Admin HTMX: `src/ordering/adapters/driving/admin.py`
- Filters subsystem: [../subsystems/smart-filters.md](../subsystems/smart-filters.md)
- Notifications subsystem: [../subsystems/notifications.md](../subsystems/notifications.md)
