# Security Notes

Last checked: 2026-06-03

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

The login page and business app shell are separated at the server route level:

- Unauthenticated `GET /` and `GET /login` return `login.html`.
- Unauthenticated business routes such as `/app`, `/clients`, `/formulas`, `/export`, `/index.html`, and `/app.js` redirect to `/login`.
- Authenticated `GET /` redirects to `/app`, and `/app` serves the business app shell.
- Authenticated `/app.js` is served as JavaScript, not as the app shell HTML, so the front end can initialize the current user before enabling business controls.
- Current-user checks are available through both `/api/session` and `/api/me`; browser requests use `credentials: "include"` so the session cookie is sent consistently for `/app` and `/api/*`.
- Login/app HTML, business scripts, and API responses send `Cache-Control: no-store`; the app shell loads a versioned `app.js` URL to avoid stale edge caches serving the wrong asset after auth-route changes.
- Login sessions expire after `1800` seconds by default. The browser cookie uses `Max-Age=1800`, and every protected page/API request also checks the server-side `sessions.expires_at` value.
- `POST /api/logout` deletes the current server-side session and clears the session cookie with `Max-Age=0` and an expired `Expires` value.
- Inside the authenticated app, protected API `401` responses and save actions with missing in-memory user state open a local re-login modal instead of navigating away. The page is not refreshed, unsaved form input remains in place, and the failed request is retried after `/api/login` plus `/api/me` confirm the admin session.
- `/app` business flows must not call `/login` directly on session expiry. Direct login-page navigation is reserved for initial unauthenticated page loads, explicit re-login cancellation, and active logout.
- Session-expiry verification uses the local CLI helper `scripts/expire_session.py`; no public test endpoint is exposed.

This prevents the customer, case-center, formula-library, and export UI shell from flashing before the login check completes. Business data still remains protected by authenticated `/api/*` endpoints.

## Current Risk Points

- There is one admin account model; no per-user roles or audit log yet.
- Session cookies are `HttpOnly`, `SameSite=Lax`, `Max-Age=1800`, and `Secure` in the default production configuration. For local HTTP-only development, set `TCM_COOKIE_SECURE=0`.
- Current Cloudflare origin certificate is self-signed. It works with Cloudflare Full, but Full strict should use Cloudflare Origin CA or Let's Encrypt.

## Minimal Security Hardening Plan

Recommended next minimal changes, without redesigning the auth system:

1. Keep all customer, follow-up, tea formula, and export data behind authenticated `/api/*` endpoints.
2. Keep login HTML separate from the authenticated app shell.
3. Add a small audit trail table for business mutations: customer create/update, follow-up create, tea formula create.

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

These were marked by their IDs and notes with `verify`, `测试`, or `验证`.

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

- Deleted on `2026-06-02` after explicit confirmation.
- Pre-deletion backup: `/root/tcm-tea-studio-backups/sqlite/tcm_tea_studio_20260602-100955.sqlite3`.
- Deleted rows: `2` from `client_formulas`, `2` from `client_sessions`, and `2` from `clients`.
- Post-deletion `PRAGMA integrity_check`: `ok`.
- Post-deletion table counts: `clients=0`, `client_sessions=0`, `client_formulas=0`.
- Business API verification after deletion: authenticated `GET /api/data` returned valid empty arrays for `clients`, `clientSessions`, and `clientFormulas`; anonymous `GET /api/data` still returned `401`.

## Safe Test Data Deletion Plan

This plan was executed on `2026-06-02` after explicit confirmation. Keep it as the audit trail for what was removed.

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
