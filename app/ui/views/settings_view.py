import asyncio
import os
import json

import flet as ft

from ...models.video_format_model import VideoFormat
from ...models.video_quality_model import VideoQuality
from ...utils.delay import DelayedTaskExecutor
from ...utils.logger import logger
from ..base_page import PageBase
from ..components.help_dialog import HelpDialog
from ...core.platform_handlers import get_platform_info
from app.core.platform_handlers.platform_map import get_platform_display_name, platform_map


class SettingsPage(PageBase):
    def __init__(self, app):
        super().__init__(app)
        self.page_name = "settings"
        self.config_manager = self.app.config_manager

        self.user_config = self.config_manager.load_user_config()
        self.language_option = self.config_manager.load_language_config()
        self.default_config = self.config_manager.load_default_config()
        self.cookies_config = self.config_manager.load_cookies_config()
        self.accounts_config = self.config_manager.load_accounts_config()

        self.language_code = None
        self.default_language = None
        self.focused_control = None
        self.tab_recording = None
        self.tab_push = None
        self.tab_cookies = None
        self.tab_accounts = None
        self.tab_security = None
        self.has_unsaved_changes = {}
        self.delay_handler = DelayedTaskExecutor(self.app, self)
        self.load_language()
        self.init_unsaved_changes()
        self.page.on_keyboard_event = self.on_keyboard

    async def load(self):
        self.content_area.clean()
        language = self.app.language_manager.language
        self._ = language["settings_page"] | language["video_quality"] | language["base"]
        self.tab_recording = self.create_recording_settings_tab()
        self.tab_push = self.create_push_settings_tab()
        self.tab_cookies = self.create_cookies_settings_tab()
        self.tab_accounts = self.create_accounts_settings_tab()
        self.page.on_keyboard_event = self.on_keyboard

        tabs = [
            ft.Tab(text=self._["recording_settings"], content=self.tab_recording),
            ft.Tab(text=self._["push_settings"], content=self.tab_push),
            ft.Tab(text=self._["cookies_settings"], content=self.tab_cookies),
            ft.Tab(text=self._["accounts_settings"], content=self.tab_accounts),
        ]
        
        if self.app.page.web:
            self.tab_security = self.create_security_settings_tab()
            tabs.append(ft.Tab(text=self._["security_settings"], content=self.tab_security))

        settings_tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=tabs,
        )

        scrollable_content = ft.Container(
            content=settings_tabs,
            expand=True,
        )

        settings_content = ft.Container(
            content=scrollable_content,
            expand=True,
        )

        column_layout = ft.Column(
            [
                settings_content,
            ],
            spacing=0,
            expand=True,
        )

        self.content_area.controls.append(column_layout)
        self.app.complete_page.update()

    def init_unsaved_changes(self):
        self.has_unsaved_changes = {
            "user_config": False,
            "cookies_config": False,
            "accounts_config": False
        }

    def load_language(self):
        self.default_language, default_language_code = list(self.language_option.items())[0]
        select_language = self.user_config.get("language")
        self.language_code = self.language_option.get(select_language, default_language_code)
        self.app.language_code = self.language_code

    def get_config_value(self, key, default=None):
        # 默认平台筛选风格为平铺
        if key == "platform_filter_style":
            return self.user_config.get(key, self.default_config.get(key, "tile"))
        return self.user_config.get(key, self.default_config.get(key, default))

    def get_cookies_value(self, key, default=""):
        return self.cookies_config.get(key, default)

    def get_accounts_value(self, key, default=None):
        k1, k2 = key.split("_", maxsplit=1)
        return self.accounts_config.get(k1, {}).get(k2, default)

    async def restore_default_config(self, _):
        """Restore settings to their default values."""

        async def confirm_dlg(_):
            ui_language = self.user_config["language"]
            vlc_path = self.user_config.get("vlc_path", "")
            self.user_config = self.default_config.copy()
            self.user_config["language"] = ui_language
            self.user_config["enable_proxy"] = False
            # 保留VLC路径设置
            if vlc_path:
                self.user_config["vlc_path"] = vlc_path
            # 恢复默认平台筛选风格为平铺
            self.user_config["platform_filter_style"] = "tile"
            self.app.language_manager.notify_observers()
            self.page.run_task(self.load)
            await self.config_manager.save_user_config(self.user_config)
            logger.success("Default configuration restored.")
            await self.app.snack_bar.show_snack_bar(self._["success_restore_tip"], bgcolor=ft.Colors.GREEN)
            await close_dialog(None)

        async def close_dialog(_):
            restore_alert_dialog.open = False
            restore_alert_dialog.update()

        restore_alert_dialog = ft.AlertDialog(
            title=ft.Text(self._["confirm"]),
            content=ft.Text(self._["query_restore_config_tip"]),
            actions=[
                ft.TextButton(text=self._["cancel"], on_click=close_dialog),
                ft.TextButton(text=self._["sure"], on_click=confirm_dlg),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            modal=False,
        )

        self.app.dialog_area.content = restore_alert_dialog
        self.app.dialog_area.content.open = True
        self.app.dialog_area.update()

    async def on_change(self, e):
        """Handle changes in any input field and trigger auto-save."""
        key = e.control.data
        if isinstance(e.control, (ft.Switch, ft.Checkbox)):
            self.user_config[key] = e.data.lower() == "true"
        else:
            # 特殊处理vlc_path，替换为Windows风格分隔符
            if key == "vlc_path":
                self.user_config[key] = e.data.replace("/", "\\")
            else:
                self.user_config[key] = e.data
            
        if key in ["folder_name_platform", "folder_name_author", "folder_name_time", "folder_name_title"]:
            for recording in self.app.record_manager.recordings:
                recording.recording_dir = None
            self.page.run_task(self.app.record_manager.persist_recordings)
            
        if key == "language":
            self.load_language()
            self.app.language_manager.load()
            self.app.language_manager.notify_observers()
            self.page.run_task(self.load)
            # 国际化提示
            is_zh = getattr(self.app, "language_code", "zh_CN").startswith("zh")
            tip = "请点击主界面的刷新按钮来刷新监控卡片信息" if is_zh else "Please click the refresh button on the main page to refresh the monitor cards"
            self.page.run_task(self.app.snack_bar.show_snack_bar, tip, ft.Colors.AMBER)

        if key == "loop_time_seconds":
            self.app.record_manager.initialize_dynamic_state()
        self.page.run_task(self.delay_handler.start_task_timer, self.save_user_config_after_delay, None)
        self.has_unsaved_changes['user_config'] = True

    def on_cookies_change(self, e):
        """Handle changes in any input field and trigger auto-save."""
        key = e.control.data
        self.cookies_config[key] = e.data
        self.page.run_task(self.delay_handler.start_task_timer, self.save_cookies_after_delay, None)
        self.has_unsaved_changes['cookies_config'] = True

    def on_accounts_change(self, e):
        """Handle changes in any input field and trigger auto-save."""
        key = e.control.data
        k1, k2 = key.split("_", maxsplit=1)
        if k1 not in self.accounts_config:
            self.accounts_config[k1] = {}

        self.accounts_config[k1][k2] = e.data
        self.page.run_task(self.delay_handler.start_task_timer, self.save_accounts_after_delay, None)
        self.has_unsaved_changes['accounts_config'] = True

    async def save_user_config_after_delay(self, delay):
        await asyncio.sleep(delay)
        if self.has_unsaved_changes['user_config']:
            await self.config_manager.save_user_config(self.user_config)

    async def save_cookies_after_delay(self, delay):
        await asyncio.sleep(delay)
        if self.has_unsaved_changes['cookies_config']:
            await self.config_manager.save_cookies_config(self.cookies_config)

    async def save_accounts_after_delay(self, delay):
        await asyncio.sleep(delay)
        if self.has_unsaved_changes['accounts_config']:
            await self.config_manager.save_accounts_config(self.accounts_config)

    def get_video_save_path(self):
        live_save_path = self.get_config_value("live_save_path")
        if not live_save_path:
            live_save_path = os.path.join(self.app.run_path, 'downloads')
        return live_save_path

    def create_recording_settings_tab(self):
        """Create UI elements for recording settings."""
        def get_all_platforms():
            return platform_map
        def get_platform_display_name_wrapper(key):
            lang = self.app.language_code if hasattr(self.app, 'language_code') else 'zh_CN'
            return get_platform_display_name(key, lang)

        def get_selected_platforms_text():
            current_value = self.get_config_value("default_platform_with_proxy", "")
            # 增强处理，过滤掉空值
            selected_keys = [k for k in current_value.replace("，", ",").split(",") if k and k.strip()]
            if not selected_keys:
                return self._["none"] if "none" in self._ else "无"
            return ", ".join([get_platform_display_name_wrapper(k) for k in selected_keys])

        proxy_platform_text = ft.Text(get_selected_platforms_text(), width=220)
        def show_platform_select_dialog(e):
            current_value = self.get_config_value("default_platform_with_proxy", "")
            selected_keys = set([k for k in current_value.replace("，", ",").split(",") if k])
            all_platforms = get_all_platforms()
            checkboxes = []
            for key in all_platforms:
                cb = ft.Checkbox(
                    label=get_platform_display_name_wrapper(key),
                    value=key in selected_keys,
                    data=key
                )
                checkboxes.append(cb)
            dialog = ft.AlertDialog(
                title=ft.Text(self._["default_platform_with_proxy"]),
                content=ft.Column(checkboxes, scroll=ft.ScrollMode.AUTO, height=400),
                actions=[
                    ft.TextButton(self._["cancel"], on_click=lambda e: close_dialog()),
                    ft.TextButton(self._["sure"], on_click=lambda e: save_selection(checkboxes, dialog)),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
                modal=True,
            )
            self.app.dialog_area.content = dialog
            dialog.open = True
            self.app.dialog_area.update()

        def save_selection(checkboxes, dialog):
            # 过滤掉无效数据
            selected = [cb.data for cb in checkboxes if cb.value and cb.data]
            
            # 记录选择变更
            old_selected = self.get_config_value("default_platform_with_proxy", "").split(",")
            new_selected = selected
            logger.info(f"代理平台选择变更 - 旧选择: {old_selected}, 新选择: {new_selected}")
            
            # 保存到用户配置
            self.user_config["default_platform_with_proxy"] = ",".join(selected)
            self.page.run_task(self.delay_handler.start_task_timer, self.save_user_config_after_delay, None)
            self.has_unsaved_changes['user_config'] = True
            
            # 关闭对话框并更新UI
            dialog.open = False
            self.app.dialog_area.update()
            proxy_platform_text.value = get_selected_platforms_text()
            proxy_platform_text.update()
            self.page.update()

        def close_dialog():
            self.app.dialog_area.content.open = False
            self.app.dialog_area.update()

        return ft.Column(
            [
                self.create_setting_group(
                    self._["basic_settings"],
                    self._["program_config"],
                    [
                        self.create_setting_row(
                            self._["restore_defaults"],
                            ft.IconButton(
                                icon=ft.Icons.RESTORE_OUTLINED,
                                icon_size=32,
                                tooltip=self._["restore_defaults"],
                                on_click=self.restore_default_config,
                            ),
                        ),
                        self.create_setting_row(
                            self._["program_language"],
                            ft.Dropdown(
                                options=[
                                    ft.dropdown.Option(key=k, text=self._[k]) for k, v in self.language_option.items()
                                ],
                                value=self.get_config_value("language", self.default_language),
                                width=200,
                                on_change=self.on_change,
                                data="language",
                                tooltip=self._["switch_language"],
                            ),
                        ),
                        self.create_setting_row(
                            self._["filename_includes_title"],
                            ft.Switch(
                                value=self.get_config_value("filename_includes_title"),
                                on_change=self.on_change,
                                data="filename_includes_title",
                            ),
                        ),
                        self.pick_folder(
                            self._["live_recording_path"],
                            ft.TextField(
                                value=self.get_video_save_path(),
                                width=300,
                                on_change=self.on_change,
                                data="live_save_path",
                            ),
                        ),
                        self.create_setting_row(
                            self._["remove_emojis"],
                            ft.Switch(
                                value=self.get_config_value("remove_emojis"),
                                on_change=self.on_change,
                                data="remove_emojis",
                            ),
                        ),
                        self.create_folder_setting_row(self._["name_rules"]),
                        self.create_setting_row(
                            self._["vlc_path"],
                            ft.TextField(
                                value=self.get_config_value("vlc_path", ""),
                                width=380,
                                on_change=self.on_change,
                                data="vlc_path",
                                hint_text=self._["vlc_path_hint"] if "vlc_path_hint" in self._ else "",
                            ),
                        ),
                        self.create_setting_row(
                            self._["default_platform_with_proxy"],
                            ft.Row([
                                proxy_platform_text,
                                ft.ElevatedButton(
                                    text=self._["select"],
                                    icon=ft.Icons.LIST_ALT,
                                    on_click=show_platform_select_dialog,
                                    tooltip=self._["default_platform_with_proxy"]
                                )
                            ]),
                        ),
                        self.create_setting_row(
                            self._["platform_filter_style"],
                            ft.Dropdown(
                                options=[
                                    ft.dropdown.Option(key="tile", text=self._["platform_filter_style_tile"]),
                                    ft.dropdown.Option(key="dropdown", text=self._["platform_filter_style_dropdown"]),
                                ],
                                value=self.get_config_value("platform_filter_style", "tile"),
                                width=260,
                                on_change=self.on_change,
                                data="platform_filter_style",
                                tooltip=self._["platform_filter_style_tip"],
                            ),
                        ),
                    ],
                ),
                self.create_setting_group(
                    self._["proxy_settings"],
                    self._["is_proxy_enabled"],
                    [
                        self.create_setting_row(
                            self._["enable_proxy"],
                            ft.Switch(
                                value=self.get_config_value("enable_proxy"),
                                on_change=self.on_change,
                                data="enable_proxy",
                            ),
                        ),
                        self.create_setting_row(
                            self._["proxy_address"],
                            ft.TextField(
                                value=self.get_config_value("proxy_address"),
                                width=300,
                                on_change=self.on_change,
                                data="proxy_address",
                                hint_text="如: http://IP:Port 或 IP:Port",
                                helper_text="填写代理地址，如不带协议前缀，将自动添加",
                            ),
                        ),
                    ],
                ),
                self.create_setting_group(
                    self._["recording_options"],
                    self._["advanced_config"],
                    [
                        self.create_setting_row(
                            self._["video_record_format"],
                            ft.Dropdown(
                                options=[ft.dropdown.Option(i) for i in VideoFormat.get_formats()],
                                value=self.get_config_value("video_format", VideoFormat.TS),
                                width=200,
                                data="video_format",
                                on_change=self.on_change,
                                tooltip=self._["switch_video_format"],
                            ),
                        ),
                        self.create_setting_row(
                            self._["recording_quality"],
                            ft.Dropdown(
                                options=[ft.dropdown.Option(i, text=self._[i]) for i in VideoQuality.get_qualities()],
                                value=self.get_config_value("record_quality", VideoQuality.OD),
                                width=200,
                                data="record_quality",
                                on_change=self.on_change,
                                tooltip=self._["switch_recording_quality"],
                            ),
                        ),
                        self.create_setting_row(
                            self._["loop_time"],
                            ft.TextField(
                                value=self.get_config_value("loop_time_seconds"),
                                width=100,
                                data="loop_time_seconds",
                                on_change=self.on_change,
                            ),
                        ),
                        self.create_setting_row(
                            self._["is_segmented_recording_enabled"],
                            ft.Switch(
                                value=self.get_config_value("segmented_recording_enabled"),
                                data="segmented_recording_enabled",
                                on_change=self.on_change,
                            ),
                        ),
                        self.create_setting_row(
                            self._["force_https"],
                            ft.Switch(
                                value=self.get_config_value("force_https_recording"),
                                data="force_https_recording",
                                on_change=self.on_change,
                            ),
                        ),
                        self.create_setting_row(
                            self._["space_threshold"],
                            ft.TextField(
                                value=self.get_config_value("recording_space_threshold"),
                                width=100,
                                data="recording_space_threshold",
                                on_change=self.on_change,
                            ),
                        ),
                        self.create_setting_row(
                            self._["segment_time"],
                            ft.TextField(
                                value=self.get_config_value("video_segment_time"),
                                width=100,
                                data="video_segment_time",
                                on_change=self.on_change,
                            ),
                        ),
                        self.create_setting_row(
                            self._["convert_mp4"],
                            ft.Switch(
                                value=self.get_config_value("convert_to_mp4"),
                                data="convert_to_mp4",
                                on_change=self.on_change,
                            ),
                        ),
                        self.create_setting_row(
                            self._["delete_original"],
                            ft.Switch(
                                value=self.get_config_value("delete_original"),
                                data="delete_original",
                                on_change=self.on_change,
                            ),
                        ),
                        self.create_setting_row(
                            self._["generate_timestamps_subtitle"],
                            ft.Switch(
                                value=self.get_config_value("generate_time_subtitle_file"),
                                data="generate_time_subtitle_file",
                                on_change=self.on_change,
                            ),
                        ),
                        self.create_setting_row(
                            self._["custom_script"],
                            ft.Switch(
                                value=self.get_config_value("execute_custom_script"),
                                data="execute_custom_script",
                                on_change=self.on_change,
                            ),
                        ),
                        self.create_setting_row(
                            self._["script_command"],
                            ft.TextField(
                                value=self.get_config_value("custom_script_command"),
                                width=300,
                                data="custom_script_command",
                                on_change=self.on_change,
                            ),
                        ),
                    ],
                ),
            ],
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
        )

    def create_push_settings_tab(self):
        """Create the push settings tab for notification settings."""
        return ft.Column(
            [
                self.create_setting_group(
                    self._["push_notifications"],
                    self._["stream_start_notification_enabled"],
                    [
                        ft.Container(
                            content=ft.Text(
                                self._["notification_both_required"],
                                size=14,
                                color=ft.colors.AMBER_700,
                                italic=True,
                            ),
                            margin=ft.margin.only(bottom=10),
                            padding=10,
                            border_radius=5,
                            bgcolor=ft.colors.AMBER_50,
                        ),
                        self.create_setting_row(
                            self._["open_broadcast_push_enabled"],
                            ft.Switch(
                                value=self.get_config_value("stream_start_notification_enabled"),
                                data="stream_start_notification_enabled",
                                on_change=self.on_change,
                            ),
                        ),
                        self.create_setting_row(
                            self._["close_broadcast_push_enabled"],
                            ft.Switch(
                                value=self.get_config_value("stream_end_notification_enabled"),
                                data="stream_end_notification_enabled",
                                on_change=self.on_change,
                            ),
                        ),
                        self.create_setting_row(
                            self._["only_notify_no_record"],
                            ft.Switch(
                                value=self.get_config_value("only_notify_no_record"),
                                data="only_notify_no_record",
                                on_change=self.on_change,
                            ),
                        ),
                        self.create_setting_row(
                            self._["notify_loop_time"],
                            ft.TextField(
                                value=self.get_config_value("notify_loop_time"),
                                width=300,
                                data="notify_loop_time",
                                on_change=self.on_change,
                            ),
                        ),
                    ],
                ),
                self.create_setting_group(
                    self._["custom_push_settings"],
                    self._["personalized_notification_content_behavior"],
                    [
                        self.create_setting_row(
                            self._["custom_push_title"],
                            ft.TextField(
                                value=self.get_config_value("custom_notification_title"),
                                width=300,
                                data="custom_notification_title",
                                on_change=self.on_change,
                            ),
                        ),
                        self.create_setting_row(
                            self._["custom_open_broadcast_content"],
                            ft.TextField(
                                value=self.get_config_value("custom_stream_start_content"),
                                width=300,
                                data="custom_stream_start_content",
                                on_change=self.on_change,
                            ),
                        ),
                        self.create_setting_row(
                            self._["custom_close_broadcast_content"],
                            ft.TextField(
                                value=self.get_config_value("custom_stream_end_content"),
                                width=300,
                                data="custom_stream_end_content",
                                on_change=self.on_change,
                            ),
                        ),
                    ],
                ),
                self.create_setting_group(
                    self._["push_channels"],
                    self._["select_and_enable_channels"],
                    [self.create_push_channels_layout()]
                ),
                self.create_setting_group(
                    self._["channel_configuration"],
                    self._["configure_enabled_channels"],
                    [
                        self.create_channel_config(
                            self._["dingtalk"],
                            [
                                self.create_setting_row(
                                    self._["dingtalk_webhook_url"],
                                    ft.TextField(
                                        value=self.get_config_value("dingtalk_webhook_url"),
                                        hint_text=self._["dingtalk_webhook_hint"],
                                        width=300,
                                        on_change=self.on_change,
                                        data="dingtalk_webhook_url",
                                    ),
                                ),
                                self.create_setting_row(
                                    self._["dingtalk_at_objects"],
                                    ft.TextField(
                                        value=self.get_config_value("dingtalk_at_objects"),
                                        hint_text=self._["dingtalk_phone_numbers_hint"],
                                        width=300,
                                        on_change=self.on_change,
                                        data="dingtalk_at_objects",
                                    ),
                                ),
                                self.create_setting_row(
                                    self._["dingtalk_at_all"],
                                    ft.Switch(
                                        value=self.get_config_value("dingtalk_at_all"),
                                        on_change=self.on_change,
                                        data="dingtalk_at_all",
                                    ),
                                ),
                            ],
                        ),
                        self.create_channel_config(
                            self._["wechat"],
                            [
                                self.create_setting_row(
                                    self._["wechat_webhook_url"],
                                    ft.TextField(
                                        value=self.get_config_value("wechat_webhook_url"),
                                        width=300,
                                        on_change=self.on_change,
                                        data="wechat_webhook_url",
                                    ),
                                ),
                            ],
                        ),
                        self.create_channel_config(
                            "Bark",
                            [
                                self.create_setting_row(
                                    self._["bark_webhook_url"],
                                    ft.TextField(
                                        value=self.get_config_value("bark_webhook_url"),
                                        width=300,
                                        on_change=self.on_change,
                                        data="bark_webhook_url",
                                    ),
                                ),
                                self.create_setting_row(
                                    self._["bark_interrupt_level"],
                                    ft.Dropdown(
                                        options=[ft.dropdown.Option("active"), ft.dropdown.Option("passive")],
                                        value=self.get_config_value("bark_interrupt_level"),
                                        width=200,
                                        on_change=self.on_change,
                                        data="bark_interrupt_level",
                                    ),
                                ),
                                self.create_setting_row(
                                    self._["bark_sound"],
                                    ft.TextField(
                                        width=300,
                                        on_change=self.on_change,
                                        data="bark_sound",
                                        value=self.get_config_value("bark_sound"),
                                    ),
                                ),
                            ],
                        ),
                        self.create_channel_config(
                            "Ntfy",
                            [
                                self.create_setting_row(
                                    self._["ntfy_server_url"],
                                    ft.TextField(
                                        value=self.get_config_value("ntfy_server_url"),
                                        width=300,
                                        on_change=self.on_change,
                                        data="ntfy_server_url",
                                    ),
                                ),
                                self.create_setting_row(
                                    self._["ntfy_tags"],
                                    ft.TextField(
                                        value=self.get_config_value("ntfy_tags"),
                                        width=300,
                                        on_change=self.on_change,
                                        data="ntfy_tags",
                                    ),
                                ),
                                self.create_setting_row(
                                    self._["ntfy_email"],
                                    ft.TextField(
                                        value=self.get_config_value("ntfy_email"),
                                        width=300,
                                        on_change=self.on_change,
                                        data="ntfy_email",
                                    ),
                                ),
                                self.create_setting_row(
                                    self._["ntfy_action_url"],
                                    ft.TextField(
                                        value=self.get_config_value("ntfy_action_url"),
                                        width=300,
                                        on_change=self.on_change,
                                        data="ntfy_action_url",
                                    ),
                                ),
                            ],
                        ),
                        self.create_channel_config(
                            "Telegram",
                            [
                                self.create_setting_row(
                                    self._["telegram_api_token"],
                                    ft.TextField(
                                        value=self.get_config_value("telegram_api_token"),
                                        width=300,
                                        on_change=self.on_change,
                                        data="telegram_api_token",
                                    ),
                                ),
                                self.create_setting_row(
                                    self._["telegram_chat_id"],
                                    ft.TextField(
                                        value=self.get_config_value("telegram_chat_id"),
                                        width=300,
                                        on_change=self.on_change,
                                        data="telegram_chat_id",
                                    ),
                                ),
                            ],
                        ),
                        self.create_channel_config(
                            "Email",
                            [
                                self.create_setting_row(
                                    self._["smtp_server"],
                                    ft.TextField(
                                        value=self.get_config_value("smtp_server"),
                                        width=300,
                                        on_change=self.on_change,
                                        data="smtp_server",
                                    ),
                                ),
                                self.create_setting_row(
                                    self._["email_username"],
                                    ft.TextField(
                                        value=self.get_config_value("email_username"),
                                        width=300,
                                        on_change=self.on_change,
                                        data="email_username",
                                    ),
                                ),
                                self.create_setting_row(
                                    self._["email_password"],
                                    ft.TextField(
                                        value=self.get_config_value("email_password"),
                                        width=300,
                                        on_change=self.on_change,
                                        data="email_password",
                                    ),
                                ),
                                self.create_setting_row(
                                    self._["sender_email"],
                                    ft.TextField(
                                        value=self.get_config_value("sender_email"),
                                        width=300,
                                        on_change=self.on_change,
                                        data="sender_email",
                                    ),
                                ),
                                self.create_setting_row(
                                    self._["sender_name"],
                                    ft.TextField(
                                        value=self.get_config_value("sender_name"),
                                        width=300,
                                        on_change=self.on_change,
                                        data="sender_name",
                                    ),
                                ),
                                self.create_setting_row(
                                    self._["recipient_email"],
                                    ft.TextField(
                                        value=self.get_config_value("recipient_email"),
                                        width=300,
                                        on_change=self.on_change,
                                        data="recipient_email",
                                    ),
                                ),
                            ],
                        ),
                    ],
                ),
            ],
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
        )

    def create_push_channels_layout(self):
        controls = [
            self.create_channel_switch_container(
                "DingTalk", ft.Icons.BUSINESS_CENTER, "dingtalk_enabled"
            ),
            self.create_channel_switch_container(
                "WeChat", ft.Icons.WECHAT, "wechat_enabled"
            ),
            self.create_channel_switch_container(
                "ServerChan", ft.Icons.CLOUD_OUTLINED, "serverchan_enabled"
            ),
            self.create_channel_switch_container(
                "Email", ft.Icons.EMAIL, "email_enabled"
            ),
            self.create_channel_switch_container(
                "Bark", ft.Icons.NOTIFICATIONS_ACTIVE, "bark_enabled"
            ),
            self.create_channel_switch_container(
                "Ntfy", ft.Icons.NOTIFICATIONS, "ntfy_enabled"
            ),
            self.create_channel_switch_container(
                "Telegram", ft.Icons.SMS, "telegram_enabled"
            ),
        ]
        
        if self.app.page.web:
            return ft.Row(
                controls=controls,
                alignment=ft.MainAxisAlignment.START,
                spacing=8,
            )
        else:
            return ft.Container(
                content=ft.GridView(
                    controls=controls,
                    runs_count=3,
                    max_extent=180,
                    spacing=8,
                    run_spacing=8,
                    child_aspect_ratio=3.0,
                ),
                expand=True,
            )
                
    def create_cookies_settings_tab(self):
        """Create UI elements for push configuration."""
        platforms = [
            "douyin",
            "tiktok",
            "kuaishou",
            "huya",
            "douyu",
            "yy",
            "bilibili",
            "xhs",
            "bigo",
            "blued",
            "soop",
            "netease",
            "qiandurebo",
            "pandalive",
            "maoerfm",
            "winktv",
            "flextv",
            "look",
            "popkontv",
            "twitcasting",
            "baidu",
            "weibo",
            "kugou",
            "twitch",
            "liveme",
            "huajiao",
            "liuxing",
            "showroom",
            "acfun",
            "changliao",
            "yinbo",
            "inke",
            "zhihu",
            "chzzk",
            "haixiu",
            "vvxq",
            "17live",
            "lang",
            "piaopiao",
            "6room",
            "lehai",
            "catshow",
            "shopee",
            "youtube",
            "taobao",
            "jd",
        ]

        setting_rows = []
        for platform in platforms:
            cookie_field = ft.TextField(
                value=self.get_cookies_value(platform), width=500, data=platform, on_change=self.on_cookies_change
            )
            setting_rows.append(self.create_setting_row(self._[f"{platform}_cookie"], cookie_field))

        return ft.Column(
            [
                self.create_setting_group(
                    self._["cookies_settings"], self._["configure_platform_cookies"], setting_rows
                ),
            ],
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
        )

    def create_accounts_settings_tab(self):
        """Create UI elements for platform accounts configuration."""
        return ft.Column(
            [
                self.create_setting_group(
                    self._["accounts_settings"],
                    self._["configure_platform_accounts"],
                    [
                        self.create_setting_row(
                            self._["sooplive_username"],
                            ft.TextField(
                                value=self.get_accounts_value("sooplive_username"),
                                width=500,
                                data="sooplive_username",
                                on_change=self.on_accounts_change,
                            ),
                        ),
                        self.create_setting_row(
                            self._["sooplive_password"],
                            ft.TextField(
                                value=self.get_accounts_value("sooplive_password"),
                                width=500,
                                data="sooplive_password",
                                on_change=self.on_accounts_change,
                            ),
                        ),
                        self.create_setting_row(
                            self._["flextv_username"],
                            ft.TextField(
                                value=self.get_accounts_value("flextv_username"),
                                width=500,
                                data="flextv_username",
                                on_change=self.on_accounts_change,
                            ),
                        ),
                        self.create_setting_row(
                            self._["flextv_password"],
                            ft.TextField(
                                value=self.get_accounts_value("flextv_password"),
                                width=500,
                                data="flextv_password",
                                on_change=self.on_accounts_change,
                            ),
                        ),
                        self.create_setting_row(
                            self._["popkontv_username"],
                            ft.TextField(
                                value=self.get_accounts_value("popkontv_username"),
                                width=500,
                                data="popkontv_username",
                                on_change=self.on_accounts_change,
                            ),
                        ),
                        self.create_setting_row(
                            self._["popkontv_password"],
                            ft.TextField(
                                value=self.get_accounts_value("popkontv_password"),
                                width=500,
                                data="popkontv_password",
                                on_change=self.on_accounts_change,
                            ),
                        ),
                        self.create_setting_row(
                            self._["twitcasting_account_type"],
                            ft.Dropdown(
                                options=[ft.dropdown.Option("Default"), ft.dropdown.Option("Twitter")],
                                value=self.get_accounts_value("twitcasting_account_type", "Default"),
                                width=500,
                                data="twitcasting_account_type",
                                on_change=self.on_accounts_change,
                                tooltip=self._["switch_account_type"],
                            ),
                        ),
                        self.create_setting_row(
                            self._["twitcasting_username"],
                            ft.TextField(
                                value=self.get_accounts_value("twitcasting_username"),
                                width=500,
                                data="twitcasting_username",
                                on_change=self.on_accounts_change,
                            ),
                        ),
                        self.create_setting_row(
                            self._["twitcasting_password"],
                            ft.TextField(
                                value=self.get_accounts_value("twitcasting_password"),
                                width=500,
                                data="twitcasting_password",
                                on_change=self.on_accounts_change,
                            ),
                        ),
                    ],
                ),
            ],
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
        )

    def create_folder_setting_row(self, label):
        return ft.Row(
            [
                ft.Text(label, width=200, text_align=ft.TextAlign.RIGHT),
                ft.Checkbox(
                    label=self._["platform"],
                    value=self.get_config_value("folder_name_platform"),
                    on_change=self.on_change,
                    data="folder_name_platform",
                ),
                ft.Checkbox(
                    label=self._["author"],
                    value=self.get_config_value("folder_name_author"),
                    on_change=self.on_change,
                    data="folder_name_author",
                ),
                ft.Checkbox(
                    label=self._["time"],
                    value=self.get_config_value("folder_name_time"),
                    on_change=self.on_change,
                    data="folder_name_time",
                ),
                ft.Checkbox(
                    label=self._["title"],
                    value=self.get_config_value("folder_name_title"),
                    on_change=self.on_change,
                    data="folder_name_title",
                ),
            ],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def create_channel_switch_container(self, channel_name, icon, key):
        """Helper method to create a container with a switch and an icon for each channel."""
        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icon, size=20, color=ft.Colors.GREY_700),
                    ft.Container(width=2),
                    ft.Text(channel_name, size=13, no_wrap=True),
                    ft.Container(expand=True),
                    ft.Switch(
                        value=self.get_config_value(key), 
                        label="", 
                        width=40,
                        scale=0.8,
                        on_change=self.on_change, 
                        data=key
                    ),
                ],
                spacing=2,
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                tight=True,
            ),
            padding=ft.padding.only(left=6, right=6, top=5, bottom=5),
            margin=3,
            border_radius=6,
            bgcolor=ft.colors.with_opacity(0.03, ft.colors.ON_SURFACE),
        )

    @staticmethod
    def create_channel_config(channel_name, settings):
        """Helper method to create expandable configurations for each channel."""
        return ft.ExpansionTile(
            initially_expanded=False,
            title=ft.Text(channel_name, size=14, weight=ft.FontWeight.BOLD),
            controls=[ft.Container(content=ft.Column(settings, spacing=5), padding=10)],
            tile_padding=0,
        )

    @staticmethod
    def create_setting_group(title, description, settings):
        """Helper method to group settings under a title."""
        return ft.Card(
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text(title, size=16, weight=ft.FontWeight.BOLD),
                        ft.Text(description, theme_style=ft.TextThemeStyle.BODY_MEDIUM, opacity=0.7),
                        *settings,
                    ],
                    spacing=5,
                ),
                padding=10,
            ),
            elevation=5,
            margin=10,
        )

    def set_focused_control(self, control):
        """Store the currently focused control."""
        self.focused_control = control

    def create_setting_row(self, label, control):
        """Helper method to create a row for each setting."""
        if hasattr(control, 'on_focus'):
            control.on_focus = lambda e: self.set_focused_control(e.control)
        return ft.Row(
            [ft.Text(label, width=200, text_align=ft.TextAlign.RIGHT), control],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def pick_folder(self, label, control):
        def picked_folder(e: ft.FilePickerResultEvent):
            path = e.path
            if path:
                control.value = path
                control.update()
                e.control.data = control.data
                e.data = path
                self.page.run_task(self.on_change, e)

        async def pick_folder(_):
            if self.app.page.web:
                await self.app.snack_bar.show_snack_bar(self._["unsupported_select_path"])
            folder_picker.get_directory_path()

        folder_picker = ft.FilePicker(on_result=picked_folder)
        self.page.overlay.append(folder_picker)
        self.page.update()

        btn_pick_folder = ft.ElevatedButton(
            text=self._["select"], icon=ft.Icons.FOLDER_OPEN, on_click=pick_folder, tooltip=self._["select_btn_tip"]
        )
        return ft.Row(
            [ft.Text(label, width=200, text_align=ft.TextAlign.RIGHT), control, btn_pick_folder],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    async def is_changed(self):
        if self.app.current_page != self:
            return

        show_snack_bar = False
        save_methods = {
            "user_config": (self.config_manager.save_user_config, self.user_config),
            "cookies_config": (self.config_manager.save_cookies_config, self.cookies_config),
            "accounts_config": (self.config_manager.save_accounts_config, self.accounts_config)
        }

        for config_key, should_save in self.has_unsaved_changes.items():
            if should_save and config_key in save_methods:
                save_method, config_value = save_methods[config_key]
                await save_method(config_value)
                self.has_unsaved_changes[config_key] = False
                show_snack_bar = True

        if show_snack_bar:
            await self.app.snack_bar.show_snack_bar(
                self._["success_save_config_tip"], duration=1500, bgcolor=ft.Colors.GREEN
            )

    async def on_keyboard(self, e: ft.KeyboardEvent):
        if e.alt and e.key == "H":
            self.app.dialog_area.content = HelpDialog(self.app)
            self.app.dialog_area.content.open = True
            self.app.dialog_area.update()

        if self.app.current_page == self and e.ctrl and e.key == "S":
            self.page.run_task(self.is_changed)

    def create_security_settings_tab(self):
        
        async def change_password(_):
            old_password = old_password_field.value
            new_password = new_password_field.value
            confirm_password = confirm_password_field.value
            
            if not old_password:
                await self.app.snack_bar.show_snack_bar(self._["old_password_required"], bgcolor=ft.Colors.RED)
                return
                
            if not new_password:
                await self.app.snack_bar.show_snack_bar(self._["new_password_required"], bgcolor=ft.Colors.RED)
                return
                
            if new_password != confirm_password:
                await self.app.snack_bar.show_snack_bar(self._["passwords_not_match"], bgcolor=ft.Colors.RED)
                return
                
            _username = self.app.current_username
            if _username:
                success = await self.app.auth_manager.change_password(_username, old_password, new_password)
                
                if success:
                    old_password_field.value = ""
                    new_password_field.value = ""
                    confirm_password_field.value = ""
                    old_password_field.update()
                    new_password_field.update()
                    confirm_password_field.update()
                    
                    await self.app.snack_bar.show_snack_bar(self._["password_changed"], bgcolor=ft.Colors.GREEN)
                else:
                    await self.app.snack_bar.show_snack_bar(self._["old_password_incorrect"], bgcolor=ft.Colors.RED)
            else:
                await self.app.snack_bar.show_snack_bar(self._["not_logged_in"], bgcolor=ft.Colors.RED)
        
        username = self.app.current_username or "admin"
        
        old_password_field = ft.TextField(
            password=True,
            width=300,
            label=self._["old_password"],
        )
        
        new_password_field = ft.TextField(
            password=True,
            width=300,
            label=self._["new_password"],
        )
        
        confirm_password_field = ft.TextField(
            password=True,
            width=300,
            label=self._["confirm_password"],
        )
        
        change_password_button = ft.ElevatedButton(
            text=self._["change_password"],
            on_click=change_password,
            icon=ft.icons.LOCK_RESET,
        )
        
        return ft.Column(
            [
                self.create_setting_group(
                    self._["security_settings"],
                    self._["web_login_configuration"],
                    [
                        self.create_setting_row(
                            self._["current_username"],
                            ft.Text(username),
                        ),
                        self.create_setting_row(
                            self._["old_password"],
                            old_password_field,
                        ),
                        self.create_setting_row(
                            self._["new_password"],
                            new_password_field,
                        ),
                        self.create_setting_row(
                            self._["confirm_password"],
                            confirm_password_field,
                        ),
                        self.create_setting_row(
                            "",
                            change_password_button,
                        ),
                    ],
                ),
            ],
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
        )
