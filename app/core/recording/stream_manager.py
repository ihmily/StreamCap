import asyncio
import os
import shutil
import subprocess
import time
from datetime import datetime
from typing import TypeVar

from ...messages import desktop_notify, message_pusher
from ...models.media.video_quality_model import VideoQuality
from ...models.recording.recording_status_model import RecordingStatus
from ...utils import utils
from ...utils.logger import logger
from ..media import ffmpeg_builders
from ..media.direct_downloader import DirectStreamDownloader
from ..platforms import platform_handlers
from ..platforms.platform_handlers import StreamData
from ..runtime.process_manager import BackgroundService

T = TypeVar("T")


class LiveStreamRecorder:
    DEFAULT_SEGMENT_TIME = "1800"
    DEFAULT_SAVE_FORMAT = "mp4"
    DEFAULT_QUALITY = VideoQuality.OD
    STALL_TIMEOUT_SECONDS = 45
    MIN_VALID_OUTPUT_BYTES = 1024
    TEMPORARY_TS_TARGET_FORMATS = {"mp4", "mov", "mkv", "nut", "flv"}

    def __init__(self, app, recording, recording_info):
        self.app = app
        self.settings = app.settings
        self.recording = recording
        self.recording_info = recording_info
        self.subprocess_start_info = app.subprocess_start_up_info
        self.should_stop = False  # manually stopped
        self.auto_stop_requested = False

        self.user_config = self.settings.user_config
        self.account_config = self.settings.accounts_config
        self.platform_key = self._get_info("platform_key")
        self.cookies = self.settings.cookies_config.get(self.platform_key)

        self.platform = self._get_info("platform")
        self.live_url = self._get_info("live_url")
        self.output_dir = self._get_info("output_dir")
        self.segment_record = self._get_info("segment_record", default=False)
        self.segment_time = self._get_info("segment_time", default=self.DEFAULT_SEGMENT_TIME)
        self.quality = self._get_info("quality", default=self.DEFAULT_QUALITY)
        self.save_format = self._get_info("save_format", default=self.DEFAULT_SAVE_FORMAT).lower()
        self.proxy = self.is_use_proxy()
        self.direct_downloader = None
        self.uses_temporary_ts_capture = False
        self.segment_conversion_tasks: dict[str, asyncio.Task[str | None]] = {}
        self.min_valid_recording_duration = 25
        self.recording_start_time = 0
        os.makedirs(self.output_dir, exist_ok=True)
        self.app.language_manager.add_observer(self)
        self._ = {}
        self.load()

    def load(self):
        language = self.app.language_manager.language
        for key in ("recording_manager", "stream_manager"):
            self._.update(language.get(key, {}))

    def _get_info(self, key: str, default: T = None) -> T:
        return self.recording_info.get(key, default) or default

    def is_use_proxy(self):
        default_proxy_platform = self.user_config.get("default_platform_with_proxy", "")
        proxy_list = default_proxy_platform.replace("，", ",").replace(" ", "").split(",")
        if self.user_config.get("enable_proxy") and self.platform_key in proxy_list:
            self.proxy = self.app.proxy_manager.get_proxy()
            return self.proxy

    def get_status_check_proxy(self):
        if self.app.proxy_manager.is_subscription_active():
            return self.app.proxy_manager.get_status_check_proxy()

        default_proxy_platform = self.user_config.get("default_platform_with_proxy", "")
        proxy_list = default_proxy_platform.replace("，", ",").replace(" ", "").split(",")
        if self.user_config.get("enable_proxy") and self.platform_key in proxy_list:
            return self.app.proxy_manager.get_status_check_proxy()

    def _get_status_check_attempts(self) -> int:
        if not self.app.proxy_manager.is_subscription_active():
            return 1

        proxy_count = len(self.app.proxy_manager.subscription_proxy_addresses)
        if proxy_count <= 0:
            return 1

        return min(proxy_count, 3)

    def _get_filename(self, stream_info: StreamData) -> str:
        live_title = None
        stream_info.title = utils.clean_name(stream_info.title, None)
        if self.user_config.get("filename_includes_title") and stream_info.title:
            stream_info.title = self._clean_and_truncate_title(stream_info.title)
            live_title = stream_info.title

        if self.recording.streamer_name and self.recording.streamer_name != self._["live_room"]:
            stream_info.anchor_name = utils.clean_name(self.recording.streamer_name)
        else:
            stream_info.anchor_name = utils.clean_name(stream_info.anchor_name, self._["live_room"])

        now = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())

        custom_template = self.user_config.get("custom_filename_template")
        if custom_template:
            filename = custom_template
            filename = filename.replace("{anchor_name}", stream_info.anchor_name or "")
            filename = filename.replace("{title}", live_title or "")
            filename = filename.replace("{time}", now)
            filename = filename.replace("{platform}", stream_info.platform or "")

            while "__" in filename:
                filename = filename.replace("__", "_")

            filename = filename.strip("_")

            if not filename:
                full_filename = "_".join([i for i in (stream_info.anchor_name, live_title, now) if i])
            else:
                full_filename = filename
        else:
            full_filename = "_".join([i for i in (stream_info.anchor_name, live_title, now) if i])

        return full_filename

    def _get_output_dir(self, stream_info: StreamData) -> str:
        if self.recording.recording_dir and self.user_config.get("folder_name_time"):
            current_date = datetime.today().strftime("%Y-%m-%d")
            if current_date not in self.recording.recording_dir:
                self.recording.recording_dir = None

        if self.recording.recording_dir:
            return self.recording.recording_dir

        now = datetime.today().strftime("%Y-%m-%d_%H-%M-%S")
        output_dir = self.output_dir.rstrip("/").rstrip("\\")
        if self.user_config.get("folder_name_platform"):
            output_dir = os.path.join(output_dir, stream_info.platform)
        if self.user_config.get("folder_name_author"):
            output_dir = os.path.join(output_dir, stream_info.anchor_name)
        if self.user_config.get("folder_name_time"):
            output_dir = os.path.join(output_dir, now[:10])
        if self.user_config.get("folder_name_title") and stream_info.title:
            live_title = self._clean_and_truncate_title(stream_info.title)
            if self.user_config.get("folder_name_time"):
                output_dir = os.path.join(output_dir, f"{live_title}_{stream_info.anchor_name}")
            else:
                output_dir = os.path.join(output_dir, f"{now[:10]}_{live_title}")
        os.makedirs(output_dir, exist_ok=True)
        self.recording.recording_dir = output_dir
        self.app.page.run_task(self.app.record_manager.persist_recordings)
        return output_dir

    def _get_save_path(self, filename: str, use_direct_download: bool = False) -> str:
        suffix = self.save_format
        suffix = "_%03d." + suffix if self.segment_record and not use_direct_download else "." + suffix
        save_file_path = os.path.join(self.output_dir, filename + suffix).replace(" ", "_")
        return save_file_path.replace("\\", "/")

    @staticmethod
    def _clean_and_truncate_title(title: str) -> str | None:
        if not title:
            return None
        cleaned_title = title[:30].replace("，", ",").replace(" ", "")
        return cleaned_title

    def _get_output_files(self, save_file_path: str) -> list[str]:
        normalized_path = save_file_path.replace("\\", "/")
        if not self.segment_record:
            return [normalized_path] if os.path.exists(normalized_path) else []

        directory = os.path.dirname(normalized_path)
        if not os.path.isdir(directory):
            return []

        filename = os.path.basename(normalized_path)
        segment_marker = "_%03d."
        if segment_marker in filename:
            prefix, suffix = filename.split(segment_marker, maxsplit=1)
            suffix = "." + suffix
        else:
            prefix, suffix = os.path.splitext(filename)

        output_files = []
        for name in os.listdir(directory):
            full_path = os.path.join(directory, name).replace("\\", "/")
            if os.path.isfile(full_path) and name.startswith(prefix) and name.endswith(suffix):
                output_files.append(full_path)
        return sorted(output_files)

    def _get_output_size(self, save_file_path: str) -> int:
        total_size = 0
        for output_file in self._get_output_files(save_file_path):
            try:
                total_size += os.path.getsize(output_file)
            except OSError:
                continue
        return total_size

    def _get_output_progress_marker(self, save_file_path: str) -> tuple[str, int] | None:
        output_files = self._get_output_files(save_file_path)
        if not output_files:
            return None

        latest_output = output_files[-1]
        try:
            latest_size = os.path.getsize(latest_output)
        except OSError:
            return None

        return latest_output, latest_size

    def _cleanup_invalid_output_files(self, save_file_path: str) -> bool:
        valid_output_found = False
        removed_files = []

        for output_file in self._get_output_files(save_file_path):
            try:
                file_size = os.path.getsize(output_file)
            except OSError:
                continue

            if file_size >= self.MIN_VALID_OUTPUT_BYTES:
                valid_output_found = True
                continue

            try:
                os.remove(output_file)
                removed_files.append(output_file)
            except OSError as e:
                logger.warning(f"Failed to remove incomplete recording file {output_file}: {e}")

        if removed_files:
            logger.warning(f"Removed incomplete recording files: {removed_files}")

        return valid_output_found

    @property
    def is_flv_preferred_platform(self):
        return self.platform_key in {"douyin", "tiktok"}

    def _select_source_url(self, stream_info: StreamData):
        if (
                self.user_config.get("default_live_source") != "HLS"
                and self.is_flv_preferred_platform
        ):
            codec = utils.get_query_params(stream_info.flv_url, "codec")
            if codec and codec[0] == 'h265':
                logger.warning("FLV is not supported for h265 codec, use HLS source instead")
            else:
                return stream_info.flv_url

        return stream_info.record_url

    def _get_record_url(self, stream_info: StreamData):

        url = self._select_source_url(stream_info)

        http_record_list = ["shopee", "migu"]
        if self.user_config.get("force_https_recording") and url.startswith("http://"):
            url = url.replace("http://", "https://")

        if self.platform_key in http_record_list:
            url = url.replace("https://", "http://")
        return url

    def set_preview_url(self, stream_info: StreamData):
        self.recording.preview_url = stream_info.m3u8_url or stream_info.flv_url

    def _get_record_format(self, stream_info: StreamData):
        use_flv_record = ["shopee"]
        if stream_info.flv_url:
            if self.platform_key in use_flv_record or self.recording.flv_use_direct_download:
                self.save_format = "flv"
                self.recording.record_format = self.save_format
                self.recording.segment_record = False
                return self.save_format, True

            elif self.save_format == "flv":
                codec = utils.get_query_params(stream_info.flv_url, "codec")
                if codec and codec[0] == 'h265':
                    logger.warning("FLV is not supported for h265 codec, use TS format instead")
                    self.save_format = "ts"

        return self.save_format, False

    @staticmethod
    def _looks_like_hls_source(*urls: str | None) -> bool:
        for url in urls:
            if isinstance(url, str) and ".m3u8" in url.lower():
                return True
        return False

    @classmethod
    def should_capture_as_ts_for_requested_format(
            cls,
            requested_format: str,
            use_direct_download: bool,
            record_url: str | None,
            stream_info: StreamData
    ) -> bool:
        normalized_format = (requested_format or "").lower()
        if use_direct_download or normalized_format not in cls.TEMPORARY_TS_TARGET_FORMATS:
            return False

        return cls._looks_like_hls_source(
            record_url,
            getattr(stream_info, "record_url", None),
            getattr(stream_info, "m3u8_url", None),
        )

    @staticmethod
    def should_delete_original_after_conversion(
            delete_original_setting: bool,
            uses_temporary_capture: bool
    ) -> bool:
        # When TS is only a temporary capture container, it should never be
        # kept after the final requested format is produced.
        return uses_temporary_capture or delete_original_setting

    @staticmethod
    def get_post_record_conversion_target(
            capture_format: str,
            requested_format: str,
            convert_to_mp4_setting: bool,
            uses_temporary_capture: bool
    ) -> str | None:
        normalized_capture_format = (capture_format or "").lower()
        normalized_requested_format = (requested_format or "").lower()

        if uses_temporary_capture and normalized_requested_format and normalized_requested_format != normalized_capture_format:
            return normalized_requested_format

        if normalized_capture_format == "ts" and convert_to_mp4_setting:
            return "mp4"

        return None

    @staticmethod
    def get_converted_output_path(source_file_path: str, target_format: str) -> str:
        normalized_path = source_file_path.replace("\\", "/")
        return normalized_path.rsplit(".", maxsplit=1)[0] + "." + target_format.lower()

    def _get_conversion_candidates(
            self,
            save_file_path: str,
            include_latest_segment: bool = True
    ) -> list[str]:
        output_files = self._get_output_files(save_file_path)
        if self.segment_record and not include_latest_segment:
            output_files = output_files[:-1]

        in_progress_sources = set(self.segment_conversion_tasks)
        return [path for path in output_files if path not in in_progress_sources]

    def _queue_output_conversions(
            self,
            save_file_path: str,
            target_format: str,
            delete_original_after_conversion: bool,
            include_latest_segment: bool = True
    ) -> None:
        for source_path in self._get_conversion_candidates(save_file_path, include_latest_segment):
            self.segment_conversion_tasks[source_path] = asyncio.create_task(
                self.convert_recording_output(
                    source_path,
                    target_format,
                    delete_original_after_conversion,
                )
            )

    async def _drain_output_conversion_tasks(self, wait_for_all: bool = False) -> list[str]:
        converted_outputs = []
        for source_path, task in list(self.segment_conversion_tasks.items()):
            if not wait_for_all and not task.done():
                continue

            try:
                converted_path = await task
                if converted_path:
                    converted_outputs.append(converted_path)
            except Exception as e:
                logger.error(f"Failed to convert recording output: {e}")
            finally:
                self.segment_conversion_tasks.pop(source_path, None)

        return converted_outputs

    async def fetch_stream(self) -> StreamData:
        logger.info(f"Live URL: {self.live_url}")
        total_attempts = self._get_status_check_attempts()
        last_stream_info = None

        for attempt in range(total_attempts):
            request_proxy = self.get_status_check_proxy()
            masked_proxy = self.app.proxy_manager.mask_proxy_value(request_proxy) or None

            if total_attempts > 1:
                logger.info(f"Use Proxy [{attempt + 1}/{total_attempts}]: {masked_proxy}")
            else:
                logger.info(f"Use Proxy: {masked_proxy}")

            self.recording.use_proxy = bool(request_proxy or self.proxy)
            handler = platform_handlers.get_platform_handler(
                live_url=self.live_url,
                proxy=request_proxy,
                cookies=self.cookies,
                record_quality=self.quality,
                platform=self.platform,
                username=self.account_config.get(self.platform_key, {}).get("username"),
                password=self.account_config.get(self.platform_key, {}).get("password"),
                account_type=self.account_config.get(self.platform_key, {}).get("account_type")
            )

            stream_info = await handler.get_stream_info(self.live_url)
            last_stream_info = stream_info

            if stream_info and getattr(stream_info, "anchor_name", None):
                self.recording.is_checking = False
                return stream_info

            if attempt + 1 < total_attempts:
                logger.warning(
                    f"Fetch stream data failed with proxy {masked_proxy}, retrying next subscription proxy"
                )

        self.recording.is_checking = False
        return last_stream_info

    async def start_recording(self, stream_info: StreamData):
        """
        Construct ffmpeg recording parameters and start recording
        """

        self.save_format, use_direct_download = self._get_record_format(stream_info)
        requested_save_format = self.save_format
        self.uses_temporary_ts_capture = False
        self.segment_conversion_tasks.clear()
        filename = self._get_filename(stream_info)
        self.output_dir = self._get_output_dir(stream_info)
        record_url = self._get_record_url(stream_info)
        self.set_preview_url(stream_info)

        if self.should_capture_as_ts_for_requested_format(
                requested_save_format,
                use_direct_download,
                record_url,
                stream_info,
        ):
            self.uses_temporary_ts_capture = True
            self.save_format = "ts"
            logger.info(
                f"Detected HLS/TS source for requested {requested_save_format.upper()} recording, "
                "capturing as TS and converting to the requested format after recording completes"
            )

        save_path = self._get_save_path(filename, use_direct_download)
        logger.info(f"Save Path: {save_path}")
        self.recording.recording_dir = os.path.dirname(save_path)
        os.makedirs(self.recording.recording_dir, exist_ok=True)

        try:
            if self.recording.rec_id in self.app.record_manager.active_recorders:
                old_recorder = self.app.record_manager.active_recorders[self.recording.rec_id]
                logger.warning(
                    f"Found existing recorder instance for {self.recording.rec_id}, id: {id(old_recorder)}, stopping it"
                )
                old_recorder.request_stop()

                await asyncio.sleep(1)
            
            self.app.record_manager.active_recorders[self.recording.rec_id] = self
            logger.info(f"Saved recorder instance for {self.recording.rec_id}, id: {id(self)}")
        except Exception as e:
            logger.error(f"Failed to save recorder instance: {e}")

        if use_direct_download:
            logger.info(f"Use Direct Downloader to Download FLV Stream: {record_url}")
            headers = {}
            header_params = self.get_headers_params(record_url, self.platform_key)
            if header_params:
                key, value = header_params.split(":", 1)
                headers[key] = value

            self.direct_downloader = DirectStreamDownloader(
                record_url=record_url,
                save_path=save_path,
                headers=headers,
                proxy=self.proxy
            )

            self.app.page.run_task(
                self.start_direct_download,
                stream_info.anchor_name,
                self.live_url,
                record_url,
                save_path,
                self.save_format,
                self.user_config.get("custom_script_command")
            )
        else:
            ffmpeg_builder = ffmpeg_builders.create_builder(
                self.save_format,
                record_url=record_url,
                proxy=self.proxy,
                segment_record=self.segment_record,
                segment_time=self.segment_time,
                full_path=save_path,
                headers=self.get_headers_params(record_url, self.platform_key)
            )
            ffmpeg_command = ffmpeg_builder.build_command()
            self.app.page.run_task(
                self.start_ffmpeg,
                stream_info.anchor_name,
                self.live_url,
                record_url,
                ffmpeg_command,
                self.save_format,
                requested_save_format,
                self.user_config.get("custom_script_command")
            )

    async def remove_active_recorder(self):
        try:
            if self.recording.rec_id in self.app.record_manager.active_recorders:
                del self.app.record_manager.active_recorders[self.recording.rec_id]
                logger.info(f"Removed recorder from active_recorders: {self.recording.rec_id}")
        except Exception as e:
            logger.error(f"Failed to remove recorder instance: {e}")

    async def recheck_live_status(self):
        if not self.should_stop:
            # not manually stopped
            recording_duration = time.time() - self.recording_start_time
            if recording_duration > self.min_valid_recording_duration:
                if self.app.recording_enabled and not self.is_flv_preferred_platform:
                    self.app.page.run_task(self.app.record_manager.check_if_live, self.recording)
            else:
                self.recording.status_info = RecordingStatus.RECORDING_ERROR

    async def start_ffmpeg(
            self,
            record_name: str,
            live_url: str,
            record_url: str,
            ffmpeg_command: list,
            save_type: str,
            requested_save_type: str,
            script_command: str | None = None
    ) -> bool:
        """
        The child process executes ffmpeg for recording
        """

        logger.info(f"Starting ffmpeg recording - recorder id: {id(self)}, rec_id: {self.recording.rec_id}")
        self.should_stop = False
        self.auto_stop_requested = False
        runtime_task = asyncio.current_task()
        self.app.record_manager.register_runtime_task(runtime_task)

        try:
            save_file_path = ffmpeg_command[-1]
            stalled_recording = False
            valid_output = True
            conversion_target_format = self.get_post_record_conversion_target(
                capture_format=save_type,
                requested_format=requested_save_type,
                convert_to_mp4_setting=self.user_config.get("convert_to_mp4"),
                uses_temporary_capture=self.uses_temporary_ts_capture,
            )
            delete_original_after_conversion = self.should_delete_original_after_conversion(
                self.user_config.get("delete_original", False),
                self.uses_temporary_ts_capture,
            )

            process = await asyncio.create_subprocess_exec(
                *ffmpeg_command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                startupinfo=self.subprocess_start_info
            )

            self.app.add_ffmpeg_process(process)
            self.recording.status_info = RecordingStatus.RECORDING
            self.recording.record_url = record_url
            logger.info(f"Recording in Progress: {live_url}")
            logger.log("STREAM", f"Recording Stream URL: {record_url}")
            self.recording_start_time = time.time()
            last_output_marker = None
            last_output_at = self.recording_start_time

            while True:
                await self._drain_output_conversion_tasks()
                if self.segment_record and conversion_target_format:
                    self._queue_output_conversions(
                        save_file_path,
                        conversion_target_format,
                        delete_original_after_conversion,
                        include_latest_segment=False,
                    )

                current_output_marker = self._get_output_progress_marker(save_file_path)
                if current_output_marker and current_output_marker != last_output_marker:
                    last_output_marker = current_output_marker
                    last_output_at = time.time()
                elif (
                    time.time() - self.recording_start_time > self.min_valid_recording_duration
                    and time.time() - last_output_at > self.STALL_TIMEOUT_SECONDS
                ):
                    logger.warning(
                        f"Recording output stalled for {self.STALL_TIMEOUT_SECONDS}s, stopping recorder: {live_url}"
                    )
                    self.auto_stop_requested = True
                    stalled_recording = True

                if self.should_stop or self.auto_stop_requested or self.recording.force_stop or not self.app.recording_enabled:
                    logger.info(f"Preparing to End Recording: {live_url}")
                    await self.remove_active_recorder()
                    self.recording.is_recording = False
                    try:
                        if os.name == "nt":
                            if process.stdin:
                                process.stdin.write(b"q")
                                await process.stdin.drain()
                                await asyncio.sleep(5)
                        else:
                            import signal
                            process.send_signal(signal.SIGINT)
                            # process.terminate()
                            await asyncio.sleep(5)

                        if process.stdin:
                            process.stdin.close()

                        await asyncio.wait_for(process.wait(), timeout=15.0)
                    except asyncio.TimeoutError:
                        logger.warning(f"FFmpeg process did not exit gracefully, forcing termination: {live_url}")
                        process.kill()
                        await process.wait()

                    self.recording.force_stop = False
                    break

                if process.returncode is not None:
                    logger.info(f"Exit loop recording (normal 0 | abnormal 1): code={process.returncode}, {live_url}")
                    await self.remove_active_recorder()
                    self.recording.is_recording = False
                    break

                await asyncio.sleep(1)

            return_code = process.returncode
            safe_return_code = [0, 255]
            stdout, stderr = await process.communicate()
            valid_output = self._cleanup_invalid_output_files(save_file_path)
             
            if return_code not in safe_return_code and stderr:
                if not self.recording.is_recording:
                    logger.error(f"FFmpeg Stderr Output: {str(stderr.decode()).splitlines()[0]}")
                    self.recording.status_info = RecordingStatus.RECORDING_ERROR

                    try:
                        self.app.record_manager.stop_recording(self.recording)
                        await self.app.record_card_manager.update_card(self.recording)
                        self.app.page.pubsub.send_others_on_topic("update", self.recording)
                        await self.app.snack_bar.show_snack_bar(
                            record_name + " " + self._["record_stream_error"], duration=2000
                        )
                    except Exception as e:
                        logger.debug(f"Failed to update UI: {e}")

            if return_code in safe_return_code:
                self.recording.is_live = False
                if not self.recording.is_recording:
                    if self.recording.monitor_status:
                        self.recording.status_info = RecordingStatus.MONITORING
                        display_title = self.recording.title
                    else:
                        self.recording.status_info = RecordingStatus.STOPPED_MONITORING
                        display_title = self.recording.display_title

                    self.recording.live_title = None
                    if self.should_stop:
                        logger.success(f"Live recording has stopped: {record_name}")
                    elif stalled_recording:
                        logger.warning(f"Live recording stopped after stream stalled: {record_name}")
                    else:
                        logger.success(f"Live recording completed: {record_name}")
                        if valid_output:
                            self.app.page.run_task(self.end_message_push)
                    
                    try:
                        self.recording.update({"display_title": display_title})
                        self.app.page.run_task(self.app.record_card_manager.update_card, self.recording)
                        self.app.page.pubsub.send_others_on_topic("update", self.recording)
                    except Exception as e:
                        logger.debug(f"Failed to update UI: {e}")

                if not self.app.recording_enabled:
                    self.recording.status_info = RecordingStatus.NOT_RECORDING_SPACE
                    self.app.page.run_task(self.stop_recording_notify)

                await self.recheck_live_status()

                if not valid_output:
                    logger.warning(f"Discarded invalid recording output: {save_file_path}")
                    return True

                script_save_file_path = save_file_path
                script_save_type = save_type

                if conversion_target_format:
                    converted_outputs = await self._drain_output_conversion_tasks()
                    self._queue_output_conversions(
                        save_file_path,
                        conversion_target_format,
                        delete_original_after_conversion,
                        include_latest_segment=True,
                    )
                    converted_outputs.extend(await self._drain_output_conversion_tasks(wait_for_all=True))

                    if converted_outputs:
                        script_save_file_path = self.get_converted_output_path(
                            save_file_path,
                            conversion_target_format,
                        )
                        script_save_type = conversion_target_format

                if self.user_config.get("execute_custom_script") and script_command:
                    logger.info("Prepare a direct script in the background")
                    try:
                        self.app.page.run_task(
                            self.custom_script_execute,
                            script_command,
                            record_name,
                            script_save_file_path,
                            script_save_type,
                            self.segment_record,
                            script_save_type == "mp4"
                        )
                        logger.success("Successfully added script execution")
                    except Exception as e:
                        logger.error(f"Failed to execute custom script: {e}")
                        await self.custom_script_execute(
                            script_command,
                            record_name,
                            script_save_file_path,
                            script_save_type,
                            self.segment_record,
                            script_save_type == "mp4"
                        )

        except Exception as e:
            logger.error(f"An error occurred during the subprocess execution: {e}")
            self.recording.status_info = RecordingStatus.RECORDING_ERROR

            try:
                self.app.record_manager.stop_recording(self.recording)
                await self.app.record_card_manager.update_card(self.recording)
                self.app.page.pubsub.send_others_on_topic("update", self.recording)
                await self.app.snack_bar.show_snack_bar(
                    record_name + " " + self._["no_ffmpeg_tip"], duration=4000
                )
            except Exception as e:
                logger.debug(f"Failed to update UI: {e}")
            return False
        finally:
            if self.segment_conversion_tasks:
                await self._drain_output_conversion_tasks(wait_for_all=True)
            self.app.record_manager.unregister_runtime_task(runtime_task)
            self.recording.record_url = None
            self.auto_stop_requested = False

        return True

    async def converts_mp4(self, converts_file_path: str, is_original_delete: bool = True) -> None:
        """Asynchronous transcoding method, can be added to the background service to continue execution"""
        await self.convert_recording_output(converts_file_path, "mp4", is_original_delete)

    def converts_mp4_sync(self, converts_file_path: str, is_original_delete: bool = True) -> None:
        """Synchronous version of the transcoding method, used for background service"""
        self.convert_recording_output_sync(converts_file_path, "mp4", is_original_delete)

    async def convert_recording_output(
            self,
            source_file_path: str,
            target_format: str,
            is_original_delete: bool = True
    ) -> str | None:
        """Convert a temporary recording output into the requested target format."""
        if not self.app.recording_enabled:
            logger.info(
                f"Application is closing, adding conversion task to background service: {source_file_path}"
            )
            BackgroundService.get_instance().add_task(
                self.convert_recording_output_sync, source_file_path, target_format, is_original_delete
            )
            return self.get_converted_output_path(source_file_path, target_format)

        return await self._do_convert_recording_output(source_file_path, target_format, is_original_delete)

    def convert_recording_output_sync(
            self,
            source_file_path: str,
            target_format: str,
            is_original_delete: bool = True
    ) -> str | None:
        """Synchronous version of the conversion method, used for background service."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self._do_convert_recording_output(source_file_path, target_format, is_original_delete)
            )
        finally:
            loop.close()

    @staticmethod
    def _build_conversion_command(
            source_file_path: str,
            target_format: str,
            save_path: str
    ) -> list[str]:
        base_command = [
            "ffmpeg",
            "-y",
            "-i", source_file_path,
            "-map", "0",
        ]
        format_options = {
            "mp4": [
                "-c:v", "copy",
                "-c:a", "copy",
                "-f", "mp4",
                "-movflags", "+faststart",
            ],
            "mov": [
                "-c:v", "copy",
                "-c:a", "aac",
                "-f", "mov",
                "-movflags", "+faststart",
            ],
            "mkv": [
                "-flags", "global_header",
                "-c:v", "copy",
                "-c:a", "copy",
                "-f", "matroska",
            ],
            "flv": [
                "-c:v", "copy",
                "-c:a", "copy",
                "-bsf:a", "aac_adtstoasc",
                "-f", "flv",
            ],
            "nut": [
                "-c:v", "copy",
                "-c:a", "copy",
                "-f", "nut",
                "-muxdelay", "0",
                "-muxpreload", "0",
            ],
        }
        conversion_options = format_options.get(target_format.lower())
        if not conversion_options:
            raise ValueError(f"Unsupported conversion target format: {target_format}")

        return base_command + conversion_options + [save_path]

    async def _do_convert_recording_output(
            self,
            source_file_path: str,
            target_format: str,
            is_original_delete: bool = True
    ) -> str | None:
        """Actual execution method for converting recordings into the final target format."""
        converts_success = False
        save_path = None
        try:
            source_file_path = source_file_path.replace("\\", "/")
            if os.path.exists(source_file_path) and os.path.getsize(source_file_path) > 0:
                save_path = self.get_converted_output_path(source_file_path, target_format)
                ffmpeg_command = self._build_conversion_command(
                    source_file_path,
                    target_format,
                    save_path,
                )
                process = await asyncio.create_subprocess_exec(
                    *ffmpeg_command,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    startupinfo=self.subprocess_start_info
                )

                self.app.add_ffmpeg_process(process)
                task = asyncio.create_task(process.communicate())
                _, stderr = await task
                if process.returncode == 0:
                    converts_success = True
                    logger.info(f"Recording conversion completed: {save_path}")
                else:
                    logger.error(
                        f"Recording conversion failed! Error message: {stderr.decode() if stderr else 'Unknown error'}")

        except subprocess.CalledProcessError as e:
            logger.error(f"Recording conversion failed! Error message: {e.output.decode()}")

        try:
            if converts_success:
                if is_original_delete:
                    await asyncio.sleep(1)
                    if os.path.exists(source_file_path):
                        os.remove(source_file_path)
                    logger.info(f"Delete Original File: {source_file_path}")
                else:
                    converts_dir = f"{os.path.dirname(save_path)}/original"
                    os.makedirs(converts_dir, exist_ok=True)
                    shutil.move(source_file_path, converts_dir)
                    logger.info(f"Move Converted Source File: {source_file_path}")
                return save_path

        except subprocess.CalledProcessError as e:
            logger.error(f"Error occurred during conversion: {e}")
        except Exception as e:
            logger.error(f"An unknown error occurred: {e}")

        return None

    async def custom_script_execute(
            self,
            script_command: str,
            record_name: str,
            save_file_path: str,
            save_type: str,
            split_video_by_time: bool,
            converts_to_mp4: bool
    ):
        from ..runtime.process_manager import BackgroundService

        if "python" in script_command:
            params = [
                f'--record_name "{record_name}"',
                f'--save_file_path "{save_file_path}"',
                f'--save_type {save_type}',
                f'--split_video_by_time {split_video_by_time}',
                f'--converts_to_mp4 {converts_to_mp4}',
            ]
        else:
            params = [
                f'"{record_name.split(" ", maxsplit=1)[-1]}"',
                f'"{save_file_path}"',
                save_type,
                f"split_video_by_time: {split_video_by_time}",
                f"converts_to_mp4: {converts_to_mp4}"
            ]
        script_command = script_command.strip() + " " + " ".join(params)

        if not self.app.recording_enabled:
            logger.info("Application is closing, adding script execution task to background service")
            BackgroundService.get_instance().add_task(self.run_script_sync, script_command)
        else:
            self.app.page.run_task(self.run_script_async, script_command)

        logger.success("Script command execution initiated!")

    def run_script_sync(self, command: str) -> None:
        """Synchronous version of the script execution method, used for background service"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.run_script_async(command))
        finally:
            loop.close()

    async def run_script_async(self, command: str) -> None:
        try:
            process = await asyncio.create_subprocess_exec(
                *command.split(),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                startupinfo=self.subprocess_start_info,
                text=False
            )

            stdout, stderr = await process.communicate()

            if stdout:
                logger.info(stdout.splitlines()[0].decode())
            if stderr:
                logger.error(stderr.splitlines()[0].decode())

            if process.returncode != 0:
                logger.info(f"Custom Script process exited with return code {process.returncode}")

        except PermissionError:
            logger.error(
                "Script has no execution permission!, If it is a Linux environment, "
                "please first execute: chmod+x your_script.sh to grant script executable permission"
            )
        except OSError:
            logger.error("Please add `#!/bin/bash` at the beginning of your bash script file.")
        except Exception as e:
            logger.error(f"An error occurred: {e}")

    @staticmethod
    def get_headers_params(live_url, platform_key):
        live_domain = "/".join(live_url.split("/")[0:3])
        record_headers = {
            "pandalive": "origin:https://www.pandalive.co.kr",
            "winktv": "origin:https://www.winktv.co.kr",
            "popkontv": "origin:https://www.popkontv.com",
            "flextv": "origin:https://www.flextv.co.kr",
            "qiandurebo": "referer:https://qiandurebo.com",
            "17live": "referer:https://17.live/en/live/6302408",
            "lang": "referer:https://www.lang.live",
            "shopee": "origin:" + live_domain,
            "blued": "referer:https://app.blued.cn",
        }
        return record_headers.get(platform_key)

    async def start_direct_download(
            self,
            record_name: str,
            live_url: str,
            record_url: str,
            save_file_path: str,
            save_type: str,
            script_command: str | None = None
    ) -> bool:
        """
        Use the direct downloader to download the live stream
        """
        
        logger.info(f"Starting direct download - recorder id: {id(self)}, rec_id: {self.recording.rec_id}")
        self.should_stop = False
        self.auto_stop_requested = False
        runtime_task = asyncio.current_task()
        self.app.record_manager.register_runtime_task(runtime_task)
        
        try:
            await self.direct_downloader.start_download()
            stalled_recording = False
            valid_output = True

            self.recording.status_info = RecordingStatus.RECORDING
            self.recording.record_url = record_url
            logger.info(f"Direct Downloading: {live_url}")
            logger.log("STREAM", f"Direct Download Stream URL: {record_url}")
            self.recording_start_time = time.time()
            last_output_size = 0
            last_output_at = self.recording_start_time

            while True:
                current_output_size = self._get_output_size(save_file_path)
                if current_output_size > last_output_size:
                    last_output_size = current_output_size
                    last_output_at = time.time()
                elif (
                    time.time() - self.recording_start_time > self.min_valid_recording_duration
                    and time.time() - last_output_at > self.STALL_TIMEOUT_SECONDS
                ):
                    logger.warning(
                        f"Direct download stalled for {self.STALL_TIMEOUT_SECONDS}s, stopping recorder: {live_url}"
                    )
                    self.auto_stop_requested = True
                    stalled_recording = True

                if self.should_stop or self.auto_stop_requested or self.recording.force_stop or not self.app.recording_enabled:
                    logger.info(f"Prepare to end direct download: {live_url}")
                    await self.remove_active_recorder()
                    self.recording.is_recording = False
                    await self.direct_downloader.stop_download()
                    self.recording.force_stop = False
                    break

                await asyncio.sleep(1)

                if self.direct_downloader.download_task and self.direct_downloader.download_task.done():
                    break

            await self.remove_active_recorder()
            self.recording.is_recording = False
            valid_output = self._cleanup_invalid_output_files(save_file_path)

            if not self.recording.is_recording:
                self.recording.is_live = False
                if self.recording.monitor_status:
                    self.recording.status_info = RecordingStatus.MONITORING
                    display_title = self.recording.title
                else:
                    self.recording.status_info = RecordingStatus.STOPPED_MONITORING
                    display_title = self.recording.display_title

                self.recording.live_title = None
                if self.should_stop:
                    logger.success(f"Direct Downloading Stopped: {record_name}")
                elif stalled_recording:
                    logger.warning(f"Direct download stopped after stream stalled: {record_name}")
                else:
                    logger.success(f"Direct Downloading Completed: {record_name}")
                    if valid_output:
                        self.app.page.run_task(self.end_message_push)

                try:
                    self.recording.update({"display_title": display_title})
                    await self.app.record_card_manager.update_card(self.recording)
                    self.app.page.pubsub.send_others_on_topic("update", self.recording)
                except Exception as e:
                    logger.debug(f"Failed to update UI: {e}")

            if not self.app.recording_enabled:
                self.recording.status_info = RecordingStatus.NOT_RECORDING_SPACE
                self.app.page.run_task(self.stop_recording_notify)

            await self.recheck_live_status()

            if not valid_output:
                logger.warning(f"Discarded invalid direct download output: {save_file_path}")
                return True

            if self.user_config.get("execute_custom_script") and script_command:
                logger.info("Prepare to execute custom script in the background")
                try:
                    self.app.page.run_task(
                        self.custom_script_execute,
                        script_command,
                        record_name,
                        save_file_path,
                        save_type,
                        False,
                        False
                    )
                    logger.success("Successfully added script execution")
                except Exception as e:
                    logger.error(f"Failed to execute custom script: {e}")
                    await self.custom_script_execute(
                        script_command,
                        record_name,
                        save_file_path,
                        save_type,
                        False,
                        False
                    )

            return True

        except Exception as e:
            logger.error(f"Error occurred during direct download: {e}")
            self.recording.status_info = RecordingStatus.RECORDING_ERROR

            try:
                self.app.record_manager.stop_recording(self.recording)
                await self.app.record_card_manager.update_card(self.recording)
                self.app.page.pubsub.send_others_on_topic("update", self.recording)
                await self.app.snack_bar.show_snack_bar(
                    record_name + " " + self._["record_stream_error"], duration=2000
                )
            except Exception as e:
                logger.debug(f"Failed to update UI: {e}")
            return False
        finally:
            self.app.record_manager.unregister_runtime_task(runtime_task)
            self.recording.record_url = None
            self.auto_stop_requested = False

    async def stop_recording_notify(self):
        if desktop_notify.should_push_notification(self.app):
            desktop_notify.send_notification(
                title=self._["notify"],
                message=self.recording.streamer_name + ' | ' + self._["live_recording_stopped_message"],
                app_icon=self.app.tray_manager.icon_path
            )

    async def end_message_push(self):
        msg_manager = message_pusher.MessagePusher(self.settings)
        user_config = self.settings.user_config

        if (self.app.recording_enabled and msg_manager.should_push_message(
                self.settings, self.recording, check_manually_stopped=True, message_type='end') and
                not self.recording.notified_live_end):
            self.recording.notified_live_end = True
            push_content = self._["push_content_end"]
            end_push_message_text = user_config.get("custom_stream_end_content")
            if end_push_message_text:
                push_content = end_push_message_text

            push_at = datetime.today().strftime("%Y-%m-%d %H:%M:%S")
            push_content = push_content.replace("[room_name]", self.recording.streamer_name).replace(
                "[time]", push_at).replace("[title]", self.recording.live_title or "None")
            msg_title = user_config.get("custom_notification_title").strip()
            msg_title = msg_title or self._["status_notify"]

            self.app.page.run_task(msg_manager.push_messages, msg_title, push_content)

    def request_stop(self):
        logger.info(f"Stop requested for recorder: {self.recording.url}, rec_id: {self.recording.rec_id}")
        logger.info(f"Recorder instance details - id: {id(self)}, recording: {self.recording.title}")
        
        old_value = self.should_stop
        self.should_stop = True
        
        logger.info(f"Set should_stop from {old_value} to {self.should_stop} for recorder: {self.recording.rec_id}")
