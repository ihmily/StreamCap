import asyncio
import unittest
from types import SimpleNamespace

from app.core.recording.record_manager import GlobalRecordingState, RecordingManager
from app.models.recording.recording_model import Recording


class DummyLanguageManager:
    def __init__(self):
        self.language = {
            "recording_manager": {},
            "video_quality": {},
        }

    def add_observer(self, _observer):
        return None


class DummyConfigManager:
    def __init__(self):
        self.saved_configs = []

    def load_recordings_config(self):
        return []

    async def save_recordings_config(self, config):
        self.saved_configs.append(config)


class DummyPage:
    def run_task(self, *_args, **_kwargs):
        return None


class RecordingManagerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        GlobalRecordingState.recordings = []
        self.config_manager = DummyConfigManager()
        self.app = SimpleNamespace(
            settings=SimpleNamespace(user_config={"platform_max_concurrent_requests": 3, "loop_time_seconds": "180"}),
            language_manager=DummyLanguageManager(),
            config_manager=self.config_manager,
            page=DummyPage(),
        )

    def tearDown(self):
        GlobalRecordingState.recordings = []

    @staticmethod
    def _make_recording(rec_id: str, url: str) -> Recording:
        return Recording(
            rec_id=rec_id,
            url=url,
            streamer_name=f"streamer-{rec_id}",
            record_format="MP4",
            quality="OD",
            segment_record=True,
            segment_time="1800",
            monitor_status=True,
            scheduled_recording=False,
            scheduled_start_time="",
            monitor_hours="5",
            recording_dir="",
            enabled_message_push=False,
            only_notify_no_record=False,
            flv_use_direct_download=False,
        )

    async def test_add_recordings_persists_once_for_multiple_items(self):
        manager = RecordingManager(self.app)
        recordings = [
            self._make_recording("rec-1", "https://example.com/1"),
            self._make_recording("rec-2", "https://example.com/2"),
        ]

        await manager.add_recordings(recordings)

        self.assertEqual(len(manager.recordings), 2)
        self.assertEqual(len(self.config_manager.saved_configs), 1)
        self.assertEqual(
            [item["rec_id"] for item in self.config_manager.saved_configs[0]],
            ["rec-1", "rec-2"],
        )

    async def test_wait_for_runtime_tasks_waits_for_registered_task_completion(self):
        manager = RecordingManager(self.app)

        async def background_work():
            await asyncio.sleep(0.01)

        task = asyncio.create_task(background_work())
        manager.register_runtime_task(task)

        completed = await manager.wait_for_runtime_tasks(timeout=1)

        self.assertTrue(completed)
        self.assertTrue(task.done())
        self.assertNotIn(task, manager.active_runtime_tasks)


if __name__ == "__main__":
    unittest.main()
