import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fabric import sync


class FabricCheckpointTest(unittest.TestCase):
    def test_save_get_and_clear_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            with patch.object(sync, "OUTBOX_DIR", tmp_path), patch.object(sync, "CHECKPOINT_PATH", tmp_path / "sync-checkpoint.json"):
                saved = sync.save_fabric_checkpoint(
                    {
                        "status": "running",
                        "next_offset": 120,
                        "completed": 90,
                        "target": 2568,
                        "batch_size": 300,
                        "commit_timeout": 900,
                        "last_message": "Progress: 120/2568",
                    }
                )

                self.assertEqual(saved["status"], "running")
                self.assertTrue((tmp_path / "sync-checkpoint.json").exists())

                loaded = sync.get_fabric_checkpoint()
                self.assertEqual(loaded["next_offset"], 120)
                self.assertEqual(loaded["completed"], 90)
                self.assertEqual(loaded["target"], 2568)
                self.assertEqual(loaded["batch_size"], 300)
                self.assertEqual(loaded["commit_timeout"], 900)

                self.assertTrue(sync.clear_fabric_checkpoint())
                self.assertFalse((tmp_path / "sync-checkpoint.json").exists())
                self.assertEqual(sync.get_fabric_checkpoint()["status"], "idle")


if __name__ == "__main__":
    unittest.main()
