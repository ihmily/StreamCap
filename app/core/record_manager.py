import asyncio
import os
import threading
from datetime import datetime, timedelta
from typing import Any, Callable
import time

from ..messages.message_pusher import MessagePusher
from ..models.recording_model import Recording
from ..models.recording_status_model import RecordingStatus
from ..utils import utils
from ..utils.logger import logger
from .platform_handlers import get_platform_info
from .stream_manager import LiveStreamRecorder


class GlobalRecordingState:
    recordings = []
    lock = threading.Lock()


class RecordingManager:
    def __init__(self, app):
        self.app = app
        self.settings = app.settings
        self.periodic_task_started = False
        self.loop_time_seconds = None
        self.app.language_manager.add_observer(self)
        self.load_recordings()
        self._ = {}
        self.load()
        self.initialize_dynamic_state()

    @property
    def recordings(self):
        return GlobalRecordingState.recordings

    @recordings.setter
    def recordings(self, value):
        raise AttributeError("Please use add_recording/update_recording methods to modify data")

    def load(self):
        language = self.app.language_manager.language
        for key in ("recording_manager", "video_quality"):
            self._.update(language.get(key, {}))

    def load_recordings(self):
        """Load recordings from a JSON file into objects."""
        recordings_data = self.app.config_manager.load_recordings_config()
        if not GlobalRecordingState.recordings:
            GlobalRecordingState.recordings = [Recording.from_dict(rec) for rec in recordings_data]
        logger.info(f"Live Recordings: Loaded {len(self.recordings)} items")

    def initialize_dynamic_state(self):
        """Initialize dynamic state for all recordings."""
        loop_time_seconds = self.settings.user_config.get("loop_time_seconds")
        self.loop_time_seconds = int(loop_time_seconds or 300)
        for recording in self.recordings:
            recording.loop_time_seconds = self.loop_time_seconds
            recording.update_title(self._[recording.quality])

    async def add_recording(self, recording):
        with GlobalRecordingState.lock:
            GlobalRecordingState.recordings.append(recording)
            await self.persist_recordings()

    async def remove_recording(self, recording: Recording):
        with GlobalRecordingState.lock:
            GlobalRecordingState.recordings.remove(recording)
            await self.persist_recordings()

    async def clear_all_recordings(self):
        with GlobalRecordingState.lock:
            GlobalRecordingState.recordings.clear()
            await self.persist_recordings()

    async def persist_recordings(self):
        """Persist recordings to a JSON file."""
        data_to_save = [rec.to_dict() for rec in self.recordings]
        await self.app.config_manager.save_recordings_config(data_to_save)

    async def update_recording_card(self, recording: Recording, updated_info: dict):
        """Update an existing recording object and persist changes to a JSON file."""
        if recording:
            recording.update(updated_info)
            self.app.page.run_task(self.persist_recordings)

    @staticmethod
    async def _update_recording(
        recording: Recording, monitor_status: bool, display_title: str, status_info: str, selected: bool
    ):
        attrs_update = {
            "monitor_status": monitor_status,
            "display_title": display_title,
            "status_info": status_info,
            "selected": selected,
        }
        for attr, value in attrs_update.items():
            setattr(recording, attr, value)

    async def start_monitor_recording(self, recording: Recording, auto_save: bool = True):
        """
        Start monitoring a single recording if it is not already being monitored.
        """
        # 首先检查磁盘空间是否足够
        if not await self.check_free_space():
            # 如果磁盘空间不足，显示对话框并返回
            logger.error("磁盘空间不足，无法开始监控")
            return False
            
        if not recording.monitor_status:
            await self._update_recording(
                recording=recording,
                monitor_status=True,
                display_title=recording.title,
                status_info=RecordingStatus.MONITORING,
                selected=False,
            )
            self.app.page.run_task(self.check_if_live, recording)
            self.app.page.run_task(self.app.record_card_manager.update_card, recording)
            self.app.page.pubsub.send_others_on_topic("update", recording)
            if auto_save:
                self.app.page.run_task(self.persist_recordings)
            return True
        return False

    async def stop_monitor_recording(self, recording: Recording, auto_save: bool = True):
        """
        Stop monitoring a single recording if it is currently being monitored.
        """
        if recording.monitor_status:
            await self._update_recording(
                recording=recording,
                monitor_status=False,
                display_title=f"[{self._['monitor_stopped']}] {recording.title}",
                status_info=RecordingStatus.STOPPED_MONITORING,
                selected=False,
            )
            self.stop_recording(recording, manually_stopped=True)
            
            # 手动停止监控时，重置通知状态和was_recording标志
            # 这样下次开始监控时可以再次发送通知
            recording.notification_sent = False
            recording.end_notification_sent = False
            if hasattr(recording, 'was_recording'):
                recording.was_recording = False
            logger.info(f"手动停止监控，重置通知状态: {recording.streamer_name}")
            
            self.app.page.run_task(self.app.record_card_manager.update_card, recording)
            self.app.page.pubsub.send_others_on_topic("update", recording)
            if auto_save:
                self.app.page.run_task(self.persist_recordings)

    async def start_monitor_recordings(self):
        """
        Start monitoring multiple recordings based on user selection or all recordings if none are selected.
        """
        # 首先检查磁盘空间是否足够
        if not await self.check_free_space():
            # 如果磁盘空间不足，显示对话框并返回
            logger.error("磁盘空间不足，无法开始批量监控")
            return False
            
        selected_recordings = await self.get_selected_recordings()
        pre_start_monitor_recordings = selected_recordings if selected_recordings else self.recordings
        cards_obj = self.app.record_card_manager.cards_obj
        success_count = 0
        
        for recording in pre_start_monitor_recordings:
            if cards_obj[recording.rec_id]["card"].visible:
                result = await self.start_monitor_recording(recording, auto_save=False)
                if result:
                    success_count += 1
                    
        self.app.page.run_task(self.persist_recordings)
        logger.info(f"Batch Start Monitor Recordings: {[i.rec_id for i in pre_start_monitor_recordings]}, 成功: {success_count}")
        return success_count > 0

    async def stop_monitor_recordings(self, selected_recordings: list[Recording | None] | None = None):
        """
        Stop monitoring multiple recordings based on user selection or all recordings if none are selected.
        """
        if not selected_recordings:
            selected_recordings = await self.get_selected_recordings()
        pre_stop_monitor_recordings = selected_recordings or self.recordings
        cards_obj = self.app.record_card_manager.cards_obj
        for recording in pre_stop_monitor_recordings:
            if cards_obj[recording.rec_id]["card"].visible:
                self.app.page.run_task(self.stop_monitor_recording, recording, auto_save=False)
        self.app.page.run_task(self.persist_recordings)
        logger.info(f"Batch Stop Monitor Recordings: {[i.rec_id for i in pre_stop_monitor_recordings]}")

    async def get_selected_recordings(self):
        return [recording for recording in self.recordings if recording.selected]

    async def remove_recordings(self, recordings: list[Recording]):
        """Remove a recording from the list and update the JSON file."""
        for recording in recordings:
            if recording in self.recordings:
                await self.remove_recording(recording)
                logger.info(f"Delete Items: {recording.rec_id}-{recording.streamer_name}")

    def find_recording_by_id(self, rec_id: str):
        """Find a recording by its ID (hash of dict representation)."""
        for rec in self.recordings:
            if rec.rec_id == rec_id:
                return rec
        return None

    async def check_all_live_status(self):
        """Check the live status of all recordings and update their display titles."""
        for recording in self.recordings:
            if recording.monitor_status and not recording.recording:
                is_exceeded = utils.is_time_interval_exceeded(recording.detection_time, recording.loop_time_seconds)
                if not recording.detection_time or is_exceeded:
                    self.app.page.run_task(self.check_if_live, recording)

    async def setup_periodic_live_check(self, interval: int = 300): # 5分钟检查一次磁盘空间
        """Set up a periodic task to check live status."""

        async def periodic_check():
            while True:
                await asyncio.sleep(interval)
                await self.check_free_space()
                if self.app.recording_enabled:
                    await self.check_all_live_status()

        if not self.periodic_task_started:
            self.periodic_task_started = True
            await periodic_check()

    async def check_if_live(self, recording: Recording):
        """Check if the live stream is available, fetch stream data and update is_live status."""

        if recording.recording:
            return

        if not recording.monitor_status:
            recording.display_title = f"[{self._['monitor_stopped']}] {recording.title}"
            recording.status_info = RecordingStatus.STOPPED_MONITORING

        elif not recording.is_checking:
            recording.status_info = RecordingStatus.STATUS_CHECKING
            recording.detection_time = datetime.now().time()
            if recording.scheduled_recording and recording.scheduled_start_time and recording.monitor_hours:
                scheduled_time_range = await self.get_scheduled_time_range(
                    recording.scheduled_start_time, recording.monitor_hours)
                recording.scheduled_time_range = scheduled_time_range
                in_scheduled = utils.is_current_time_within_range(scheduled_time_range)
                if not in_scheduled:
                    recording.status_info = RecordingStatus.NOT_IN_SCHEDULED_CHECK
                    logger.info(f"Skip Detection: {recording.url} not in scheduled check range {scheduled_time_range}")
                    return

            recording.is_checking = True
            platform, platform_key = get_platform_info(recording.url)

            if self.settings.user_config["language"] != "zh_CN":
                platform = platform_key

            output_dir = self.settings.get_video_save_path()
            await self.check_free_space(output_dir)
            if not self.app.recording_enabled:
                recording.is_checking = False
                recording.status_info = RecordingStatus.NOT_RECORDING_SPACE
                return

            recording_info = {
                "platform": platform,
                "platform_key": platform_key,
                "live_url": recording.url,
                "output_dir": output_dir,
                "segment_record": recording.segment_record,
                "segment_time": recording.segment_time,
                "save_format": recording.record_format,
                "quality": recording.quality,
            }

            recorder = LiveStreamRecorder(self.app, recording, recording_info)

            stream_info = await recorder.fetch_stream()
            logger.info(f"Stream Data: {stream_info}")
            if not stream_info:
                logger.error(f"Fetch stream data failed: {recording.url}")
                recording.is_checking = False
                recording.status_info = RecordingStatus.LIVE_STATUS_CHECK_ERROR
                # 如果之前在直播中，但现在获取数据失败，认为主播已下播
                if recording.is_live:
                    logger.info(f"主播可能已下播，自动更新状态: {recording.streamer_name}")
                    recording.is_live = False
                    recording.notification_sent = False
                    recording.display_title = f"{recording.title}"
                    recording.status_info = RecordingStatus.MONITORING
                    if recording.recording:
                        self.stop_recording(recording, manually_stopped=False)
                    # 更新UI
                    self.app.page.run_task(self.app.record_card_manager.update_card, recording)
                    self.app.page.pubsub.send_others_on_topic("update", recording)
                return
            
            if not stream_info.anchor_name:
                logger.error(f"Invalid stream data - missing anchor name: {recording.url}")
                recording.is_checking = False
                recording.status_info = RecordingStatus.LIVE_STATUS_CHECK_ERROR
                return

            if self.settings.user_config.get("remove_emojis"):
                stream_info.anchor_name = utils.clean_name(stream_info.anchor_name, self._["live_room"])

            # 检查直播状态变化
            was_live = recording.is_live
            recording.is_live = stream_info.is_live
            
            # 如果直播状态从在线变为离线，重置通知状态并更新UI
            if was_live and not recording.is_live:
                recording.notification_sent = False
                logger.info(f"直播已结束，重置通知状态: {recording.streamer_name}")
                
                # 添加这部分代码，处理直播结束状态的更新
                recording.display_title = f"{recording.title}"
                recording.status_info = RecordingStatus.MONITORING
                # 如果正在录制，停止录制
                if recording.recording:
                    self.stop_recording(recording, manually_stopped=False)
                # 更新UI
                self.app.page.run_task(self.app.record_card_manager.update_card, recording)
                self.app.page.pubsub.send_others_on_topic("update", recording)
                
                # 修改：无论是否之前处于录制状态，只要状态从"直播中"变为"未开播"，就发送直播结束通知
                # 这样可以确保从"直播中（未录制）"状态变为"未开播"状态时也会发送通知
                if self.settings.user_config.get("stream_end_notification_enabled", False) and recording.enabled_message_push:
                    # 检查是否已经发送过关闭通知
                    end_notification_sent = getattr(recording, "end_notification_sent", False)
                    if not end_notification_sent:
                        # 检查是否有至少一个推送渠道被启用
                        user_config = self.settings.user_config
                        bark_enabled = user_config.get("bark_enabled", False)
                        wechat_enabled = user_config.get("wechat_enabled", False)
                        dingtalk_enabled = user_config.get("dingtalk_enabled", False)
                        ntfy_enabled = user_config.get("ntfy_enabled", False)
                        telegram_enabled = user_config.get("telegram_enabled", False)
                        email_enabled = user_config.get("email_enabled", False)
                        serverchan_enabled = user_config.get("serverchan_enabled", False)
                        
                        any_channel_enabled = (
                            bark_enabled or wechat_enabled or dingtalk_enabled or 
                            ntfy_enabled or telegram_enabled or email_enabled or
                            serverchan_enabled
                        )
                        
                        if any_channel_enabled:
                            push_content = self._["push_content_end"]
                            end_push_message_text = self.settings.user_config.get("custom_stream_end_content")
                            if end_push_message_text:
                                push_content = end_push_message_text

                            push_at = datetime.today().strftime("%Y-%m-%d %H:%M:%S")
                            push_content = push_content.replace("[room_name]", recording.streamer_name).replace(
                                "[time]", push_at
                            )
                            msg_title = self.settings.user_config.get("custom_notification_title", "").strip()
                            msg_title = msg_title or self._["status_notify"]

                            logger.info(f"直播结束通知: {msg_title} - {push_content}")
                            msg_manager = MessagePusher(self.settings)
                            self.app.page.run_task(msg_manager.push_messages, msg_title, push_content)
                            # 设置已发送关闭通知标志，避免重复发送
                            recording.end_notification_sent = True
                        else:
                            logger.info(f"已经发送过关播通知，跳过重复发送: {recording.streamer_name}")
                
                # 由于已经处理了状态更新和UI刷新，如果当前检测是正确的（直播已结束），
                # 可以在这里提前结束check_if_live函数，以避免后面的不必要处理
                recording.is_checking = False
                return

            is_record = True
            if recording.is_live and not recording.recording:
                recording.live_title = stream_info.title
                if not recording.streamer_name or recording.streamer_name.strip() == self._["live_room"]:
                    recording.streamer_name = stream_info.anchor_name
                recording.title = f"{recording.streamer_name} - {self._[recording.quality]}"
                recording.display_title = f"[{self._['is_live']}] {recording.title}"

                if getattr(recording, "record_mode", "auto") == "auto":
                    recording.status_info = RecordingStatus.PREPARING_RECORDING
                    
                    # 首先检查是否启用了"仅通知不录制"全局设置
                    # 此设置应该全局影响所有自动录制模式的房间，无论是否有推送通知
                    if self.settings.user_config.get("only_notify_no_record"):
                        # 如果启用了"仅通知不录制"，则不录制，只通知（如果设置了通知）
                        notify_loop_time = self.settings.user_config.get("notify_loop_time")
                        recording.loop_time_seconds = int(notify_loop_time or 3600)
                        is_record = False
                        # 设置状态为"直播中（未录制）"，确保UI显示正确
                        recording.status_info = RecordingStatus.NOT_RECORDING
                        logger.info(f"全局已启用'仅通知不录制'，跳过录制: {recording.streamer_name}")
                    else:
                        # 重置为默认循环时间
                        recording.loop_time_seconds = self.loop_time_seconds
                    
                    # 处理消息推送逻辑（不影响录制决策）
                    if self.settings.user_config["stream_start_notification_enabled"] and recording.enabled_message_push:
                        # 检查是否有至少一个推送渠道被启用
                        user_config = self.settings.user_config
                        bark_enabled = user_config.get("bark_enabled", False)
                        wechat_enabled = user_config.get("wechat_enabled", False)
                        dingtalk_enabled = user_config.get("dingtalk_enabled", False)
                        ntfy_enabled = user_config.get("ntfy_enabled", False)
                        telegram_enabled = user_config.get("telegram_enabled", False)
                        email_enabled = user_config.get("email_enabled", False)
                        serverchan_enabled = user_config.get("serverchan_enabled", False)
                        
                        any_channel_enabled = (
                            bark_enabled or wechat_enabled or dingtalk_enabled or 
                            ntfy_enabled or telegram_enabled or email_enabled or
                            serverchan_enabled
                        )
                        
                        logger.info(f"推送渠道状态: bark={bark_enabled}, wechat={wechat_enabled}, "
                                   f"dingtalk={dingtalk_enabled}, ntfy={ntfy_enabled}, "
                                   f"telegram={telegram_enabled}, email={email_enabled}, "
                                   f"serverchan={serverchan_enabled}")
                        
                        # 检查是否已经发送过通知，避免重复发送
                        if any_channel_enabled and not recording.notification_sent:
                            push_content = self._["push_content"]
                            begin_push_message_text = self.settings.user_config.get("custom_stream_start_content")
                            if begin_push_message_text:
                                push_content = begin_push_message_text

                            push_at = datetime.today().strftime("%Y-%m-%d %H:%M:%S")
                            push_content = push_content.replace("[room_name]", recording.streamer_name).replace(
                                "[time]", push_at
                            )
                            msg_title = self.settings.user_config.get("custom_notification_title").strip()
                            msg_title = msg_title or self._["status_notify"]

                            logger.info(f"自动录制模式下触发消息推送: {msg_title} - {push_content}")
                            msg_manager = MessagePusher(self.settings)
                            self.app.page.run_task(msg_manager.push_messages, msg_title, push_content)
                            # 设置通知已发送标志
                            recording.notification_sent = True
                        elif recording.notification_sent:
                            logger.info(f"已经发送过开播通知，跳过重复发送: {recording.streamer_name}")
                        else:
                            logger.info("没有启用任何推送渠道，跳过消息推送")

                    if is_record:
                        self.start_update(recording)
                        self.app.page.run_task(recorder.start_recording, stream_info)

                    self.app.page.run_task(self.app.record_card_manager.update_card, recording)
                    self.app.page.pubsub.send_others_on_topic("update", recording)
                else:
                    # 手动录制模式下，设置状态为"直播中（未录制）"
                    recording.status_info = RecordingStatus.NOT_RECORDING
                    
                    # 在手动模式下，当直播间处于"直播中（未录制）"状态时也触发消息推送
                    # 但要避免从"录制中"状态变为"直播中（未录制）"状态时重复发送
                    was_recording = getattr(recording, "was_recording", False)
                    
                    if self.settings.user_config["stream_start_notification_enabled"] and recording.enabled_message_push:
                        # 检查是否有至少一个推送渠道被启用
                        user_config = self.settings.user_config
                        bark_enabled = user_config.get("bark_enabled", False)
                        wechat_enabled = user_config.get("wechat_enabled", False)
                        dingtalk_enabled = user_config.get("dingtalk_enabled", False)
                        ntfy_enabled = user_config.get("ntfy_enabled", False)
                        telegram_enabled = user_config.get("telegram_enabled", False)
                        email_enabled = user_config.get("email_enabled", False)
                        serverchan_enabled = user_config.get("serverchan_enabled", False)
                        
                        any_channel_enabled = (
                            bark_enabled or wechat_enabled or dingtalk_enabled or 
                            ntfy_enabled or telegram_enabled or email_enabled or
                            serverchan_enabled
                        )
                        
                        logger.info(f"推送渠道状态: bark={bark_enabled}, wechat={wechat_enabled}, "
                                  f"dingtalk={dingtalk_enabled}, ntfy={ntfy_enabled}, "
                                  f"telegram={telegram_enabled}, email={email_enabled}, "
                                  f"serverchan={serverchan_enabled}")
                        
                        # 检查是否已经发送过通知，避免重复发送
                        # 如果是从"录制中"状态变为"直播中（未录制）"状态，则不发送通知
                        if any_channel_enabled and not recording.notification_sent and not was_recording:
                            push_content = self._["push_content"]
                            begin_push_message_text = self.settings.user_config.get("custom_stream_start_content")
                            if begin_push_message_text:
                                push_content = begin_push_message_text

                            push_at = datetime.today().strftime("%Y-%m-%d %H:%M:%S")
                            push_content = push_content.replace("[room_name]", recording.streamer_name).replace(
                                "[time]", push_at
                            )
                            msg_title = self.settings.user_config.get("custom_notification_title").strip()
                            msg_title = msg_title or self._["status_notify"]

                            logger.info(f"手动录制模式下直播中（未录制）状态触发消息推送: {msg_title} - {push_content}")
                            msg_manager = MessagePusher(self.settings)
                            self.app.page.run_task(msg_manager.push_messages, msg_title, push_content)
                            # 设置通知已发送标志
                            recording.notification_sent = True
                        elif recording.notification_sent:
                            logger.info(f"已经发送过开播通知，跳过重复发送: {recording.streamer_name}")
                        elif was_recording:
                            logger.info(f"从录制中状态变为直播中（未录制）状态，跳过消息推送: {recording.streamer_name}")
                        else:
                            logger.info("没有启用任何推送渠道，跳过消息推送")
                    else:
                        logger.info("全局推送开关和单独推送设置必须同时启用，跳过消息推送")
                    
                    # 重置was_recording标志
                    recording.was_recording = False
                    
                    self.app.page.run_task(self.app.record_card_manager.update_card, recording)
                    self.app.page.pubsub.send_others_on_topic("update", recording)

    @staticmethod
    def start_update(recording: Recording):
        """Start the recording process."""
        if recording.is_live and not recording.recording:
            # Reset cumulative and last durations for a fresh start
            recording.update(
                {
                    "cumulative_duration": timedelta(),
                    "last_duration": timedelta(),
                    "start_time": datetime.now(),
                    "recording": True,
                }
            )
            logger.info(f"Started recording for {recording.title}")

    @staticmethod
    def stop_recording(recording: Recording, manually_stopped: bool = True):
        """Stop the recording process."""
        if recording.recording:
            if recording.start_time is not None:
                elapsed = datetime.now() - recording.start_time
                # Add the elapsed time to the cumulative duration.
                recording.cumulative_duration += elapsed
                # Update the last recorded duration.
                recording.last_duration = recording.cumulative_duration
            recording.start_time = None
            recording.recording = False
            recording.manually_stopped = manually_stopped
            logger.info(f"Stopped recording for {recording.title}")
            
            # 当直播结束时（而不是仅仅停止录制时），重置notification_sent标志
            # 这样下次直播开始时可以再次发送通知
            if not recording.is_live:
                recording.notification_sent = False
                # 同时重置end_notification_sent标志，以便下次直播结束时可以再次发送通知
                recording.end_notification_sent = False
                logger.info(f"直播已结束，重置通知状态: {recording.streamer_name}")
            else:
                # 如果直播仍在进行中，设置was_recording标志
                # 这样在下次检测到直播状态时知道这是从"录制中"状态变为"直播中（未录制）"状态
                recording.was_recording = True
                logger.info(f"直播仍在进行中，保持通知状态，避免重复推送: {recording.streamer_name}")
        # 无论是否正在录制，如果直播已经结束，都确保重置通知状态
        elif not recording.is_live and hasattr(recording, 'notification_sent') and recording.notification_sent:
            recording.notification_sent = False
            # 同时重置end_notification_sent标志
            recording.end_notification_sent = False
            logger.info(f"从\"直播中（未录制）\"变为\"未开播\"状态，重置通知状态: {recording.streamer_name}")

    def get_duration(self, recording: Recording):
        """Get the duration of the current recording session in a formatted string."""
        if recording.recording and recording.start_time is not None:
            elapsed = datetime.now() - recording.start_time
            # If recording, add the current session time.
            total_duration = recording.cumulative_duration + elapsed
            return self._["recorded"] + " " + str(total_duration).split(".")[0]
        else:
            # If stopped, show the last recorded total duration.
            total_duration = recording.last_duration
            return str(total_duration).split(".")[0]

    async def delete_recording_cards(self, recordings: list[Recording]):
        self.app.page.run_task(self.app.record_card_manager.remove_recording_card, recordings)
        self.app.page.pubsub.send_others_on_topic('delete', recordings)
        await self.remove_recordings(recordings)
        
        # 检查是否需要切换平台视图
        home_page = self.app.current_page
        if hasattr(home_page, "current_platform_filter") and home_page.current_platform_filter != "all":
            current_platform = home_page.current_platform_filter
            
            # 检查是否还有当前平台的录制项
            remaining_items = False
            for recording in self.recordings:
                _, platform_key = get_platform_info(recording.url)
                if platform_key == current_platform:
                    remaining_items = True
                    break
            
            # 如果当前平台没有剩余录制项，自动切换到全部平台视图
            if not remaining_items:
                logger.info(f"批量删除后平台 {current_platform} 下没有剩余直播间，自动切换到全部平台视图")
                home_page.current_platform_filter = "all"
        
        # 删除后更新主页筛选区域
        if hasattr(self.app.current_page, "create_filter_area") and hasattr(self.app.current_page, "content_area"):
            self.app.current_page.content_area.controls[1] = self.app.current_page.create_filter_area()
            self.app.current_page.content_area.update()
            
            # 应用筛选
            if hasattr(self.app.current_page, "apply_filter"):
                self.app.page.run_task(self.app.current_page.apply_filter)

    async def check_free_space(self, output_dir: str | None = None):
        disk_space_limit = float(self.settings.user_config.get("recording_space_threshold"))
        output_dir = output_dir or self.settings.get_video_save_path()
        free_space = utils.check_disk_capacity(output_dir)
        if free_space < disk_space_limit:
            # 设置录制状态为禁用
            self.app.recording_enabled = False
            logger.error(
                f"Disk space remaining is below {disk_space_limit} GB. Recording function disabled"
            )
            
            # 显示持久性通知
            self.app.page.run_task(
                self.app.snack_bar.show_snack_bar,
                self._["not_disk_space_tip"],
                duration=86400,
                show_close_icon=True
            )
            
            # 发送磁盘空间不足的消息推送和显示对话框
            await self.send_disk_space_notification(disk_space_limit, free_space)
            
            return False
        else:
            self.app.recording_enabled = True
            return True

    async def send_disk_space_notification(self, threshold: float, free_space: float):
        """发送磁盘空间不足的消息推送和显示对话框"""
        try:
            # 检查距离上次推送通知的时间间隔
            current_time = time.time()
            elapsed_seconds = current_time - self.app.disk_space_last_notification_time
            
            # 如果距离上次推送不足60秒，则跳过推送消息，但仍然显示对话框
            skip_push = False
            if self.app.disk_space_notification_sent and elapsed_seconds < 60:
                logger.info(f"跳过磁盘空间不足推送通知: 距离上次通知仅过了 {elapsed_seconds:.1f}秒 (小于60秒)")
                skip_push = True
            else:
                logger.info(f"发送磁盘空间不足通知: 距离上次通知已过了 {elapsed_seconds:.1f}秒")
            
            # 更新通知状态和时间
            self.app.disk_space_notification_sent = True
            self.app.disk_space_last_notification_time = current_time
            
            # 显示磁盘空间不足警告对话框 - 确保这个调用在主UI线程中执行
            # 重要修改：无论何时检测到磁盘空间不足，都显示警告对话框
            logger.info("准备显示磁盘空间不足警告对话框...")
            await self.app.show_disk_space_warning_dialog(threshold, free_space)
            
            # 如果需要跳过推送消息，则直接返回
            if skip_push:
                return
                
            # ========== 消息推送逻辑 ==========
            # 获取用户配置
            user_config = self.settings.user_config
            
            # 1. 检查全局推送开关是否打开
            global_push_enabled = user_config.get("stream_start_notification_enabled", False)
            if not global_push_enabled:
                logger.info("全局消息推送开关未启用，跳过磁盘空间不足消息推送")
                return
                
            # 2. 检查是否有至少一个推送渠道被启用
            bark_enabled = user_config.get("bark_enabled", False)
            wechat_enabled = user_config.get("wechat_enabled", False)
            dingtalk_enabled = user_config.get("dingtalk_enabled", False)
            ntfy_enabled = user_config.get("ntfy_enabled", False)
            telegram_enabled = user_config.get("telegram_enabled", False)
            email_enabled = user_config.get("email_enabled", False)
            serverchan_enabled = user_config.get("serverchan_enabled", False)
            
            any_channel_enabled = (
                bark_enabled or wechat_enabled or dingtalk_enabled or 
                ntfy_enabled or telegram_enabled or email_enabled or
                serverchan_enabled
            )
            
            if not any_channel_enabled:
                logger.info("没有启用任何推送渠道，跳过磁盘空间不足消息推送")
                return
                
            # 记录当前启用的推送渠道信息
            logger.info(f"推送渠道状态: bark={bark_enabled}, wechat={wechat_enabled}, "
                       f"dingtalk={dingtalk_enabled}, ntfy={ntfy_enabled}, "
                       f"telegram={telegram_enabled}, email={email_enabled}, "
                       f"serverchan={serverchan_enabled}")
            
            # 准备推送内容
            msg_title = self._["disk_space_insufficient_title"]
            push_content = self._["disk_space_insufficient_content"].replace("[threshold]", str(threshold))
            
            # 添加实际剩余空间信息
            push_content += f" 当前剩余: {free_space:.2f}GB"
            
            logger.info(f"发送磁盘空间不足通知: {msg_title} - {push_content}")
            msg_manager = MessagePusher(self.settings)
            await msg_manager.push_messages(msg_title, push_content)
            logger.info("磁盘空间不足通知已发送")
            
        except Exception as e:
            logger.error(f"发送磁盘空间不足通知时出错: {e}", exc_info=True)

    @staticmethod
    async def get_scheduled_time_range(scheduled_start_time, monitor_hours) -> str | None:
        monitor_hours = float(monitor_hours or 5)
        if scheduled_start_time and monitor_hours:
            end_time = utils.add_hours_to_time(scheduled_start_time, monitor_hours)
            scheduled_time_range = f"{scheduled_start_time}~{end_time}"
            return scheduled_time_range

    async def get_stream_url(self, recording: Recording):
        """
        获取直播源地址，仅在已开始监控状态下可用。
        返回record_url（如m3u8/flv），如未获取到则返回None。
        """
        if not recording.monitor_status:
            return None, "未开始监控，无法获取直播源地址"
        platform, platform_key = get_platform_info(recording.url)
        output_dir = self.settings.get_video_save_path()
        recording_info = {
            "platform": platform,
            "platform_key": platform_key,
            "live_url": recording.url,
            "output_dir": output_dir,
            "segment_record": recording.segment_record,
            "segment_time": recording.segment_time,
            "save_format": recording.record_format,
            "quality": recording.quality,
        }
        recorder = LiveStreamRecorder(self.app, recording, recording_info)
        stream_info = await recorder.fetch_stream()
        if not stream_info or not getattr(stream_info, "record_url", None):
            return None, "未获取到直播源地址，可能未开播或平台暂不支持"
        return stream_info.record_url, None
