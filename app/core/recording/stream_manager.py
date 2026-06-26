import asyncio
import os
import shutil
import subprocess
import sys
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

    def __init__(self, services, recording, recording_info):
        self.services = services
        self.settings = services.settings_config
        self.recording = recording
        self.recording_info = recording_info
        self.subprocess_start_info = services.subprocess_start_up_info
        self.should_stop = False  # manually stopped

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
        self.min_valid_recording_duration = 25
        self.recording_start_time = 0
        self.history_start_recorded = False
        os.makedirs(self.output_dir, exist_ok=True)
        self.services.language_manager.add_observer(self)
        self._ = {}
        self.load()

    @property
    def app(self):
        bridges = self.services.snapshot_bridges()
        return bridges[0] if bridges else None

    def load(self):
        language = self.services.language_manager.language
        for key in ("recording_manager", "stream_manager"):
            self._.update(language.get(key, {}))

    def _get_info(self, key: str, default: T = None) -> T:
        return self.recording_info.get(key, default) or default

    def is_use_proxy(self):
        default_proxy_platform = self.user_config.get("default_platform_with_proxy", "")
        proxy_list = default_proxy_platform.replace("，", ",").replace(" ", "").split(",")
        if self.user_config.get("enable_proxy") and self.platform_key in proxy_list:
            self.proxy = self.user_config.get("proxy_address")
            return self.proxy
        return None

    def _get_filename(self, stream_info: StreamData) -> str:
        live_title = None
        stream_info.title = utils.clean_name(stream_info.title, None)
        if self.user_config.get("filename_includes_title") and stream_info.title:
            stream_info.title = self._clean_and_truncate_title(stream_info.title) or stream_info.title
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
                full_filename = "_".join(i for i in (stream_info.anchor_name, live_title, now) if isinstance(i, str))
            else:
                full_filename = filename
        else:
            full_filename = "_".join(i for i in (stream_info.anchor_name, live_title, now) if isinstance(i, str))

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
        self.services.run_coro(self.services.recording_manager.persist_recordings())
        return output_dir

    def _get_save_path(self, filename: str, use_direct_download: bool = False) -> str:
        suffix = self.save_format
        suffix = "_%03d." + suffix if self.segment_record and not use_direct_download else "." + suffix
        full_output_dir = self.output_dir if sys.platform != "linux" else self.output_dir.replace(" ", "_")
        save_file_path = os.path.join(full_output_dir, (filename + suffix).replace(" ", "_"))
        return save_file_path.replace("\\", "/")

    @staticmethod
    def _clean_and_truncate_title(title: str) -> str | None:
        if not title:
            return None
        cleaned_title = title[:30].replace("，", ",").replace(" ", "")
        return cleaned_title

    def _handle_recording_error(self, record_name: str, error_msg: str, duration: int = 2000) -> None:
        self.recording.status_info = RecordingStatus.RECORDING_ERROR
        try:
            self.services.recording_manager.stop_recording(self.recording)
            self.services.broadcast_card_update(self.recording)
            self.services.broadcast_pubsub("update", self.recording)
            self.services.broadcast_snack(record_name + " " + error_msg, duration=duration)
        except Exception as e:
            logger.debug(f"Failed to update UI: {e}")

    def _is_stopping_or_shutting_down(self) -> bool:
        return self.should_stop or self.recording.manually_stopped or not self.services.recording_enabled

    @staticmethod
    def _decode_first_stderr_line(stderr: bytes | None) -> str:
        if not stderr:
            return ""
        decoded = stderr.decode(errors="replace").strip()
        return decoded.splitlines()[0] if decoded else ""

    async def _record_session_history(
        self,
        file_path: str | None,
        file_format: str | None,
        status: str,
        error_message: str = "",
    ) -> None:
        start_timestamp = getattr(self, "recording_start_time", None)
        started_at = None
        duration_seconds = None
        if start_timestamp:
            started_at = datetime.fromtimestamp(start_timestamp).isoformat(timespec="seconds")
            duration_seconds = max(0, int(time.time() - start_timestamp))

        if self.should_stop or self.recording.manually_stopped:
            stop_reason = "manual"
        elif not self.services.recording_enabled:
            stop_reason = "shutdown"
        else:
            stop_reason = status
        try:
            await self.services.recording_manager.record_session_history(
                recording=self.recording,
                file_path=file_path,
                file_format=file_format,
                status=status,
                stop_reason=stop_reason,
                error_message=error_message,
                started_at=started_at,
                ended_at=datetime.now().isoformat(timespec="seconds"),
                duration_seconds=duration_seconds,
            )
        except Exception as e:
            logger.debug(f"Failed to write recording history: {e}")

    async def _record_session_started(self, file_format: str | None) -> None:
        if self.history_start_recorded:
            return

        start_timestamp = getattr(self, "recording_start_time", None) or time.time()
        started_at = datetime.fromtimestamp(start_timestamp).isoformat(timespec="seconds")
        try:
            await self.services.recording_manager.record_session_history(
                recording=self.recording,
                file_path=None,
                file_format=file_format,
                status="started",
                stop_reason="started",
                started_at=started_at,
                ended_at=None,
                duration_seconds=0,
            )
            self.history_start_recorded = True
        except Exception as e:
            logger.debug(f"Failed to write recording start history: {e}")

    async def _handle_recording_finished(
        self,
        record_name: str,
        stop_msg: str = "",
        complete_msg: str = "",
        file_path: str | None = None,
        file_format: str | None = None,
    ) -> None:
        self.recording.is_live = False
        if self.recording.monitor_status:
            self.recording.status_info = RecordingStatus.MONITORING
            display_title = self.recording.title
        else:
            self.recording.status_info = RecordingStatus.STOPPED_MONITORING
            display_title = self.recording.display_title

        self.recording.live_title = None
        is_stopped = self._is_stopping_or_shutting_down()
        if is_stopped:
            logger.success(stop_msg or f"Live recording has stopped: {record_name}")
        else:
            logger.success(complete_msg or f"Live recording completed: {record_name}")
            asyncio.create_task(self.end_message_push())

        await self._record_session_history(
            file_path=file_path,
            file_format=file_format,
            status="stopped" if is_stopped else "completed",
        )

        try:
            self.recording.update({"display_title": display_title})
            self.services.broadcast_card_update(self.recording)
            self.services.broadcast_pubsub("update", self.recording)
        except Exception as e:
            logger.debug(f"Failed to update UI: {e}")

    @property
    def is_flv_preferred_platform(self):
        return self.platform_key in {"douyin", "tiktok"}

    def _select_source_url(self, stream_info: StreamData):
        if self.user_config.get("default_live_source") != "HLS" and self.is_flv_preferred_platform:
            codec = utils.get_query_params(stream_info.flv_url, "codec")
            if codec and codec[0] == "h265":
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
                if codec and codec[0] == "h265":
                    logger.warning("FLV is not supported for h265 codec, use TS format instead")
                    self.save_format = "ts"

        return self.save_format, False

    async def fetch_stream(self) -> StreamData | None:
        logger.info(f"Live URL: {self.live_url}")
        logger.info(f"Use Proxy: {self.proxy or None}")
        self.recording.use_proxy = bool(self.proxy)
        handler = platform_handlers.get_platform_handler(
            live_url=self.live_url,
            proxy=self.proxy,
            cookies=self.cookies,
            record_quality=self.quality,
            platform=self.platform,
            username=self.account_config.get(self.platform_key, {}).get("username"),
            password=self.account_config.get(self.platform_key, {}).get("password"),
            account_type=self.account_config.get(self.platform_key, {}).get("account_type"),
        )
        if not handler:
            logger.error(f"No handler found for platform: {self.recording.url}")
            return
        stream_info = await handler.get_stream_info(self.live_url)
        self.recording.is_checking = False
        return stream_info

    async def start_recording(self, stream_info: StreamData):
        """
        Construct ffmpeg recording parameters and start recording
        """

        self.save_format, use_direct_download = self._get_record_format(stream_info)
        filename = self._get_filename(stream_info)
        self.output_dir = self._get_output_dir(stream_info)
        save_path = self._get_save_path(filename, use_direct_download)
        logger.info(f"Save Path: {save_path}")
        self.recording.recording_dir = os.path.dirname(save_path)
        os.makedirs(self.recording.recording_dir, exist_ok=True)
        record_url = self._get_record_url(stream_info)
        self.set_preview_url(stream_info)

        try:
            if self.recording.rec_id in self.services.recording_manager.active_recorders:
                old_recorder = self.services.recording_manager.active_recorders[self.recording.rec_id]
                logger.warning(
                    f"Found existing recorder instance for {self.recording.rec_id}, id: {id(old_recorder)}, stopping it"
                )
                old_recorder.request_stop()

                await asyncio.sleep(1)

            self.services.recording_manager.active_recorders[self.recording.rec_id] = self
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
                record_url=record_url, save_path=save_path, headers=headers, proxy=self.proxy
            )

            self.services.run_coro(
                self.start_direct_download(
                    stream_info.anchor_name,
                    self.live_url,
                    record_url,
                    save_path,
                    self.save_format,
                    self.user_config.get("custom_script_command"),
                )
            )
        else:
            ffmpeg_builder = ffmpeg_builders.create_builder(
                self.save_format,
                record_url=record_url,
                proxy=self.proxy,
                segment_record=self.segment_record,
                segment_time=self.segment_time,
                full_path=save_path,
                headers=self.get_headers_params(record_url, self.platform_key),
            )
            ffmpeg_command = ffmpeg_builder.build_command()
            self.services.run_coro(
                self.start_ffmpeg(
                    stream_info.anchor_name,
                    self.live_url,
                    record_url,
                    ffmpeg_command,
                    self.save_format,
                    self.user_config.get("custom_script_command"),
                )
            )

    async def remove_active_recorder(self):
        try:
            if self.recording.rec_id in self.services.recording_manager.active_recorders:
                del self.services.recording_manager.active_recorders[self.recording.rec_id]
                logger.info(f"Removed recorder from active_recorders: {self.recording.rec_id}")
        except Exception as e:
            logger.error(f"Failed to remove recorder instance: {e}")

    async def recheck_live_status(self):
        if not self.should_stop:
            # not manually stopped
            recording_duration = time.time() - self.recording_start_time
            if recording_duration > self.min_valid_recording_duration:
                if self.services.recording_enabled and not self.is_flv_preferred_platform:
                    self.services.run_coro(self.services.recording_manager.check_if_live(self.recording))
            else:
                self.recording.status_info = RecordingStatus.RECORDING_ERROR

    async def start_ffmpeg(
        self,
        record_name: str,
        live_url: str,
        record_url: str,
        ffmpeg_command: list,
        save_type: str,
        script_command: str | None = None,
    ) -> bool:
        """
        The child process executes ffmpeg for recording
        """

        logger.info(f"Starting ffmpeg recording - recorder id: {id(self)}, rec_id: {self.recording.rec_id}")
        self.should_stop = False

        try:
            save_file_path = ffmpeg_command[-1]

            process = await asyncio.create_subprocess_exec(
                *ffmpeg_command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                startupinfo=self.subprocess_start_info,
            )

            self.services.process_manager.add_process(process)
            self.recording.status_info = RecordingStatus.RECORDING
            self.recording.record_url = record_url
            logger.info(f"Recording in Progress: {live_url}")
            logger.log("STREAM", f"Recording Stream URL: {record_url}")
            self.recording_start_time = time.time()
            await self._record_session_started(save_type)

            while True:
                if self.should_stop or self.recording.force_stop or not self.services.recording_enabled:
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

            if return_code not in safe_return_code:
                if not self.recording.is_recording:
                    error_message = self._decode_first_stderr_line(stderr)
                    if self._is_stopping_or_shutting_down():
                        logger.info(
                            f"FFmpeg exited while stopping, code={return_code}, "
                            f"message={error_message or 'None'}"
                        )
                        await self._handle_recording_finished(
                            record_name,
                            file_path=save_file_path,
                            file_format=save_type,
                        )
                    else:
                        logger.error(f"FFmpeg Stderr Output: {error_message or 'Unknown error'}")
                        await self._record_session_history(save_file_path, save_type, "error", error_message)
                        self._handle_recording_error(record_name, self._["record_stream_error"])

            if return_code in safe_return_code:
                if not self.recording.is_recording:
                    await self._handle_recording_finished(record_name, file_path=save_file_path, file_format=save_type)

                if not self.services.recording_enabled:
                    self.recording.status_info = RecordingStatus.NOT_RECORDING_SPACE
                    self.services.run_coro(self.stop_recording_notify())

                if not self.recording.manually_stopped:
                    await self.recheck_live_status()

                if self.user_config.get("convert_to_mp4") and self.save_format == "ts":
                    if self.segment_record:
                        file_paths = utils.get_file_paths(os.path.dirname(save_file_path))
                        prefix = os.path.basename(save_file_path).rsplit("_", maxsplit=1)[0]
                        for path in file_paths:
                            if prefix in path:
                                try:
                                    self.services.run_coro(self.converts_mp4(path, self.user_config["delete_original"]))
                                except Exception as e:
                                    logger.error(f"Failed to convert video: {e}")
                                    await self.converts_mp4(path, self.user_config["delete_original"])
                    else:
                        try:
                            self.services.run_coro(
                                self.converts_mp4(save_file_path, self.user_config["delete_original"])
                            )
                        except Exception as e:
                            logger.error(f"Failed to convert video: {e}")
                            await self.converts_mp4(save_file_path, self.user_config["delete_original"])

                if self.user_config.get("execute_custom_script") and script_command:
                    logger.info("Prepare a direct script in the background")
                    try:
                        self.services.run_coro(
                            self.custom_script_execute(
                                script_command,
                                record_name,
                                save_file_path,
                                save_type,
                                self.segment_record,
                                self.user_config.get("convert_to_mp4"),
                            )
                        )
                        logger.success("Successfully added script execution")
                    except Exception as e:
                        logger.error(f"Failed to execute custom script: {e}")
                        await self.custom_script_execute(
                            script_command,
                            record_name,
                            save_file_path,
                            save_type,
                            self.segment_record,
                            self.user_config.get("convert_to_mp4"),
                        )

        except Exception as e:
            logger.error(f"An error occurred during the subprocess execution: {e}")
            await self._record_session_history(None, save_type, "error", str(e))
            self._handle_recording_error(record_name, self._["no_ffmpeg_tip"], duration=4000)
            return False
        finally:
            self.recording.record_url = None

        return True

    async def converts_mp4(self, converts_file_path: str, is_original_delete: bool = True) -> None:
        """Asynchronous transcoding method, can be added to the background service to continue execution"""
        if not self.services.recording_enabled:
            logger.info(f"Application is closing, adding transcoding task to background service: {converts_file_path}")
            BackgroundService.get_instance().add_task(self.converts_mp4_sync, converts_file_path, is_original_delete)
            return

        # Otherwise, execute transcoding normally
        await self._do_converts_mp4(converts_file_path, is_original_delete)

    def converts_mp4_sync(self, converts_file_path: str, is_original_delete: bool = True) -> None:
        """Synchronous version of the transcoding method, used for background service"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._do_converts_mp4(converts_file_path, is_original_delete))
        finally:
            loop.close()

    async def _do_converts_mp4(self, converts_file_path: str, is_original_delete: bool = True) -> None:
        """Actual execution method for transcoding"""
        converts_success = False
        save_path = ""
        try:
            converts_file_path = converts_file_path.replace("\\", "/")
            if os.path.exists(converts_file_path) and os.path.getsize(converts_file_path) > 0:
                save_path = converts_file_path.rsplit(".", maxsplit=1)[0] + ".mp4"
                ffmpeg_command = [
                    "ffmpeg",
                    "-i",
                    converts_file_path,
                    "-c:v",
                    "copy",
                    "-c:a",
                    "copy",
                    "-f",
                    "mp4",
                    save_path,
                ]
                process = await asyncio.create_subprocess_exec(
                    *ffmpeg_command,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    startupinfo=self.subprocess_start_info,
                )

                self.services.process_manager.add_process(process)
                task = asyncio.create_task(process.communicate())
                _, stderr = await task
                if process.returncode == 0:
                    converts_success = True
                    logger.info(f"Video transcoding completed: {save_path}")
                else:
                    logger.error(
                        f"Video transcoding failed! Error message: {stderr.decode() if stderr else 'Unknown error'}"
                    )

        except subprocess.CalledProcessError as e:
            logger.error(f"Video transcoding failed! Error message: {e.output.decode()}")

        try:
            if converts_success:
                if is_original_delete:
                    await asyncio.sleep(1)
                    if os.path.exists(converts_file_path):
                        os.remove(converts_file_path)
                    logger.info(f"Delete Original File: {converts_file_path}")
                else:
                    converts_dir = f"{os.path.dirname(save_path)}/original"
                    os.makedirs(converts_dir, exist_ok=True)
                    shutil.move(converts_file_path, converts_dir)
                    logger.info(f"Move Transcoding Files: {converts_file_path}")

        except subprocess.CalledProcessError as e:
            logger.error(f"Error occurred during conversion: {e}")
        except Exception as e:
            logger.error(f"An unknown error occurred: {e}")

    async def custom_script_execute(
        self,
        script_command: str,
        record_name: str,
        save_file_path: str,
        save_type: str,
        split_video_by_time: bool,
        converts_to_mp4: bool,
    ):
        from ..runtime.process_manager import BackgroundService

        if "python" in script_command:
            params = [
                f'--record_name "{record_name}"',
                f'--save_file_path "{save_file_path}"',
                f"--save_type {save_type}",
                f"--split_video_by_time {split_video_by_time}",
                f"--converts_to_mp4 {converts_to_mp4}",
            ]
        else:
            params = [
                f'"{record_name.split(" ", maxsplit=1)[-1]}"',
                f'"{save_file_path}"',
                save_type,
                f"split_video_by_time: {split_video_by_time}",
                f"converts_to_mp4: {converts_to_mp4}",
            ]
        script_command = script_command.strip() + " " + " ".join(params)

        if not self.services.recording_enabled:
            logger.info("Application is closing, adding script execution task to background service")
            BackgroundService.get_instance().add_task(self.run_script_sync, script_command)
        else:
            self.services.run_coro(self.run_script_async(script_command))

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
                text=False,
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
            "xindongrebo": "referer:https://xcqrkj.com",
        }
        return record_headers.get(platform_key)

    async def start_direct_download(
        self,
        record_name: str,
        live_url: str,
        record_url: str,
        save_file_path: str,
        save_type: str,
        script_command: str | None = None,
    ) -> bool:
        """
        Use the direct downloader to download the live stream
        """

        logger.info(f"Starting direct download - recorder id: {id(self)}, rec_id: {self.recording.rec_id}")
        self.should_stop = False

        try:
            await self.direct_downloader.start_download()

            self.recording.status_info = RecordingStatus.RECORDING
            self.recording.record_url = record_url
            logger.info(f"Direct Downloading: {live_url}")
            logger.log("STREAM", f"Direct Download Stream URL: {record_url}")
            self.recording_start_time = time.time()
            await self._record_session_started(save_type)

            while True:
                if self.should_stop or self.recording.force_stop or not self.services.recording_enabled:
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

            if not self.recording.is_recording:
                await self._handle_recording_finished(
                    record_name,
                    stop_msg=f"Direct Downloading Stopped: {record_name}",
                    complete_msg=f"Direct Downloading Completed: {record_name}",
                    file_path=save_file_path,
                    file_format=save_type,
                )

            if not self.services.recording_enabled:
                self.recording.status_info = RecordingStatus.NOT_RECORDING_SPACE
                self.services.run_coro(self.stop_recording_notify())

            await self.recheck_live_status()

            if self.user_config.get("execute_custom_script") and script_command:
                logger.info("Prepare to execute custom script in the background")
                try:
                    self.services.run_coro(
                        self.custom_script_execute(
                            script_command,
                            record_name,
                            save_file_path,
                            save_type,
                            False,
                            False,
                        )
                    )
                    logger.success("Successfully added script execution")
                except Exception as e:
                    logger.error(f"Failed to execute custom script: {e}")
                    await self.custom_script_execute(
                        script_command, record_name, save_file_path, save_type, False, False
                    )

            return True

        except Exception as e:
            logger.error(f"Error occurred during direct download: {e}")
            await self._record_session_history(save_file_path, save_type, "error", str(e))
            self._handle_recording_error(record_name, self._["record_stream_error"])
            return False
        finally:
            self.recording.record_url = None

    async def stop_recording_notify(self):
        if desktop_notify.should_push_notification(self.app):
            tray_icon_path = self.services.tray_manager.icon_path if self.services.tray_manager is not None else ""
            desktop_notify.send_notification(
                title=self._["notify"],
                message=self.recording.streamer_name + " | " + self._["live_recording_stopped_message"],
                app_icon=tray_icon_path,
            )

    async def end_message_push(self):
        msg_manager = message_pusher.MessagePusher(self.settings)
        user_config = self.settings.user_config

        if (
            self.services.recording_enabled
            and msg_manager.should_push_message(
                self.settings, self.recording, check_manually_stopped=True, message_type="end"
            )
            and not self.recording.notified_live_end
        ):
            self.recording.notified_live_end = True
            push_content = self._["push_content_end"]
            end_push_message_text = user_config.get("custom_stream_end_content")
            if end_push_message_text:
                push_content = end_push_message_text

            push_at = datetime.today().strftime("%Y-%m-%d %H:%M:%S")
            push_content = (
                push_content.replace("[room_name]", self.recording.streamer_name)
                .replace("[time]", push_at)
                .replace("[title]", self.recording.live_title or "None")
            )
            msg_title = user_config.get("custom_notification_title").strip()
            msg_title = msg_title or self._["status_notify"]

            self.services.run_coro(msg_manager.push_messages(msg_title, push_content))

    def request_stop(self):
        logger.info(f"Stop requested for recorder: {self.recording.url}, rec_id: {self.recording.rec_id}")
        logger.info(f"Recorder instance details - id: {id(self)}, recording: {self.recording.title}")

        old_value = self.should_stop
        self.should_stop = True

        logger.info(f"Set should_stop from {old_value} to {self.should_stop} for recorder: {self.recording.rec_id}")
