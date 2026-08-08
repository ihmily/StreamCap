from ..base import FFmpegCommandBuilder


class MOVCommandBuilder(FFmpegCommandBuilder):
    def build_command(self) -> list[str]:
        command = self._get_basic_ffmpeg_command()

        # fmt: off
        if self.segment_record:
            additional_commands = [
                *self._get_video_codec_options(),
                "-c:a", "aac",
                "-map", "0",
                "-f", "segment",
                "-segment_time", str(self.segment_time),
                "-segment_format", "mov",
                "-reset_timestamps", "1",
                "-movflags", "+frag_keyframe+empty_moov+faststart",
                "-flags", "global_header",
                self.full_path,
            ]
        else:
            additional_commands = [
                "-map", "0",
                *self._get_video_codec_options(),
                "-c:a", "aac",
                "-f", "mov",
                "-movflags", "+faststart",
                self.full_path,
            ]
        # fmt: on

        command.extend(additional_commands)
        return command
