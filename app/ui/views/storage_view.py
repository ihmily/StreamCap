import asyncio
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor

import flet as ft
from dotenv import find_dotenv, load_dotenv

from ...utils.logger import logger
from ..base_page import PageBase as BasePage

dotenv_path = find_dotenv()
load_dotenv(dotenv_path)
VIDEO_API_EXTERNAL_URL = os.getenv("VIDEO_API_EXTERNAL_URL")
MEDIA_EXTENSIONS = {".mp4", ".ts", ".flv", ".mkv", ".mov", ".avi", ".webm"}


class StoragePage(BasePage):
    def __init__(self, app):
        super().__init__(app)
        self.page_name = "storage"
        self.root_path = None
        self.current_path = None
        self.path_display = None
        self.content = None
        self.file_list = None
        self.summary_area = None
        self.maintenance_area = None
        self.recent_area = None
        self.storage_stats = {}
        self._ = {}
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.load_language()
        self.app.language_manager.add_observer(self)

    async def load(self):
        self.root_path = self.app.settings.get_video_save_path()
        self.current_path = self.root_path
        self.setup_ui()
        await self.refresh_storage()

    def setup_ui(self):
        title_row = ft.Row(
            controls=[
                ft.Text(self._["storage_manage"], size=20, weight=ft.FontWeight.BOLD, expand=True),
                ft.Button(
                    self._["refresh_storage"],
                    icon=ft.Icons.REFRESH,
                    on_click=lambda _: self.app.page.run_task(self.refresh_storage),
                ),
                ft.Button(
                    self._["open_storage_folder"],
                    icon=ft.Icons.FOLDER_OPEN,
                    on_click=lambda _: self.app.page.run_task(self.open_storage_folder),
                ),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self.path_display = ft.Text(
            self._["storage_path"] + ": " + self.current_path,
            size=14,
            color=ft.Colors.GREY_600,
            selectable=True,
        )
        self.summary_area = ft.Row(wrap=True, spacing=8, run_spacing=8)
        self.maintenance_area = ft.Column(spacing=8)
        self.recent_area = ft.ListView(expand=True, spacing=6, padding=0)
        self.file_list = ft.ListView(expand=True, spacing=2, padding=8)
        file_panel_height = 430

        header_panel = ft.Container(
            padding=12,
            border=ft.Border.all(1, ft.Colors.GREY_300),
            border_radius=8,
            content=ft.Column(
                tight=True,
                spacing=8,
                controls=[
                    title_row,
                    self.path_display,
                ],
            ),
        )
        file_panel = self.create_panel(
            self._["file_browser"],
            self.file_list,
            icon=ft.Icons.FOLDER_OPEN,
            height=file_panel_height,
        )
        overview_panel = self.create_panel(
            self._["storage_overview"],
            self.summary_area,
        )
        tools_panel = self.create_panel(self._["clean_tools"], self.maintenance_area, icon=ft.Icons.DELETE_SWEEP)
        recent_panel = self.create_panel(
            self._["recent_recording_files"],
            self.recent_area,
            icon=ft.Icons.VIDEO_FILE,
            height=file_panel_height,
        )
        if getattr(self.app, "is_mobile", False):
            file_area = ft.Column(
                spacing=12,
                controls=[file_panel, recent_panel],
            )
        else:
            file_area = ft.Row(
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.START,
                controls=[
                    ft.Container(content=file_panel, expand=3),
                    ft.Container(content=recent_panel, expand=2),
                ],
            )

        self.content = ft.ListView(
            expand=True,
            spacing=12,
            padding=10,
            controls=[
                header_panel,
                overview_panel,
                tools_panel,
                file_area,
            ],
        )
        self.app.content_area.controls = [self.content]
        self.app.content_area.update()

    def load_language(self):
        language = self.app.language_manager.language
        for key in ("storage_page", "base"):
            self._.update(language.get(key, {}))

    async def refresh_storage(self, *_):
        await self.update_storage_summary()
        await self.update_file_list()

    async def update_storage_summary(self):
        self.storage_stats = await self.scan_storage()
        self.summary_area.controls.clear()
        self.maintenance_area.controls.clear()
        self.recent_area.controls.clear()

        self.summary_area.controls.extend(
            [
                self.create_metric_group(
                    self._["storage_space"],
                    [
                        (self._["recording_size"], self.format_size(self.storage_stats["recording_size"])),
                        (self._["disk_free"], self.format_size(self.storage_stats["disk_free"])),
                    ],
                ),
                self.create_metric_group(
                    self._["recording_files"],
                    [
                        (self._["video_files"], str(self.storage_stats["video_files"])),
                        (self._["original_size"], self.format_size(self.storage_stats["original_size"])),
                    ],
                ),
                self.create_metric_group(
                    self._["app_cleanup"],
                    [
                        (self._["logs_size"], self.format_size(self.storage_stats["logs_size"])),
                        (self._["database_size"], self.format_size(self.storage_stats["database_size"])),
                        (self._["empty_dirs"], str(self.storage_stats["empty_dirs"])),
                    ],
                ),
            ]
        )

        self.update_recent_recordings()

        self.maintenance_area.controls.append(
            ft.Row(
                wrap=True,
                spacing=8,
                run_spacing=8,
                controls=[
                    ft.Button(
                        self._["delete_all_files"],
                        icon=ft.Icons.DELETE_FOREVER,
                        width=150,
                        on_click=lambda _: self.app.page.run_task(self.confirm_delete_all_files),
                    ),
                    ft.Button(
                        self._["clean_empty_dirs"],
                        icon=ft.Icons.FOLDER_DELETE,
                        width=150,
                        on_click=lambda _: self.app.page.run_task(self.confirm_cleanup_empty_dirs),
                    ),
                    ft.Button(
                        self._["clean_logs"],
                        icon=ft.Icons.DELETE_SWEEP,
                        width=150,
                        on_click=lambda _: self.app.page.run_task(self.confirm_cleanup_logs),
                    ),
                ],
            )
        )
        self.maintenance_area.controls.append(
            ft.Text(
                self._["maintenance_tip"]
                .replace("{original_size}", self.format_size(self.storage_stats["original_size"]))
                .replace("{empty_dirs}", str(self.storage_stats["empty_dirs"]))
                .replace("{logs_size}", self.format_size(self.storage_stats["logs_size"])),
                size=12,
                color=ft.Colors.GREY_600,
            )
        )

        try:
            self.summary_area.update()
            self.maintenance_area.update()
            self.recent_area.update()
        except (ft.FletPageDisconnectedException, AssertionError):
            pass

    async def scan_storage(self):
        return await asyncio.get_event_loop().run_in_executor(self.executor, self.scan_storage_sync)

    def scan_storage_sync(self):
        stats = {
            "recording_size": 0,
            "disk_free": 0,
            "video_files": 0,
            "original_size": 0,
            "original_files": 0,
            "empty_dirs": 0,
            "logs_size": self.get_directory_size(os.path.join(self.app.run_path, "log")),
            "database_size": self.get_directory_size(os.path.join(self.app.run_path, "data", "database")),
        }

        root_path = self.root_path or ""
        disk_target = root_path if os.path.exists(root_path) else os.path.dirname(root_path) or self.app.run_path
        try:
            stats["disk_free"] = shutil.disk_usage(disk_target).free
        except OSError:
            stats["disk_free"] = 0

        if not os.path.exists(root_path):
            return stats

        stats["empty_dirs"] = len(self.get_removable_empty_dirs(root_path))

        for file_path in self.iter_files(root_path):
            if not self.is_media_file(file_path):
                continue
            size = self.get_file_size(file_path)
            stats["recording_size"] += size
            stats["video_files"] += 1

            if self.is_original_file(file_path, root_path):
                stats["original_files"] += 1
                stats["original_size"] += size

        return stats

    @staticmethod
    def iter_files(root_path: str):
        for dir_path, _, file_names in os.walk(root_path):
            for file_name in file_names:
                yield os.path.join(dir_path, file_name)

    @staticmethod
    def is_media_file(file_path: str) -> bool:
        return os.path.splitext(file_path)[1].lower() in MEDIA_EXTENSIONS

    def iter_media_files(self, root_path: str | None = None):
        root_path = root_path or self.root_path
        if not root_path or not os.path.exists(root_path):
            return
        for file_path in self.iter_files(root_path):
            if self.is_media_file(file_path):
                yield file_path

    @staticmethod
    def get_file_size(file_path: str) -> int:
        try:
            return os.path.getsize(file_path)
        except OSError:
            return 0

    def get_directory_size(self, dir_path: str) -> int:
        if not os.path.exists(dir_path):
            return 0
        return sum(self.get_file_size(file_path) for file_path in self.iter_files(dir_path))

    @staticmethod
    def get_removable_empty_dirs(root_path: str) -> list[str]:
        root_path = os.path.realpath(root_path)
        if not os.path.exists(root_path):
            return []

        removable_dirs = []
        removable_set = set()
        for dir_path, dir_names, file_names in os.walk(root_path, topdown=False):
            real_dir_path = os.path.realpath(dir_path)
            if real_dir_path == root_path or file_names:
                continue
            try:
                if os.path.commonpath([root_path, real_dir_path]) != root_path:
                    continue
            except ValueError:
                continue

            child_paths = [os.path.realpath(os.path.join(dir_path, name)) for name in dir_names]
            if all(child_path in removable_set for child_path in child_paths):
                removable_dirs.append(real_dir_path)
                removable_set.add(real_dir_path)
        return removable_dirs

    @staticmethod
    def is_original_file(file_path: str, root_path: str) -> bool:
        try:
            relative_path = os.path.relpath(file_path, root_path)
        except ValueError:
            return False
        path_parts = [part.lower() for part in relative_path.split(os.sep)]
        return "original" in path_parts

    def get_recent_history_items(self, limit: int = 5) -> list[dict]:
        record_manager = getattr(self.app, "record_manager", None)
        if not record_manager:
            return []
        try:
            recent_items = []
            seen_paths = set()
            history_items = record_manager.get_recent_recording_history(limit=max(limit * 4, 20))
            root_path = os.path.realpath(self.root_path) if self.root_path else ""
            for item in history_items:
                real_file_path = self.resolve_recent_recording_file(item, root_path)
                if not real_file_path:
                    continue
                if real_file_path in seen_paths:
                    continue
                seen_paths.add(real_file_path)
                recent_item = dict(item)
                recent_item["file_path"] = real_file_path
                recent_items.append(recent_item)
                if len(recent_items) >= limit:
                    break
            return recent_items
        except Exception as e:
            logger.error(f"Load recent recording history failed: {e}")
            return []

    def resolve_recent_recording_file(self, item: dict, root_path: str) -> str | None:
        file_path = item.get("file_path")
        real_file_path = os.path.realpath(file_path) if file_path else ""
        if self.is_usable_media_file(real_file_path, root_path):
            return real_file_path

        output_dir = item.get("output_dir") or (os.path.dirname(file_path) if file_path else "")
        return self.find_latest_media_file(output_dir, root_path)

    def find_latest_media_file(self, dir_path: str | None, root_path: str) -> str | None:
        if not dir_path:
            return None
        real_dir_path = os.path.realpath(dir_path)
        if not os.path.isdir(real_dir_path) or not self.is_path_inside_root(real_dir_path, root_path):
            return None

        media_files = []
        for file_path in self.iter_files(real_dir_path):
            real_file_path = os.path.realpath(file_path)
            if self.is_usable_media_file(real_file_path, root_path):
                media_files.append(real_file_path)
        if not media_files:
            return None
        media_files.sort(key=lambda path: os.path.getmtime(path), reverse=True)
        return media_files[0]

    def is_usable_media_file(self, file_path: str, root_path: str) -> bool:
        return (
            bool(file_path)
            and os.path.isfile(file_path)
            and self.is_media_file(file_path)
            and self.is_path_inside_root(file_path, root_path)
        )

    @staticmethod
    def is_path_inside_root(path: str, root_path: str) -> bool:
        if not root_path:
            return True
        try:
            return os.path.commonpath([root_path, os.path.realpath(path)]) == root_path
        except ValueError:
            return False

    def update_recent_recordings(self):
        recent_items = self.get_recent_history_items(limit=5)
        if not recent_items:
            self.recent_area.controls.append(ft.Text(self._["empty_recent_files"], size=12, color=ft.Colors.GREY_600))
            return

        for item in recent_items:
            file_path = item.get("file_path") or ""
            title = item.get("streamer_name") or os.path.basename(file_path) or self._["unknown_extension"]
            ended_at = item.get("ended_at") or item.get("created_at") or ""
            subtitle = (
                self._["recent_file_item"]
                .replace("{time}", ended_at)
                .replace("{size}", self.format_size(self.get_file_size(file_path)))
            )
            self.recent_area.controls.append(
                ft.ListTile(
                    dense=True,
                    leading=ft.Icon(ft.Icons.VIDEO_FILE, color=ft.Colors.BLUE),
                    title=ft.Text(title, size=13),
                    subtitle=ft.Text(subtitle, size=11),
                    trailing=ft.Row(
                        tight=True,
                        spacing=2,
                        controls=[
                            ft.IconButton(
                                icon=ft.Icons.PLAY_ARROW,
                                tooltip=self._["previewing"],
                                on_click=lambda _, path=file_path: self.app.page.run_task(self.preview_file, path),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.FOLDER_OPEN,
                                tooltip=self._["open_storage_folder"],
                                on_click=lambda _, path=file_path: self.app.page.run_task(
                                    self.open_local_folder, os.path.dirname(path)
                                ),
                            ),
                        ],
                    ),
                )
            )

    @staticmethod
    def create_panel(title: str, content, icon=None, height: int | None = None):
        title_controls = []
        if icon:
            title_controls.append(ft.Icon(icon, size=18, color=ft.Colors.BLUE))
        title_controls.append(ft.Text(title, size=15, weight=ft.FontWeight.BOLD))

        return ft.Container(
            height=height,
            padding=12,
            border=ft.Border.all(1, ft.Colors.GREY_300),
            border_radius=8,
            content=ft.Column(
                expand=bool(height),
                spacing=10,
                controls=[
                    ft.Row(
                        tight=True,
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=title_controls,
                    ),
                    content,
                ],
            ),
        )

    def create_metric_group(self, label: str, rows: list[tuple[str, str]]):
        return ft.Container(
            width=250,
            height=112,
            padding=10,
            border=ft.Border.all(1, ft.Colors.GREY_300),
            border_radius=6,
            content=ft.Column(
                tight=True,
                spacing=8,
                controls=[
                    ft.Text(label, size=13, weight=ft.FontWeight.BOLD),
                    ft.Column(
                        tight=True,
                        spacing=4,
                        controls=[
                            ft.Row(
                                tight=True,
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Text(row_label, size=12, color=ft.Colors.GREY_600, expand=True),
                                    ft.Text(
                                        row_value, size=12, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.RIGHT
                                    ),
                                ],
                            )
                            for row_label, row_value in rows
                        ],
                    ),
                ],
            ),
        )

    @staticmethod
    def create_section_title(title: str):
        return ft.Text(title, size=15, weight=ft.FontWeight.BOLD)

    async def update_file_list(self):
        try:
            self.path_display.value = self._["current_path"] + ":" + self.current_path
            self.file_list.controls.clear()

            if self.current_path != self.root_path:
                back_button = ft.Button(
                    self._["go_back"],
                    icon=ft.Icons.ARROW_BACK,
                    on_click=lambda _: self.app.page.run_task(self.navigate_to_parent),
                )
                if self.app.is_mobile:
                    back_item = ft.ListTile(
                        leading=ft.Icon(ft.Icons.ARROW_BACK, color=ft.Colors.BLUE),
                        title=ft.Text(self._["go_back"]),
                        on_click=lambda _: self.app.page.run_task(self.navigate_to_parent),
                    )
                    self.file_list.controls.append(back_item)
                else:
                    self.file_list.controls.append(back_button)

            exists, is_empty = await self.check_directory()
            if not exists or is_empty:
                self.show_empty_folder_message()
                self.file_list.update()
                return

            await self.create_file_buttons()

        except Exception as e:
            logger.error(f"Error updating file list: {e}")
            await self.app.snack_bar.show_snack_bar(self._["file_list_update_error"])
        finally:
            self.file_list.update()

    async def check_directory(self):
        def _check():
            if not os.path.exists(self.current_path):
                return False, True
            try:
                with os.scandir(self.current_path) as it:
                    return True, not any(True for _ in it)
            except Exception:
                return False, True

        return await asyncio.get_event_loop().run_in_executor(self.executor, _check)

    async def create_file_buttons(self):
        def _get_items():
            try:
                _items = []
                with os.scandir(self.current_path) as it:
                    for entry in it:
                        _items.append((entry.name, entry.is_dir(), entry.path))
                return sorted(_items, key=lambda x: (-x[1], x[0].lower()))
            except Exception as e:
                logger.error(f"Error listing directory: {e}")
                return []

        items = await asyncio.get_event_loop().run_in_executor(self.executor, _get_items)

        buttons = []
        is_mobile = self.app.is_mobile
        for name, is_dir, full_path in items:
            if is_mobile:
                icon = ft.Icon(ft.Icons.FOLDER, color=ft.Colors.BLUE) if is_dir else ft.Icon(ft.Icons.INSERT_DRIVE_FILE)
                item = ft.ListTile(
                    leading=icon,
                    title=ft.Text(name),
                    on_click=lambda e, path=full_path, is_directory=is_dir: self.app.page.run_task(
                        self.navigate_to if is_directory else self.preview_file, path
                    ),
                )
                buttons.append(item)
            else:
                if is_dir:
                    btn = ft.Button(
                        f"📁 {name}", on_click=lambda e, path=full_path: self.app.page.run_task(self.navigate_to, path)
                    )
                else:
                    btn = ft.Button(
                        f"📄 {name}", on_click=lambda e, path=full_path: self.app.page.run_task(self.preview_file, path)
                    )
                buttons.append(btn)

        self.file_list.controls.extend(buttons)

    def show_empty_folder_message(self):
        self.file_list.controls.append(
            ft.Card(
                content=ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.FOLDER_OPEN),
                            ft.Text(self._["empty_recording_folder"], size=16, weight=ft.FontWeight.BOLD),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    padding=20,
                ),
                elevation=2,
                margin=10,
                width=400,
            )
        )

    async def navigate_to(self, path):
        self.current_path = path
        self.path_display.value = self._["current_path"] + ":" + self.current_path
        await self.update_file_list()
        self.content.update()

    async def navigate_to_parent(self):
        self.current_path = os.path.dirname(self.current_path)
        self.path_display.value = self._["current_path"] + ":" + self.current_path
        await self.update_file_list()
        self.content.update()

    async def open_storage_folder(self, *_):
        await self.open_local_folder(self.root_path)

    async def open_local_folder(self, folder_path):
        if not os.path.exists(folder_path):
            os.makedirs(folder_path, exist_ok=True)
            if not os.path.exists(folder_path):
                await self.app.snack_bar.show_snack_bar(self._["no_recording_folder"])
                return

        if self.app.page.web:
            await self.app.snack_bar.show_snack_bar(self._["web_open_folder_tip"])
            return

        try:
            if os.name == "nt":
                os.startfile(folder_path)
            elif os.uname().sysname == "Darwin":
                subprocess.Popen(["open", folder_path])
            else:
                subprocess.Popen(["xdg-open", folder_path])
        except Exception as e:
            logger.error(f"Open local folder failed: {folder_path}, {e}")
            await self.app.snack_bar.show_snack_bar(self._["open_folder_failed"])

    async def confirm_cleanup_empty_dirs(self, *_):
        stats = self.storage_stats or await self.scan_storage()
        empty_dirs = int(stats.get("empty_dirs") or 0)
        if not empty_dirs:
            await self.app.snack_bar.show_snack_bar(self._["no_empty_dirs"])
            return

        await self.show_confirm_dialog(
            self._["clean_empty_dirs"],
            self._["clean_empty_dirs_confirm"].replace("{count}", str(empty_dirs)),
            self.cleanup_empty_dirs,
        )

    async def confirm_cleanup_logs(self, *_):
        stats = self.storage_stats or await self.scan_storage()
        logs_size = int(stats.get("logs_size") or 0)
        if not logs_size:
            await self.app.snack_bar.show_snack_bar(self._["no_logs_to_clean"])
            return

        await self.show_confirm_dialog(
            self._["clean_logs"],
            self._["clean_logs_confirm"].replace("{size}", self.format_size(logs_size)),
            self.cleanup_logs,
        )

    async def confirm_delete_all_files(self, *_):
        files = list(self.iter_media_files())
        if not files:
            await self.app.snack_bar.show_snack_bar(self._["no_files_to_delete"])
            return

        total_size = sum(self.get_file_size(path) for path in files)

        await self.show_confirm_dialog(
            self._["delete_all_files"],
            self._["delete_all_files_confirm"]
            .replace("{count}", str(len(files)))
            .replace("{size}", self.format_size(total_size)),
            lambda: self.cleanup_selected_files(files, self._["delete_all_files_success"]),
        )

    async def show_confirm_dialog(self, title: str, message: str, confirm_action):
        async def close_dialog(_=None):
            try:
                dialog.open = False
                dialog.update()
            except (ft.FletPageDisconnectedException, AssertionError) as e:
                logger.debug(f"Close storage confirm dialog failed: {e}")

            await asyncio.sleep(0.05)
            try:
                if self.app.dialog_area.content is dialog:
                    self.app.dialog_area.content = None
                self.app.page.update()
            except (ft.FletPageDisconnectedException, AssertionError) as e:
                logger.debug(f"Clear storage confirm dialog failed: {e}")

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

    async def cleanup_selected_files(self, files: list[str], success_template: str):
        deleted_count, deleted_size = await asyncio.get_event_loop().run_in_executor(
            self.executor, self.cleanup_selected_files_sync, files
        )
        if deleted_count:
            await self.app.snack_bar.show_snack_bar(
                success_template.replace("{count}", str(deleted_count)).replace(
                    "{size}", self.format_size(deleted_size)
                )
            )
        else:
            await self.app.snack_bar.show_snack_bar(self._["no_files_cleaned"])
        if not os.path.exists(self.current_path):
            self.current_path = self.root_path
        await self.refresh_storage()

    def cleanup_selected_files_sync(self, files: list[str]):
        root_path = os.path.realpath(self.root_path)
        deleted_count = 0
        deleted_size = 0
        for file_path in files:
            real_file_path = os.path.realpath(file_path)
            try:
                if os.path.commonpath([root_path, real_file_path]) != root_path:
                    continue
            except ValueError:
                continue
            size = self.get_file_size(real_file_path)
            try:
                os.remove(real_file_path)
                deleted_count += 1
                deleted_size += size
            except OSError as e:
                logger.warning(f"Skip deleting file: {real_file_path}, {e}")
        logger.info(f"Cleaned selected files: count={deleted_count}, size={deleted_size}")
        return deleted_count, deleted_size

    async def cleanup_empty_dirs(self):
        deleted_count = await asyncio.get_event_loop().run_in_executor(self.executor, self.cleanup_empty_dirs_sync)
        if deleted_count:
            await self.app.snack_bar.show_snack_bar(
                self._["clean_empty_dirs_success"].replace("{count}", str(deleted_count))
            )
        else:
            await self.app.snack_bar.show_snack_bar(self._["no_empty_dirs"])

        if not os.path.exists(self.current_path):
            self.current_path = self.root_path
        await self.refresh_storage()

    def cleanup_empty_dirs_sync(self):
        root_path = os.path.realpath(self.root_path)
        if not os.path.exists(root_path):
            return 0

        deleted_count = 0
        for real_dir_path in self.get_removable_empty_dirs(root_path):
            try:
                os.rmdir(real_dir_path)
                deleted_count += 1
            except OSError:
                pass

        logger.info(f"Cleaned empty storage dirs: count={deleted_count}")
        return deleted_count

    async def cleanup_logs(self):
        deleted_count, deleted_size = await asyncio.get_event_loop().run_in_executor(
            self.executor, self.cleanup_logs_sync
        )
        if deleted_count:
            await self.app.snack_bar.show_snack_bar(
                self._["clean_logs_success"]
                .replace("{count}", str(deleted_count))
                .replace("{size}", self.format_size(deleted_size))
            )
        else:
            await self.app.snack_bar.show_snack_bar(self._["no_logs_to_clean"])
        await self.refresh_storage()

    def cleanup_logs_sync(self):
        logs_dir = os.path.realpath(os.path.join(self.app.run_path, "log"))
        if not os.path.exists(logs_dir):
            return 0, 0

        deleted_count = 0
        deleted_size = 0
        for file_path in list(self.iter_files(logs_dir)):
            real_file_path = os.path.realpath(file_path)
            try:
                if os.path.commonpath([logs_dir, real_file_path]) != logs_dir:
                    continue
            except ValueError:
                continue
            size = self.get_file_size(real_file_path)
            try:
                os.remove(real_file_path)
                deleted_count += 1
                deleted_size += size
            except OSError as e:
                logger.warning(f"Skip deleting active log file: {real_file_path}, {e}")

        logger.info(f"Cleaned logs: count={deleted_count}, size={deleted_size}")
        return deleted_count, deleted_size

    async def preview_file(self, file_path, room_url=None):
        import urllib.parse

        from ..components.business.video_player import VideoPlayer

        if not os.path.isfile(file_path):
            await self.app.snack_bar.show_snack_bar(self._["recording_file_missing"])
            await self.refresh_storage()
            return

        video_player = VideoPlayer(self.app)

        if self.app.page.web:
            if not VIDEO_API_EXTERNAL_URL:
                logger.error("VIDEO_API_EXTERNAL_URL is not set in .env")
                await self.app.snack_bar.show_snack_bar(self._["video_api_server_not_set"])
                return

            relative_path = os.path.relpath(file_path, self.root_path)
            filename = urllib.parse.quote(os.path.basename(file_path))
            subfolder = urllib.parse.quote(os.path.dirname(relative_path).replace("\\", "/"))
            api_url = f"{VIDEO_API_EXTERNAL_URL}/api/videos?filename={filename}&subfolder={subfolder}"
            await video_player.preview_video(api_url, is_file_path=False, room_url=room_url)
        else:
            await video_player.preview_video(file_path, is_file_path=True, room_url=room_url)

    @staticmethod
    def format_size(size: int | float | None) -> str:
        size = float(size or 0)
        units = ["B", "KB", "MB", "GB", "TB"]
        unit_index = 0
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        if unit_index == 0:
            return f"{int(size)} {units[unit_index]}"
        return f"{size:.2f} {units[unit_index]}"
