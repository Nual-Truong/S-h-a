import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

from api.app import app


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_status_uses_patched_sources(self):
        with patch("api.app.get_fabric_status", return_value={"status": "synced"}), patch(
            "api.app.summarize_fabric_outbox", return_value={"valid": True}
        ), patch("api.app.get_fabric_checkpoint", return_value={"status": "completed"}), patch(
            "api.app.get_recent_runtime_logs", return_value=[{"message": "hello"}]
        ):
            response = self.client.get("/status")
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["fabric_status"]["status"], "synced")
            self.assertEqual(body["fabric_checkpoint"]["status"], "completed")

    def test_report_downloads_excel(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            db_path = tmp_path / "sfm.db"
            import sqlite3

            conn = sqlite3.connect(db_path)
            conn.execute(
                "CREATE TABLE transactions (date TEXT, category TEXT, amount INTEGER, cost INTEGER, profit INTEGER)"
            )
            conn.execute(
                "INSERT INTO transactions VALUES (?, ?, ?, ?, ?)",
                ("2024-01-01", "Food", 100, 70, 30),
            )
            conn.commit()
            conn.close()

            def connection_factory():
                return sqlite3.connect(db_path, check_same_thread=False)

            with patch("api.app.get_connection", side_effect=connection_factory):
                response = self.client.get("/report.xlsx")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["content-type"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                self.assertTrue(len(response.content) > 0)

    def test_report_downloads_pdf(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            db_path = tmp_path / "sfm.db"
            import sqlite3

            conn = sqlite3.connect(db_path)
            conn.execute(
                "CREATE TABLE transactions (date TEXT, category TEXT, amount INTEGER, cost INTEGER, profit INTEGER)"
            )
            conn.execute(
                "INSERT INTO transactions VALUES (?, ?, ?, ?, ?)",
                ("2024-01-01", "Food", 100, 70, 30),
            )
            conn.commit()
            conn.close()

            def connection_factory():
                return sqlite3.connect(db_path, check_same_thread=False)

            with patch("api.app.get_connection", side_effect=connection_factory):
                response = self.client.get("/report.pdf")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["content-type"], "application/pdf")
                self.assertTrue(response.content.startswith(b"%PDF"))

    def test_user_login_checkout_and_receipt(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            db_path = tmp_path / "sfm.db"

            with patch("db.database.DB_PATH", str(db_path)):
                with TestClient(app) as client:
                    login_response = client.post(
                        "/auth/login",
                        json={"username": "user", "password": "user"},
                    )
                    self.assertEqual(login_response.status_code, 200)
                    login_body = login_response.json()
                    token = login_body["access_token"]

                    products_response = client.get("/products")
                    self.assertEqual(products_response.status_code, 200)
                    products = products_response.json()["items"]
                    self.assertTrue(len(products) > 0)

                    checkout_response = client.post(
                        "/checkout",
                        headers={"Authorization": f"Bearer {token}"},
                        json={"items": [{"product_id": "ML01", "quantity": 1}], "payment_method": "COD"},
                    )
                    self.assertEqual(checkout_response.status_code, 200)
                    receipt_body = checkout_response.json()
                    self.assertEqual(receipt_body["buyer"]["username"], "user")
                    self.assertTrue(receipt_body["order_id"])
                    self.assertTrue(receipt_body["transaction_id"])
                    self.assertTrue(receipt_body["receipt_number"])
                    self.assertTrue(receipt_body["total_amount"] > 0)
                    self.assertTrue(len(receipt_body["items"]) > 0)

                    receipt_response = client.get(
                        f"/orders/{receipt_body['order_id']}/receipt",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    self.assertEqual(receipt_response.status_code, 200)
                    self.assertEqual(receipt_response.json()["order_id"], receipt_body["order_id"])


if __name__ == "__main__":
    unittest.main()
