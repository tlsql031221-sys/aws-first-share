import os
import tempfile
import unittest
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
        return {"title":title,"description":"정상 작동","category":"디지털","location":"성수동","giver":"테스터"}

    def test_create_success_and_missing_title(self):
        self.assertEqual(self.client.post("/api/items", json=self.item()).status_code, 201)
        self.assertEqual(self.client.post("/api/items", json=self.item("")).status_code, 400)

    def test_search_match_and_no_result(self):
        self.client.post("/api/items", json=self.item())
        self.assertEqual(len(self.client.get("/api/items?q=키보드").get_json()), 1)
        self.assertEqual(self.client.get("/api/items?q=없는물건").get_json(), [])

    def test_claim_success_and_duplicate(self):
        item_id = self.client.post("/api/items", json=self.item()).get_json()["id"]
        self.assertEqual(self.client.post(f"/api/items/{item_id}/claim", json={"name":"민지"}).status_code, 200)
        self.assertEqual(self.client.post(f"/api/items/{item_id}/claim", json={"name":"철수"}).status_code, 409)

if __name__ == "__main__":
    unittest.main()
