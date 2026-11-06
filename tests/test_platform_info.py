import unittest

from app.core.platforms.platform_handlers import get_platform_info


class TestGetPlatformInfo(unittest.TestCase):
    def test_douyin(self):
        self.assertEqual(get_platform_info("https://live.douyin.com/123456"), ("抖音直播", "douyin"))

    def test_twitch(self):
        self.assertEqual(get_platform_info("https://www.twitch.tv/somechannel"), ("TwitchTV", "twitch"))

    def test_custom_m3u8(self):
        self.assertEqual(get_platform_info("http://example.com/stream.m3u8"), ("自定义录制直播", "custom"))

    def test_unknown_platform(self):
        self.assertEqual(get_platform_info("https://unknown.example.com/live"), (None, None))


if __name__ == "__main__":
    unittest.main()
