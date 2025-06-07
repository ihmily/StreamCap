import asyncio
import os.path
from datetime import datetime, timedelta
from functools import partial

import flet as ft

from ...core.platform_handlers import get_platform_info
from ...core.stream_manager import LiveStreamRecorder
from ...messages.message_pusher import MessagePusher
from ...models.recording_model import Recording
from ...models.recording_status_model import RecordingStatus
from ...utils import utils
from ...utils.logger import logger
from ..views.storage_view import StoragePage
from .card_dialog import CardDialog
from .recording_dialog import RecordingDialog
from .video_player import VideoPlayer


class RecordingCardManager:
    def __init__(self, app):
        self.app = app
        self.cards_obj = {}
        self.update_duration_tasks = {}
        self.selected_cards = {}
        self.app.language_manager.add_observer(self)
        self._ = {}
        self.load()
        self.pubsub_subscribe()

    def load(self):
        language = self.app.language_manager.language
        for key in ("recording_card", "recording_manager", "base", "home_page", "video_quality", "storage_page"):
            self._.update(language.get(key, {}))

    def pubsub_subscribe(self):
        self.app.page.pubsub.subscribe_topic("update", self.subscribe_update_card)
        self.app.page.pubsub.subscribe_topic("delete", self.subscribe_remove_cards)

    async def create_card(self, recording: Recording):
        """Create a card for a given recording."""
        rec_id = recording.rec_id
        if not self.cards_obj.get(rec_id):
            if self.app.recording_enabled:
                self.app.page.run_task(self.app.record_manager.check_if_live, recording)
            else:
                recording.status_info = RecordingStatus.NOT_RECORDING_SPACE
        card_data = self._create_card_components(recording)
        self.cards_obj[rec_id] = card_data
        self.start_update_task(recording)
        return card_data["card"]

    def _create_card_components(self, recording: Recording):
        """create card components."""
        speed = recording.speed
        duration_text_label = ft.Text(self.app.record_manager.get_duration(recording), size=12)

        # 判断是否为手动录制模式且监控未开启
        is_manual_mode = recording.record_mode == "manual"
        is_record_button_disabled = is_manual_mode and not recording.monitor_status
        
        record_button = ft.IconButton(
            icon=self.get_icon_for_recording_state(recording),
            tooltip=self.get_tip_for_recording_state(recording),
            on_click=partial(self.recording_button_on_click, recording=recording),
            disabled=is_record_button_disabled,  # 在手动模式下，只有监控开启时才能点击录制按钮
        )

        edit_button = ft.IconButton(
            icon=ft.Icons.EDIT,
            tooltip=self._["edit_record_config"],
            on_click=partial(self.edit_recording_button_click, recording=recording),
        )

        preview_button = ft.IconButton(
            icon=ft.Icons.VIDEO_LIBRARY,
            tooltip=self._["preview_video"],
            on_click=partial(self.preview_video_button_on_click, recording=recording),
        )

        monitor_button = ft.IconButton(
            icon=self.get_icon_for_monitor_state(recording),
            tooltip=self.get_tip_for_monitor_state(recording),
            on_click=partial(self.monitor_button_on_click, recording=recording),
        )

        delete_button = ft.IconButton(
            icon=ft.Icons.DELETE,
            tooltip=self._["delete_monitor"],
            on_click=partial(self.recording_delete_button_click, recording=recording),
        )

        # 判断当前语言环境
        is_zh = getattr(self.app, "language_code", "zh_CN").startswith("zh")
        disabled_tip = "请开启监控或点击刷新按钮" if is_zh else "Please enable monitor or click the refresh button"
        get_stream_button = ft.IconButton(
            icon=ft.Icons.LINK,
            tooltip=(self._["copy_stream_url"] if (recording.monitor_status and (recording.is_live or recording.recording)) else disabled_tip),
            on_click=partial(self.get_stream_url_on_click, recording=recording),
            disabled=not (recording.monitor_status and (recording.is_live or recording.recording)),
        )

        play_button = ft.IconButton(
            icon=ft.Icons.PLAY_ARROW,
            tooltip=(self._["play_stream"] if (recording.monitor_status and (recording.is_live or recording.recording)) else disabled_tip),
            on_click=partial(self.play_stream_on_click, recording=recording),
            disabled=not (recording.monitor_status and (recording.is_live or recording.recording)),
        )

        status_prefix = ""
        if not recording.monitor_status:
            status_prefix = f"[{self._['monitor_stopped']}] "
        
        display_title = f"{status_prefix}{recording.title}"
        display_title_label = ft.Text(
            display_title, 
            size=14, 
            selectable=True, 
            max_lines=1, 
            no_wrap=True,
            overflow=ft.TextOverflow.ELLIPSIS,
            expand=True,
            weight=ft.FontWeight.BOLD if recording.recording or recording.is_live else None,
        )
        
        open_folder_button = ft.IconButton(
            icon=ft.Icons.FOLDER,
            tooltip=self._["open_folder"],
            on_click=partial(self.recording_dir_button_on_click, recording=recording),
        )
        recording_info_button = ft.IconButton(
            icon=ft.Icons.INFO,
            tooltip=self._["recording_info"],
            on_click=partial(self.recording_info_button_on_click, recording=recording),
        )
        speed_text_label = ft.Text(speed, size=12)

        status_label = self.create_status_label(recording)

        title_row = ft.Row(
            [display_title_label, status_label] if status_label else [display_title_label],
            alignment=ft.MainAxisAlignment.START,
            spacing=5,
            tight=True,
        )

        card_container = ft.Container(
            content=ft.Column(
                [
                    title_row,
                    duration_text_label,
                    speed_text_label,
                    ft.Row(
                        [
                            record_button,
                            open_folder_button,
                            recording_info_button,
                            preview_button,
                            get_stream_button,
                            play_button,
                            edit_button,
                            delete_button,
                            monitor_button
                        ],
                        spacing=3,
                        alignment=ft.MainAxisAlignment.START
                    ),
                ],
                spacing=3,
                tight=True
            ),
            padding=8,
            on_click=partial(self.recording_card_on_click, recording=recording),
            bgcolor=self.get_card_background_color(recording),
            border_radius=5,
            border=ft.border.all(2, self.get_card_border_color(recording)),
        )
        card = ft.Card(key=str(recording.rec_id), content=card_container)

        return {
            "card": card,
            "display_title_label": display_title_label,
            "duration_label": duration_text_label,
            "speed_label": speed_text_label,
            "record_button": record_button,
            "open_folder_button": open_folder_button,
            "recording_info_button": recording_info_button,
            "edit_button": edit_button,
            "monitor_button": monitor_button,
            "status_label": status_label,
            "get_stream_button": get_stream_button,
            "play_button": play_button,
            "preview_button": preview_button,
            "delete_button": delete_button,
        }
        
    def get_card_background_color(self, recording: Recording):
        is_dark_mode = self.app.page.theme_mode == ft.ThemeMode.DARK
        if recording.selected:
            return ft.colors.GREY_800 if is_dark_mode else ft.colors.GREY_400
        return None

    @staticmethod
    def get_card_border_color(recording: Recording):
        """Get the border color of the card."""
        if recording.recording:
            return ft.colors.GREEN
        elif recording.status_info == RecordingStatus.RECORDING_ERROR:
            return ft.colors.RED
        elif not recording.is_live and recording.monitor_status:
            return ft.colors.AMBER
        elif not recording.monitor_status:
            return ft.colors.GREY
        return ft.colors.TRANSPARENT

    def create_status_label(self, recording: Recording):
        if recording.recording:
            return ft.Container(
                content=ft.Text(self._["recording"], color=ft.colors.WHITE, size=12, weight=ft.FontWeight.BOLD),
                bgcolor=ft.colors.GREEN,
                border_radius=5,
                padding=5,
                width=60,
                height=26,
                alignment=ft.alignment.center,
            )
        elif recording.status_info == RecordingStatus.RECORDING_ERROR:
            return ft.Container(
                content=ft.Text(self._["recording_error"], color=ft.colors.WHITE, size=12, weight=ft.FontWeight.BOLD),
                bgcolor=ft.colors.RED,
                border_radius=5,
                padding=5,
                width=60,
                height=26,
                alignment=ft.alignment.center,
            )
        elif not recording.is_live and recording.monitor_status:
            return ft.Container(
                content=ft.Text(self._["offline"], color=ft.colors.BLACK, size=12, weight=ft.FontWeight.BOLD),
                bgcolor=ft.colors.AMBER,
                border_radius=5,
                padding=5,
                width=60,
                height=26,
                alignment=ft.alignment.center,
            )
        elif not recording.monitor_status:
            return ft.Container(
                content=ft.Text(self._["no_monitor"], color=ft.colors.WHITE, size=12, weight=ft.FontWeight.BOLD),
                bgcolor=ft.colors.GREY,
                border_radius=5,
                padding=5,
                width=60,
                height=26,
                alignment=ft.alignment.center,
            )
        elif recording.is_live and recording.monitor_status and not recording.recording:
            # 显示"直播中（未录制）"状态标签
            return ft.Container(
                content=ft.Text(self._.get("live_monitoring_not_recording", "直播中（未录制）"), color=ft.colors.WHITE, size=12, weight=ft.FontWeight.BOLD),
                bgcolor=ft.colors.CYAN,
                border_radius=5,
                padding=5,
                width=160,
                height=26,
                alignment=ft.alignment.center,
            )
        return None

    async def update_card(self, recording):
        """Update the card display based on the recording's state."""
        try:
            recording_card = self.cards_obj.get(recording.rec_id)
            if not recording_card:
                return

            new_status_label = self.create_status_label(recording)
            
            if recording_card["card"] and recording_card["card"].content and recording_card["card"].content.content:
                title_row = recording_card["card"].content.content.controls[0]
                title_row.alignment = ft.MainAxisAlignment.START
                title_row.spacing = 5
                title_row.tight = True
                
                title_row_controls = title_row.controls
                if len(title_row_controls) > 1:
                    if new_status_label:
                        title_row_controls[1] = new_status_label
                    else:
                        title_row_controls.pop(1)
                elif new_status_label:
                    title_row_controls.append(new_status_label)
            
            recording_card["status_label"] = new_status_label
            
            # 还原显示标题前缀的逻辑
            if recording_card.get("display_title_label"):
                status_prefix = ""
                if not recording.monitor_status:
                    status_prefix = f"[{self._['monitor_stopped']}] "
                
                display_title = f"{status_prefix}{recording.title}"
                recording_card["display_title_label"].value = display_title
                title_label_weight = ft.FontWeight.BOLD if recording.recording or recording.is_live else None
                recording_card["display_title_label"].weight = title_label_weight
            
            if recording_card.get("duration_label"):
                recording_card["duration_label"].value = self.app.record_manager.get_duration(recording)
            
            if recording_card.get("speed_label"):
                recording_card["speed_label"].value = recording.speed
            
            # 动态获取当前语言，定义disabled_tip
            is_zh = getattr(self.app, "language_code", "zh_CN").startswith("zh")
            disabled_tip = "请开启监控或点击刷新按钮" if is_zh else "Please enable monitor or click the refresh button"

            # 全面刷新所有按钮和文本的国际化内容
            if recording_card.get("record_button"):
                recording_card["record_button"].icon = self.get_icon_for_recording_state(recording)
                recording_card["record_button"].tooltip = self.get_tip_for_recording_state(recording)
                # 更新录制按钮的禁用状态
                is_manual_mode = recording.record_mode == "manual"
                is_record_button_disabled = is_manual_mode and not recording.monitor_status
                recording_card["record_button"].disabled = is_record_button_disabled
            if recording_card.get("edit_button"):
                recording_card["edit_button"].tooltip = self._["edit_record_config"]
            if recording_card.get("preview_button"):
                recording_card["preview_button"].tooltip = self._["preview_video"]
            if recording_card.get("monitor_button"):
                recording_card["monitor_button"].icon = self.get_icon_for_monitor_state(recording)
                recording_card["monitor_button"].tooltip = self.get_tip_for_monitor_state(recording)
            if recording_card.get("delete_button"):
                recording_card["delete_button"].tooltip = self._["delete_monitor"]
            if recording_card.get("get_stream_button"):
                recording_card["get_stream_button"].disabled = not (recording.monitor_status and (recording.is_live or recording.recording))
                recording_card["get_stream_button"].tooltip = (
                    self._["copy_stream_url"] if (recording.monitor_status and (recording.is_live or recording.recording)) else disabled_tip
                )
            if recording_card.get("play_button"):
                recording_card["play_button"].disabled = not (recording.monitor_status and (recording.is_live or recording.recording))
                recording_card["play_button"].tooltip = (
                    self._["play_stream"] if (recording.monitor_status and (recording.is_live or recording.recording)) else disabled_tip
                )
            if recording_card.get("open_folder_button"):
                recording_card["open_folder_button"].tooltip = self._["open_folder"]
            if recording_card.get("recording_info_button"):
                recording_card["recording_info_button"].tooltip = self._["recording_info"]

            if recording_card["card"] and recording_card["card"].content:
                recording_card["card"].content.bgcolor = self.get_card_background_color(recording)
                recording_card["card"].content.border = ft.border.all(2, self.get_card_border_color(recording))
                recording_card["card"].update()
        except Exception as e:
            print(f"Error updating card: {e}")

    async def update_monitor_state(self, recording: Recording):
        """Update the monitor button state based on the current monitoring status."""
        if recording.monitor_status:
            recording.update(
                {
                    "recording": False,
                    "monitor_status": not recording.monitor_status,
                    "status_info": RecordingStatus.STOPPED_MONITORING,
                    "display_title": f"[{self._['monitor_stopped']}] {recording.title}",
                }
            )
            self.app.record_manager.stop_recording(recording)
            
            # 手动停止监控时，重置通知状态和was_recording标志
            # 这样下次开始监控时可以再次发送通知
            recording.notification_sent = False
            if hasattr(recording, 'was_recording'):
                recording.was_recording = False
            logger.info(f"手动停止监控，重置通知状态: {recording.streamer_name}")
            
            self.app.page.run_task(self.app.snack_bar.show_snack_bar, self._["stop_monitor_tip"])
        else:
            recording.update(
                {
                    "monitor_status": not recording.monitor_status,
                    "status_info": RecordingStatus.MONITORING,
                    "display_title": f"{recording.title}",
                }
            )
            self.app.page.run_task(self.app.record_manager.check_if_live, recording)
            self.app.page.run_task(self.app.snack_bar.show_snack_bar, self._["start_monitor_tip"], ft.Colors.GREEN)

        await self.update_card(recording)
        self.app.page.pubsub.send_others_on_topic("update", recording)
        self.app.page.run_task(self.app.record_manager.persist_recordings)

        # 如果是手动录制模式，更新录制按钮的状态
        if recording.record_mode == "manual":
            recording_card = self.cards_obj.get(recording.rec_id)
            if recording_card and recording_card.get("record_button"):
                recording_card["record_button"].disabled = not recording.monitor_status
                recording_card["record_button"].update()

    async def show_recording_info_dialog(self, recording: Recording):
        """Display a dialog with detailed information about the recording."""
        # 修复：同时判断开播和关播推送
        global_push_enabled = self.app.settings.user_config.get("stream_start_notification_enabled", False)
        global_end_push_enabled = self.app.settings.user_config.get("stream_end_notification_enabled", False)
        final_push_enabled = global_push_enabled or global_end_push_enabled or recording.enabled_message_push
        dialog = CardDialog(self.app, recording, final_push_enabled=final_push_enabled)
        dialog.open = True
        self.app.dialog_area.content = dialog
        self.app.page.update()

    async def edit_recording_callback(self, recording_list: list[dict]):
        recording_dict = recording_list[0]
        rec_id = recording_dict["rec_id"]
        recording = self.app.record_manager.find_recording_by_id(rec_id)

        await self.app.record_manager.update_recording_card(recording, updated_info=recording_dict)
        if not recording_dict["monitor_status"]:
            recording.display_title = f"[{self._['monitor_stopped']}] " + recording.title

        recording.scheduled_time_range = await self.app.record_manager.get_scheduled_time_range(
            recording.scheduled_start_time, recording.monitor_hours)

        await self.update_card(recording)
        self.app.page.pubsub.send_others_on_topic("update", recording_dict)

    async def on_toggle_recording(self, recording: Recording):
        """Toggle the recording state for a specific recording."""
        if recording and self.app.recording_enabled:
            # 手动录制模式下，检查监控状态
            if recording.record_mode == "manual" and not recording.monitor_status and not recording.recording:
                await self.app.snack_bar.show_snack_bar(
                    self._["manual_mode_monitor_required"], 
                    bgcolor=ft.Colors.AMBER, 
                    duration=3000
                )
                return
                
            if recording.recording:
                self.app.record_manager.stop_recording(recording)
                await self.app.snack_bar.show_snack_bar(self._["stop_record_tip"])
            else:
                # 复用自动录制参数构建方式，保证平台识别一致
                platform, platform_key = get_platform_info(recording.url)
                if not platform or not platform_key:
                    await self.app.snack_bar.show_snack_bar(
                        self._["platform_not_supported_tip"] if "platform_not_supported_tip" in self._ else "不支持的平台或链接", bgcolor=ft.Colors.RED
                    )
                    return
                output_dir = self.app.record_manager.settings.get_video_save_path()
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
                recording.is_live = getattr(stream_info, "is_live", False)
                if stream_info and getattr(stream_info, "record_url", None) and recording.is_live:
                    # 新增：手动模式下也赋值主播id、标题等
                    recording.live_title = getattr(stream_info, "title", None)
                    recording.streamer_name = getattr(stream_info, "anchor_name", recording.streamer_name)
                    recording.title = f"{recording.streamer_name} - {self._[recording.quality]}"
                    recording.display_title = f"[{self._['is_live']}] {recording.title}"
                    
                    # 修复手动录制模式下的消息推送逻辑
                    if recording.record_mode == "manual":
                        try:
                            # 手动模式下，检查全局推送设置和单独的消息推送设置
                            user_config = self.app.settings.user_config
                            
                            # 检查是否启用了全局直播状态推送开关
                            global_push_enabled = user_config.get("stream_start_notification_enabled", False)
                            # 检查是否启用了该录制项的消息推送
                            item_push_enabled = recording.enabled_message_push
                            
                            logger.info(f"全局推送设置: {global_push_enabled}, 单独推送设置: {item_push_enabled}")
                            
                            # 只有当全局直播状态推送开关打开或该录制项单独启用了消息推送时，才进行推送
                            if global_push_enabled or item_push_enabled:
                                # 检查是否有至少一个推送渠道被启用
                                bark_enabled = user_config.get("bark_enabled", False)
                                wechat_enabled = user_config.get("wechat_enabled", False)
                                dingtalk_enabled = user_config.get("dingtalk_enabled", False)
                                ntfy_enabled = user_config.get("ntfy_enabled", False)
                                telegram_enabled = user_config.get("telegram_enabled", False)
                                email_enabled = user_config.get("email_enabled", False)
                                
                                any_channel_enabled = (
                                    bark_enabled or wechat_enabled or dingtalk_enabled or 
                                    ntfy_enabled or telegram_enabled or email_enabled
                                )
                                
                                logger.info(f"推送渠道状态: bark={bark_enabled}, wechat={wechat_enabled}, "
                                           f"dingtalk={dingtalk_enabled}, ntfy={ntfy_enabled}, "
                                           f"telegram={telegram_enabled}, email={email_enabled}")
                                
                                # 检查是否已经发送过通知，避免重复发送
                                if any_channel_enabled and not recording.notification_sent:
                                    # 准备推送内容
                                    push_content = self._["push_content"]
                                    custom_content = user_config.get("custom_stream_start_content")
                                    if custom_content:
                                        push_content = custom_content
                                    
                                    push_at = datetime.today().strftime("%Y-%m-%d %H:%M:%S")
                                    push_content = push_content.replace("[room_name]", recording.streamer_name).replace(
                                        "[time]", push_at
                                    )
                                    
                                    msg_title = user_config.get("custom_notification_title", "").strip()
                                    msg_title = msg_title or self._["status_notify"]
                                    
                                    # 记录推送信息
                                    logger.info(f"手动录制模式下触发消息推送: {msg_title} - {push_content}")
                                    
                                    # 创建消息推送器并发送消息
                                    msg_manager = MessagePusher(self.app.settings)
                                    # 直接在当前任务中执行推送，不使用run_task
                                    push_tasks = await msg_manager.push_messages(msg_title, push_content)
                                    logger.info(f"已创建 {len(push_tasks)} 个推送任务")
                                    # 设置通知已发送标志
                                    recording.notification_sent = True
                                elif recording.notification_sent:
                                    logger.info(f"已经发送过开播通知，跳过重复发送: {recording.streamer_name}")
                                else:
                                    logger.info("没有启用任何推送渠道，跳过消息推送")
                            else:
                                logger.info("全局推送开关和单独推送设置均未启用，跳过消息推送")
                        except Exception as e:
                            logger.error(f"手动录制模式下消息推送失败: {str(e)}")
                    
                    self.app.record_manager.start_update(recording)
                    await recorder.start_recording(stream_info)
                    await self.app.snack_bar.show_snack_bar(self._["pre_record_tip"], bgcolor=ft.Colors.GREEN)
                    # 注意：此时不重置notification_sent标志，保持其状态
                    # 这样在停止录制返回"直播中（未录制）"状态时不会重复发送通知
                    logger.info(f"开始录制，保持通知状态: {recording.streamer_name}")
                else:
                    await self.app.snack_bar.show_snack_bar(
                        self._["is_not_live_tip"] if "is_not_live_tip" in self._ else "未开播，无法录制", bgcolor=ft.Colors.RED
                    )
            await self.update_card(recording)
            self.app.page.pubsub.send_others_on_topic("update", recording)

    async def on_delete_recording(self, recording: Recording):
        """Delete a recording from the list and update UI."""
        if recording:
            # 在删除前检查是否需要切换平台视图
            home_page = self.app.current_page
            need_switch_to_all = False
            
            if hasattr(home_page, "current_platform_filter") and home_page.current_platform_filter != "all":
                # 获取当前平台
                current_platform = home_page.current_platform_filter
                _, recording_platform = get_platform_info(recording.url)
                
                # 如果要删除的是当前筛选平台的录制项
                if recording_platform == current_platform:
                    # 检查是否还有其他相同平台的录制项
                    remaining_items = 0
                    for rec in self.app.record_manager.recordings:
                        if rec.rec_id != recording.rec_id:  # 排除当前要删除的项
                            _, platform_key = get_platform_info(rec.url)
                            if platform_key == current_platform:
                                remaining_items += 1
                    
                    # 如果没有剩余项，准备切换到全部平台视图
                    if remaining_items == 0:
                        need_switch_to_all = True
                        logger.info(f"删除后平台 {current_platform} 下没有剩余直播间，将切换到全部平台视图")
            
            # 执行删除操作
            await self.app.record_manager.delete_recording_cards([recording])
            
            # 如果需要切换到全部平台视图
            if need_switch_to_all and hasattr(home_page, "current_platform_filter"):
                home_page.current_platform_filter = "all"
            
            # 更新筛选区域
            if hasattr(home_page, "create_filter_area") and hasattr(home_page, "content_area"):
                home_page.content_area.controls[1] = home_page.create_filter_area()
                home_page.content_area.update()
                
                # 应用筛选
                if hasattr(home_page, "apply_filter"):
                    await home_page.apply_filter()
                
            await self.app.snack_bar.show_snack_bar(
                self._["delete_recording_success_tip"], bgcolor=ft.Colors.GREEN, duration=2000
            )

    async def remove_recording_card(self, recordings: list[Recording]):
        home_page = self.app.current_page

        existing_ids = {rec.rec_id for rec in self.app.record_manager.recordings}
        remove_ids = {rec.rec_id for rec in recordings}
        keep_ids = existing_ids - remove_ids

        cards_to_remove = [
            card_data["card"]
            for rec_id, card_data in self.cards_obj.items()
            if rec_id not in keep_ids
        ]

        home_page.recording_card_area.content.controls = [
            control
            for control in home_page.recording_card_area.content.controls
            if control not in cards_to_remove
        ]

        self.cards_obj = {
            k: v for k, v in self.cards_obj.items()
            if k in keep_ids
        }
        home_page.recording_card_area.update()
        
        # 删除卡片后更新筛选区域
        if hasattr(home_page, "create_filter_area") and hasattr(home_page, "content_area"):
            # 检查是否需要切换到全部平台视图
            if hasattr(home_page, "current_platform_filter") and home_page.current_platform_filter != "all":
                # 获取当前平台下的录制项
                current_platform = home_page.current_platform_filter
                remaining_items = False
                
                # 检查是否还有当前平台的录制项
                for recording in self.app.record_manager.recordings:
                    _, platform_key = get_platform_info(recording.url)
                    if platform_key == current_platform:
                        remaining_items = True
                        break
                
                # 如果当前平台没有剩余录制项，自动切换到全部平台视图
                if not remaining_items:
                    logger.info(f"平台 {current_platform} 下没有剩余直播间，自动切换到全部平台视图")
                    home_page.current_platform_filter = "all"
            
            # 更新筛选区域
            home_page.content_area.controls[1] = home_page.create_filter_area()
            home_page.content_area.update()
            
            # 应用筛选
            if hasattr(home_page, "apply_filter"):
                self.app.page.run_task(home_page.apply_filter)

    @staticmethod
    async def update_record_hover(recording: Recording):
        return ft.Colors.GREY_400 if recording.selected else None

    @staticmethod
    def get_icon_for_recording_state(recording: Recording):
        """Return the appropriate icon based on the recording's state."""
        return ft.Icons.PLAY_CIRCLE if not recording.recording else ft.Icons.STOP_CIRCLE

    def get_tip_for_recording_state(self, recording: Recording):
        # 在手动录制模式下，如果监控未开启，显示特殊提示
        if recording.record_mode == "manual" and not recording.monitor_status:
            return self._["manual_mode_monitor_required"]
        return self._["stop_record"] if recording.recording else self._["start_record"]

    @staticmethod
    def get_icon_for_monitor_state(recording: Recording):
        """Return the appropriate icon based on the monitor's state."""
        return ft.Icons.VISIBILITY if recording.monitor_status else ft.Icons.VISIBILITY_OFF

    def get_tip_for_monitor_state(self, recording: Recording):
        return self._["stop_monitor"] if recording.monitor_status else self._["start_monitor"]

    async def update_duration(self, recording: Recording):
        """Update the duration text periodically."""
        while True:
            await asyncio.sleep(1)  # Update every second
            if not recording or recording.rec_id not in self.cards_obj:  # Stop task if card is removed
                break

            if recording.recording:
                duration_label = self.cards_obj[recording.rec_id]["duration_label"]
                duration_label.value = self.app.record_manager.get_duration(recording)
                duration_label.update()

    def start_update_task(self, recording: Recording):
        """Start a background task to update the duration text."""
        self.update_duration_tasks[recording.rec_id] = self.app.page.run_task(self.update_duration, recording)

    async def on_card_click(self, recording: Recording):
        """Handle card click events."""
        recording.selected = not recording.selected
        self.selected_cards[recording.rec_id] = recording
        self.cards_obj[recording.rec_id]["card"].content.bgcolor = await self.update_record_hover(recording)
        self.cards_obj[recording.rec_id]["card"].update()

    async def recording_dir_on_click(self, recording: Recording):
        if recording.recording_dir:
            if os.path.exists(recording.recording_dir):
                if not utils.open_folder(recording.recording_dir):
                    await self.app.snack_bar.show_snack_bar(self._['no_video_file'])
            else:
                await self.app.snack_bar.show_snack_bar(self._["no_recording_folder"])
        else:
            await self.app.snack_bar.show_snack_bar(self._["no_recording_started"])

    async def edit_recording_button_click(self, _, recording: Recording):
        """Handle edit button click by showing the edit dialog with existing recording info."""

        if recording.recording or recording.monitor_status:
            await self.app.snack_bar.show_snack_bar(self._["please_stop_monitor_tip"])
            return

        await RecordingDialog(
            self.app,
            on_confirm_callback=self.edit_recording_callback,
            recording=recording,
        ).show_dialog()

    async def recording_delete_button_click(self, _, recording: Recording):
        # 检查是否正在录制，如果是则直接提示
        if recording.recording:
            await self.app.snack_bar.show_snack_bar(
                self._["recording_in_progress_tip"], bgcolor=ft.Colors.RED
            )
            return

        async def confirm_dlg(_):
            self.app.page.run_task(self.on_delete_recording, recording)
            await close_dialog(None)

        async def close_dialog(_):
            delete_alert_dialog.open = False
            delete_alert_dialog.update()

        delete_alert_dialog = ft.AlertDialog(
            title=ft.Text(self._["confirm"]),
            content=ft.Text(self._["delete_confirm_tip"]),
            actions=[
                ft.TextButton(text=self._["cancel"], on_click=close_dialog),
                ft.TextButton(text=self._["sure"], on_click=confirm_dlg),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            modal=False,
        )
        delete_alert_dialog.open = True
        self.app.dialog_area.content = delete_alert_dialog
        self.app.page.update()

    async def preview_video_button_on_click(self, _, recording: Recording):
        if self.app.page.web and recording.record_url:
            video_player = VideoPlayer(self.app)
            await video_player.preview_video(recording.record_url, is_file_path=False, room_url=recording.url)
        elif recording.recording_dir and os.path.exists(recording.recording_dir):
            video_files = []
            for root, _, files in os.walk(recording.recording_dir):
                for file in files:
                    if utils.is_valid_video_file(file):
                        video_files.append(os.path.join(root, file))

            if video_files:
                video_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                latest_video = video_files[0]
                await StoragePage(self.app).preview_file(latest_video, recording.url)
            else:
                await self.app.snack_bar.show_snack_bar(self._["no_video_file"])
        elif not recording.recording_dir:
            await self.app.snack_bar.show_snack_bar(self._["no_recording_started"])
        else:
            await self.app.snack_bar.show_snack_bar(self._["no_recording_folder"])

    async def recording_button_on_click(self, _, recording: Recording):
        await self.on_toggle_recording(recording)

    async def recording_dir_button_on_click(self, _, recording: Recording):
        await self.recording_dir_on_click(recording)

    async def recording_info_button_on_click(self, _, recording: Recording):
        await self.show_recording_info_dialog(recording)

    async def monitor_button_on_click(self, _, recording: Recording):
        await self.update_monitor_state(recording)
        
        # 如果是手动录制模式，更新录制按钮的状态
        if recording.record_mode == "manual":
            recording_card = self.cards_obj.get(recording.rec_id)
            if recording_card and recording_card.get("record_button"):
                recording_card["record_button"].disabled = not recording.monitor_status
                recording_card["record_button"].update()

    async def recording_card_on_click(self, _, recording: Recording):
        await self.on_card_click(recording)

    async def subscribe_update_card(self, _, recording: Recording):
        await self.update_card(recording)

    async def subscribe_remove_cards(self, _, recordings: list[Recording]):
        await self.remove_recording_card(recordings)

    async def get_stream_url_on_click(self, _, recording: Recording):
        if not recording.monitor_status:
            await self.app.snack_bar.show_snack_bar(self._["please_start_monitor"], bgcolor=ft.Colors.RED)
            return
        stream_url, err = await self.app.record_manager.get_stream_url(recording)
        if stream_url:
            self.app.page.set_clipboard(stream_url)
            await self.app.snack_bar.show_snack_bar(self._["stream_url_copied"], bgcolor=ft.Colors.GREEN)
        else:
            await self.app.snack_bar.show_snack_bar(err or self._["no_stream_url"], bgcolor=ft.Colors.RED)

    async def play_stream_on_click(self, _, recording: Recording):
        if not recording.monitor_status:
            await self.app.snack_bar.show_snack_bar(self._["please_start_monitor"], bgcolor=ft.Colors.RED)
            return
        vlc_path = self.app.settings.user_config.get("vlc_path")
        if not vlc_path or not os.path.exists(vlc_path):
            await self.app.snack_bar.show_snack_bar(self._["vlc_not_set"], bgcolor=ft.Colors.RED)
            return
        stream_url, err = await self.app.record_manager.get_stream_url(recording)
        if stream_url:
            import subprocess
            try:
                subprocess.Popen([vlc_path, stream_url])
                await self.app.snack_bar.show_snack_bar(self._["play_stream"] + "...", bgcolor=ft.Colors.GREEN)
            except Exception as e:
                await self.app.snack_bar.show_snack_bar(self._["play_failed"] + f"\n{e}", bgcolor=ft.Colors.RED)
        else:
            await self.app.snack_bar.show_snack_bar(err or self._["play_failed"], bgcolor=ft.Colors.RED)
