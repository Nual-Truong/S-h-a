import importlib
import os
import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import patch

import pandas as pd

from etl.transform import transform_data


class ConfigDotenvTest(unittest.TestCase):
    def test_loads_env_from_dotenv_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_file = Path(tmp_dir) / ".env"
            env_file.write_text(
                "APP_MODE=legacy\nFABRIC_AUTO_SYNC=0\nFABRIC_HASH_MODE=both\n",
                encoding="utf-8",
            )

            original_cwd = os.getcwd()
            try:
                with patch.dict(os.environ, {}, clear=True):
                    os.chdir(tmp_dir)
                    config = importlib.import_module("config")
                    importlib.reload(config)

                    self.assertEqual(config.APP_MODE, "legacy")
                    self.assertFalse(config.FABRIC_AUTO_SYNC)
                    self.assertEqual(config.FABRIC_HASH_MODE, "both")
            finally:
                os.chdir(original_cwd)
                if "config" in sys.modules:
                    importlib.reload(sys.modules["config"])


class TransformDataTest(unittest.TestCase):
    def test_transform_data_drops_invalid_rows_and_computes_profit(self):
        df = pd.DataFrame(
            [
                {"date": "2024-01-01", "category": "Food", "amount": 100, "cost": 70},
                {"date": "2024-01-02", "category": "Tech", "amount": -10, "cost": 20},
                {"date": "bad-date", "category": "Other", "amount": 50, "cost": 10},
            ]
        )

        result = transform_data(df)

        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["category"], "Food")
        self.assertEqual(result.iloc[0]["amount"], 100)
        self.assertEqual(result.iloc[0]["cost"], 70)
        self.assertEqual(result.iloc[0]["profit"], 30)
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(result["date"]))


if __name__ == "__main__":
    unittest.main()
