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
          claimant TEXT, created_at TEXT NOT NULL)""")

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
    required = ["title", "description", "category", "location", "giver"]
    missing = [key for key in required if not str(data.get(key, "")).strip()]
    if missing:
        return jsonify(error=f"필수 입력 누락: {', '.join(missing)}"), 400
    title = str(data["title"]).strip()
    if len(title) > 80:
        return jsonify(error="물건 이름은 80자 이하여야 합니다."), 400
    values = (title, str(data["description"]).strip()[:500], str(data["category"]).strip()[:20],
              str(data["location"]).strip()[:50], str(data["giver"]).strip()[:40],
              str(data.get("imageUrl", "")).strip()[:1000], datetime.now(timezone.utc).isoformat())
    with db_session() as conn:
        cursor = conn.execute("""INSERT INTO items(title,description,category,location,giver,image_url,created_at)
                             VALUES(?,?,?,?,?,?,?)""", values)
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
    with db_session() as conn:
        result = conn.execute("UPDATE items SET status='claimed', claimant=? WHERE id=? AND status='open'", (name, item_id))
        if result.rowcount != 1:
            exists = conn.execute("SELECT id FROM items WHERE id=?", (item_id,)).fetchone()
            if not exists:
                return jsonify(error="존재하지 않는 물건입니다."), 404
            return jsonify(error="다른 사용자가 먼저 신청했습니다."), 409
        row = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    return jsonify(dict(row))

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)
