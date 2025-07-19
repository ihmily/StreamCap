from ..base import FFmpegCommandBuilder


class AACCommandBuilder(FFmpegCommandBuilder):
    def build_command(self) -> list[str]:
        command = self._get_basic_ffmpeg_command()

        if self.segment_record:
            additional_commands = [
                "-c:a", "aac",
                "-ar", "44100",
                "-ac", "2",
                "-map", "0:a",
                "-f", "adts",
                "-segment_time", str(self.segment_time),
                "-reset_timestamps", "1",
                self.full_path,
            ]
        else:
            additional_commands = [
                "-map", "0:a",
                "-c:a", "aac",
                "-ar", "44100",
                "-ac", "2",
                "-f", "ipod",
                self.full_path,
            ]

        command.extend(additional_commands)
        return command
