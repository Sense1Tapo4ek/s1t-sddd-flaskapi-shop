# Infra: Migrations (yoyo)

Raw-SQL migrations managed by `yoyo-migrations`. Lives in
[`migrations/`](../../migrations/). Schema is owned by these files —
the Flask app never issues DDL.

## File layout

```
migrations/
├── 0001_init.sql              forward
├── 0001_init.rollback.sql     optional rollback
└── README.md
```

- `NNNN_<slug>.sql` — forward DDL/DML.
- `NNNN_<slug>.rollback.sql` — yoyo runs this on `rollback`. Omit for
  forward-only migrations.
- Numbers are monotonic and **never renumbered** once applied
  anywhere.
- yoyo tracks applied migrations in a `_yoyo_migration` table it
  creates the first time it runs.

## Daily operations

| Action | Command |
|---|---|
| Apply pending | `python scripts/db_apply.py` |
| Show state | `python scripts/db_status.py` |
| Roll back last | `python scripts/db_rollback.py` |

All read `INFRA_DATABASE_URL` from the environment (loading `.env` at
the project root).

## Adding a migration

```bash
ls migrations | tail -n 2     # find current highest NNNN
$EDITOR migrations/00NN_<slug>.sql
$EDITOR migrations/00NN_<slug>.rollback.sql    # optional
$EDITOR src/<ctx>/adapters/driven/db/models.py # update ORM to match
python scripts/db_apply.py                     # apply locally
pytest -m integration                          # if integration tests exist
git add migrations/ src/                       # commit together
```

Rules:

- One logical change per migration. "Add column + backfill + drop old"
  is three migrations.
- DDL is **idempotent if possible** (`CREATE TABLE IF NOT EXISTS`,
  `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` — supported on MariaDB).
  For pure MySQL 5.7, idempotency relies on yoyo's tracking table.
- Migrations MUST match the ORM. Drift = bug. CI greps for
  `Base.metadata.create_all` in `src/` and fails if it appears outside
  tests.

## Rollback

`scripts/db_rollback.py` reverts the most recently applied migration.
If the migration is forward-only (no `.rollback.sql`), yoyo refuses
and exits non-zero. Re-rolling requires writing the rollback file
first.

For production rollbacks across multiple migrations, run yoyo directly:

```bash
yoyo rollback --batch --count 3 \
    --database "$INFRA_DATABASE_URL" \
    ./migrations
```

## CI / safety

- The schema guard `src/shared/adapters/driven/db/schema_guard.py`
  refuses to start the app if `_yoyo_migration` or any canonical
  table is missing.
- Never edit an applied migration. Append a new one.
- Never `DROP DATABASE` from a migration. Destructive ops belong in
  the rollback file.

## Pointers

- Runner config: `yoyo.ini`
- Helpers: `scripts/db_apply.py`, `db_status.py`, `db_rollback.py`
- ADR: [../adr/0006-mysql-yoyo.md](../adr/0006-mysql-yoyo.md)
