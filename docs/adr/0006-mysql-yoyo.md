# 0006 — Switch storage to MySQL with yoyo migrations
Status: accepted
Date: 2026-05-15

## Context

The primary deployment target — CPanel shared hosting — ships MySQL /
MariaDB but not PostgreSQL. SQLite worked at template scale but:
break-glass concurrent writes, no real backups via the host UI, and
the SQLite-only `compat.py` ALTER patches grew unwieldy. Forks running
in production need a real RDBMS with reliable migrations.

## Decision

- Drop SQLite. `INFRA_DATABASE_URL` defaults to
  `mysql+pymysql://...?charset=utf8mb4`.
- Driver: `PyMySQL` (pure Python — no `libmysqlclient` / compiler on
  shared hosting).
- Schema is owned by `migrations/*.sql` run by `yoyo-migrations`.
  Removed `Base.metadata.create_all` and `compat.py`.
- All tables get `InnoDB` + `utf8mb4` + `utf8mb4_unicode_ci` via a
  `mysql_table_opts()` helper appended to every `__table_args__`.
- Connection pool tuned for shared hosting: `pool_pre_ping=True`,
  `pool_recycle=3600`.
- DB-dump admin endpoint serves the newest file from `data/dumps/`;
  dump creation moves to `scripts/db_dump.py` (cron).

## Consequences

- + Real concurrent writes, transactions, FK enforcement by default.
- + Migrations are reviewable SQL files; rollback is first-class.
- + Hosting scripts (`db_apply`/`db_dump`/`db_shell`) make CPanel ops
  routine.
- − Forks must provision MySQL before first run.
- − Cross-dialect tests no longer free; tests gate integration on
  `MYSQL_TEST_URL`.
- − Schema changes now require two artefacts: the migration AND the
  ORM update.

## Alternatives considered

- PostgreSQL + Alembic — superseded ADR-0004 for the same reasons;
  CPanel does not host PostgreSQL.
- Keep SQLite alongside MySQL — double maintenance of `compat.py` and
  per-dialect quirks; rejected.
- Alembic on MySQL — heavier ergonomics for template-scale schema
  evolution; raw SQL with yoyo wins on transparency.
