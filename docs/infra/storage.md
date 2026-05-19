# File Storage (local vs S3)

How product images and other uploads are stored, served, and switched
between backends. Owned by the `system` context.

## Purpose

Single source of truth for the `IFileStorage` port: where uploads
land, how URLs are served to the public storefront, and what changes
when the admin toggles the backend.

## Mental model

```
┌─ admin upload (image-editor.js) ─┐
│       multipart POST              │
└──────────────┬───────────────────┘
               ▼
        ProductFacade ──► CreateProductUC ──► IFileStorage (Protocol)
                                              │
                              ┌───────────────┴───────────────┐
                              ▼                               ▼
                       LocalFsStorage                    S3Storage
                       (system/ports/driven)             (system/ports/driven)
                              │                               │
                       writes to media/                writes to bucket;
                       saves relative path             saves absolute URL
                              │                               │
                              ▼                               ▼
                /media/products/<file>           https://bucket.s3...../<file>
                served by Flask                  served directly by S3
                (serve_upload route)             (browser bypasses Flask)
```

The active backend is decided at runtime by `StorageRouter`, which
reads `storage_settings.backend` from the DB and caches the choice
for 30 seconds. The admin UI flips the row; `StorageRouter` invalidates
its own cache on settings save.

## Public surface

| Concern | Where |
|---|---|
| Port (Protocol) | `src/system/app/interfaces/i_file_storage.py` |
| Local impl | `src/system/ports/driven/local_fs_storage.py` |
| S3 impl | `src/system/ports/driven/s3_storage.py` |
| Router (cache + dispatch) | `src/system/ports/driven/storage_router.py` |
| Local-serve route | `src/root/entrypoints/api.py` — `serve_upload` |
| Admin form | `src/system/templates/system/partials/storage_form.html` |

## Required environment

| Var | Required when | Notes |
|---|---|---|
| `SYSTEM_STORAGE_SECRETS_KEY` | backend = `s3` | Fernet key (URL-safe base64, 32 raw bytes) used to encrypt `storage_settings.secret_access_key_enc`. Generate via `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. **Losing this key after writing an S3 secret = the secret cannot be decrypted and S3 access is lost.** Generate once at provisioning; never rotate without re-saving credentials. |

The S3 endpoint URL, region, bucket, access key id, and public base
URL are stored in `storage_settings` (DB row), edited via the admin
form. The secret access key is stored encrypted using the env key
above.

## Invariants & gotchas

- **Local backend is the default.** A fresh install writes to
  `./media/products/<file>` and serves via the `/media/products/...`
  Flask route. No S3 envs are required.
- **S3 URLs bypass Flask.** When backend = `s3`, `Product.images[]`
  already holds absolute public URLs. The `serve_upload` route is
  NOT used; the browser fetches directly from S3 / CDN.
- **Switching backends does not migrate files.** Existing image paths
  remain in the DB. Switch only at provisioning, or write a migration
  script that re-uploads + rewrites paths.
- **Cache invalidation.** `StorageRouter` caches the active backend
  for 30 s. The settings facade calls `invalidate_cache()` after every
  successful save so the admin sees immediate effect.
- **Force-path-style flag.** Needed for MinIO / non-AWS S3 backends
  that don't support virtual-host style addressing.

## Operational checklist

When enabling S3 on a new deployment:

1. Generate `SYSTEM_STORAGE_SECRETS_KEY`; back it up safely.
2. Set it in `.env` and restart the app.
3. Open `/admin/settings/` → storage section, switch backend to `s3`.
4. Fill endpoint URL, region, bucket, access key id, secret access
   key, public base URL. Tick `force_path_style` if your endpoint
   needs it.
5. Press "Test connection" before saving.
6. Save. New uploads go to S3 from this point onward.

## Pointers

- ADR: storage backend strategy (none yet — promote when reviewed).
- Subsystem (feature flags & socials): [../subsystems/feature-flags.md](../subsystems/feature-flags.md).
- System context: [../contexts/system.md](../contexts/system.md).
