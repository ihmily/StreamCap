from ..base import FFmpegCommandBuilder


class NUTCommandBuilder(FFmpegCommandBuilder):
    def build_command(self) -> list[str]:
        command = self._get_basic_ffmpeg_command()
        if self.segment_record:
            additional_commands = [
                "-c:v", "copy",
                "-c:a", "copy",
                "-map", "0",
                "-f", "segment",
                "-segment_time", str(self.segment_time),
                "-segment_format", "nut",
                "-reset_timestamps", "1",
                "-muxdelay", "0",
                "-muxpreload", "0",
                self.full_path,
            ]
        else:
            additional_commands = [
                "-c:v", "copy",
                "-c:a", "copy",
                "-map", "0",
                "-f", "nut",
                "-muxdelay", "0",
                "-muxpreload", "0",
                self.full_path,
            ]

        command.extend(additional_commands)
        return command
