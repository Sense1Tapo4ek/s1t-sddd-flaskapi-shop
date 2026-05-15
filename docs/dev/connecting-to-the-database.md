# Connecting to the database

For developers who need a working MySQL connection on their machine —
to run the app, apply migrations, open a shell, or point an IDE at the
DB.

The project targets **MySQL 5.7+ / MariaDB 10.3+** via the `PyMySQL`
driver. The connection string format used everywhere is:

```
mysql+pymysql://<user>:<password>@<host>:<port>/<database>?charset=utf8mb4
```

It lives in `.env` as `INFRA_DATABASE_URL`. Pick the scenario that
matches you.

---

## Scenario A — Local development with docker-compose (recommended)

The simplest path. `docker-compose.yml` ships a `db` service
(`mysql:5.7`) wired to the API container.

### Step 1 — Copy the example env file

```bash
cp .env.example .env
```

It already contains a working URL for the bundled DB:

```
INFRA_DATABASE_URL=mysql+pymysql://shop:shop@db:3306/shop?charset=utf8mb4
```

Credentials:

| Field | Value |
|---|---|
| Host (from inside compose) | `db` |
| Host (from your workstation) | `localhost` |
| Port | `3306` |
| User | `shop` |
| Password | `shop` |
| Database | `shop` |
| Root password | `root` (only for emergency `db_shell` as root) |

These are dev-only defaults — never deploy them.

### Step 2 — Start MySQL

```bash
docker compose up -d db          # MySQL only
# or
docker compose up --build        # MySQL + API (API runs db_apply automatically)
```

### Step 3 — Apply migrations and run the app

If you're using the API container, this is already done by the
container's CMD. If you're running the app natively, run it yourself:

```bash
python scripts/db_apply.py
PYTHONPATH=src FLASK_DEBUG=1 uv run src/root/entrypoints/api.py
```

### Step 4 — Open a shell against the dev DB

```bash
# from your workstation, override the host to localhost:
INFRA_DATABASE_URL="mysql+pymysql://shop:shop@localhost:3306/shop?charset=utf8mb4" \
    bash scripts/db_shell.sh
```

Or use the docker container directly:

```bash
docker compose exec db mysql -ushop -pshop shop
```

---

## Scenario B — Local development without Docker

You have a local MySQL/MariaDB already installed.

### Step 1 — Create the database and user

In the local `mysql` shell as root:

```sql
CREATE DATABASE shop CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'shop'@'localhost' IDENTIFIED BY 'CHOOSE_A_PASSWORD';
GRANT ALL PRIVILEGES ON shop.* TO 'shop'@'localhost';
FLUSH PRIVILEGES;
```

### Step 2 — Point `.env` at it

```
INFRA_DATABASE_URL=mysql+pymysql://shop:CHOOSE_A_PASSWORD@localhost:3306/shop?charset=utf8mb4
```

### Step 3 — Apply migrations

```bash
python scripts/db_apply.py
```

### Step 4 — Run the app

```bash
PYTHONPATH=src FLASK_DEBUG=1 uv run src/root/entrypoints/api.py
```

---

## Scenario C — CPanel shared hosting (production)

Credentials are issued by CPanel. You do NOT pick them yourself — you
create them once in the CPanel UI and copy them into `.env`.

### Step 1 — Get the credentials

CPanel → **MySQL Databases**:

1. **Create New Database** → name e.g. `shop`. CPanel prepends your
   cPanel username, so the real database name becomes
   `cpaneluser_shop`.
2. **Add New User** → name `shop`. CPanel prepends your username, so
   the real user becomes `cpaneluser_shop`. Use CPanel's password
   generator and **copy the password now** — it will not be shown
   again. If you lose it, change it via CPanel → MySQL Databases →
   "Current Users" → "Change Password".
3. **Add User to Database** → grant **ALL PRIVILEGES**.

Connection facts CPanel gives you:

| Field | Value |
|---|---|
| Host | `localhost` |
| Port | `3306` (default) |
| User | `cpaneluser_shop` |
| Password | what you generated in step 2 |
| Database | `cpaneluser_shop` |

> If your provider exposes a different MySQL host (some do — look for
> "Remote MySQL" docs or a notice on the MySQL Databases page), use
> that instead of `localhost`.

### Step 2 — Build the URL and put it in `.env` (server side)

SSH to the server and edit `~/<app-root>/.env`:

```
INFRA_DATABASE_URL=mysql+pymysql://cpaneluser_shop:THE_PASSWORD@localhost:3306/cpaneluser_shop?charset=utf8mb4
```

If the password contains special characters (`@`, `:`, `/`, `#`, `?`,
`&`), URL-encode them. The safe characters in CPanel-generated
passwords usually need no escaping; if yours does, encode with
`python3 -c "from urllib.parse import quote; print(quote('YOUR_PASS', safe=''))"`.

### Step 3 — Bootstrap

```bash
ssh user@hosting
source ~/virtualenv/<app-root>/3.11/bin/activate
cd ~/<app-root>
bash scripts/bootstrap_cpanel.sh    # pip install + db_apply + seed
```

Then restart the Python app in CPanel.

### Step 4 — Connect from your workstation (optional)

CPanel hides MySQL from the public internet by default. Two ways in:

**Option 1 — "Remote MySQL" whitelist.** CPanel → **Remote MySQL** →
add your home IP. Then on your laptop:

```bash
INFRA_DATABASE_URL="mysql+pymysql://cpaneluser_shop:PASS@your-host.tld:3306/cpaneluser_shop?charset=utf8mb4" \
    bash scripts/db_shell.sh
```

**Option 2 — SSH tunnel** (no whitelist needed):

```bash
ssh -L 3307:localhost:3306 user@hosting
# in a second terminal:
INFRA_DATABASE_URL="mysql+pymysql://cpaneluser_shop:PASS@127.0.0.1:3307/cpaneluser_shop?charset=utf8mb4" \
    python scripts/db_status.py
```

Once connected, the same `scripts/db_*.py` helpers work against the
remote DB.

---

## Connecting an IDE / GUI tool

The same credentials and host you set up above also work in DBeaver,
TablePlus, JetBrains DataGrip, MySQL Workbench, etc. Point them at:

| Field | Local (docker) | Local (native) | CPanel (via SSH tunnel) |
|---|---|---|---|
| Host | `localhost` | `localhost` | `127.0.0.1` |
| Port | `3306` | `3306` | `3307` |
| User | `shop` | `shop` | `cpaneluser_shop` |
| Password | `shop` | what you chose | what CPanel issued |
| Database | `shop` | `shop` | `cpaneluser_shop` |

Always set the connection charset to **utf8mb4** so multi-byte text
roundtrips correctly.

---

## Recovering / rotating credentials

| Situation | Action |
|---|---|
| Lost CPanel DB password | CPanel → MySQL Databases → "Current Users" → user → "Change Password". Update `.env`. |
| Compromised password | Rotate it in CPanel, update `.env`, restart the Python app in CPanel. |
| Local dev password forgotten | Stop docker-compose, drop the named volume `docker volume rm <project>_mysql_data`, restart — defaults are recreated. |

`.env` is the only place the connection string lives in this repo —
no credentials are committed.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Access denied for user '...'@'localhost'` | Wrong password in `.env`, or user not granted on the database. Check CPanel → MySQL Databases. |
| `Can't connect to MySQL server on '...'` | Host or port wrong. CPanel often uses `localhost`; some providers use a different hostname. |
| `Unknown database '...'` | Real DB name has the CPanel prefix (`cpaneluser_<name>`). |
| `SchemaNotReadyError` at app startup | Migrations haven't been applied — run `python scripts/db_apply.py`. |
| Idle disconnects ("MySQL server has gone away") | `INFRA_DB_POOL_PRE_PING=true` (default). If you turned it off, turn it back on. |
| Special characters in URL break parsing | URL-encode the password (see Scenario C step 2). |

## Pointers

- Migrations runner: [docs/infra/migrations.md](../infra/migrations.md)
- MySQL infra reference: [docs/infra/mysql.md](../infra/mysql.md)
- CPanel walkthrough: [docs/infra/cpanel.md](../infra/cpanel.md)
- Scripts: [scripts/](../../scripts/)
