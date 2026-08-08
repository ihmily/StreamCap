import abc

DEFAULT_CONFIG = {
    "rw_timeout": "15000000",
    "analyzeduration": "20000000",
    "probesize": "10000000",
    "bufsize": "8000k",
    "max_muxing_queue_size": "1024",
}

OVERSEAS_CONFIG = {
    "rw_timeout": "50000000",
    "analyzeduration": "40000000",
    "probesize": "20000000",
    "bufsize": "15000k",
    "max_muxing_queue_size": "2048",
}

FFMPEG_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 11; SAMSUNG SM-G973U) AppleWebKit/537.36 (KHTML, like Gecko) "
    "SamsungBrowser/14.2 Chrome/87.0.4280.141 Mobile Safari/537.36"
)

# HLS streams from these platforms may use media segment extensions that do
# not match the container detected by FFmpeg.
RELAXED_HLS_EXTENSION_CHECK_PLATFORMS = ["chzzk"]


class FFmpegCommandBuilder(abc.ABC):
    """
    Abstract base class for building FFmpeg command lines.
    """

    def __init__(
        self,
        record_url: str,
        is_overseas: bool = False,
        segment_record: bool = False,
        segment_time: str | None = None,
        full_path: str | None = None,
        headers: str | None = None,
        proxy: str | None = None,
        platform_key: str | None = None,
        video_bitrate: int | None = None,
    ):
        """
        Initializes the FFmpegCommandBuilder.

        :param record_url: URL of the media to be recorded.(m3u8/flv format)
        :param is_overseas: Boolean flag indicating if the connection is overseas.
        :param segment_record: Boolean flag indicating if segmented recording is needed.
        :param segment_time: Time duration for each segment (if applicable).
        :param full_path: Full path where the output file will be saved.
        :param headers: Additional headers to include in the request.
        :param proxy: Proxy server URL to use for the connection.
        :param platform_key: Platform identifier used for platform-specific FFmpeg compatibility options.
        :param video_bitrate: Custom output video bitrate in kbps. Enables H.264 transcoding when set.
        """
        self.record_url = record_url
        self.is_overseas = is_overseas
        self.segment_record = segment_record
        self.segment_time = segment_time
        self.full_path = full_path or ""
        self.proxy = proxy or ""
        self.headers = headers or ""
        self.platform_key = platform_key
        self.video_bitrate = video_bitrate

    @abc.abstractmethod
    def build_command(self) -> list[str]:
        pass

    def _get_basic_ffmpeg_command(self) -> list[str]:
        """
        Constructs the basic part of the FFmpeg command.

        :return: List of strings representing the FFmpeg command components.
        """
        config = OVERSEAS_CONFIG if self.is_overseas else DEFAULT_CONFIG
        hls_input_options = []
        if self.platform_key in RELAXED_HLS_EXTENSION_CHECK_PLATFORMS:
            # FFmpeg 8 rejects container/extension mismatches in strict mode.
            hls_input_options = ["-extension_picky", "0"]

        # fmt: off
        command = [
            "ffmpeg",
            "-y",
            "-v", "verbose",
            "-rw_timeout", config["rw_timeout"],
            "-loglevel", "error",
            "-hide_banner",
            "-user_agent", FFMPEG_USER_AGENT,
            "-protocol_whitelist", "rtmp,crypto,file,http,https,tcp,tls,udp,rtp,httpproxy",
            "-thread_queue_size", "1024",
            "-analyzeduration", config["analyzeduration"],
            "-probesize", config["probesize"],
            "-fflags", "+discardcorrupt+igndts",
            "-re",
            *hls_input_options,
            "-i", self.record_url,
            "-bufsize", config["bufsize"],
            "-sn",
            "-dn",
            "-reconnect_delay_max", "60",
            "-reconnect_streamed",
            "-reconnect_at_eof",
            "-max_muxing_queue_size", config["max_muxing_queue_size"],
            "-correct_ts_overflow", "1",
            "-avoid_negative_ts", "1",
            "-flush_packets", "1"
        ]
        # fmt: on

        if self.headers:
            command.insert(11, "-headers")
            command.insert(12, self.headers)

        if self.proxy:
            command.insert(1, "-http_proxy")
            command.insert(2, self.proxy)

        return command

    def _get_video_codec_options(self) -> list[str]:
        if self.video_bitrate:
            return ["-c:v", "libx264", "-preset", "veryfast", "-b:v", f"{self.video_bitrate}k"]
        return ["-c:v", "copy"]
