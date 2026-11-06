import unittest

from app.core.recording.stream_manager import LiveStreamRecorder


class TestSplitCommand(unittest.TestCase):
    def test_simple_command(self):
        self.assertEqual(LiveStreamRecorder._split_command("python script.py"), ["python", "script.py"])

    def test_windows_path_with_spaces(self):
        cmd = 'python "C:\\my dir\\post.py" --record_name "room 1"'
        self.assertEqual(
            LiveStreamRecorder._split_command(cmd),
            ["python", "C:\\my dir\\post.py", "--record_name", "room 1"],
        )

    def test_posix_single_quotes(self):
        self.assertEqual(
            LiveStreamRecorder._split_command("bash '/home/user/my script.sh' arg"),
            ["bash", "/home/user/my script.sh", "arg"],
        )

    def test_extra_whitespace(self):
        self.assertEqual(LiveStreamRecorder._split_command("python  a  b "), ["python", "a", "b"])

    def test_ffmpeg_args(self):
        cmd = 'ffmpeg -i "C:\\a b\\in.flv" -c copy out.mp4'
        self.assertEqual(
            LiveStreamRecorder._split_command(cmd),
            ["ffmpeg", "-i", "C:\\a b\\in.flv", "-c", "copy", "out.mp4"],
        )


if __name__ == "__main__":
    unittest.main()
