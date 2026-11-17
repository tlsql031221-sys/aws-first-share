import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
import app as service

class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.NamedTemporaryFile(delete=False)
        self.temp.close()
        service.DB_PATH = self.temp.name
        service.init_db()
        self.client = service.app.test_client()

    def tearDown(self):
        os.unlink(self.temp.name)

    def item(self, title="테스트 키보드"):
        start = datetime.now(timezone.utc) + timedelta(minutes=5)
        return {"title":title,"description":"정상 작동","category":"디지털","location":"성수동",
                "giver":"테스터","claimStartAt":start.isoformat()}

    def make_claimable(self, item_id):
        started = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        with service.db_session() as conn:
            conn.execute("UPDATE items SET claim_start_at=? WHERE id=?", (started, item_id))

    def test_create_success_and_missing_title(self):
        self.assertEqual(self.client.post("/api/items", json=self.item()).status_code, 201)
        self.assertEqual(self.client.post("/api/items", json=self.item("")).status_code, 400)

    def test_search_match_and_no_result(self):
        self.client.post("/api/items", json=self.item())
        self.assertEqual(len(self.client.get("/api/items?q=키보드").get_json()), 1)
        self.assertEqual(self.client.get("/api/items?q=없는물건").get_json(), [])

    def test_claim_success_and_duplicate(self):
        item_id = self.client.post("/api/items", json=self.item()).get_json()["id"]
        self.make_claimable(item_id)
        self.assertEqual(self.client.post(f"/api/items/{item_id}/claim", json={"name":"민지"}).status_code, 200)
        self.assertEqual(self.client.post(f"/api/items/{item_id}/claim", json={"name":"철수"}).status_code, 409)

    def test_claim_before_start(self):
        item_id = self.client.post("/api/items", json=self.item()).get_json()["id"]
        response = self.client.post(f"/api/items/{item_id}/claim", json={"name":"민지"})
        self.assertEqual(response.status_code, 425)
        self.assertIn("아직 신청 시작 시간이", response.get_json()["error"])

    def test_init_db_migrates_existing_table(self):
        migration = tempfile.NamedTemporaryFile(delete=False)
        migration.close()
        original_path = service.DB_PATH
        try:
            service.DB_PATH = migration.name
            conn = sqlite3.connect(migration.name)
            try:
                conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY)")
                conn.commit()
            finally:
                conn.close()
            service.init_db()
            conn = service.db()
            try:
                columns = {row["name"] for row in conn.execute("PRAGMA table_info(items)")}
            finally:
                conn.close()
            self.assertIn("claim_start_at", columns)
        finally:
            service.DB_PATH = original_path
            os.unlink(migration.name)

if __name__ == "__main__":
    unittest.main()
