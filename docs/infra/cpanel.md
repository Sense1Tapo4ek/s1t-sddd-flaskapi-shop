# Infra: CPanel / Passenger

For deploying the template on shared hosting that exposes "Setup
Python App" (Phusion Passenger). For Docker or generic WSGI hosting,
see [../../README.md](../../README.md).

## Prerequisites

- CPanel with **Setup Python App** and **MySQL Databases** wizards.
- Python 3.11+ available in CPanel.
- SSH access (strongly recommended for migrations and dumps).

## Step 1 — Provision the MySQL database

CPanel → **MySQL Databases**:

1. **Create New Database** — name e.g. `shop`. The wizard prefixes it
   with your CPanel user, so the real name becomes `cpaneluser_shop`.
2. **Add New User** — pick a username (also auto-prefixed:
   `cpaneluser_shop`). Generate a strong password and **store it now**
   — CPanel will not show it again.
3. **Add User to Database** — grant **ALL PRIVILEGES**.

The connection details you now have:

| Item | Value |
|---|---|
| Host | `localhost` |
| Port | `3306` (default; usually not shown in the UI) |
| Database name | `cpaneluser_shop` (with prefix) |
| Username | `cpaneluser_shop` (with prefix) |
| Password | what you generated above |

> If the hosting provider blocks `localhost` and exposes a separate
> MySQL hostname, look under "phpMyAdmin" or "Remote MySQL" — the
> connection string is documented there.

The full SQLAlchemy URL is:

```
mysql+pymysql://cpaneluser_shop:STRONG_PASSWORD@localhost:3306/cpaneluser_shop?charset=utf8mb4
```

Put it in `.env` as `INFRA_DATABASE_URL` (see Step 4).

## Step 2 — Create the Python application

CPanel → **Setup Python App** → **Create Application**:

- Python version: 3.11 (or newest available).
- Application root: project directory (e.g., `shop`).
- Application URL: domain or subdomain.
- Startup file: `passenger_wsgi.py`.
- Entry point: `application`.

CPanel creates a virtualenv at `/home/<user>/virtualenv/<app-root>/3.11/`
automatically.

## Step 3 — Upload the project

Via File Manager, SSH/SFTP, or git pull:

```
your-app-root/
├── passenger_wsgi.py
├── requirements.txt
├── migrations/
├── scripts/
├── .env
├── data/dumps/
├── media/
├── static/
└── src/
```

Do not upload `__pycache__/`, `.git/`, `uv.lock`, `.venv/`.

## Step 4 — Configure `.env`

Copy `.env.example` to `.env` and fill in:

```bash
ROOT_APP_NAME=My Shop
ROOT_APP_ENV=prod

INFRA_DATABASE_URL=mysql+pymysql://cpaneluser_shop:STRONG_PASSWORD@localhost:3306/cpaneluser_shop?charset=utf8mb4

ACCESS_JWT_SECRET=<strong random>
ACCESS_DEFAULT_LOGIN=admin
ACCESS_DEFAULT_PASSWORD=<strong>
# Single admin row. Set to `true` to grant role=superadmin to that admin;
# otherwise role=owner and per-permission ACCESS_OWNER_CAN_* flags apply.
ACCESS_PROMOTE_TO_SUPERADMIN=true
CATALOG_UPLOAD_DIR=media/products
SYSTEM_RECOVERY_TOKEN=<strong random>

ROOT_PUBLIC_CORS_ORIGINS=["https://your-shop.com"]
ROOT_ADMIN_CORS_ORIGINS=["https://your-shop.com"]

PORT=5000
PYTHONPATH=src
```

The DB-dump endpoint refuses to serve until the calling superadmin has
changed their bootstrap password.

## Step 5 — Bootstrap (SSH)

```bash
ssh user@hosting
source ~/virtualenv/shop/3.11/bin/activate
cd ~/shop
bash scripts/bootstrap_cpanel.sh
```

The script: `pip install -r requirements.txt` → `python scripts/db_apply.py`
(applies all yoyo migrations) → `python data/seed.py` (idempotent
defaults).

> No SSH? Run the same commands in CPanel → **Setup Python App** →
> your app → "Run Script". Drop `bash` from the command.

## Step 6 — Static files

CPanel/Apache should serve `static/` and `media/` directly. Add to
`.htaccess`:

```apache
RewriteEngine On
RewriteRule ^static/(.*)$ static/$1 [L]
RewriteRule ^media/(.*)$ media/$1 [L]
```

```bash
chmod -R 755 static/ media/
```

## Step 7 — Restart and verify

CPanel → "Setup Python App" → **Restart**. Visit the domain; you
should land on the admin login. Swagger is disabled in `prod`.

## Step 8 — Schedule backups

CPanel → **Cron Jobs** → add a daily entry:

```
0 3 * * * cd ~/shop && /home/USER/virtualenv/shop/3.11/bin/python scripts/db_dump.py
```

Dumps land in `data/dumps/shop-<timestamp>.sql.gz` (last 14 retained
by default — pass `--keep N` to change). The admin UI's "Download
database dump" link serves the newest file.

## Updating

```bash
ssh user@hosting && cd ~/shop
git pull                              # or upload via SFTP
source ~/virtualenv/shop/3.11/bin/activate
pip install -r requirements.txt        # only if requirements.txt changed
python scripts/db_apply.py             # only if migrations/ changed
# Restart in CPanel
```

## Connecting from your workstation

If "Remote MySQL" is enabled by the host (CPanel → "Remote MySQL"
adds your IP to a whitelist):

```bash
bash scripts/db_shell.sh        # opens a mysql CLI using .env creds
python scripts/db_apply.py      # apply migrations remotely
python scripts/db_dump.py       # take a local dump
```

Otherwise, tunnel through SSH:

```bash
ssh -L 3307:localhost:3306 user@hosting
# in another terminal, point .env at port 3307:
INFRA_DATABASE_URL=mysql+pymysql://cpaneluser_shop:PASS@127.0.0.1:3307/cpaneluser_shop?charset=utf8mb4 \
    python scripts/db_status.py
```

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| 500 / Application Error on first request | Migrations not applied — run `python scripts/db_apply.py` |
| `SchemaNotReadyError` in logs | Same — run migrations |
| `ModuleNotFoundError` | `.env` missing `PYTHONPATH=src` |
| `Access denied for user 'cpaneluser_shop'@'localhost'` | Wrong password in `.env` or user not added to database |
| `Can't connect to MySQL server` | Host is not `localhost` on your provider — check "Remote MySQL" docs |
| Static files 404 | `chmod` and `.htaccess` rewrite |
| Connection drops after idle | Confirm `INFRA_DB_POOL_PRE_PING=true` |

## Pointers

- Passenger entry: `passenger_wsgi.py`
- App factory: `src/root/entrypoints/api.py`
- Migrations: [migrations.md](./migrations.md)
- MySQL infra: [mysql.md](./mysql.md)
- Hosting scripts: `scripts/`
