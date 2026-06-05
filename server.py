#!/usr/bin/env python3
import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import sys
import time
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DB_PATH = Path(os.environ.get("TCM_DB_PATH", DATA_DIR / "tcm_tea_studio.sqlite3"))
SESSION_COOKIE = "tcm_session"
SESSION_TTL_SECONDS = int(os.environ.get("TCM_SESSION_TTL_SECONDS", "1800"))
COOKIE_SECURE = os.environ.get("TCM_COOKIE_SECURE", "1") != "0"
LEGACY_FORMULA_LIBRARY_CLIENT_ID = "formula_library_client"


def connect():
    DATA_DIR.mkdir(exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_column(conn, table, column, definition):
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db():
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS clients (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                gender TEXT,
                phone TEXT,
                age TEXT,
                constitution TEXT NOT NULL,
                concern TEXT,
                notes TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS formulas (
                id TEXT PRIMARY KEY,
                client_id TEXT NOT NULL,
                name TEXT NOT NULL,
                daily_bags INTEGER NOT NULL,
                days INTEGER NOT NULL,
                water_ml INTEGER NOT NULL,
                status TEXT NOT NULL,
                usage TEXT,
                cautions TEXT,
                ingredients_json TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS client_sessions (
                id TEXT PRIMARY KEY,
                client_id TEXT NOT NULL,
                visit_date TEXT NOT NULL,
                complaint_change TEXT,
                sleep TEXT,
                diet TEXT,
                stool TEXT,
                tongue TEXT,
                pulse TEXT,
                advice TEXT,
                notes TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS client_formulas (
                id TEXT PRIMARY KEY,
                client_id TEXT NOT NULL,
                client_session_id TEXT,
                formula_date TEXT NOT NULL,
                name TEXT NOT NULL,
                herbs TEXT,
                dosages TEXT,
                preparation TEXT,
                period TEXT,
                modifications TEXT,
                cautions TEXT,
                notes TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
                FOREIGN KEY (client_session_id) REFERENCES client_sessions(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS client_todos (
                id TEXT PRIMARY KEY,
                client_id TEXT NOT NULL,
                content TEXT NOT NULL,
                reminder_date TEXT,
                is_done INTEGER NOT NULL DEFAULT 0,
                notes TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS formula_templates (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT,
                pattern TEXT,
                audience TEXT,
                composition TEXT,
                default_dosage TEXT,
                usage TEXT,
                modifications TEXT,
                cautions TEXT,
                taste_notes TEXT,
                cost_notes TEXT,
                notes TEXT,
                package_count INTEGER NOT NULL DEFAULT 14,
                unit_total_grams REAL NOT NULL DEFAULT 0,
                total_grams REAL NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );
            """
        )
        ensure_column(conn, "clients", "gender", "TEXT")
        ensure_column(conn, "formulas", "category", "TEXT")
        ensure_column(conn, "formulas", "pattern", "TEXT")
        ensure_column(conn, "formulas", "audience", "TEXT")
        ensure_column(conn, "formulas", "composition", "TEXT")
        ensure_column(conn, "formulas", "default_dosage", "TEXT")
        ensure_column(conn, "formulas", "modifications", "TEXT")
        ensure_column(conn, "formulas", "taste_notes", "TEXT")
        ensure_column(conn, "formulas", "cost_notes", "TEXT")
        ensure_column(conn, "formulas", "notes", "TEXT")
        ensure_column(conn, "formula_templates", "package_count", "INTEGER NOT NULL DEFAULT 14")
        ensure_column(conn, "formula_templates", "unit_total_grams", "REAL NOT NULL DEFAULT 0")
        ensure_column(conn, "formula_templates", "total_grams", "REAL NOT NULL DEFAULT 0")
        conn.execute(
            """
            INSERT INTO formula_templates
            (id, name, category, pattern, audience, composition, default_dosage, usage,
             modifications, cautions, taste_notes, cost_notes, notes, created_at, updated_at)
            SELECT
                id,
                name,
                COALESCE(category, ''),
                COALESCE(pattern, ''),
                COALESCE(audience, ''),
                COALESCE(composition, ''),
                COALESCE(default_dosage, ''),
                COALESCE(usage, ''),
                COALESCE(modifications, ''),
                COALESCE(cautions, ''),
                COALESCE(taste_notes, ''),
                COALESCE(cost_notes, ''),
                COALESCE(notes, ''),
                created_at,
                updated_at
            FROM formulas
            WHERE client_id = ? OR id LIKE 'formula_library_verify_%' OR COALESCE(notes, '') LIKE '%formula_library_verify_20260602%'
            ON CONFLICT(id) DO NOTHING
            """,
            (LEGACY_FORMULA_LIBRARY_CLIENT_ID,),
        )


def password_hash(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 240000)
    return "pbkdf2_sha256$240000${}${}".format(
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(password, stored):
    try:
        scheme, rounds, salt_b64, digest_b64 = stored.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(rounds))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def create_admin(username, password):
    init_db()
    now = int(time.time())
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO users (id, username, password_hash, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET password_hash = excluded.password_hash
            """,
            (f"user_{secrets.token_hex(8)}", username, password_hash(password), now),
        )
    print(f"管理员账号已创建/更新：{username}")


def row_to_client(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "gender": row["gender"] or "",
        "phone": row["phone"] or "",
        "age": row["age"] or "",
        "constitution": row["constitution"],
        "concern": row["concern"] or "",
        "notes": row["notes"] or "",
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def row_to_formula(row):
    ingredients = json.loads(row["ingredients_json"] or "[]")
    composition = row["composition"] or "、".join(item.get("name", "") for item in ingredients if item.get("name"))
    default_dosage = row["default_dosage"] or "，".join(
        f"{item.get('name', '')}{item.get('grams', '')}g" for item in ingredients if item.get("name") and item.get("grams") is not None
    )
    return {
        "id": row["id"],
        "clientId": row["client_id"],
        "isLibrary": row["client_id"] == LEGACY_FORMULA_LIBRARY_CLIENT_ID,
        "isLegacy": True,
        "name": row["name"],
        "category": row["category"] or "",
        "pattern": row["pattern"] or "",
        "audience": row["audience"] or "",
        "composition": composition,
        "defaultDosage": default_dosage,
        "dailyBags": row["daily_bags"],
        "days": row["days"],
        "waterMl": row["water_ml"],
        "status": row["status"],
        "usage": row["usage"] or "",
        "modifications": row["modifications"] or "",
        "cautions": row["cautions"] or "",
        "tasteNotes": row["taste_notes"] or "",
        "costNotes": row["cost_notes"] or "",
        "notes": row["notes"] or "",
        "ingredients": ingredients,
    }


def row_to_formula_template(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "category": row["category"] or "",
        "pattern": row["pattern"] or "",
        "audience": row["audience"] or "",
        "composition": row["composition"] or "",
        "defaultDosage": row["default_dosage"] or "",
        "usage": row["usage"] or "",
        "modifications": row["modifications"] or "",
        "cautions": row["cautions"] or "",
        "tasteNotes": row["taste_notes"] or "",
        "costNotes": row["cost_notes"] or "",
        "notes": row["notes"] or "",
        "packageCount": row["package_count"],
        "unitTotalGrams": row["unit_total_grams"],
        "totalGrams": row["total_grams"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def row_to_client_session(row):
    return {
        "id": row["id"],
        "clientId": row["client_id"],
        "visitDate": row["visit_date"],
        "complaintChange": row["complaint_change"] or "",
        "sleep": row["sleep"] or "",
        "diet": row["diet"] or "",
        "stool": row["stool"] or "",
        "tongue": row["tongue"] or "",
        "pulse": row["pulse"] or "",
        "advice": row["advice"] or "",
        "notes": row["notes"] or "",
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def row_to_client_formula(row):
    return {
        "id": row["id"],
        "clientId": row["client_id"],
        "clientSessionId": row["client_session_id"] or "",
        "formulaDate": row["formula_date"],
        "name": row["name"],
        "herbs": row["herbs"] or "",
        "dosages": row["dosages"] or "",
        "preparation": row["preparation"] or "",
        "period": row["period"] or "",
        "modifications": row["modifications"] or "",
        "cautions": row["cautions"] or "",
        "notes": row["notes"] or "",
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def row_to_client_todo(row):
    return {
        "id": row["id"],
        "clientId": row["client_id"],
        "content": row["content"],
        "reminderDate": row["reminder_date"] or "",
        "isDone": bool(row["is_done"]),
        "notes": row["notes"] or "",
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def read_json(handler):
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length <= 0:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8"))


def response_json(handler, data, status=HTTPStatus.OK, headers=None):
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    for key, value in (headers or {}).items():
        handler.send_header(key, value)
    handler.end_headers()
    handler.wfile.write(body)


def redirect(handler, location, headers=None):
    handler.send_response(HTTPStatus.FOUND)
    handler.send_header("Location", location)
    for key, value in (headers or {}).items():
        handler.send_header(key, value)
    handler.end_headers()


def cookie_header(token, expires=False):
    secure = "; Secure" if COOKIE_SECURE else ""
    if expires:
        return f"{SESSION_COOKIE}=; Path=/; Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly; SameSite=Lax{secure}"
    return f"{SESSION_COOKIE}={token}; Path=/; Max-Age={SESSION_TTL_SECONDS}; HttpOnly; SameSite=Lax{secure}"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith("/api/"):
            self.handle_api("GET", path)
            return
        app_routes = {"/app", "/dashboard", "/clients", "/client-detail", "/formulas", "/export", "/index.html"}
        protected_assets = {"/app.js"}

        if path in ("/", "/login", "/login.html"):
            if self.current_user():
                redirect(self, "/app")
                return
            self.path = "/login.html"
            super().do_GET()
            return

        if path in app_routes or path.startswith("/app/") or path in protected_assets:
            if not self.current_user():
                redirect(self, "/login", headers=self.clear_cookie_header_if_present())
                return
            if path in protected_assets:
                self.path = path
            else:
                self.path = "/index.html"
            super().do_GET()
            return

        super().do_GET()

    def do_POST(self):
        self.handle_api("POST", urlparse(self.path).path)

    def do_PUT(self):
        self.handle_api("PUT", urlparse(self.path).path)

    def end_headers(self):
        path = urlparse(self.path).path
        no_store_paths = {
            "/",
            "/login",
            "/login.html",
            "/app",
            "/index.html",
            "/app.js",
            "/login.js",
        }
        if path in no_store_paths or path.startswith("/api/"):
            self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        super().end_headers()

    def current_user(self):
        cookie = SimpleCookie(self.headers.get("Cookie"))
        token = cookie.get(SESSION_COOKIE)
        if not token:
            return None
        now = int(time.time())
        with connect() as conn:
            conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
            row = conn.execute(
                """
                SELECT users.id, users.username
                FROM sessions
                JOIN users ON users.id = sessions.user_id
                WHERE sessions.token = ? AND sessions.expires_at > ?
                """,
                (token.value, now),
            ).fetchone()
        if not row:
            return None
        return {"id": row["id"], "username": row["username"]}

    def clear_cookie_header_if_present(self):
        cookie = SimpleCookie(self.headers.get("Cookie"))
        if cookie.get(SESSION_COOKIE):
            return {"Set-Cookie": cookie_header("", expires=True)}
        return {}

    def require_user(self):
        user = self.current_user()
        if not user:
            response_json(
                self,
                {"error": "请先登录"},
                HTTPStatus.UNAUTHORIZED,
                headers=self.clear_cookie_header_if_present(),
            )
            return None
        return user

    def handle_api(self, method, path):
        try:
            if path == "/api/login" and method == "POST":
                return self.login()
            if path == "/api/logout" and method == "POST":
                return self.logout()
            if path in ("/api/session", "/api/me") and method == "GET":
                return self.session()

            user = self.require_user()
            if not user:
                return

            if path == "/api/data" and method == "GET":
                return self.data()
            if path == "/api/change-password" and method == "POST":
                return self.change_password(user)
            if path == "/api/demo" and method == "POST":
                return self.demo()
            if path == "/api/clients" and method == "POST":
                return self.create_client()
            if path.startswith("/api/clients/") and method == "PUT":
                return self.update_client(unquote(path.removeprefix("/api/clients/")))
            if path == "/api/client-sessions" and method == "POST":
                return self.create_client_session()
            if path == "/api/client-formulas" and method == "POST":
                return self.create_client_formula()
            if path == "/api/client-todos" and method == "POST":
                return self.create_client_todo()
            if path.startswith("/api/client-todos/") and method == "PUT":
                return self.update_client_todo(unquote(path.removeprefix("/api/client-todos/")))
            if path == "/api/formula-templates" and method == "POST":
                return self.create_formula_template()
            if path.startswith("/api/formula-templates/") and method == "PUT":
                return self.update_formula_template(unquote(path.removeprefix("/api/formula-templates/")))
            if path == "/api/formulas" and method == "POST":
                return self.create_formula()
            if path.startswith("/api/formulas/") and method == "PUT":
                return self.update_formula(unquote(path.removeprefix("/api/formulas/")))

            response_json(self, {"error": "接口不存在"}, HTTPStatus.NOT_FOUND)
        except json.JSONDecodeError:
            response_json(self, {"error": "JSON 格式错误"}, HTTPStatus.BAD_REQUEST)
        except sqlite3.IntegrityError as exc:
            response_json(self, {"error": f"数据保存失败：{exc}"}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            response_json(self, {"error": f"服务器错误：{exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def login(self):
        payload = read_json(self)
        username = (payload.get("username") or "").strip()
        password = payload.get("password") or ""
        with connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            if not row or not verify_password(password, row["password_hash"]):
                response_json(self, {"error": "账号或密码错误"}, HTTPStatus.UNAUTHORIZED)
                return
            token = secrets.token_urlsafe(32)
            now = int(time.time())
            conn.execute(
                "INSERT INTO sessions (token, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
                (token, row["id"], now + SESSION_TTL_SECONDS, now),
            )
        response_json(
            self,
            {"user": {"id": row["id"], "username": row["username"]}},
            headers={"Set-Cookie": cookie_header(token)},
        )

    def logout(self):
        cookie = SimpleCookie(self.headers.get("Cookie"))
        token = cookie.get(SESSION_COOKIE)
        if token:
            with connect() as conn:
                conn.execute("DELETE FROM sessions WHERE token = ?", (token.value,))
        response_json(self, {"ok": True}, headers={"Set-Cookie": cookie_header("", expires=True)})

    def change_password(self, user):
        payload = read_json(self)
        current_password = payload.get("currentPassword") or ""
        new_password = payload.get("newPassword") or ""
        confirm_password = payload.get("confirmPassword") or ""

        if not current_password:
            response_json(self, {"error": "请输入当前密码"}, HTTPStatus.BAD_REQUEST)
            return
        if not new_password:
            response_json(self, {"error": "请输入新密码"}, HTTPStatus.BAD_REQUEST)
            return
        if len(new_password) < 8:
            response_json(self, {"error": "新密码至少需要 8 位"}, HTTPStatus.BAD_REQUEST)
            return
        if new_password != confirm_password:
            response_json(self, {"error": "两次输入的新密码不一致"}, HTTPStatus.BAD_REQUEST)
            return
        if hmac.compare_digest(current_password, new_password):
            response_json(self, {"error": "新密码不能和当前密码相同"}, HTTPStatus.BAD_REQUEST)
            return

        with connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
            if not row or not verify_password(current_password, row["password_hash"]):
                response_json(self, {"error": "当前密码不正确"}, HTTPStatus.BAD_REQUEST)
                return
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (password_hash(new_password), user["id"]),
            )
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user["id"],))
        response_json(
            self,
            {"ok": True, "message": "密码已修改，请重新登录"},
            headers={"Set-Cookie": cookie_header("", expires=True)},
        )

    def session(self):
        user = self.current_user()
        if not user:
            response_json(
                self,
                {"error": "请先登录"},
                HTTPStatus.UNAUTHORIZED,
                headers=self.clear_cookie_header_if_present(),
            )
            return
        response_json(self, {"user": user})

    def data(self):
        with connect() as conn:
            clients = [
                row_to_client(row)
                for row in conn.execute(
                    "SELECT * FROM clients WHERE id != ? ORDER BY updated_at DESC",
                    (LEGACY_FORMULA_LIBRARY_CLIENT_ID,),
                )
            ]
            formulas = [row_to_formula(row) for row in conn.execute("SELECT * FROM formulas ORDER BY updated_at DESC")]
            formula_templates = [
                row_to_formula_template(row)
                for row in conn.execute("SELECT * FROM formula_templates ORDER BY updated_at DESC")
            ]
            client_sessions = [
                row_to_client_session(row)
                for row in conn.execute("SELECT * FROM client_sessions ORDER BY visit_date DESC, created_at DESC")
            ]
            client_formulas = [
                row_to_client_formula(row)
                for row in conn.execute("SELECT * FROM client_formulas ORDER BY formula_date DESC, created_at DESC")
            ]
            client_todos = [
                row_to_client_todo(row)
                for row in conn.execute(
                    """
                    SELECT * FROM client_todos
                    ORDER BY is_done ASC, reminder_date IS NULL ASC, reminder_date ASC, created_at DESC
                    """
                )
            ]
        response_json(
            self,
            {
                "clients": clients,
                "formulas": formulas,
                "formulaTemplates": formula_templates,
                "clientSessions": client_sessions,
                "clientFormulas": client_formulas,
                "clientTodos": client_todos,
            },
        )

    def create_client(self):
        payload = read_json(self)
        now = int(time.time())
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO clients (id, name, gender, phone, age, constitution, concern, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("id") or f"client_{secrets.token_hex(8)}",
                    payload["name"],
                    payload.get("gender", ""),
                    payload.get("phone", ""),
                    str(payload.get("age", "")),
                    payload.get("constitution") or "未分类",
                    payload.get("concern", ""),
                    payload.get("notes", ""),
                    now,
                    now,
                ),
            )
        response_json(self, {"ok": True}, HTTPStatus.CREATED)

    def update_client(self, client_id):
        payload = read_json(self)
        now = int(time.time())
        with connect() as conn:
            conn.execute(
                """
                UPDATE clients
                SET name = ?, gender = ?, phone = ?, age = ?, constitution = ?, concern = ?, notes = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    payload["name"],
                    payload.get("gender", ""),
                    payload.get("phone", ""),
                    str(payload.get("age", "")),
                    payload.get("constitution") or "未分类",
                    payload.get("concern", ""),
                    payload.get("notes", ""),
                    now,
                    client_id,
                ),
            )
        response_json(self, {"ok": True})

    def create_client_session(self):
        payload = read_json(self)
        now = int(time.time())
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO client_sessions
                (id, client_id, visit_date, complaint_change, sleep, diet, stool, tongue, pulse, advice, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("id") or f"visit_{secrets.token_hex(8)}",
                    payload["clientId"],
                    payload["visitDate"],
                    payload.get("complaintChange", ""),
                    payload.get("sleep", ""),
                    payload.get("diet", ""),
                    payload.get("stool", ""),
                    payload.get("tongue", ""),
                    payload.get("pulse", ""),
                    payload.get("advice", ""),
                    payload.get("notes", ""),
                    now,
                    now,
                ),
            )
        response_json(self, {"ok": True}, HTTPStatus.CREATED)

    def create_formula(self):
        payload = read_json(self)
        now = int(time.time())
        ingredients = payload.get("ingredients", [])
        client_id = payload.get("clientId")
        if not client_id:
            response_json(self, {"error": "旧茶包方案必须关联客户；通用配方请使用 formula_templates。"}, HTTPStatus.BAD_REQUEST)
            return
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO formulas
                (id, client_id, name, category, pattern, audience, composition, default_dosage,
                 daily_bags, days, water_ml, status, usage, modifications, cautions, taste_notes,
                 cost_notes, notes, ingredients_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("id") or f"formula_{secrets.token_hex(8)}",
                    client_id,
                    payload["name"],
                    payload.get("category", ""),
                    payload.get("pattern", ""),
                    payload.get("audience", ""),
                    payload.get("composition", ""),
                    payload.get("defaultDosage", ""),
                    int(payload.get("dailyBags") or 1),
                    int(payload.get("days") or 1),
                    int(payload.get("waterMl") or 350),
                    payload.get("status") or "待复核",
                    payload.get("usage", ""),
                    payload.get("modifications", ""),
                    payload.get("cautions", ""),
                    payload.get("tasteNotes", ""),
                    payload.get("costNotes", ""),
                    payload.get("notes", ""),
                    json.dumps(ingredients, ensure_ascii=False),
                    now,
                    now,
                ),
            )
        response_json(self, {"ok": True}, HTTPStatus.CREATED)

    def create_client_formula(self):
        payload = read_json(self)
        now = int(time.time())
        session_id = payload.get("clientSessionId") or None
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO client_formulas
                (id, client_id, client_session_id, formula_date, name, herbs, dosages, preparation, period,
                 modifications, cautions, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("id") or f"client_formula_{secrets.token_hex(8)}",
                    payload["clientId"],
                    session_id,
                    payload["formulaDate"],
                    payload["name"],
                    payload.get("herbs", ""),
                    payload.get("dosages", ""),
                    payload.get("preparation", ""),
                    payload.get("period", ""),
                    payload.get("modifications", ""),
                    payload.get("cautions", ""),
                    payload.get("notes", ""),
                    now,
                    now,
                ),
            )
        response_json(self, {"ok": True}, HTTPStatus.CREATED)

    def create_client_todo(self):
        payload = read_json(self)
        now = int(time.time())
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO client_todos
                (id, client_id, content, reminder_date, is_done, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("id") or f"client_todo_{secrets.token_hex(8)}",
                    payload["clientId"],
                    payload["content"],
                    payload.get("reminderDate", ""),
                    1 if payload.get("isDone") else 0,
                    payload.get("notes", ""),
                    now,
                    now,
                ),
            )
        response_json(self, {"ok": True}, HTTPStatus.CREATED)

    def update_client_todo(self, todo_id):
        payload = read_json(self)
        now = int(time.time())
        with connect() as conn:
            conn.execute(
                """
                UPDATE client_todos
                SET content = ?, reminder_date = ?, is_done = ?, notes = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    payload["content"],
                    payload.get("reminderDate", ""),
                    1 if payload.get("isDone") else 0,
                    payload.get("notes", ""),
                    now,
                    todo_id,
                ),
            )
        response_json(self, {"ok": True})

    def create_formula_template(self):
        payload = read_json(self)
        now = int(time.time())
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO formula_templates
                (id, name, category, pattern, audience, composition, default_dosage, usage,
                 modifications, cautions, taste_notes, cost_notes, notes, package_count,
                 unit_total_grams, total_grams, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("id") or f"formula_template_{secrets.token_hex(8)}",
                    payload["name"],
                    payload.get("category", ""),
                    payload.get("pattern", ""),
                    payload.get("audience", ""),
                    payload.get("composition", ""),
                    payload.get("defaultDosage", ""),
                    payload.get("usage", ""),
                    payload.get("modifications", ""),
                    payload.get("cautions", ""),
                    payload.get("tasteNotes", ""),
                    payload.get("costNotes", ""),
                    payload.get("notes", ""),
                    int(payload.get("packageCount") or 14),
                    float(payload.get("unitTotalGrams") or 0),
                    float(payload.get("totalGrams") or 0),
                    now,
                    now,
                ),
            )
        response_json(self, {"ok": True}, HTTPStatus.CREATED)

    def update_formula_template(self, template_id):
        payload = read_json(self)
        now = int(time.time())
        with connect() as conn:
            conn.execute(
                """
                UPDATE formula_templates
                SET name = ?, category = ?, pattern = ?, audience = ?, composition = ?,
                    default_dosage = ?, usage = ?, modifications = ?, cautions = ?,
                    taste_notes = ?, cost_notes = ?, notes = ?, package_count = ?,
                    unit_total_grams = ?, total_grams = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    payload["name"],
                    payload.get("category", ""),
                    payload.get("pattern", ""),
                    payload.get("audience", ""),
                    payload.get("composition", ""),
                    payload.get("defaultDosage", ""),
                    payload.get("usage", ""),
                    payload.get("modifications", ""),
                    payload.get("cautions", ""),
                    payload.get("tasteNotes", ""),
                    payload.get("costNotes", ""),
                    payload.get("notes", ""),
                    int(payload.get("packageCount") or 14),
                    float(payload.get("unitTotalGrams") or 0),
                    float(payload.get("totalGrams") or 0),
                    now,
                    template_id,
                ),
            )
        response_json(self, {"ok": True})

    def update_formula(self, formula_id):
        payload = read_json(self)
        now = int(time.time())
        client_id = payload.get("clientId")
        if not client_id:
            response_json(self, {"error": "旧茶包方案必须关联客户；通用配方请使用 formula_templates。"}, HTTPStatus.BAD_REQUEST)
            return
        with connect() as conn:
            conn.execute(
                """
                UPDATE formulas
                SET client_id = ?, name = ?, category = ?, pattern = ?, audience = ?, composition = ?,
                    default_dosage = ?, daily_bags = ?, days = ?, water_ml = ?, status = ?,
                    usage = ?, modifications = ?, cautions = ?, taste_notes = ?, cost_notes = ?,
                    notes = ?, ingredients_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    client_id,
                    payload["name"],
                    payload.get("category", ""),
                    payload.get("pattern", ""),
                    payload.get("audience", ""),
                    payload.get("composition", ""),
                    payload.get("defaultDosage", ""),
                    int(payload.get("dailyBags") or 1),
                    int(payload.get("days") or 1),
                    int(payload.get("waterMl") or 350),
                    payload.get("status") or "待复核",
                    payload.get("usage", ""),
                    payload.get("modifications", ""),
                    payload.get("cautions", ""),
                    payload.get("tasteNotes", ""),
                    payload.get("costNotes", ""),
                    payload.get("notes", ""),
                    json.dumps(payload.get("ingredients", []), ensure_ascii=False),
                    now,
                    formula_id,
                ),
            )
        response_json(self, {"ok": True})

    def demo(self):
        with connect() as conn:
            exists = conn.execute("SELECT COUNT(*) AS count FROM clients").fetchone()["count"]
            if exists:
                response_json(self, {"ok": True, "skipped": True})
                return
            now = int(time.time())
            client_id = f"client_{secrets.token_hex(8)}"
            formula_id = f"formula_{secrets.token_hex(8)}"
            conn.execute(
                """
                INSERT INTO clients (id, name, gender, phone, age, constitution, concern, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    client_id,
                    "林女士",
                    "女",
                    "13800000000",
                    "36",
                    "痰湿质",
                    "困倦乏力，饭后腹胀，舌苔偏腻。",
                    "经期量多时暂停。对薏苡仁不适者调整。",
                    now,
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO formulas
                (id, client_id, name, daily_bags, days, water_ml, status, usage, cautions, ingredients_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    formula_id,
                    client_id,
                    "健脾祛湿代茶饮",
                    2,
                    7,
                    350,
                    "待复核",
                    "每日2包，饭后温饮，可反复冲泡至味淡。",
                    "孕期、哺乳期及正在服药者需先咨询专业人员。",
                    json.dumps(
                        [
                            {"name": "茯苓", "grams": 3},
                            {"name": "陈皮", "grams": 2},
                            {"name": "炒薏苡仁", "grams": 5},
                            {"name": "荷叶", "grams": 1.5},
                        ],
                        ensure_ascii=False,
                    ),
                    now,
                    now,
                ),
            )
        response_json(self, {"ok": True}, HTTPStatus.CREATED)


def run_server():
    init_db()
    host = os.environ.get("TCM_HOST", "127.0.0.1")
    port = int(os.environ.get("TCM_PORT", "8080"))
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"TCM Tea Studio running at http://{host}:{port}")
    httpd.serve_forever()


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "init-admin":
        if len(sys.argv) != 4:
            print("用法：python3 server.py init-admin 用户名 密码")
            sys.exit(1)
        create_admin(sys.argv[2], sys.argv[3])
    else:
        run_server()
