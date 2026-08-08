from ..base import FFmpegCommandBuilder


class MKVCommandBuilder(FFmpegCommandBuilder):
    def build_command(self) -> list[str]:
        command = self._get_basic_ffmpeg_command()
        # fmt: off
        if self.segment_record:
            additional_commands = [
                "-flags", "global_header",
                *self._get_video_codec_options(),
                "-c:a", "aac",
                "-map", "0",
                "-f", "segment",
                "-segment_time", str(self.segment_time),
                "-segment_format", "matroska",
                "-reset_timestamps", "1",
                self.full_path,
            ]
        else:
            additional_commands = [
                "-flags", "global_header",
                "-map", "0",
                *self._get_video_codec_options(),
                "-c:a", "copy",
                "-f", "matroska",
                self.full_path,
            ]
        # fmt: on

        command.extend(additional_commands)
        return command
