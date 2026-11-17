import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
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
        conn.execute("""CREATE TABLE IF NOT EXISTS items (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          title TEXT NOT NULL, description TEXT NOT NULL,
          category TEXT NOT NULL, location TEXT NOT NULL,
          giver TEXT NOT NULL, image_url TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'open',
          claimant TEXT, claim_start_at TEXT,
          created_at TEXT NOT NULL)""")
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(items)").fetchall()}
        if "claim_start_at" not in columns:
            conn.execute("ALTER TABLE items ADD COLUMN claim_start_at TEXT")

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/api/health")
def health():
    return jsonify(status="ok")

@app.get("/api/items")
def list_items():
    query = request.args.get("q", "").strip()
    category = request.args.get("category", "전체").strip()
    sql, params = "SELECT * FROM items WHERE 1=1", []
    if query:
        sql += " AND (title LIKE ? OR location LIKE ?)"
        params += [f"%{query}%", f"%{query}%"]
    if category and category != "전체":
        sql += " AND category = ?"
        params.append(category)
    with db_session() as conn:
        rows = [dict(row) for row in conn.execute(sql + " ORDER BY id DESC", params).fetchall()]
    return jsonify(rows)

@app.post("/api/items")
def create_item():
    data = request.get_json(silent=True) or {}
    required = ["title", "description", "category", "location", "giver", "claimStartAt"]
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
              str(data["location"]).strip()[:50], str(data["giver"]).strip()[:40],
              str(data.get("imageUrl", "")).strip()[:1000], claim_start_at.isoformat(),
              datetime.now(timezone.utc).isoformat())
    with db_session() as conn:
        cursor = conn.execute("""INSERT INTO items(
                                  title,description,category,location,giver,image_url,claim_start_at,created_at)
                                  VALUES(?,?,?,?,?,?,?,?)""", values)
        row = conn.execute("SELECT * FROM items WHERE id=?", (cursor.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201

@app.post("/api/items/<int:item_id>/claim")
def claim_item(item_id):
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    if not name:
        return jsonify(error="신청자 이름을 입력해 주세요."), 400
    if len(name) > 40:
        return jsonify(error="신청자 이름은 40자 이하여야 합니다."), 400
    now = datetime.now(timezone.utc)
    with db_session() as conn:
        result = conn.execute("""UPDATE items SET status='claimed', claimant=?
                               WHERE id=? AND status='open'
                               AND (claim_start_at IS NULL OR claim_start_at <= ?)""",
                              (name, item_id, now.isoformat()))
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
