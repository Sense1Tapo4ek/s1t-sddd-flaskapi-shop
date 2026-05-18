# 0010 — Split Inquiry and Order into two aggregates
Status: accepted
Date: 2026-05-17

## Context

The original `Order` aggregate stored `name / phone / comment / status` —
a guest contact form, not a real product order. The user requested a
clear split: "обращения" (any guest, no auth) vs "заказы" (customer
with cart + delivery). Both live in the `ordering` bounded context.

## Decision

Rename the original aggregate to `Inquiry` and build a new `Order`
alongside it. Each has its own status enum, repo, facade, and admin
route group. A unified `/admin/requests` page surfaces both via two
tabs with a shared `CardsFeed` JS component.

## Consequences

- + Clean semantics: lifecycle, validation, and notifications are
  independent per type.
- + Independent Telegram notification format per type.
- − Rename touched every layer (domain → app → ports → adapters → DB),
  mitigated by atomic per-wave commits.
- − Two facades (`InquiriesFacade`, `OrdersFacade`) to maintain.
- − Permissions deferred (D2): `view_orders`/`manage_orders` currently
  guard both; `view_inquiries`/`manage_inquiries` are not yet added.

## Alternatives considered

- Single discriminated `Request` aggregate — rejected (different
  invariants per type force conditionals throughout the domain).
- Extend old `Order` with items + customer + delivery — rejected
  (naming stays misleading; semantics keep drifting indefinitely).
