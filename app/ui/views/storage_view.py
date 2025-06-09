import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

import flet as ft
from dotenv import find_dotenv, load_dotenv

from ...utils.logger import logger
from ..base_page import PageBase as BasePage

dotenv_path = find_dotenv()
load_dotenv(dotenv_path)
VIDEO_API_EXTERNAL_URL = os.getenv("VIDEO_API_EXTERNAL_URL")


class StoragePage(BasePage):
    def __init__(self, app):
        super().__init__(app)
        self.page_name = "storage"
        self.root_path = None
        self.current_path = None
        self.path_display = None
        self.content = None
        self.file_list = None
        self._ = {}
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.load_language()
        self.app.language_manager.add_observer(self)

    async def load(self):
        self.root_path = self.app.settings.get_video_save_path()
        self.current_path = self.root_path
        self.setup_ui()
        await self.update_file_list()

    def setup_ui(self):
        # 创建导航栏
        navigation_bar = ft.Row(
            controls=[
                ft.Icon(ft.icons.FOLDER, color=ft.colors.BLUE),
                ft.Text(
                    self._["storage_path"] + ":",
                    size=14,
                    weight=ft.FontWeight.BOLD,
                    color=ft.colors.BLUE_700
                ),
            ],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        
        # 创建路径显示区域（可滚动）
        self.path_display = ft.Text(
            self.current_path,
            size=14,
            color=ft.colors.GREY_800,
            overflow=ft.TextOverflow.ELLIPSIS,
            max_lines=1,
            expand=True,
            selectable=True,
        )
        
        # 组合导航栏和路径显示
        path_container = ft.Container(
            content=ft.Row(
                [navigation_bar, self.path_display],
                alignment=ft.MainAxisAlignment.START,
                spacing=8,
            ),
            padding=ft.padding.only(left=16, right=16, top=10, bottom=10),
            margin=ft.margin.only(bottom=5),
            border_radius=8,
            bgcolor=ft.colors.with_opacity(0.05, ft.colors.BLUE_GREY),
        )
        
        # 创建文件列表区域
        self.file_list = ft.ListView(
            expand=True,
            spacing=5,
            padding=10,
        )
        
        # 组合所有元素
        self.content = ft.Column(
            controls=[path_container, self.file_list],
            expand=True,
        )
        
        self.app.content_area.controls = [self.content]
        self.app.content_area.update()

    def load_language(self):
        language = self.app.language_manager.language
        for key in ("storage_page", "base"):
            self._.update(language.get(key, {}))

    async def update_file_list(self):
        try:
            self.path_display.value = self.current_path
            self.file_list.controls.clear()

            # 始终显示返回按钮，除非在根目录
            if self.current_path != self.root_path:
                self.add_back_button()

            exists, is_empty = await self.check_directory()
            if not exists:
                self.show_error_message(self._["no_recording_folder"])
                self.file_list.update()
                return
                
            if is_empty:
                self.show_empty_folder_message()
                self.file_list.update()
                return

            await self.create_file_buttons()
            
        except Exception as e:
            logger.error(f"Error updating file list: {e}")
            await self.app.snack_bar.show_snack_bar(self._["file_list_update_error"])
        finally:
            self.file_list.update()

    def add_back_button(self):
        """添加返回上一级按钮"""
        self.file_list.controls.append(
            ft.Container(
                content=ft.ElevatedButton(
                    content=ft.Row(
                        [
                            ft.Icon(ft.icons.ARROW_BACK, size=20),
                            ft.Text(self._["go_back"], size=14),
                        ],
                        alignment=ft.MainAxisAlignment.START,
                        spacing=5,
                    ),
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8),
                        color=ft.colors.BLUE,
                    ),
                    on_click=lambda _: self.app.page.run_task(self.navigate_to_parent),
                ),
                margin=ft.margin.only(bottom=10),
            )
        )

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
        
        # 先创建文件夹按钮
        folders = []
        files = []
        
        for name, is_dir, full_path in items:
            if is_dir:
                folder_btn = self.create_folder_button(name, full_path)
                folders.append(folder_btn)
            else:
                file_btn = self.create_file_button(name, full_path)
                if file_btn:  # 只添加视频文件按钮
                    files.append(file_btn)

        # 如果有文件夹，添加一个标题
        if folders:
            self.file_list.controls.append(
                ft.Container(
                    content=ft.Text(
                        "📁 " + self._["folders"],
                        size=14,
                        weight=ft.FontWeight.BOLD,
                        color=ft.colors.BLUE_700,
                    ),
                    margin=ft.margin.only(left=5, top=5, bottom=5),
                )
            )
            self.file_list.controls.extend(folders)
        
        # 如果有视频文件，添加一个标题
        if files:
            self.file_list.controls.append(
                ft.Container(
                    content=ft.Text(
                        "🎬 " + self._["files"],
                        size=14,
                        weight=ft.FontWeight.BOLD,
                        color=ft.colors.BLUE_700,
                    ),
                    margin=ft.margin.only(left=5, top=15, bottom=5),
                )
            )
            self.file_list.controls.extend(files)

    def create_folder_button(self, name, full_path):
        return ft.Container(
            content=ft.ElevatedButton(
                content=ft.Row(
                    [
                        ft.Icon(ft.icons.FOLDER, color=ft.colors.AMBER),
                        ft.Text(
                            name,
                            size=14,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            max_lines=1,
                            expand=True,
                        ),
                        ft.Icon(ft.icons.ARROW_FORWARD_IOS, size=14, color=ft.colors.GREY_600),
                    ],
                    spacing=10,
                    alignment=ft.MainAxisAlignment.START,
                    expand=True,
                ),
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=8),
                ),
                on_click=lambda e, path=full_path: self.app.page.run_task(self.navigate_to, path),
                width=600,
            ),
            margin=ft.margin.only(bottom=5),
        )

    def create_file_button(self, name, full_path):
        # 仅检查视频文件扩展名
        ext = os.path.splitext(name)[1].lower()
        if ext not in ['.mp4', '.ts', '.flv', '.mkv', '.avi', '.mov']:
            return None  # 如果不是视频文件，则不创建按钮
            
        return ft.Container(
            content=ft.ElevatedButton(
                content=ft.Row(
                    [
                        ft.Icon(ft.icons.VIDEO_FILE, color=ft.colors.BLUE),
                        ft.Text(
                            name,
                            size=14,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            max_lines=1,
                            expand=True,
                        ),
                        ft.IconButton(
                            icon=ft.icons.PLAY_CIRCLE,
                            tooltip=self._["preview_video"],
                            icon_color=ft.colors.BLUE,
                            icon_size=20,
                            on_click=lambda e, path=full_path: self.app.page.run_task(self.preview_file, path),
                        ),
                    ],
                    spacing=10,
                    alignment=ft.MainAxisAlignment.START,
                    expand=True,
                ),
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=8),
                ),
                on_click=lambda e, path=full_path: self.app.page.run_task(self.preview_file, path),
                width=600,
            ),
            margin=ft.margin.only(bottom=5),
        )

    def show_empty_folder_message(self):
        """显示空文件夹消息"""
        self.file_list.controls.append(
            ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.icons.FOLDER_OPEN, size=40, color=ft.colors.AMBER),
                                ft.Text(
                                    self._["empty_recording_folder"],
                                    size=16,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.colors.GREY_700,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=10,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                margin=ft.margin.only(top=40),
                alignment=ft.alignment.center,
            )
        )

    def show_error_message(self, message):
        """显示错误消息"""
        self.file_list.controls.append(
            ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.icons.ERROR, size=40, color=ft.colors.RED),
                                ft.Text(
                                    message,
                                    size=16,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.colors.RED_700,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=10,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                margin=ft.margin.only(top=40),
                alignment=ft.alignment.center,
            )
        )

    async def navigate_to(self, path):
        self.current_path = path
        self.path_display.value = self.current_path
        await self.update_file_list()
        self.content.update()

    async def navigate_to_parent(self):
        self.current_path = os.path.dirname(self.current_path)
        self.path_display.value = self.current_path
        await self.update_file_list()
        self.content.update()

    async def preview_file(self, file_path, room_url=None):
        import urllib.parse

        from ..components.video_player import VideoPlayer

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
