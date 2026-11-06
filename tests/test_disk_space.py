import os
import shutil
import tempfile
import time
import unittest
from unittest import mock

from app.utils import utils


def _make_file(path: str, age_seconds: float = 3600) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"x" * 1024)
    old = time.time() - age_seconds
    os.utime(path, (old, old))
    return path


class TestCleanOldRecordings(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _set_free_gb(self, free_gb: float):
        def fake_disk_usage(path):
            total = 100 * 1024**3
            used = (100 - free_gb) * 1024**3
            return shutil._ntuple_diskusage(total=total, used=used, free=free_gb * 1024**3)

        return mock.patch.object(utils.shutil, "disk_usage", side_effect=fake_disk_usage)

    def test_no_deletion_when_space_sufficient(self):
        path = _make_file(os.path.join(self.tmp, "a", "old.mp4"))
        with self._set_free_gb(10.0):
            deleted = utils.clean_old_recordings(self.tmp, target_free_gb=2.0)
        self.assertEqual(deleted, [])
        self.assertTrue(os.path.exists(path))

    def test_deletes_oldest_first_until_target(self):
        old1 = _make_file(os.path.join(self.tmp, "a", "1.mp4"), age_seconds=9000)
        old2 = _make_file(os.path.join(self.tmp, "b", "2.flv"), age_seconds=8000)
        old3 = _make_file(os.path.join(self.tmp, "c", "3.ts"), age_seconds=7000)
        # free space rises with each deletion: 0.5 -> 1.5 -> 2.5 GB
        frees = iter([0.5, 1.5, 2.5, 2.5])
        with (
            self._set_free_gb(0),
            mock.patch.object(
                utils.shutil,
                "disk_usage",
                side_effect=lambda p: shutil._ntuple_diskusage(total=100 * 1024**3, used=0, free=next(frees) * 1024**3),
            ),
        ):
            deleted = utils.clean_old_recordings(self.tmp, target_free_gb=2.0)
        self.assertEqual(deleted, [old1, old2])
        self.assertFalse(os.path.exists(old1))
        self.assertFalse(os.path.exists(old2))
        self.assertTrue(os.path.exists(old3))

    def test_protects_recent_files(self):
        fresh = _make_file(os.path.join(self.tmp, "new.mp4"), age_seconds=60)
        old = _make_file(os.path.join(self.tmp, "old.mp4"), age_seconds=9000)
        with self._set_free_gb(0.1):
            deleted = utils.clean_old_recordings(self.tmp, target_free_gb=2.0)
        self.assertEqual(deleted, [old])
        self.assertTrue(os.path.exists(fresh))

    def test_ignores_non_video_files(self):
        doc = _make_file(os.path.join(self.tmp, "notes.txt"))
        with self._set_free_gb(0.1):
            deleted = utils.clean_old_recordings(self.tmp, target_free_gb=2.0)
        self.assertEqual(deleted, [])
        self.assertTrue(os.path.exists(doc))

    def test_covers_nested_directories(self):
        nested = _make_file(os.path.join(self.tmp, "p", "q", "deep.mkv"), age_seconds=9000)
        with self._set_free_gb(0.1):
            deleted = utils.clean_old_recordings(self.tmp, target_free_gb=2.0)
        self.assertEqual(deleted, [nested])


if __name__ == "__main__":
    unittest.main()
