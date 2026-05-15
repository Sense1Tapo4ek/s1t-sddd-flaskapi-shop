#!/usr/bin/env bash
# One-shot post-clone setup for CPanel shared hosting.
#
# Assumes:
#   - A Python venv has already been created via "Setup Python App"
#     and you're running this script inside it (`source ~/virtualenv/app/3.11/bin/activate`).
#   - `.env` is filled in (copy from `.env.example`, edit MySQL creds).
#   - MySQL database + user already exist in CPanel ("MySQL Databases" wizard).
#
# Usage (from the project root):
#   bash scripts/bootstrap_cpanel.sh

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [[ ! -f .env ]]; then
    echo "ERROR: .env is missing. cp .env.example .env and fill in MySQL creds." >&2
    exit 2
fi

echo "==> Installing Python dependencies"
pip install -r requirements.txt

echo "==> Applying database migrations"
python scripts/db_apply.py

echo "==> Seeding default rows (idempotent)"
python data/seed.py || true

echo
echo "Bootstrap complete."
echo "In CPanel -> Setup Python App, set:"
echo "  Application Startup File   = passenger_wsgi.py"
echo "  Application Entry Point    = application"
echo "and click 'Restart App'."
