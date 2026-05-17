# Exec-plan: 2026-05-17-customer-accounts-plan

## Phase 1 — Superadmin removal
✅ Done. Committed: c77fa29 — `refactor(access): Phase-1 — drop separate superadmin user`

## Wave 1 — Phase 2 (domain) + Phase 7 (SMTP infra) + Phase 11 (schema)
✅ Done.
- Phase 11: c99f71d — schema customers + token_version + last_login_at
- Phase 2:  ac5ae28 — Customer domain aggregate + new errors
- Phase 7:  9c25cef — SMTP + logging email senders + recovery code helper

Tests: 66 passed (8 pre-existing bulk-test failures from Phase 1 — fix in Phase 12).

Review findings:
- Phase 2 — 2 HIGH accepted as DEVIATION (matches existing User pattern: pure-data aggregates, mutation in repos). Logged for future ADR consideration.
- Phase 7 — 2 CRITICAL + 2 HIGH cycled through rework agent; re-review ACCEPT all 8 fixes.
- Phase 11 — 1 MEDIUM fixed inline (timezone-aware vs naive mismatch); 1 LOW logged.

## Wave 2 — Phase 3 (app/interfaces)
in progress
