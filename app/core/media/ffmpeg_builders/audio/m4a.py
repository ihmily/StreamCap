from ..base import FFmpegCommandBuilder


class M4ACommandBuilder(FFmpegCommandBuilder):
    def build_command(self) -> list[str]:
        command = self._get_basic_ffmpeg_command()

        if self.segment_record:
            additional_commands = [
                "-c:a", "aac",
                "-b:a","320k",
                "-map", "0:a",
                "-f", "segment",
                "-segment_time", str(self.segment_time),
                "-reset_timestamps", "1",
                self.full_path,
            ]
        else:
            additional_commands = [
                "-map", "0:a",
                "-c:a", "aac",
                "-b:a", "320k",
                "-f", "mp4",
                self.full_path,
            ]

        command.extend(additional_commands)
        return command
