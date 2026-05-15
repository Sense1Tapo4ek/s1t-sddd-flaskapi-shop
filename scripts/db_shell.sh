#!/usr/bin/env bash
# Open the MySQL CLI against the database described by INFRA_DATABASE_URL.
# Reads .env at the project root if no env var is set.
#
# Usage:
#   bash scripts/db_shell.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ -z "${INFRA_DATABASE_URL:-}" && -f "$PROJECT_ROOT/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "$PROJECT_ROOT/.env"
    set +a
fi

if [[ -z "${INFRA_DATABASE_URL:-}" ]]; then
    echo "INFRA_DATABASE_URL is not set." >&2
    exit 2
fi

# mysql+pymysql://user:pass@host:port/db?charset=utf8mb4
URL="$INFRA_DATABASE_URL"
URL="${URL#*://}"
USERPASS="${URL%%@*}"
HOSTPORTDB="${URL#*@}"
USER="${USERPASS%%:*}"
PASS="${USERPASS#*:}"
HOSTPORT="${HOSTPORTDB%%/*}"
HOST="${HOSTPORT%%:*}"
PORT="${HOSTPORT#*:}"
[[ "$PORT" == "$HOST" ]] && PORT=3306
DB="${HOSTPORTDB#*/}"
DB="${DB%%\?*}"

exec mysql \
    --host="$HOST" --port="$PORT" \
    --user="$USER" --password="$PASS" \
    --default-character-set=utf8mb4 \
    "$DB"
