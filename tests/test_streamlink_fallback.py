import unittest

from app.core.platforms.platform_handlers.streamlink_fallback import _pick_stream


class FakeStream:
    def __init__(self, url):
        self.url = url


class TestPickStream(unittest.TestCase):
    def test_empty_streams(self):
        self.assertIsNone(_pick_stream({}, "OD"))

    def test_best_for_od(self):
        streams = {"720p": FakeStream("a"), "best": FakeStream("b")}
        self.assertIs(_pick_stream(streams, "OD"), streams["best"])

    def test_hd_prefers_1080p(self):
        streams = {"720p": FakeStream("a"), "1080p": FakeStream("b"), "best": FakeStream("c")}
        self.assertIs(_pick_stream(streams, "HD"), streams["1080p"])

    def test_hd_falls_back_to_highest_resolution(self):
        streams = {"720p": FakeStream("a"), "480p": FakeStream("b")}
        self.assertIs(_pick_stream(streams, "HD"), streams["720p"])

    def test_audio_excluded(self):
        streams = {"audio": FakeStream("a"), "worst": FakeStream("b")}
        self.assertIs(_pick_stream(streams, "LD"), streams["worst"])

    def test_none_quality_defaults_to_best(self):
        streams = {"best": FakeStream("b")}
        self.assertIs(_pick_stream(streams, None), streams["best"])


if __name__ == "__main__":
    unittest.main()
