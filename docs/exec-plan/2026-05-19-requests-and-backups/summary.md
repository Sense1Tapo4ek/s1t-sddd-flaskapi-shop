# /exec-plan summary — 2026-05-19-requests-and-backups

Stages completed: 4 / 4 (4 commits on `main`).
Pending user action (manual): live verification.
Halted: none.

## Commits (one per stage)

```
2af1a57 fix(catalog):  S1 — category column sort works on MySQL 5.7
8adeffe feat(ordering): S4 — tab-conditional test-row buttons + JSON test endpoints
64b096d fix(ordering):  S3 — move help badge into page-header__right next to action button
708ef53 feat(system):   S5 — backups admin nav + is_superadmin helper
```

## Root-cause notes

- **S1.** Recursive CTE in `_apply_catalog_sort` crashed on MySQL 5.7
  (`WITH RECURSIVE` requires MySQL 8.0+). Replaced with a non-recursive
  correlated scalar subquery on `categories.title`. Matches user's
  "простая сортировка как по строке" requirement.
- **S4.** Demo button removed from UI; endpoint kept for API consumers.
  Inquiry-test endpoint refactored from HTMX partial to JSON (no
  callers were broken). New `CreateTestOrderUseCase` covered by 3
  flow tests.
- **S5.** Backups blueprint was already registered but unreachable —
  no sidebar entry existed. Added `is_superadmin()` Jinja global and a
  new "База данных" section in the sidebar.

## Verification (auto-run)

- `pytest -m "unit or flow"` → 621 passed, 53 deselected.
- Live curl `GET /catalog/admin/search?sort_by=category&sort_dir=asc`
  → HTTP 200, items sorted by category title.
- Live `POST /auth/login` → token issued.

## Next steps

1. Open `/admin/catalog/`, click the «Категория» column header — table
   re-sorts both ASC and DESC without 500.
2. Open `/admin/requests/`, switch between «Заказы» / «Обращения» tabs
   — only the matching test-row button is visible. Each click creates
   one row and the feed refreshes in-place.
3. Open the sidebar — "База данных → Резервные копии" link visible
   for the superadmin (`admin/changeme`). Page is the existing backups
   admin (`/admin/backups/`).
4. Files left uncommitted in working tree are from previous turns
   (catalog help modals, backups templates from Stage-3); those land
   in their own dedicated commits when ready.
