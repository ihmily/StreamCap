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
    def test_hls_mp4_requests_are_captured_as_ts(self):
        stream_info = SimpleNamespace(
            record_url="https://cdn.example.com/live/index.m3u8",
            m3u8_url="https://cdn.example.com/live/index.m3u8",
        )

        self.assertTrue(
            LiveStreamRecorder.should_capture_as_ts_for_mp4(
                requested_format="mp4",
                use_direct_download=False,
                record_url=stream_info.record_url,
                stream_info=stream_info,
            )
        )

    def test_non_hls_mp4_requests_keep_mp4_capture(self):
        stream_info = SimpleNamespace(
            record_url="https://cdn.example.com/live.flv",
            m3u8_url=None,
        )

        self.assertFalse(
            LiveStreamRecorder.should_capture_as_ts_for_mp4(
                requested_format="mp4",
                use_direct_download=False,
                record_url=stream_info.record_url,
                stream_info=stream_info,
            )
        )


if __name__ == "__main__":
    unittest.main()
