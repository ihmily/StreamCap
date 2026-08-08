from ..base import FFmpegCommandBuilder


class MP4CommandBuilder(FFmpegCommandBuilder):
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
                "-segment_format", "mp4",
                "-reset_timestamps", "1",
                "-movflags", "+frag_keyframe+empty_moov+faststart+delay_moov",
                "-flags", "global_header",
                self.full_path,
            ]
        else:
            additional_commands = [
                "-map", "0",
                *self._get_video_codec_options(),
                "-c:a", "copy",
                "-f", "mp4",
                "-movflags", "+faststart+frag_keyframe+empty_moov+delay_moov",
                self.full_path,
            ]
        # fmt: on

        command.extend(additional_commands)
        return command
