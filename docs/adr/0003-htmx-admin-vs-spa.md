# 0003 — Admin UI: HTMX + Jinja, not an SPA
Status: accepted
Date: 2026-05-15

## Context

Forkable template targeting CPanel shared hosting. Admin pages are
CRUD over a handful of entities; no rich client-side state. A
separate frontend build pipeline raises the bar for forks.

## Decision

Render admin pages with Jinja, use HTMX for partial updates. A tiny
vanilla-JS SmartTable (`static/js/smart-table.js`) handles dynamic
widgets (filters, sorting, pagination). No SPA framework, no JS build
step. CSS in `static/<context>/`.

## Consequences

- + Zero JS toolchain: `git clone && uv sync && run` shows the UI.
- + Same auth/CSRF rules as the JSON API.
- + Server is the single source of truth for state.
- − Rich interactions (drag-drop trees) end up as ad-hoc JS.
- − HX-* response semantics need a small learning curve.

## Alternatives considered

- React/Vue SPA — build pipeline, CORS, separate auth flow.
- Full-page-reload Jinja only — UX too poor for forms-heavy admin.
- Hotwire/Turbo — equivalent ergonomics; HTMX has smaller surface and
  better Python-community familiarity.
