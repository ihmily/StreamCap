import asyncio
import os
import re
from collections import deque

import flet as ft

from ...utils.logger import logger
from ..base_page import PageBase as BasePage


class LogsPage(BasePage):
    RECORDING_KEYWORDS = (
        "recording",
        "record",
        "ffmpeg",
        "direct download",
        "stream",
        "录制",
        "直播",
        "转码",
    )
    TRANSLATION_PATTERNS = (
        (re.compile(r"Live Recordings: Loaded (\d+) items"), "已加载 {0} 个录制任务", "Loaded {0} recording rooms"),
        (re.compile(r"Live Recordings: Migrated (\d+) items from recordings\.json"), "已从旧配置迁移 {0} 个录制任务", "Migrated {0} recording rooms from recordings.json"),
        (re.compile(r"Started recording for (.+)"), "开始录制：{0}", "Started recording: {0}"),
        (re.compile(r"Stopped recording for (.+)"), "录制已停止：{0}", "Stopped recording: {0}"),
        (re.compile(r"Stop requested for recorder: (.+), rec_id: (.+)"), "请求停止录制：{0}（ID：{1}）", "Stop requested: {0} (ID: {1})"),
        (re.compile(r"Requested stop for recorder: (.+)"), "已发送停止录制请求：{0}", "Requested recording stop: {0}"),
        (re.compile(r"No active recorder found for (.+), cannot request stop"), "未找到正在录制的任务，无法停止：{0}", "No active recorder found: {0}"),
        (re.compile(r"Batch Start Monitor Recordings: (.+)"), "批量开始监控：{0}", "Batch started monitoring: {0}"),
        (re.compile(r"Batch Stop Monitor Recordings:?(.+)"), "批量停止监控：{0}", "Batch stopped monitoring: {0}"),
        (re.compile(r"Delete Items: (.+)"), "删除录制任务：{0}", "Deleted recording room: {0}"),
        (re.compile(r"Add items recording: (.+)"), "新增录制任务：{0}", "Added recording room: {0}"),
        (re.compile(r"Starting periodic live check background task"), "开始后台直播检测任务", "Started background live check task"),
        (re.compile(r"Initializing periodic live check task with interval: (.+)s"), "初始化后台直播检测，间隔 {0} 秒", "Initialized live check interval: {0}s"),
        (re.compile(r"Saved last route: (.+)"), "已保存上次打开页面：{0}", "Saved last page: {0}"),
        (re.compile(r"Restored last route: (.+)"), "已恢复上次打开页面：{0}", "Restored last page: {0}"),
        (re.compile(r"Language Code: (.+)"), "已加载语言：{0}", "Loaded language: {0}"),
        (re.compile(r"desktop device detected, enable desktop layout"), "已启用桌面端布局", "Desktop layout enabled"),
        (re.compile(r"mobile device detected, enable mobile layout"), "已启用移动端布局", "Mobile layout enabled"),
        (re.compile(r"Logs page refreshed: runtime=(\d+), start=(\d+), stop=(\d+)"), "日志页已刷新：运行 {0} 条，开始 {1} 条，停止 {2} 条", "Logs refreshed: runtime {0}, start {1}, stop {2}"),
    )

    def __init__(self, app):
        super().__init__(app)
        self.page_name = "logs"
        self.recording_log_list = None
        self.history_list = None
        self.summary_text = None
        self.app.language_manager.add_observer(self)
        self.load_language()

    def load_language(self):
        language = self.app.language_manager.language
        for key in ("logs_page", "recording_card", "base"):
            self._.update(language.get(key, {}))

    async def load(self):
        self.load_language()
        self.recording_log_list = ft.ListView(expand=True, spacing=8, padding=0)
        self.history_list = ft.ListView(expand=True, spacing=10, padding=0)
        self.summary_text = ft.Text("", size=13, color=ft.Colors.GREY_600)

        tabs = ft.Tabs(
            content=ft.Column(
                [
                    ft.TabBar(
                        tabs=[
                            ft.Tab(label=self._["recording_logs"]),
                            ft.Tab(label=self._["recording_history"]),
                        ]
                    ),
                    ft.TabBarView(
                        controls=[
                            self.create_tab_content(
                                self._["recording_logs"],
                                self._["clear_recording_logs"],
                                self.recording_log_list,
                                self.confirm_clear_recording_logs,
                            ),
                            self.create_history_tab_content(),
                        ],
                        expand=True,
                    ),
                ],
                expand=True,
            ),
            length=2,
            selected_index=0,
            animation_duration=200,
            expand=True,
        )

        self.content_area.controls = [
            ft.Container(
                expand=True,
                padding=20,
                content=ft.Column(
                    expand=True,
                    spacing=14,
                    controls=[
                        self.create_header(),
                        self.summary_text,
                        ft.Divider(height=1),
                        tabs,
                    ],
                ),
            )
        ]
        self.content_area.update()
        await self.refresh_logs()

    def create_header(self):
        return ft.Row(
            controls=[
                ft.Text(self._["title"], size=20, weight=ft.FontWeight.BOLD, expand=True),
                ft.IconButton(
                    icon=ft.Icons.REFRESH,
                    icon_color=ft.Colors.PRIMARY,
                    tooltip=self._["refresh"],
                    on_click=lambda e: self.page.run_task(self.refresh_logs),
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def create_tab_content(self, title: str, clear_tooltip: str, list_control, clear_handler):
        return ft.Column(
            expand=True,
            spacing=8,
            controls=[
                ft.Row(
                    controls=[
                        ft.Text(title, size=14, weight=ft.FontWeight.BOLD, expand=True),
                        ft.Button(
                            clear_tooltip,
                            icon=ft.Icons.DELETE_SWEEP,
                            on_click=lambda e: self.page.run_task(clear_handler),
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                list_control,
            ],
        )

    def create_history_tab_content(self):
        return ft.Column(
            expand=True,
            spacing=8,
            controls=[
                ft.Row(
                    controls=[
                        ft.Text(self._["recording_history"], size=14, weight=ft.FontWeight.BOLD, expand=True),
                        ft.Button(
                            self._["clear_recording_history"],
                            icon=ft.Icons.DELETE_SWEEP,
                            on_click=lambda e: self.page.run_task(self.confirm_clear_recording_history),
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                self.history_list,
            ],
        )

    async def refresh_logs(self, *_):
        recording_lines = self.read_text_logs()
        history_items = self.app.record_manager.get_recent_recording_history(limit=100)
        history_events = self.build_history_events(history_items)
        start_count = sum(1 for event in history_events if event["type"] == "start")
        stop_count = sum(1 for event in history_events if event["type"] == "stop")

        self.fill_text_log_list(self.recording_log_list, recording_lines, self._["empty_recording_logs"])
        self.fill_history_list(history_events)

        logger.debug(
            "Logs page refreshed: "
            f"runtime={len(recording_lines)}, start={start_count}, stop={stop_count}"
        )

        self.summary_text.value = (
            self._["summary"]
            .replace("{recording_count}", str(len(recording_lines)))
            .replace("{start_count}", str(start_count))
            .replace("{stop_count}", str(stop_count))
        )

        try:
            self.recording_log_list.update()
            self.history_list.update()
            self.summary_text.update()
        except (ft.FletPageDisconnectedException, AssertionError):
            pass

    def read_text_logs(self) -> list[str]:
        log_path = os.path.join(self.app.run_path, "logs", "streamget.log")
        if not os.path.exists(log_path):
            return []

        try:
            with open(log_path, encoding="utf-8", errors="replace") as file:
                recent_lines = list(deque((line.strip() for line in file if line.strip()), maxlen=1200))
        except OSError:
            return []

        return self.filter_lines(recent_lines, self.RECORDING_KEYWORDS, limit=100)

    @staticmethod
    def filter_lines(lines: list[str], keywords: tuple[str, ...], limit: int) -> list[str]:
        lowered_keywords = tuple(keyword.lower() for keyword in keywords)
        matched = [line for line in lines if any(keyword in line.lower() for keyword in lowered_keywords)]
        return matched[-limit:][::-1]

    def fill_text_log_list(self, target_list, lines: list[str], empty_text: str):
        target_list.controls.clear()
        if not lines:
            target_list.controls.append(self.create_empty_state(empty_text, ft.Icons.NOTES))
            return

        for line in lines:
            target_list.controls.append(self.create_text_log_item(line))

    @staticmethod
    def build_history_events(history_items: list[dict]) -> list[dict]:
        events = []
        started_keys = {
            (item.get("rec_id"), item.get("started_at"))
            for item in history_items
            if item.get("status") == "started" and item.get("started_at")
        }
        for item in history_items:
            status = item.get("status")
            started_at = item.get("started_at")
            stopped_at = item.get("ended_at") if status != "started" else None
            started_key = (item.get("rec_id"), started_at)
            if started_at and (status == "started" or started_key not in started_keys):
                events.append({"type": "start", "time": started_at, "item": item})
            if stopped_at:
                events.append({"type": "stop", "time": stopped_at, "item": item})
        return sorted(events, key=lambda event: event["time"] or "", reverse=True)

    def fill_history_list(self, history_events: list[dict]):
        self.history_list.controls.clear()
        if not history_events:
            self.history_list.controls.append(self.create_empty_state(self._["empty_history"], ft.Icons.HISTORY))
            return

        for event in history_events:
            self.history_list.controls.append(self.create_history_event_item(event))

    def create_empty_state(self, text: str, icon):
        return ft.Container(
            padding=20,
            content=ft.Row(
                controls=[
                    ft.Icon(icon, color=ft.Colors.GREY_500),
                    ft.Text(text, size=14, color=ft.Colors.GREY_600),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
        )

    def create_text_log_item(self, line: str):
        level, color = self.get_log_level(line)
        display_line, raw_message = self.format_log_line(line)
        message_controls = [ft.Text(display_line, size=12, selectable=True, expand=True)]
        if raw_message and raw_message != display_line:
            message_controls.append(ft.Text(raw_message, size=11, color=ft.Colors.GREY_500, selectable=True))

        return ft.Container(
            padding=10,
            border=ft.Border.all(1, ft.Colors.GREY_300),
            border_radius=6,
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Text(self._.get(f"log_level_{level.lower()}", level), size=11, color=ft.Colors.WHITE),
                        bgcolor=color,
                        border_radius=5,
                        padding=ft.Padding.symmetric(horizontal=7, vertical=3),
                    ),
                    ft.Column(
                        expand=True,
                        tight=True,
                        spacing=4,
                        controls=message_controls,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
        )

    def create_history_event_item(self, event: dict):
        item = event["item"]
        event_type = event["type"]
        status = item.get("status") or self._["none"]
        status_text = self._.get(f"history_status_{status}", status)
        event_color = ft.Colors.GREEN if event_type == "start" else ft.Colors.RED
        event_time = event.get("time") or self._["none"]
        duration = self.format_duration(item.get("duration_seconds"))
        streamer_name = item.get("streamer_name") or self._["unknown_room"]
        platform = item.get("platform") or item.get("platform_key") or self._["none"]
        file_path = item.get("file_path") or self._["none"]
        file_name = os.path.basename(file_path) if file_path and file_path != self._["none"] else file_path
        error_message = item.get("error_message")
        live_title = item.get("live_title")
        event_text = self._["history_start_recording"] if event_type == "start" else self._["history_stop_recording"]
        event_icon = ft.Icons.PLAY_CIRCLE if event_type == "start" else ft.Icons.STOP_CIRCLE

        event_chip = ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            border=ft.Border.all(1, event_color),
            border_radius=6,
            content=ft.Row(
                tight=True,
                spacing=5,
                controls=[
                    ft.Icon(event_icon, size=15, color=event_color),
                    ft.Text(event_text, size=12, color=event_color, weight=ft.FontWeight.BOLD),
                ],
            ),
        )

        title_row = ft.Row(
            spacing=10,
            controls=[
                event_chip,
                ft.Text(streamer_name, size=14, weight=ft.FontWeight.BOLD, expand=True),
                ft.Text(event_time, size=12, color=ft.Colors.GREY_600),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        meta_controls = [
            ft.Text(platform, size=12, color=ft.Colors.GREY_600),
        ]
        if event_type == "stop":
            meta_controls.extend(
                [
                    ft.Text(f"{self._['duration']}: {duration}", size=12, color=ft.Colors.GREY_700),
                ]
            )
        details = [
            title_row,
            ft.Row(wrap=True, spacing=12, run_spacing=4, controls=meta_controls),
        ]
        if event_type == "stop":
            details.append(ft.Text(f"{self._['file']}: {file_name}", size=12, selectable=True))
        if live_title:
            details.append(ft.Text(f"{self._['live_title']}: {live_title}", size=12, selectable=True))
        if error_message:
            details.append(ft.Text(f"{self._['error']}: {error_message}", size=12, color=ft.Colors.RED))

        return ft.Container(
            height=96,
            padding=12,
            border=ft.Border.all(1, ft.Colors.GREY_300),
            border_radius=6,
            content=ft.Column(tight=True, spacing=7, controls=details),
        )

    @staticmethod
    def get_log_level(line: str):
        if "ERROR" in line:
            return "ERROR", ft.Colors.RED
        if "WARNING" in line:
            return "WARN", ft.Colors.AMBER
        if "SUCCESS" in line:
            return "OK", ft.Colors.GREEN
        if "STREAM" in line:
            return "STREAM", ft.Colors.BLUE
        return "INFO", ft.Colors.GREY

    @staticmethod
    def get_status_color(status: str):
        status_map = {
            "completed": ft.Colors.GREEN,
            "stopped": ft.Colors.BLUE,
            "error": ft.Colors.RED,
        }
        return status_map.get(status, ft.Colors.GREY)

    def format_duration(self, seconds):
        if seconds is None:
            return self._["none"]
        seconds = int(seconds)
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def format_log_line(self, line: str) -> tuple[str, str | None]:
        parsed = self.parse_log_line(line)
        if not parsed:
            return self.translate_log_message(line), None

        timestamp, level, source, message = parsed
        translated = self.translate_log_message(message)
        display = f"{timestamp} · {translated}"
        raw_message = None if translated == message else f"{self._['raw_log']}: {message}"
        return display, raw_message

    @staticmethod
    def parse_log_line(line: str) -> tuple[str, str, str, str] | None:
        parts = line.split(" | ", 2)
        if len(parts) != 3:
            return None
        timestamp, level, rest = parts
        if " - " not in rest:
            return None
        source, message = rest.split(" - ", 1)
        return timestamp.strip(), level.strip(), source.strip(), message.strip()

    def translate_log_message(self, message: str) -> str:
        if self.get_language_code() != "zh_CN":
            return self.translate_log_message_en(message)

        for pattern, zh_template, _ in self.TRANSLATION_PATTERNS:
            match = pattern.search(message)
            if match:
                return zh_template.format(*match.groups())
        if self.has_cjk(message):
            return message
        return message

    def get_language_code(self) -> str:
        settings = getattr(self.app, "settings", None)
        return getattr(settings, "language_code", "zh_CN") or "zh_CN"

    def translate_log_message_en(self, message: str) -> str:
        for pattern, _, en_template in self.TRANSLATION_PATTERNS:
            match = pattern.search(message)
            if match:
                return en_template.format(*match.groups())
        return message

    @staticmethod
    def has_cjk(text: str) -> bool:
        return any("\u4e00" <= char <= "\u9fff" for char in text)

    async def confirm_clear_recording_logs(self, *_):
        await self.show_confirm_dialog(
            self._["clear_recording_logs"],
            self._["clear_recording_logs_confirm"],
            lambda: self.clear_text_logs(self.RECORDING_KEYWORDS, self._["clear_recording_logs_success"]),
        )

    async def confirm_clear_recording_history(self, *_):
        await self.show_confirm_dialog(
            self._["clear_recording_history"],
            self._["clear_recording_history_confirm"],
            self.clear_recording_history,
        )

    async def show_confirm_dialog(self, title: str, message: str, confirm_action):
        async def close_dialog(_=None):
            try:
                dialog.open = False
                dialog.update()
            except (ft.FletPageDisconnectedException, AssertionError) as e:
                logger.debug(f"Close logs confirm dialog failed: {e}")

            await asyncio.sleep(0.05)
            try:
                if self.app.dialog_area.content is dialog:
                    self.app.dialog_area.content = None
                self.app.page.update()
            except (ft.FletPageDisconnectedException, AssertionError) as e:
                logger.debug(f"Clear logs confirm dialog failed: {e}")

        async def confirm_dlg(_):
            await close_dialog()
            await confirm_action()

        dialog = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[
                ft.TextButton(self._["cancel"], on_click=close_dialog),
                ft.TextButton(self._["sure"], on_click=confirm_dlg),
            ],
            modal=True,
        )
        self.app.dialog_area.content = dialog
        dialog.open = True
        self.app.page.update()

    async def clear_text_logs(self, keywords: tuple[str, ...], success_template: str):
        removed_count = await asyncio.to_thread(self.remove_text_log_lines, keywords)
        await self.app.snack_bar.show_snack_bar(success_template.replace("{count}", str(removed_count)))
        await self.refresh_logs()

    def remove_text_log_lines(self, keywords: tuple[str, ...]) -> int:
        log_path = os.path.join(self.app.run_path, "logs", "streamget.log")
        if not os.path.exists(log_path):
            return 0

        lowered_keywords = tuple(keyword.lower() for keyword in keywords)
        try:
            with open(log_path, encoding="utf-8", errors="replace") as file:
                lines = file.readlines()
            kept_lines = [line for line in lines if not any(keyword in line.lower() for keyword in lowered_keywords)]
            removed_count = len(lines) - len(kept_lines)
            with open(log_path, "w", encoding="utf-8", errors="replace") as file:
                file.writelines(kept_lines)
            return removed_count
        except OSError as e:
            logger.error(f"Clear text logs failed: {e}")
            return 0

    async def clear_recording_history(self):
        removed_count = await self.app.record_manager.clear_recording_history()
        await self.app.snack_bar.show_snack_bar(
            self._["clear_recording_history_success"].replace("{count}", str(removed_count))
        )
        await self.refresh_logs()
