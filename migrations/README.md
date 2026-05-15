# Database migrations (yoyo)

This folder is the **single source of truth** for the database schema.
The Flask app never issues DDL.

## Format

- `NNNN_<slug>.sql` — forward migration, raw MySQL DDL.
- `NNNN_<slug>.rollback.sql` — optional rollback (yoyo runs it when
  you `yoyo rollback`). Forward-only migrations omit this file.
- Numbering is monotonic. Never renumber an applied migration.

## How to add one

1. Pick the next number: `ls migrations | tail -1`.
2. Create `migrations/00NN_<slug>.sql` with `ALTER TABLE` / `CREATE TABLE`.
3. Update the matching ORM model in `src/<context>/adapters/driven/db/models.py`.
4. Apply locally: `python scripts/db_apply.py`.
5. Add a `00NN_<slug>.rollback.sql` if the change is reversible.

## Apply / status / rollback

```bash
python scripts/db_apply.py    # apply all pending
python scripts/db_status.py   # show applied + pending
python scripts/db_rollback.py # rollback the most recent migration
```

See [../docs/infra/migrations.md](../docs/infra/migrations.md).
