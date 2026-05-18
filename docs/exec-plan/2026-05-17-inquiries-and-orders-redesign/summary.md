# Plan execution: 2026-05-17-inquiries-and-orders-redesign

Mode: AUTO
Started: 2026-05-17

## Progress

| Stage | Status | Commit |
|---|---|---|
| 0.5 | done    | 5ccd12a — extended shared customer_required (deviation: extend in place vs new file) |
| 1   | done    | 700de94 — combined 1+2+3 (deviation: atomic rename) |
| 2   | done    | 700de94 — combined with 1 |
| 3   | done    | 700de94 — combined with 1 |
| 4   | done    | 02660f7 — combined 4+5+6 (new Order aggregate) |
| 5   | done    | 02660f7 — combined with 4 |
| 6   | done    | 02660f7 — combined with 4 |
| 7   | done    | 2be3d89 — order + inquiry Telegram fan-out |
| 8   | done    | 9832223 — /admin/requests + cards-feed |
| 9   | done    | 76fb8cb — public endpoints auth contract tests |
| 10  | done    | 5c37294 — docs + ADR-0010 + late Stage-8 wiring catch |

## Final

All 10 stages green. 7 atomic commits on `main` (5ccd12a..5c37294).
543 tests pass (was 445 at plan start; +98 new).
Routes: 118.

### Pending user actions

- Manual smoke: open `/admin/requests`, switch tabs, verify cards
  render, bulk-bar mounts, filters/sort work, drawer opens.
- D2 (new `view_inquiries`/`manage_inquiries` permissions) intentionally
  deferred — open as a follow-up ticket.
- Storefront UI for POST /orders / POST /inquiries — not built (project
  doesn't yet have a public cart flow). Contract is pinned by
  `test_public_endpoints.py`.

### Deviations logged

- Stage 0.5: extended existing `shared/adapters/driving/middleware.py`
  `customer_required` instead of creating new file in `access/`.
- Stages 1–3: combined into one atomic commit (rename touches all
  layers; intermediate splits would be broken states).
- Stages 4–6: combined into one atomic commit (new aggregate touches
  all layers consistently).
