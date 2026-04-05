import sqlite3
import unittest

import pandas as pd

from blockchain.ledger import rebuild_ledger, tamper_random_transaction, verify_ledger


class BlockchainSmokeTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute(
            """
            CREATE TABLE transactions (
                date TEXT,
                category TEXT,
                amount INTEGER,
                cost INTEGER,
                profit INTEGER
            )
            """
        )
        sample = [
            ("2024-01-01", "Food", 100, 70, 30),
            ("2024-01-02", "Tech", 120, 80, 40),
            ("2024-01-03", "Food", 90, 50, 40),
        ]
        self.conn.executemany(
            "INSERT INTO transactions (date, category, amount, cost, profit) VALUES (?, ?, ?, ?, ?)",
            sample,
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_verify_passes_after_rebuild(self):
        df = pd.read_sql("SELECT * FROM transactions", self.conn)
        rebuild_ledger(self.conn, df)

        result = verify_ledger(self.conn)
        self.assertTrue(result["valid"])
        self.assertEqual(result["blocks"], 3)

    def test_verify_fails_after_tamper(self):
        df = pd.read_sql("SELECT * FROM transactions", self.conn)
        rebuild_ledger(self.conn, df)

        tamper_random_transaction(self.conn, amount_delta=10)
        result = verify_ledger(self.conn)

        self.assertFalse(result["valid"])
        self.assertGreater(len(result["issues"]), 0)


if __name__ == "__main__":
    unittest.main()
