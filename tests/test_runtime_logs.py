import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fabric import sync


class RuntimeLogTest(unittest.TestCase):
    def test_append_and_read_runtime_logs(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            log_dir = tmp_path / "logs"
            runtime_log_path = log_dir / "runtime-log.jsonl"

            with patch.object(sync, "LOG_DIR", log_dir), patch.object(sync, "RUNTIME_LOG_PATH", runtime_log_path):
                sync.append_runtime_log("etl", "completed", "ETL completed successfully", {"rows": 10})
                sync.append_runtime_log("fabric_client", "synced", "Fabric sync completed", {"count": 5})

                entries = sync.get_recent_runtime_logs(limit=10)
                self.assertEqual(len(entries), 2)
                self.assertEqual(entries[0]["component"], "etl")
                self.assertEqual(entries[0]["status"], "completed")
                self.assertEqual(entries[1]["component"], "fabric_client")
                self.assertEqual(entries[1]["status"], "synced")


if __name__ == "__main__":
    unittest.main()
