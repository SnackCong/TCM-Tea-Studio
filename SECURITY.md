# Security Notes

Last checked: 2026-06-01

## Current Auth Status

API endpoints that expose or mutate business data are protected by the server-side session check:

- `GET /api/data`
- `POST /api/clients`
- `PUT /api/clients/<id>`
- `POST /api/client-sessions`
- `POST /api/client-formulas`
- `POST /api/formulas`
- `PUT /api/formulas/<id>`

Anonymous API checks returned `401` with:

```json
{"error": "请先登录"}
```

Static assets such as `/`, `/index.html`, `/app.js`, and `/styles.css` are public. The browser UI displays a login overlay and then loads business data only after `/api/session` succeeds. This means unauthenticated visitors can download the app shell, but they cannot retrieve customer, follow-up, formula, or prescription data through the API.

## Current Risk Points

- Static business UI code is public because this is a single-page app served before login.
- The current login protection is API-centered, not route-centered.
- There is one admin account model; no per-user roles or audit log yet.
- Session cookies are `HttpOnly`, `SameSite=Lax`, and `Secure` in the default production configuration. For local HTTP-only development, set `TCM_COOKIE_SECURE=0`.
- Current Cloudflare origin certificate is self-signed. It works with Cloudflare Full, but Full strict should use Cloudflare Origin CA or Let's Encrypt.

## Minimal Security Hardening Plan

Recommended next minimal changes, without redesigning the auth system:

1. Keep all customer, follow-up, tea formula, and export data behind authenticated `/api/*` endpoints.
2. Add a `/api/bootstrap` or `/api/session`-gated app initialization path that renders business views only after a valid session.
3. Add a server-side protected HTML route for the app shell, or split unauthenticated login HTML from authenticated app HTML.
4. Add a small audit trail table for business mutations: customer create/update, follow-up create, tea formula create.

## Test Data

The following records were created during deployment verification and should be treated as test data:

Customers:

- `client_verify_20260601` — `测试客户`
- `client_visit_verify_20260601_b` — `回访隔离客户`

Follow-up records:

- `visit_verify_20260601_a`
- `visit_verify_20260601_b`

Tea formula records:

- `client_formula_verify_20260601_a`
- `client_formula_verify_20260601_b`

These are already marked by their IDs and notes with `verify`, `测试`, or `验证`. They were intentionally left in place for traceability.

Latest deletion preview from `2026-06-01`:

Customers:

- `client_verify_20260601`: `测试客户`, phone `13900001111`, notes `部署验证记录`
- `client_visit_verify_20260601_b`: `回访隔离客户`, phone `13900002222`, notes `回访隔离验证客户`

Follow-up records:

- `visit_verify_20260601_a`: client `client_verify_20260601`, notes `客户A回访记录`
- `visit_verify_20260601_b`: client `client_visit_verify_20260601_b`, notes `客户B回访记录`

Tea formula records:

- `client_formula_verify_20260601_a`: client `client_verify_20260601`, formula `测试安神茶方A`
- `client_formula_verify_20260601_b`: client `client_visit_verify_20260601_b`, formula `测试益气茶方B`

Deletion status:

- Pending explicit final confirmation.
- No test data has been deleted yet.

## Safe Test Data Deletion Plan

Do not run this without explicit confirmation.

Before deletion:

```bash
TCM_DB_PATH=/opt/tcm-tea-studio/data/tcm_tea_studio.sqlite3 \
TCM_BACKUP_DIR=/root/tcm-tea-studio-backups/sqlite \
TCM_BACKUP_RETENTION_DAYS=14 \
/usr/bin/python3 /opt/tcm-tea-studio/scripts/backup_sqlite.py
```

Preview records:

```bash
python3 - <<'PY'
import sqlite3
con = sqlite3.connect('/opt/tcm-tea-studio/data/tcm_tea_studio.sqlite3')
for table in ('client_formulas', 'client_sessions', 'clients'):
    print(table)
    id_col = 'id'
    for row in con.execute(f"select * from {table} where id like '%verify%'"):
        print(row)
con.close()
PY
```

Deletion SQL:

```sql
BEGIN;
DELETE FROM client_formulas
WHERE id IN ('client_formula_verify_20260601_a', 'client_formula_verify_20260601_b');

DELETE FROM client_sessions
WHERE id IN ('visit_verify_20260601_a', 'visit_verify_20260601_b');

DELETE FROM clients
WHERE id IN ('client_verify_20260601', 'client_visit_verify_20260601_b');
COMMIT;
```

Verify after deletion:

```sql
SELECT COUNT(*) FROM clients WHERE id LIKE '%verify%';
SELECT COUNT(*) FROM client_sessions WHERE id LIKE '%verify%';
SELECT COUNT(*) FROM client_formulas WHERE id LIKE '%verify%';
```

Rollback path:

- Restore from the backup created immediately before deletion.
- Do not overwrite production DB without a maintenance window and a fresh backup.
