from ..base import FFmpegCommandBuilder


class FLVCommandBuilder(FFmpegCommandBuilder):
    def build_command(self) -> list[str]:
        command = self._get_basic_ffmpeg_command()
        if self.segment_record:
            additional_commands = [
                "-map", "0",
                "-c:v", "copy",
                "-c:a", "copy",
                "-bsf:a", "aac_adtstoasc",
                "-f", "segment",
                "-segment_time", str(self.segment_time),
                "-segment_format", "flv",
                "-reset_timestamps", "1",
                self.full_path
            ]
        else:
            additional_commands = [
                "-map", "0",
                "-c:v", "copy",
                "-c:a", "copy",
                "-bsf:a", "aac_adtstoasc",
                "-f", "flv",
                self.full_path
            ]
        command.extend(additional_commands)
        return command
