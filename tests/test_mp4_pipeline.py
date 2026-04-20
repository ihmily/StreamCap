import os
import tempfile
import unittest
from types import SimpleNamespace

from app.core.media.ffmpeg_builders.video.mp4 import MP4CommandBuilder
from app.core.recording.stream_manager import LiveStreamRecorder


class MP4CommandBuilderTests(unittest.TestCase):
    def test_segmented_mp4_uses_segment_format_options_for_movflags(self):
        command = MP4CommandBuilder(
            record_url="https://example.com/live.m3u8",
            segment_record=True,
            segment_time="1800",
            full_path="C:/tmp/out_%03d.mp4",
        ).build_command()

        self.assertIn("-segment_format_options", command)
        self.assertIn("movflags=+frag_keyframe+empty_moov+default_base_moof", command)
        self.assertNotIn("+frag_keyframe+empty_moov+faststart+delay_moov", command)

    def test_non_segmented_mp4_avoids_delay_moov(self):
        command = MP4CommandBuilder(
            record_url="https://example.com/live.m3u8",
            segment_record=False,
            full_path="C:/tmp/out.mp4",
        ).build_command()

        movflags_index = command.index("-movflags") + 1
        self.assertEqual(command[movflags_index], "+frag_keyframe+empty_moov+default_base_moof")


class LiveStreamRecorderFormatSelectionTests(unittest.TestCase):
    def test_hls_requested_video_formats_are_captured_as_ts(self):
        stream_info = SimpleNamespace(
            record_url="https://cdn.example.com/live/index.m3u8",
            m3u8_url="https://cdn.example.com/live/index.m3u8",
        )

        self.assertTrue(
            LiveStreamRecorder.should_capture_as_ts_for_requested_format(
                requested_format="mp4",
                use_direct_download=False,
                record_url=stream_info.record_url,
                stream_info=stream_info,
            )
        )
        self.assertTrue(
            LiveStreamRecorder.should_capture_as_ts_for_requested_format(
                requested_format="mkv",
                use_direct_download=False,
                record_url=stream_info.record_url,
                stream_info=stream_info,
            )
        )

    def test_non_hls_requested_formats_keep_direct_capture(self):
        stream_info = SimpleNamespace(
            record_url="https://cdn.example.com/live.flv",
            m3u8_url=None,
        )

        self.assertFalse(
            LiveStreamRecorder.should_capture_as_ts_for_requested_format(
                requested_format="mp4",
                use_direct_download=False,
                record_url=stream_info.record_url,
                stream_info=stream_info,
            )
        )
        self.assertFalse(
            LiveStreamRecorder.should_capture_as_ts_for_requested_format(
                requested_format="ts",
                use_direct_download=False,
                record_url=stream_info.record_url,
                stream_info=stream_info,
            )
        )

    def test_temporary_ts_capture_always_removes_intermediates(self):
        self.assertTrue(
            LiveStreamRecorder.should_delete_original_after_conversion(
                delete_original_setting=False,
                uses_temporary_capture=True,
            )
        )

    def test_regular_ts_conversion_still_respects_delete_original_setting(self):
        self.assertFalse(
            LiveStreamRecorder.should_delete_original_after_conversion(
                delete_original_setting=False,
                uses_temporary_capture=False,
            )
        )
        self.assertTrue(
            LiveStreamRecorder.should_delete_original_after_conversion(
                delete_original_setting=True,
                uses_temporary_capture=False,
            )
        )

    def test_temporary_ts_capture_converts_back_to_requested_format(self):
        self.assertEqual(
            LiveStreamRecorder.get_post_record_conversion_target(
                capture_format="ts",
                requested_format="mov",
                convert_to_mp4_setting=False,
                uses_temporary_capture=True,
            ),
            "mov",
        )

    def test_regular_ts_capture_can_still_optionally_generate_mp4(self):
        self.assertEqual(
            LiveStreamRecorder.get_post_record_conversion_target(
                capture_format="ts",
                requested_format="ts",
                convert_to_mp4_setting=True,
                uses_temporary_capture=False,
            ),
            "mp4",
        )

    def test_converted_output_path_uses_target_extension(self):
        self.assertEqual(
            LiveStreamRecorder.get_converted_output_path("C:/tmp/out_001.ts", "mkv"),
            "C:/tmp/out_001.mkv",
        )

    def test_segmented_incremental_conversion_excludes_latest_active_segment(self):
        recorder = LiveStreamRecorder.__new__(LiveStreamRecorder)
        recorder.segment_record = True
        recorder.segment_conversion_tasks = {}

        with tempfile.TemporaryDirectory() as temp_dir:
            for index in range(3):
                open(os.path.join(temp_dir, f"out_{index:03d}.ts"), "wb").close()

            save_file_path = os.path.join(temp_dir, "out_%03d.ts").replace("\\", "/")
            self.assertEqual(
                recorder._get_conversion_candidates(save_file_path, include_latest_segment=False),
                [
                    os.path.join(temp_dir, "out_000.ts").replace("\\", "/"),
                    os.path.join(temp_dir, "out_001.ts").replace("\\", "/"),
                ],
            )

    def test_segmented_final_conversion_includes_latest_segment(self):
        recorder = LiveStreamRecorder.__new__(LiveStreamRecorder)
        recorder.segment_record = True
        recorder.segment_conversion_tasks = {}

        with tempfile.TemporaryDirectory() as temp_dir:
            for index in range(2):
                open(os.path.join(temp_dir, f"out_{index:03d}.ts"), "wb").close()

            save_file_path = os.path.join(temp_dir, "out_%03d.ts").replace("\\", "/")
            self.assertEqual(
                recorder._get_conversion_candidates(save_file_path, include_latest_segment=True),
                [
                    os.path.join(temp_dir, "out_000.ts").replace("\\", "/"),
                    os.path.join(temp_dir, "out_001.ts").replace("\\", "/"),
                ],
            )

    def test_progress_marker_ignores_removed_old_segment_during_incremental_conversion(self):
        recorder = LiveStreamRecorder.__new__(LiveStreamRecorder)
        recorder.segment_record = True

        with tempfile.TemporaryDirectory() as temp_dir:
            old_segment = os.path.join(temp_dir, "out_000.ts")
            latest_segment = os.path.join(temp_dir, "out_001.ts")

            with open(old_segment, "wb") as file:
                file.write(b"old-segment")
            with open(latest_segment, "wb") as file:
                file.write(b"latest")

            save_file_path = os.path.join(temp_dir, "out_%03d.ts").replace("\\", "/")
            marker_before = recorder._get_output_progress_marker(save_file_path)

            os.remove(old_segment)

            marker_after = recorder._get_output_progress_marker(save_file_path)
            self.assertEqual(marker_before, marker_after)


if __name__ == "__main__":
    unittest.main()
