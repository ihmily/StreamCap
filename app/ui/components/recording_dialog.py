import flet as ft

from ...core.platform_handlers import get_platform_info
from ...models.audio_format_model import AudioFormat
from ...models.video_format_model import VideoFormat
from ...models.video_quality_model import VideoQuality
from ...utils import utils
from ...utils.logger import logger


class RecordingDialog:
    def __init__(self, app, on_confirm_callback=None, recording=None):
        self.app = app
        self.page = self.app.page
        self.on_confirm_callback = on_confirm_callback
        self.recording = recording
        self.app.language_manager.add_observer(self)
        self._ = {}
        self.load()

    def load(self):
        language = self.app.language_manager.language
        for key in ("recording_dialog", "home_page", "base", "video_quality"):
            self._.update(language.get(key, {}))

    async def show_dialog(self):
        """Show a dialog for adding or editing a recording."""
        initial_values = self.recording.to_dict() if self.recording else {}

        async def on_url_change(_):
            """Enable or disable the submit button based on whether the URL field is filled."""
            is_active = utils.is_valid_url(url_field.value.strip()) or utils.contains_url(batch_input.value.strip())
            dialog.actions[1].disabled = not is_active
            self.page.update()

        async def update_format_options(e):
            if e.control.value == "video":
                record_format_field.options = [ft.dropdown.Option(i) for i in VideoFormat.get_formats()]
            else:
                record_format_field.options = [ft.dropdown.Option(i) for i in AudioFormat.get_formats()]
            record_format_field.value = record_format_field.options[0].key
            record_format_field.update()

        url_field = ft.TextField(
            label=self._["input_live_link"],
            hint_text=self._["example"] + "：https://www.example.com/xxxxxx",
            border_radius=5,
            filled=False,
            value=initial_values.get("url"),
            on_change=on_url_change,
        )
        user_config = self.app.settings.user_config
        quality_dropdown = ft.Dropdown(
            label=self._["select_resolution"],
            options=[ft.dropdown.Option(i, text=self._[i]) for i in VideoQuality.get_qualities()],
            border_radius=5,
            filled=False,
            value=initial_values.get("quality", user_config.get("record_quality", VideoQuality.OD)),
            width=500,
        )
        streamer_name_field = ft.TextField(
            label=self._["input_anchor_name"],
            hint_text=self._["default_input"],
            border_radius=5,
            filled=False,
            value=initial_values.get("streamer_name", ""),
        )
        media_type_dropdown = ft.Dropdown(
            label=self._["select_media_type"],
            options=[
                ft.dropdown.Option("video", text=self._["video"]),
                ft.dropdown.Option("audio", text=self._["audio"])
            ],
            width=245,
            value="video",
            on_change=update_format_options
        )
        user_config = self.app.settings.user_config
        record_format_field = ft.Dropdown(
            label=self._["select_record_format"],
            options=[ft.dropdown.Option(i) for i in VideoFormat.get_formats()],
            border_radius=5,
            filled=False,
            value=initial_values.get("record_format", user_config.get("video_format", VideoFormat.TS)),
            width=245,
            menu_height=200
        )

        format_row = ft.Row([media_type_dropdown, record_format_field], expand=True)

        recording_dir_field = ft.TextField(
            label=self._["input_save_path"],
            hint_text=self._["default_input"],
            border_radius=5,
            filled=False,
            value=initial_values.get("recording_dir"),
        )

        user_config = self.app.settings.user_config
        segmented_recording_enabled = user_config.get('segmented_recording_enabled', False)
        video_segment_time = user_config.get('video_segment_time', 1800)
        segment_record = initial_values.get("segment_record", segmented_recording_enabled)
        segment_time = initial_values.get("segment_time", video_segment_time)

        async def on_segment_setting_change(e):
            selected_value = e.control.value
            segment_input.visible = selected_value == self._["yes"]
            self.page.update()

        segment_setting_dropdown = ft.Dropdown(
            label=self._["is_segment_enabled"],
            options=[
                ft.dropdown.Option(self._["yes"]),
                ft.dropdown.Option(self._["no"]),
            ],
            border_radius=5,
            filled=False,
            value=self._["yes"] if segment_record else self._["no"],
            on_change=on_segment_setting_change,
            width=500,
        )

        segment_input = ft.TextField(
            label=self._["segment_record_time"],
            hint_text=self._["input_segment_time"],
            border_radius=5,
            filled=False,
            value=segment_time,
            visible=segment_record,
        )

        scheduled_recording = initial_values.get("scheduled_recording", False)
        scheduled_start_time = initial_values.get("scheduled_start_time")
        monitor_hours = initial_values.get("monitor_hours", 5)
        message_push_enabled = initial_values.get('enabled_message_push', False)

        async def on_scheduled_setting_change(e):
            selected_value = e.control.value
            schedule_and_monitor_row.visible = selected_value == "true"
            monitor_hours_input.visible = selected_value == "true"
            self.page.update()

        async def pick_time(_):
            async def handle_change(_):
                scheduled_start_time_input.value = time_picker.value
                scheduled_start_time_input.update()

            time_picker = ft.TimePicker(
                confirm_text=self._['confirm'],
                cancel_text=self._['cancel'],
                error_invalid_text=self._['time_out_of_range'],
                help_text=self._['pick_time_slot'],
                hour_label_text=self._['hour_label_text'],
                minute_label_text=self._['minute_label_text'],
                on_change=handle_change
            )
            self.page.open(time_picker)

        scheduled_setting_dropdown = ft.Dropdown(
            label=self._["scheduled_recording"],
            options=[
                ft.dropdown.Option("true", self._["yes"]),
                ft.dropdown.Option("false", self._["no"]),
            ],
            border_radius=5,
            filled=False,
            value="true" if scheduled_recording else "false",
            on_change=on_scheduled_setting_change,
            width=500,
        )

        scheduled_start_time_input = ft.TextField(
            label=self._["scheduled_start_time"],
            hint_text=self._["example"] + "：18:30:00",
            border_radius=5,
            filled=False,
            value=scheduled_start_time,
        )

        time_picker_button = ft.ElevatedButton(
            self._['pick_time'],
            icon=ft.Icons.TIME_TO_LEAVE,
            on_click=pick_time,
            tooltip=self._['pick_time_tip']
        )

        schedule_and_monitor_row = ft.Row(
            [
                ft.Container(content=scheduled_start_time_input, expand=True),
                ft.Container(content=time_picker_button),
            ],
            spacing=10,
            visible=scheduled_recording,
        )

        monitor_hours_input = ft.TextField(
            label=self._["monitor_hours"],
            hint_text=self._["example"] + "：5",
            border_radius=5,
            filled=False,
            value=monitor_hours,
            keyboard_type=ft.KeyboardType.NUMBER,
            visible=scheduled_recording,
        )

        message_push_dropdown = ft.Dropdown(
            label=self._["enable_message_push"],
            options=[
                ft.dropdown.Option("true", self._["yes"]),
                ft.dropdown.Option("false", self._["no"]),
            ],
            border_radius=5,
            filled=False,
            value="true" if message_push_enabled else "false",
            width=500,
        )

        record_mode_dropdown = ft.Dropdown(
            label=self._.get("record_mode", "录制模式"),
            options=[
                ft.dropdown.Option("auto", self._.get("auto_record", "自动录制")),
                ft.dropdown.Option("manual", self._.get("manual_record", "手动录制"))
            ],
            value=initial_values.get("record_mode", "auto"),
            width=500,
        )

        hint_text_dict = {
            "en": "Example:\n0，https://v.douyin.com/AbcdE，nickname1\n0，https://v.douyin.com/EfghI，nickname2\n\nPS: "
            "0=original image or Blu ray, 1=ultra clear, 2=high-definition, 3=standard definition, 4=smooth\n",
            "zh_CN": "示例:\n0，https://v.douyin.com/AbcdE，主播名1\n0，https://v.douyin.com/EfghI，主播名2"
            "\n\n其中0=原画或者蓝光，1=超清，2=高清，3=标清，4=流畅",
        }

        # Batch input field
        batch_input = ft.TextField(
            label=self._["batch_input_tip"],
            multiline=True,
            min_lines=15,
            max_lines=20,
            border_radius=5,
            filled=False,
            visible=True,
            hint_style=ft.TextStyle(
                size=14,
                color=ft.Colors.GREY_500,
                font_family="Arial",
            ),
            on_change=on_url_change,
            hint_text=hint_text_dict.get(self.app.language_code, hint_text_dict["zh_CN"]),
        )

        tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            height=500,
            tabs=[
                ft.Tab(
                    text=self._["single_input"],
                    content=ft.Container(
                        content=ft.Column(
                            [
                                ft.Container(margin=ft.margin.only(top=10)),
                                url_field,
                                streamer_name_field,
                                format_row,
                                quality_dropdown,
                                record_mode_dropdown,
                                recording_dir_field,
                                segment_setting_dropdown,
                                segment_input,
                                scheduled_setting_dropdown,
                                schedule_and_monitor_row,
                                monitor_hours_input,
                                message_push_dropdown
                            ],
                            tight=True,
                            spacing=10,
                            scroll=ft.ScrollMode.AUTO,
                        )
                    ),
                ),
                ft.Tab(
                    text=self._["batch_input"], content=ft.Container(content=batch_input, margin=ft.margin.only(top=15))
                ),
            ],
        )

        async def not_supported(url):
            lang_code = getattr(self.app, "language_code", "zh_CN").lower()
            if not lang_code or "zh" in lang_code:
                log_msg = f"⚠️ 暂不支持该平台录制: {url}"
            else:
                log_msg = f"⚠️ This platform does not support recording: {url}"
            logger.warning(log_msg)
            await self.app.snack_bar.show_snack_bar(self._["platform_not_supported_tip"], duration=3000)

        async def on_confirm(e):
            if tabs.selected_index == 0:
                quality_info = self._[quality_dropdown.value]

                if not streamer_name_field.value:
                    anchor_name = self._["live_room"]
                    title = f"{anchor_name} - {quality_info}"
                else:
                    anchor_name = streamer_name_field.value.strip()
                    title = f"{anchor_name} - {quality_info}"

                display_title = title
                rec_id = self.recording.rec_id if self.recording else None
                live_url = url_field.value.strip()
                platform, platform_key = get_platform_info(live_url)
                if not platform:
                    await not_supported(url_field.value)
                    await close_dialog(e)
                    return

                # 新增：直接获取直播间信息
                real_anchor_name = anchor_name
                real_title = title
                try:
                    from ...core.stream_manager import LiveStreamRecorder
                    recording_info_dict = {
                        "platform": platform,
                        "platform_key": platform_key,
                        "live_url": live_url,
                        "output_dir": self.app.record_manager.settings.get_video_save_path(),
                        "segment_record": segment_input.visible,
                        "segment_time": segment_input.value,
                        "save_format": record_format_field.value,
                        "quality": quality_dropdown.value,
                    }
                    # 创建一个临时Recording对象传递给LiveStreamRecorder，避免使用None
                    from ...models.recording_model import Recording
                    temp_recording = Recording(
                        rec_id=None,
                        url=live_url,
                        streamer_name=anchor_name,
                        record_format=record_format_field.value,
                        quality=quality_dropdown.value,
                        segment_record=segment_input.visible,
                        segment_time=segment_input.value,
                        monitor_status=False,
                        scheduled_recording=False,
                        scheduled_start_time=None,
                        monitor_hours=None,
                        recording_dir=None,
                        enabled_message_push=False
                    )
                    
                    # 在编辑对话框中获取直播间信息时，不使用代理，避免可能的JSON解析错误
                    # 强制设置proxy为None，避免使用系统代理
                    user_config = self.app.settings.user_config
                    original_proxy_setting = user_config.get("enable_proxy", False)
                    original_proxy_platforms = user_config.get("default_platform_with_proxy", "")
                    
                    # 临时禁用代理
                    try:
                        # 创建不使用代理的LiveStreamRecorder实例
                        recorder = LiveStreamRecorder(self.app, temp_recording, recording_info_dict)
                        # 强制设置proxy为None
                        recorder.proxy = None
                        stream_info = await recorder.fetch_stream()
                        if stream_info:
                            real_anchor_name = getattr(stream_info, "anchor_name", anchor_name)
                            real_title = getattr(stream_info, "title", title)
                    except Exception as ex:
                        logger.error(f"[Dialog] 不使用代理获取直播间信息失败: {ex}")
                        # 如果不使用代理失败，尝试使用代理
                        logger.info("[Dialog] 尝试使用代理获取直播间信息")
                        try:
                            recorder = LiveStreamRecorder(self.app, temp_recording, recording_info_dict)
                            stream_info = await recorder.fetch_stream()
                            if stream_info:
                                real_anchor_name = getattr(stream_info, "anchor_name", anchor_name)
                                real_title = getattr(stream_info, "title", title)
                        except Exception as ex2:
                            logger.error(f"[Dialog] 使用代理获取直播间信息也失败: {ex2}")
                            # 继续使用默认值
                except Exception as ex:
                    logger.error(f"[Dialog] 获取直播间信息失败: {ex}")
                    # 继续使用默认值

                recordings_info = [
                    {
                        "rec_id": rec_id,
                        "url": live_url,
                        "streamer_name": real_anchor_name,
                        "record_format": record_format_field.value,
                        "quality": quality_dropdown.value,
                        "quality_info": quality_info,
                        "title": f"{real_anchor_name} - {quality_info}",
                        "speed": "X KB/s",
                        "segment_record": segment_input.visible,
                        "segment_time": segment_input.value,
                        "monitor_status": initial_values.get("monitor_status", True),
                        "display_title": f"{real_anchor_name} - {quality_info}",
                        "scheduled_recording": schedule_and_monitor_row.visible,
                        "scheduled_start_time": str(scheduled_start_time_input.value),
                        "monitor_hours": monitor_hours_input.value,
                        "recording_dir": recording_dir_field.value,
                        "enabled_message_push": message_push_dropdown.value == "true",
                        "record_mode": record_mode_dropdown.value,
                        "live_title": real_title,
                    }
                ]
                await self.on_confirm_callback(recordings_info)

            elif tabs.selected_index == 1:  # Batch entry
                lines = batch_input.value.splitlines()
                recordings_info = []
                streamer_name = ""
                quality = "OD"
                quality_dict = {"0": "OD", "1": "UHD", "2": "HD", "3": "SD", "4": "LD"}
                for line in lines:
                    if "http" not in line:
                        continue
                    res = [i for i in line.strip().replace("，", ",").split(",") if i]
                    if len(res) == 3:
                        quality, url, streamer_name = res
                    elif len(res) == 2:
                        if res[1].startswith("http"):
                            quality, url = res
                        else:
                            url, streamer_name = res
                    else:
                        url = res[0]

                    platform, platform_key = get_platform_info(url)
                    if not platform:
                        await not_supported(url)
                        continue

                    quality = quality_dict.get(quality, "OD")
                    title = f"{streamer_name} - {self._[quality]}"
                    display_title = title
                    if not streamer_name:
                        streamer_name = self._["live_room"]
                        display_title = streamer_name + url.split("?")[0] + "... - " + self._[quality]

                    recording_info = {
                        "url": url.strip(),
                        "streamer_name": streamer_name,
                        "quality": quality,
                        "quality_info": self._[VideoQuality.OD],
                        "title": title,
                        "display_title": display_title,
                    }
                    recordings_info.append(recording_info)

                await self.on_confirm_callback(recordings_info)

            await close_dialog(e)

        async def close_dialog(_):
            dialog.open = False
            self.page.update()

        close_button = ft.IconButton(icon=ft.Icons.CLOSE, tooltip=self._["close"], on_click=close_dialog)

        title_text = self._["edit_record"] if self.recording else self._["add_record"]
        dialog = ft.AlertDialog(
            open=True,
            modal=True,
            title=ft.Row(
                [
                    ft.Text(title_text, size=16, theme_style=ft.TextThemeStyle.TITLE_LARGE),
                    ft.Container(width=10),
                    close_button,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                width=500
            ),
            content=tabs,
            actions=[
                ft.TextButton(text=self._["cancel"], on_click=close_dialog),
                ft.TextButton(text=self._["sure"], on_click=on_confirm, disabled=self.recording is None),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(radius=10)
        )

        self.page.overlay.append(dialog)
        self.page.update()
        