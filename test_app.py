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

    def register(self, username="tester", display_name="테스터", password="password123"):
        return self.client.post("/api/auth/register", json={
            "username": username, "displayName": display_name,
            "password": password, "confirmPassword": password
        })

    def test_create_success_and_missing_title(self):
        self.assertEqual(self.register().status_code, 201)
        self.assertEqual(self.client.post("/api/items", json=self.item()).status_code, 201)
        self.assertEqual(self.client.post("/api/items", json=self.item("")).status_code, 400)

    def test_search_match_and_no_result(self):
        self.assertEqual(self.register().status_code, 201)
        self.client.post("/api/items", json=self.item())
        self.assertEqual(len(self.client.get("/api/items?q=키보드").get_json()), 1)
        self.assertEqual(self.client.get("/api/items?q=없는물건").get_json(), [])

    def test_claim_success_and_duplicate(self):
        self.assertEqual(self.register(display_name="민지").status_code, 201)
        item_id = self.client.post("/api/items", json=self.item()).get_json()["id"]
        self.make_claimable(item_id)
        response = self.client.post(f"/api/items/{item_id}/claim")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["claimant"], "민지")
        self.assertEqual(self.client.post(f"/api/items/{item_id}/claim").status_code, 409)

    def test_claim_before_start(self):
        self.assertEqual(self.register().status_code, 201)
        item_id = self.client.post("/api/items", json=self.item()).get_json()["id"]
        response = self.client.post(f"/api/items/{item_id}/claim")
        self.assertEqual(response.status_code, 425)
        self.assertIn("아직 신청 시작 시간이", response.get_json()["error"])

    def test_register_login_logout_and_duplicate_username(self):
        mismatch = self.client.post("/api/auth/register", json={
            "username": "mismatch", "displayName": "불일치",
            "password": "password123", "confirmPassword": "password456"
        })
        self.assertEqual(mismatch.status_code, 400)
        self.assertEqual(self.register().status_code, 201)
        self.assertTrue(self.client.get("/api/auth/status").get_json()["authenticated"])
        self.client.post("/api/auth/logout")
        self.assertFalse(self.client.get("/api/auth/status").get_json()["authenticated"])
        self.assertEqual(self.register(username="TESTER").status_code, 409)
        self.assertEqual(self.client.post("/api/auth/login", json={
            "username": "tester", "password": "wrong-password"
        }).status_code, 401)
        self.assertEqual(self.client.post("/api/auth/login", json={
            "username": "tester", "password": "password123"
        }).status_code, 200)

    def test_claim_requires_login(self):
        self.assertEqual(self.register().status_code, 201)
        item_id = self.client.post("/api/items", json=self.item()).get_json()["id"]
        self.make_claimable(item_id)
        self.client.post("/api/auth/logout")
        self.assertEqual(self.client.post(f"/api/items/{item_id}/claim").status_code, 401)

    def test_my_page_shows_created_and_claimed_items(self):
        self.assertEqual(self.client.get("/api/me/items").status_code, 401)
        self.assertEqual(self.register(username="owner", display_name="나눔이").status_code, 201)
        item_id = self.client.post("/api/items", json=self.item()).get_json()["id"]
        self.make_claimable(item_id)
        self.client.post("/api/auth/logout")

        self.assertEqual(self.register(username="claimer", display_name="신청자").status_code, 201)
        self.assertEqual(self.client.post(f"/api/items/{item_id}/claim").status_code, 200)
        claimant_page = self.client.get("/api/me/items").get_json()
        self.assertEqual(claimant_page["created"], [])
        self.assertEqual(len(claimant_page["claimed"]), 1)
        self.assertIsNotNone(claimant_page["claimed"][0]["claimed_at"])

        self.client.post("/api/auth/logout")
        self.assertEqual(self.client.post("/api/auth/login", json={
            "username": "owner", "password": "password123"
        }).status_code, 200)
        owner_page = self.client.get("/api/me/items").get_json()
        self.assertEqual(len(owner_page["created"]), 1)
        self.assertEqual(owner_page["created"][0]["status"], "claimed")
        self.assertEqual(owner_page["claimed"], [])

    def test_only_owner_can_delete_item(self):
        self.assertEqual(self.register(username="owner", display_name="나눔자").status_code, 201)
        item_id = self.client.post("/api/items", json=self.item()).get_json()["id"]
        self.client.post("/api/auth/logout")
        self.assertEqual(self.client.delete(f"/api/items/{item_id}").status_code, 401)
        self.assertEqual(self.register(username="other", display_name="다른사람").status_code, 201)
        self.assertEqual(self.client.delete(f"/api/items/{item_id}").status_code, 403)
        self.client.post("/api/auth/logout")
        self.assertEqual(self.client.post("/api/auth/login", json={
            "username": "owner", "password": "password123"
        }).status_code, 200)
        self.assertEqual(self.client.delete(f"/api/items/{item_id}").status_code, 200)
        self.assertEqual(self.client.get("/api/items").get_json(), [])

    def test_configured_admin_can_delete_any_item(self):
        self.assertEqual(self.register(username="owner", display_name="나눔자").status_code, 201)
        item_id = self.client.post("/api/items", json=self.item()).get_json()["id"]
        self.client.post("/api/auth/logout")
        keys = ["ADMIN_USERNAME", "ADMIN_PASSWORD", "ADMIN_DISPLAY_NAME"]
        original = {key: os.environ.get(key) for key in keys}
        try:
            os.environ["ADMIN_USERNAME"] = "admin"
            os.environ["ADMIN_PASSWORD"] = "admin-password-123"
            os.environ["ADMIN_DISPLAY_NAME"] = "운영자"
            service.init_db()
        finally:
            for key, value in original.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        login = self.client.post("/api/auth/login", json={
            "username": "admin", "password": "admin-password-123"
        })
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.get_json()["user"]["role"], "admin")
        self.assertTrue(self.client.get("/api/items").get_json()[0]["can_delete"])
        self.assertEqual(self.client.delete(f"/api/items/{item_id}").status_code, 200)

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
            self.assertIn("claimant_user_id", columns)
            self.assertIn("owner_user_id", columns)
            self.assertIn("claimed_at", columns)
            conn = service.db()
            try:
                user_columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
            finally:
                conn.close()
            self.assertIn("role", user_columns)
        finally:
            service.DB_PATH = original_path
            os.unlink(migration.name)

if __name__ == "__main__":
    unittest.main()
