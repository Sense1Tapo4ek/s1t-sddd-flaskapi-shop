# CPanel Deployment Guide

This guide covers deploying the shop template on shared hosting with CPanel using Phusion Passenger.

---

## Prerequisites

- CPanel with **"Setup Python App"** feature (most shared hosting providers include it)
- Python 3.11+ available in CPanel
- SSH access (recommended, but not strictly required)

---

## Step 1: Create the Python Application

1. Log into CPanel
2. Go to **"Setup Python App"** (or "Python Selector")
3. Click **"Create Application"**
4. Set:
   - **Python version:** 3.11 (or highest available)
   - **Application root:** your project directory (e.g., `shop` or `myapp`)
   - **Application URL:** your domain or subdomain
   - **Application startup file:** `passenger_wsgi.py`
   - **Application Entry point:** `application`
5. Click **Create**

CPanel will create a virtual environment automatically.

---

## Step 2: Upload Project Files

Upload the project via **File Manager** or **SSH/SCP/SFTP**:

```
your-app-root/
├── passenger_wsgi.py    ← CPanel entry point
├── requirements.txt
├── .env
├── data/
│   ├── seed.py
│   └── seed_config.yaml
├── media/
├── static/
└── src/
    ├── root/
    ├── catalog/
    ├── ordering/
    ├── access/
    ├── system/
    └── shared/
```

> Do NOT upload `__pycache__/`, `.git/`, `uv.lock`, or `node_modules/`.

---

## Step 3: Configure Environment

Create `.env` in your application root (copy from `.env.example`):

```bash
ROOT_APP_NAME=My Shop
ROOT_APP_ENV=prod

INFRA_DATABASE_URL=sqlite:///data/shop.db
ACCESS_JWT_SECRET=your-strong-random-secret-here
ACCESS_DEFAULT_LOGIN=admin
ACCESS_DEFAULT_PASSWORD=your-admin-password
CATALOG_UPLOAD_DIR=media/products
SYSTEM_RECOVERY_TOKEN=your-recovery-token

PORT=5000
PYTHONPATH=src
```

**Important:** Change `ACCESS_JWT_SECRET` and `SYSTEM_RECOVERY_TOKEN` to strong random values in production.

---

## Step 4: Install Dependencies

Via SSH (or CPanel terminal):

```bash
# Enter the virtual environment created by CPanel
source /home/username/virtualenv/your-app-root/3.11/bin/activate

# Install dependencies
pip install -r requirements.txt
```

Or via CPanel UI: go to "Setup Python App" → your app → "Run pip install".

---

## Step 5: Initialize the Database

```bash
source /home/username/virtualenv/your-app-root/3.11/bin/activate
cd /home/username/your-app-root

PYTHONPATH=src python data/seed.py
```

This creates the SQLite database at `data/shop.db` with:
- Default admin user
- Default system settings
- Mock data from `data/seed_config.yaml`

---

## Step 6: Configure Static Files

CPanel serves static files via Apache. Add to `.htaccess` in your app root:

```apache
# Serve static files directly via Apache (bypass Passenger)
RewriteEngine On
RewriteRule ^static/(.*)$ static/$1 [L]
RewriteRule ^media/(.*)$ media/$1 [L]
```

Or configure static file aliases in CPanel's Apache settings if available.

---

## Step 7: CORS Configuration

For production, set proper CORS origins in `.env`:

```bash
ROOT_PUBLIC_CORS_ORIGINS=["https://your-shop.com"]
ROOT_ADMIN_CORS_ORIGINS=["https://your-shop.com"]
```

---

## Step 8: Restart and Verify

1. In CPanel → "Setup Python App" → click **"Restart"**
2. Visit your domain — you should see the admin login page
3. Log in with the credentials from `.env`
4. Swagger docs are disabled in production (`ROOT_APP_ENV=prod`)

---

## Troubleshooting

### Application Error / 500

Check the Passenger error log:
```bash
tail -f /home/username/logs/your-app-root/error.log
```

Common issues:
- **ModuleNotFoundError:** `PYTHONPATH` not set. Make sure `.env` has `PYTHONPATH=src`
- **Database locked:** SQLite doesn't support concurrent writes well. For high traffic, consider switching to MySQL/PostgreSQL

### Static files not loading

Ensure the `static/` directory has proper permissions:
```bash
chmod -R 755 static/
chmod -R 755 media/
```

### HTTPS / SSL

Set up SSL in CPanel → "SSL/TLS" or "Let's Encrypt". The app itself doesn't handle SSL — Passenger runs behind Apache/nginx.

---

## Updating the App

1. Upload new files (overwrite)
2. If dependencies changed: `pip install -r requirements.txt`
3. If models changed: restart the app (tables are auto-created on startup)
4. Restart: CPanel → "Setup Python App" → **"Restart"**

---

## Directory Structure on CPanel

```
/home/username/
├── your-app-root/           ← Application root
│   ├── passenger_wsgi.py
│   ├── .env
│   ├── requirements.txt
│   ├── data/
│   │   ├── shop.db          ← SQLite database (auto-created)
│   │   ├── seed.py
│   │   └── seed_config.yaml
│   ├── media/products/      ← Uploaded images
│   ├── static/              ← CSS, JS
│   └── src/                 ← Application code
└── virtualenv/
    └── your-app-root/
        └── 3.11/            ← Python virtual environment
```
