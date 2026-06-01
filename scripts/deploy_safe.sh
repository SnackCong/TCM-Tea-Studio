#!/usr/bin/env bash
set -euo pipefail

APP_DIR=${APP_DIR:-/opt/tcm-tea-studio}
SERVICE=${SERVICE:-tcm-tea-studio}
DB_PATH=${TCM_DB_PATH:-$APP_DIR/data/tcm_tea_studio.sqlite3}
BACKUP_DIR=${TCM_BACKUP_DIR:-/root/tcm-tea-studio-backups/sqlite}
RETENTION_DAYS=${TCM_BACKUP_RETENTION_DAYS:-14}
BACKUP_SCRIPT=$APP_DIR/scripts/backup_sqlite.py

cd "$APP_DIR"

echo "==> Pre-deploy SQLite backup"
TCM_DB_PATH="$DB_PATH" \
TCM_BACKUP_DIR="$BACKUP_DIR" \
TCM_BACKUP_RETENTION_DAYS="$RETENTION_DAYS" \
/usr/bin/python3 "$BACKUP_SCRIPT"

echo "==> Current revision"
git rev-parse --short HEAD

echo "==> Pulling latest code"
git pull --ff-only

echo "==> New revision"
git rev-parse --short HEAD

echo "==> Checking Python dependencies"
if [ -f requirements.txt ]; then
  if /usr/bin/python3 -m pip --version >/dev/null 2>&1; then
    /usr/bin/python3 -m pip install -r requirements.txt
  else
    echo "requirements.txt exists but python3 -m pip is unavailable" >&2
    exit 1
  fi
else
  echo "No requirements.txt found; application uses Python standard library only."
fi

echo "==> Syntax checks"
/usr/bin/python3 -m py_compile server.py scripts/backup_sqlite.py

echo "==> Restarting $SERVICE"
systemctl restart "$SERVICE"

echo "==> Verifying service"
for attempt in $(seq 1 15); do
  if systemctl is-active --quiet "$SERVICE" && curl -fsS http://127.0.0.1:8080 >/dev/null 2>&1; then
    break
  fi
  if [ "$attempt" = "15" ]; then
    echo "Service did not become healthy on http://127.0.0.1:8080" >&2
    systemctl status "$SERVICE" --no-pager -l >&2 || true
    exit 1
  fi
  sleep 1
done
systemctl is-active "$SERVICE"
curl -fsSkI https://congnet.xyz >/dev/null

echo "deploy_ok revision=$(git rev-parse --short HEAD)"
