# TCM Tea Studio Deployment

Last checked: 2026-06-01

## Overview

Production domain:

- `http://congnet.xyz`
- `https://congnet.xyz`

Application repository:

- `/opt/tcm-tea-studio`

Application data:

- `/opt/tcm-tea-studio/data/tcm_tea_studio.sqlite3`

Backups:

- `/root/tcm-tea-studio-backups`
- `/root/tcm-tea-studio-backups/sqlite`

## Runtime Topology

```text
Internet / Cloudflare
  ├─ HTTP  80/tcp  -> Docker mynginx -> 172.17.0.1:8080 -> tcm-tea-studio
  └─ HTTPS 443/tcp -> host nginx     -> 127.0.0.1:8080 -> tcm-tea-studio

Hysteria:
  └─ 443/udp -> hysteria-server
```

## Port Ownership

Current listener map:

- `80/tcp`: Docker proxy for `mynginx`
- `443/tcp`: host `nginx`
- `443/udp`: `hysteria-server`
- `8080/tcp`: `python3` running `tcm-tea-studio`

The TCP and UDP listeners on `443` are separate sockets. Host Nginx uses TCP `443`; `hysteria-server` uses UDP `443`.

## Services

Systemd services:

- `nginx`: `enabled`, `active`
- `tcm-tea-studio`: `enabled`, `active`
- `hysteria-server`: `enabled`, `active`
- `hy2`: not active at the time of inspection

Docker containers:

- `mynginx`: running, image `nginx`, publishes `0.0.0.0:80->80/tcp`
- `mynginx-before-persist-20260601052515`: stopped backup container from the persistence migration

## Nginx Layout

Host Nginx handles HTTPS:

- Config: `/etc/nginx/conf.d/tcm-tea-studio-ssl.conf`
- Certificate: `/etc/nginx/ssl/congnet.xyz.crt`
- Private key: `/etc/nginx/ssl/congnet.xyz.key`
- Proxy target: `http://127.0.0.1:8080`

Docker `mynginx` handles HTTP:

- Config source: `/opt/tcm-tea-studio/nginx-persistent/nginx.conf`
- Site configs source: `/opt/tcm-tea-studio/nginx-persistent/conf.d`
- Website files source: `/root/mywebsite`
- Proxy target for `congnet.xyz`: `http://172.17.0.1:8080`

## Docker Mounts

Current `mynginx` bind mounts:

```text
/opt/tcm-tea-studio/nginx-persistent/nginx.conf -> /etc/nginx/nginx.conf:ro
/opt/tcm-tea-studio/nginx-persistent/conf.d    -> /etc/nginx/conf.d:ro
/root/mywebsite                                -> /usr/share/nginx/html:ro
```

Restart policy:

- `mynginx`: `unless-stopped`

This is appropriate for the current deployment. No additional restart policy change is needed.

## Rollback

The previous container was preserved as:

```text
mynginx-before-persist-20260601052515
```

Manual rollback:

```bash
docker stop mynginx
docker rename mynginx mynginx-after-persist-failed-$(date +%Y%m%d%H%M%S)
docker rename mynginx-before-persist-20260601052515 mynginx
docker start mynginx
docker ps
curl -I http://congnet.xyz
```

Do not delete `/root/mywebsite`, `/opt/tcm-tea-studio`, or `/root/tcm-tea-studio-backups`.

## HTTPS Certificate

Current certificate:

- Type: self-signed origin certificate
- Subject: `CN = congnet.xyz`
- Issuer: `CN = congnet.xyz`
- Path: `/etc/nginx/ssl/congnet.xyz.crt`
- Key path: `/etc/nginx/ssl/congnet.xyz.key`
- Valid from: `2026-06-01 04:51:56 GMT`
- Valid until: `2036-05-29 04:51:56 GMT`

The private key currently has restrictive permissions:

```text
-rw------- /etc/nginx/ssl/congnet.xyz.key
```

Cloudflare currently serves HTTPS successfully with this origin setup, which is consistent with Cloudflare SSL/TLS mode being `Full`.

For Cloudflare `Full strict`, replace the current certificate with either:

- Cloudflare Origin Certificate for `congnet.xyz` and `www.congnet.xyz`
- Let's Encrypt certificate trusted by public clients

Recommended Cloudflare Origin Certificate paths:

```text
/etc/nginx/ssl/congnet.xyz.crt
/etc/nginx/ssl/congnet.xyz.key
```

After replacement:

```bash
chmod 600 /etc/nginx/ssl/congnet.xyz.key
nginx -t
systemctl reload nginx
```

Never commit private keys to GitHub.

## Verification Commands

```bash
curl -I http://congnet.xyz
curl -Ik https://congnet.xyz
docker ps
ss -tulpn | grep -E ':80|:443|:8080'
systemctl is-active hysteria-server
systemctl is-active nginx
systemctl is-active tcm-tea-studio
```

Expected high-level results:

- HTTP returns `200 OK`
- HTTPS returns `200`
- `mynginx` is running
- `hysteria-server` is `active`
- `nginx` is `active`
- `tcm-tea-studio` is `active`

## SQLite Backups

Database path:

```text
/opt/tcm-tea-studio/data/tcm_tea_studio.sqlite3
```

Backup directory:

```text
/root/tcm-tea-studio-backups/sqlite
```

Backup script:

```text
/opt/tcm-tea-studio/scripts/backup_sqlite.py
```

Cron entry:

```text
/etc/cron.d/tcm-tea-studio-backup
```

Schedule:

- Daily at `03:17` server time
- File name format: `tcm_tea_studio_YYYYMMDD-HHMMSS.sqlite3`
- Retention: keep backups from the last 14 days; remove older matching backup files

The script uses Python's built-in `sqlite3.Connection.backup()` API against the live database in read-only mode, then runs `PRAGMA integrity_check` on the backup file.

Manual backup test:

```bash
TCM_DB_PATH=/opt/tcm-tea-studio/data/tcm_tea_studio.sqlite3 \
TCM_BACKUP_DIR=/root/tcm-tea-studio-backups/sqlite \
TCM_BACKUP_RETENTION_DAYS=14 \
/usr/bin/python3 /opt/tcm-tea-studio/scripts/backup_sqlite.py
```

List backups:

```bash
ls -lh /root/tcm-tea-studio-backups/sqlite
```

Restore drill without touching production:

```bash
LATEST_BACKUP=$(ls -t /root/tcm-tea-studio-backups/sqlite/tcm_tea_studio_*.sqlite3 | head -n 1)
mkdir -p /root/tcm-tea-studio-backups/restore-drills
RESTORE_TEST=/root/tcm-tea-studio-backups/restore-drills/restore-test-$(date +%Y%m%d-%H%M%S).sqlite3
cp "$LATEST_BACKUP" "$RESTORE_TEST"

python3 - <<PY
import sqlite3
path = "$RESTORE_TEST"
con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
print("opened=ok")
print("integrity=" + con.execute("PRAGMA integrity_check").fetchone()[0])
print("schema:")
for name, sql in con.execute("select name, sql from sqlite_master where type='table' order by name"):
    print(f"- {name}: {sql}")
print("counts:")
for (name,) in con.execute("select name from sqlite_master where type='table' order by name"):
    count = con.execute(f"select count(*) from {name}").fetchone()[0]
    print(f"- {name}: {count}")
con.close()
PY
```

Restore drill result from `2026-06-01`:

- Source backup: `/root/tcm-tea-studio-backups/sqlite/tcm_tea_studio_20260601-085425.sqlite3`
- Temporary restore file: `/root/tcm-tea-studio-backups/restore-drills/restore-test-20260601-085425.sqlite3`
- Open test: `opened=ok`
- Integrity check: `integrity=ok`
- Table counts:
  - `clients`: 0
  - `formulas`: 0
  - `sessions`: 1
  - `users`: 1
- Production database was not replaced: `/opt/tcm-tea-studio/data/tcm_tea_studio.sqlite3`

## Application Data Model

Current business tables:

- `clients`: real customer profiles.
- `client_sessions`: follow-up or visit records linked to `clients.id`.
- `client_formulas`: customer-specific tea formula records linked to `clients.id`; these are actual case records, not global templates.
- `client_todos`: customer-specific reminders and follow-up tasks linked to `clients.id`.
- `formula_templates`: global reusable formula templates. The customer case center reads this table when using "从配方库调用".
- `formulas`: legacy tea package/export table kept for compatibility. It is not the source of the global formula library anymore and should not be used for new reusable templates.

Formula library separation:

- New global templates are saved in `formula_templates`.
- Customer prescriptions are saved only in `client_formulas`.
- The legacy hidden client id `formula_library_client` may still exist in older databases for compatibility, but new global template workflows do not depend on it.
- Legacy formula-library-like records from `formulas` are copied into `formula_templates` by the safe migration with `ON CONFLICT DO NOTHING`; old rows are not deleted automatically.

Verification data cleanup:

- Records with ids or notes containing `formula_library_verify_20260602` were created during deployment verification.
- Do not delete them without first listing the exact rows and receiving explicit confirmation.
- After confirmation, delete only matching verification rows from `formula_templates`, `client_formulas`, `formulas`, and `clients`, then run `PRAGMA integrity_check`.

Restore procedure outline:

1. Stop writes to the application during a maintenance window.
2. Copy the current database aside.
3. Copy the selected backup over `/opt/tcm-tea-studio/data/tcm_tea_studio.sqlite3`.
4. Start/restart `tcm-tea-studio`.
5. Verify login and data.

## Safe Deployment

Deployment script:

```text
/opt/tcm-tea-studio/scripts/deploy_safe.sh
```

The script performs these steps:

1. Run a SQLite backup before changing code.
2. Run `git pull --ff-only`.
3. Check Python dependencies:
   - If `requirements.txt` exists, install it with `python3 -m pip install -r requirements.txt`.
   - If it does not exist, continue because the current app uses only Python standard library modules.
4. Run Python syntax checks for `server.py` and `scripts/backup_sqlite.py`.
5. Restart only the `tcm-tea-studio` service.
6. Verify:
   - `systemctl is-active tcm-tea-studio`
   - `curl http://127.0.0.1:8080`
   - `curl -Ik https://congnet.xyz`

Run deployment:

```bash
cd /opt/tcm-tea-studio
./scripts/deploy_safe.sh
```

The script does not restart the VPS, does not touch `hysteria-server` or `hy2`, and does not delete databases or backups.

If deployment fails after pulling code, rollback without deleting data:

```bash
cd /opt/tcm-tea-studio
git log --oneline -5
git checkout <previous-known-good-commit>
systemctl restart tcm-tea-studio
systemctl is-active tcm-tea-studio
curl -fsS http://127.0.0.1:8080 >/dev/null
```

After investigating, return to `main` when ready:

```bash
cd /opt/tcm-tea-studio
git checkout main
git pull --ff-only
```

## Current Risks

- HTTPS uses a self-signed origin certificate. This works with Cloudflare `Full`, but Cloudflare `Full strict` requires a Cloudflare Origin Certificate or publicly trusted certificate.
- The stopped backup container is useful for rollback, but should not be kept forever without a retention decision.
- SQLite backups are now scheduled daily, but restores should still be tested periodically.
- The current Python server is intentionally lightweight. For higher traffic or multi-user production, consider moving behind a WSGI/ASGI server and adding structured logging.

## Suggested Next Steps

1. Generate a Cloudflare Origin Certificate and replace the current origin certificate, then switch Cloudflare SSL/TLS to `Full strict`.
2. Test restoring a SQLite backup in a maintenance window or on a separate staging copy.
3. Use `scripts/deploy_safe.sh` for routine deployments.
4. Decide a retention date for `mynginx-before-persist-20260601052515`.
5. Review [SECURITY.md](SECURITY.md) before deleting verification test data or tightening authentication.
