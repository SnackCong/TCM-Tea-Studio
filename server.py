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
SESSION_TTL_SECONDS = 60 * 60 * 12


def connect():
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


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
            """
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
        "phone": row["phone"] or "",
        "age": row["age"] or "",
        "constitution": row["constitution"],
        "concern": row["concern"] or "",
        "notes": row["notes"] or "",
    }


def row_to_formula(row):
    return {
        "id": row["id"],
        "clientId": row["client_id"],
        "name": row["name"],
        "dailyBags": row["daily_bags"],
        "days": row["days"],
        "waterMl": row["water_ml"],
        "status": row["status"],
        "usage": row["usage"] or "",
        "cautions": row["cautions"] or "",
        "ingredients": json.loads(row["ingredients_json"] or "[]"),
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


def cookie_header(token, expires=False):
    if expires:
        return f"{SESSION_COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"
    return f"{SESSION_COOKIE}={token}; Path=/; Max-Age={SESSION_TTL_SECONDS}; HttpOnly; SameSite=Lax"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith("/api/"):
            self.handle_api("GET", path)
            return
        if path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self):
        self.handle_api("POST", urlparse(self.path).path)

    def do_PUT(self):
        self.handle_api("PUT", urlparse(self.path).path)

    def end_headers(self):
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
            conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
            row = conn.execute(
                """
                SELECT users.id, users.username
                FROM sessions
                JOIN users ON users.id = sessions.user_id
                WHERE sessions.token = ? AND sessions.expires_at >= ?
                """,
                (token.value, now),
            ).fetchone()
        if not row:
            return None
        return {"id": row["id"], "username": row["username"]}

    def require_user(self):
        user = self.current_user()
        if not user:
            response_json(self, {"error": "请先登录"}, HTTPStatus.UNAUTHORIZED)
            return None
        return user

    def handle_api(self, method, path):
        try:
            if path == "/api/login" and method == "POST":
                return self.login()
            if path == "/api/logout" and method == "POST":
                return self.logout()
            if path == "/api/session" and method == "GET":
                return self.session()

            user = self.require_user()
            if not user:
                return

            if path == "/api/data" and method == "GET":
                return self.data()
            if path == "/api/demo" and method == "POST":
                return self.demo()
            if path == "/api/clients" and method == "POST":
                return self.create_client()
            if path.startswith("/api/clients/") and method == "PUT":
                return self.update_client(unquote(path.removeprefix("/api/clients/")))
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

    def session(self):
        user = self.current_user()
        if not user:
            response_json(self, {"error": "请先登录"}, HTTPStatus.UNAUTHORIZED)
            return
        response_json(self, {"user": user})

    def data(self):
        with connect() as conn:
            clients = [row_to_client(row) for row in conn.execute("SELECT * FROM clients ORDER BY updated_at DESC")]
            formulas = [row_to_formula(row) for row in conn.execute("SELECT * FROM formulas ORDER BY updated_at DESC")]
        response_json(self, {"clients": clients, "formulas": formulas})

    def create_client(self):
        payload = read_json(self)
        now = int(time.time())
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO clients (id, name, phone, age, constitution, concern, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("id") or f"client_{secrets.token_hex(8)}",
                    payload["name"],
                    payload.get("phone", ""),
                    str(payload.get("age", "")),
                    payload["constitution"],
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
                SET name = ?, phone = ?, age = ?, constitution = ?, concern = ?, notes = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    payload["name"],
                    payload.get("phone", ""),
                    str(payload.get("age", "")),
                    payload["constitution"],
                    payload.get("concern", ""),
                    payload.get("notes", ""),
                    now,
                    client_id,
                ),
            )
        response_json(self, {"ok": True})

    def create_formula(self):
        payload = read_json(self)
        now = int(time.time())
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO formulas
                (id, client_id, name, daily_bags, days, water_ml, status, usage, cautions, ingredients_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("id") or f"formula_{secrets.token_hex(8)}",
                    payload["clientId"],
                    payload["name"],
                    int(payload["dailyBags"]),
                    int(payload["days"]),
                    int(payload.get("waterMl") or 350),
                    payload.get("status") or "待复核",
                    payload.get("usage", ""),
                    payload.get("cautions", ""),
                    json.dumps(payload.get("ingredients", []), ensure_ascii=False),
                    now,
                    now,
                ),
            )
        response_json(self, {"ok": True}, HTTPStatus.CREATED)

    def update_formula(self, formula_id):
        payload = read_json(self)
        now = int(time.time())
        with connect() as conn:
            conn.execute(
                """
                UPDATE formulas
                SET client_id = ?, name = ?, daily_bags = ?, days = ?, water_ml = ?, status = ?,
                    usage = ?, cautions = ?, ingredients_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    payload["clientId"],
                    payload["name"],
                    int(payload["dailyBags"]),
                    int(payload["days"]),
                    int(payload.get("waterMl") or 350),
                    payload.get("status") or "待复核",
                    payload.get("usage", ""),
                    payload.get("cautions", ""),
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
                INSERT INTO clients (id, name, phone, age, constitution, concern, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    client_id,
                    "林女士",
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
