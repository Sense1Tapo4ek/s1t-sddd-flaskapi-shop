# 0004 — SQLite as the default backend; defer Alembic
Status: superseded by 0006
Date: 2026-05-15

## Context

Primary deployment target is CPanel shared hosting; provisioning
PostgreSQL/MySQL is harder. The template must run after `git clone`
with zero external services. Schema evolution at template scale is
light.

## Decision

Default `INFRA_DATABASE_URL=sqlite:///data/shop.db`. Tables created
via `Base.metadata.create_all(engine)` on startup. Idempotent column
patches for upgraded installs in `shared/adapters/driven/db/compat.py`.
`PRAGMA foreign_keys=ON` per connection. No Alembic in the template;
add it before any PostgreSQL/MySQL deploy that needs schema evolution.

## Consequences

- + Forks run immediately; no DB setup.
- + Backups = `cp data/shop.db`; DB-dump endpoint is one file.
- + Compat patches let existing template installs upgrade without
  data loss.
- − SQLite weak under concurrent writes — accept tens of writes/s.
- − Compat patches accumulate; retire when Alembic lands.
- − `ORDER BY random()` is fine only at template scale.

## Alternatives considered

- PostgreSQL + Alembic from day one — too high a bar for forks.
- SQLite + Alembic now — awkward on a cloned-and-re-bootstrapped template.
- Default to SQLite without FK enforcement — defeats `ondelete`.
