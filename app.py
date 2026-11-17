import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from flask import Flask, jsonify, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "development-only-secret"),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)
DB_PATH = os.environ.get("DB_PATH", "/data/share.db")

def db():
    directory = os.path.dirname(DB_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@contextmanager
def db_session():
    conn = db()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with db_session() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          username TEXT COLLATE NOCASE NOT NULL UNIQUE,
          display_name TEXT NOT NULL,
          password_hash TEXT NOT NULL,
          role TEXT NOT NULL DEFAULT 'user',
          created_at TEXT NOT NULL)""")
        user_columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "role" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
        conn.execute("""CREATE TABLE IF NOT EXISTS items (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          title TEXT NOT NULL, description TEXT NOT NULL,
          category TEXT NOT NULL, location TEXT NOT NULL,
          giver TEXT NOT NULL, owner_user_id INTEGER,
          image_url TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'open',
          claimant TEXT, claimant_user_id INTEGER,
          claim_start_at TEXT, claimed_at TEXT,
          created_at TEXT NOT NULL)""")
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(items)").fetchall()}
        if "claim_start_at" not in columns:
            conn.execute("ALTER TABLE items ADD COLUMN claim_start_at TEXT")
        if "claimant_user_id" not in columns:
            conn.execute("ALTER TABLE items ADD COLUMN claimant_user_id INTEGER")
        if "owner_user_id" not in columns:
            conn.execute("ALTER TABLE items ADD COLUMN owner_user_id INTEGER")
        if "claimed_at" not in columns:
            conn.execute("ALTER TABLE items ADD COLUMN claimed_at TEXT")
        admin_username = os.environ.get("ADMIN_USERNAME", "").strip()
        admin_password = os.environ.get("ADMIN_PASSWORD", "")
        admin_display_name = os.environ.get("ADMIN_DISPLAY_NAME", "관리자").strip() or "관리자"
        if admin_username and admin_password:
            password_hash = generate_password_hash(admin_password)
            existing = conn.execute("SELECT id FROM users WHERE username=?", (admin_username,)).fetchone()
            if existing:
                conn.execute("""UPDATE users SET display_name=?, password_hash=?, role='admin'
                              WHERE id=?""", (admin_display_name, password_hash, existing["id"]))
            else:
                conn.execute("""INSERT INTO users(username,display_name,password_hash,role,created_at)
                              VALUES(?,?,?,'admin',?)""",
                             (admin_username, admin_display_name, password_hash,
                              datetime.now(timezone.utc).isoformat()))

def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    with db_session() as conn:
        row = conn.execute("SELECT id, username, display_name, role FROM users WHERE id=?", (user_id,)).fetchone()
    if not row:
        session.clear()
        return None
    return dict(row)

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/api/health")
def health():
    return jsonify(status="ok")

@app.get("/api/auth/status")
def auth_status():
    user = get_current_user()
    return jsonify(authenticated=bool(user), user=user)

@app.post("/api/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    display_name = str(data.get("displayName", "")).strip()
    password = str(data.get("password", ""))
    confirm_password = str(data.get("confirmPassword", ""))
    if not re.fullmatch(r"[A-Za-z0-9_]{4,20}", username):
        return jsonify(error="아이디는 영문, 숫자, 밑줄로 4~20자여야 합니다."), 400
    if not 2 <= len(display_name) <= 20:
        return jsonify(error="닉네임은 2~20자로 입력해 주세요."), 400
    if not 8 <= len(password) <= 72:
        return jsonify(error="비밀번호는 8~72자로 입력해 주세요."), 400
    if password != confirm_password:
        return jsonify(error="비밀번호가 일치하지 않습니다."), 400
    try:
        with db_session() as conn:
            cursor = conn.execute("""INSERT INTO users(username,display_name,password_hash,created_at)
                                   VALUES(?,?,?,?)""",
                                  (username, display_name, generate_password_hash(password),
                                   datetime.now(timezone.utc).isoformat()))
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        return jsonify(error="이미 사용 중인 아이디입니다."), 409
    session.clear()
    session["user_id"] = user_id
    return jsonify(user={"id": user_id, "username": username, "display_name": display_name,
                         "role": "user"}), 201

@app.post("/api/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    with db_session() as conn:
        row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify(error="아이디 또는 비밀번호가 올바르지 않습니다."), 401
    session.clear()
    session["user_id"] = row["id"]
    return jsonify(user={"id": row["id"], "username": row["username"],
                         "display_name": row["display_name"], "role": row["role"]})

@app.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify(status="ok")

@app.get("/api/items")
def list_items():
    query = request.args.get("q", "").strip()
    category = request.args.get("category", "전체").strip()
    viewer = get_current_user()
    sql, params = "SELECT * FROM items WHERE 1=1", []
    if query:
        sql += " AND (title LIKE ? OR location LIKE ?)"
        params += [f"%{query}%", f"%{query}%"]
    if category and category != "전체":
        sql += " AND category = ?"
        params.append(category)
    with db_session() as conn:
        rows = []
        for row in conn.execute(sql + " ORDER BY id DESC", params).fetchall():
            item = dict(row)
            owner_user_id = item.pop("owner_user_id", None)
            item.pop("claimant_user_id", None)
            item["can_delete"] = bool(viewer and
                                      (viewer["role"] == "admin" or owner_user_id == viewer["id"]))
            rows.append(item)
    return jsonify(rows)

@app.get("/api/me/items")
def my_items():
    user = get_current_user()
    if not user:
        return jsonify(error="로그인 후 마이페이지를 볼 수 있습니다."), 401
    with db_session() as conn:
        created = []
        for row in conn.execute(
                "SELECT * FROM items WHERE owner_user_id=? ORDER BY id DESC", (user["id"],)).fetchall():
            item = dict(row)
            item.pop("owner_user_id", None)
            item.pop("claimant_user_id", None)
            item["can_delete"] = True
            created.append(item)
        claimed = []
        for row in conn.execute(
                "SELECT * FROM items WHERE claimant_user_id=? ORDER BY claimed_at DESC, id DESC",
                (user["id"],)).fetchall():
            item = dict(row)
            item.pop("owner_user_id", None)
            item.pop("claimant_user_id", None)
            item["can_delete"] = user["role"] == "admin"
            claimed.append(item)
    return jsonify(created=created, claimed=claimed)

@app.post("/api/items")
def create_item():
    user = get_current_user()
    if not user:
        return jsonify(error="로그인 후 나눔을 등록할 수 있습니다."), 401
    data = request.get_json(silent=True) or {}
    required = ["title", "description", "category", "location", "claimStartAt"]
    missing = [key for key in required if not str(data.get(key, "")).strip()]
    if missing:
        return jsonify(error=f"필수 입력 누락: {', '.join(missing)}"), 400
    title = str(data["title"]).strip()
    if len(title) > 80:
        return jsonify(error="물건 이름은 80자 이하여야 합니다."), 400
    try:
        claim_start_at = datetime.fromisoformat(str(data["claimStartAt"]).replace("Z", "+00:00"))
    except ValueError:
        return jsonify(error="신청 시작 시간 형식이 올바르지 않습니다."), 400
    if claim_start_at.tzinfo is None:
        return jsonify(error="신청 시작 시간에 시간대 정보가 필요합니다."), 400
    claim_start_at = claim_start_at.astimezone(timezone.utc)
    if claim_start_at <= datetime.now(timezone.utc):
        return jsonify(error="신청 시작 시간은 현재보다 이후로 설정해 주세요."), 400
    values = (title, str(data["description"]).strip()[:500], str(data["category"]).strip()[:20],
              str(data["location"]).strip()[:50], user["display_name"], user["id"],
              str(data.get("imageUrl", "")).strip()[:1000], claim_start_at.isoformat(),
              datetime.now(timezone.utc).isoformat())
    with db_session() as conn:
        cursor = conn.execute("""INSERT INTO items(
                                  title,description,category,location,giver,owner_user_id,
                                  image_url,claim_start_at,created_at)
                                  VALUES(?,?,?,?,?,?,?,?,?)""", values)
        row = conn.execute("SELECT * FROM items WHERE id=?", (cursor.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201

@app.delete("/api/items/<int:item_id>")
def delete_item(item_id):
    user = get_current_user()
    if not user:
        return jsonify(error="로그인 후 삭제할 수 있습니다."), 401
    with db_session() as conn:
        item = conn.execute("SELECT owner_user_id FROM items WHERE id=?", (item_id,)).fetchone()
        if not item:
            return jsonify(error="존재하지 않는 물건입니다."), 404
        if user["role"] != "admin" and item["owner_user_id"] != user["id"]:
            return jsonify(error="본인이 등록한 나눔만 삭제할 수 있습니다."), 403
        conn.execute("DELETE FROM items WHERE id=?", (item_id,))
    return jsonify(status="ok")

@app.post("/api/items/<int:item_id>/claim")
def claim_item(item_id):
    user = get_current_user()
    if not user:
        return jsonify(error="로그인 후 신청할 수 있습니다."), 401
    now = datetime.now(timezone.utc)
    with db_session() as conn:
        result = conn.execute("""UPDATE items SET status='claimed', claimant=?, claimant_user_id=?,
                               claimed_at=?
                               WHERE id=? AND status='open'
                               AND (claim_start_at IS NULL OR claim_start_at <= ?)""",
                              (user["display_name"], user["id"], now.isoformat(),
                               item_id, now.isoformat()))
        if result.rowcount != 1:
            item = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
            if not item:
                return jsonify(error="존재하지 않는 물건입니다."), 404
            if item["status"] == "open" and item["claim_start_at"]:
                start_at = datetime.fromisoformat(item["claim_start_at"])
                if now < start_at:
                    return jsonify(error="아직 신청 시작 시간이 되지 않았습니다.",
                                   claim_start_at=item["claim_start_at"]), 425
            return jsonify(error="다른 사용자가 먼저 신청했습니다."), 409
        row = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    return jsonify(dict(row))

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)
