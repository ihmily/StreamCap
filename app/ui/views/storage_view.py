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
        self.path_display = ft.Text(
            self._["storage_path"] + ": " + self.current_path,
            size=14,
            color=ft.Colors.GREY_600,
            selectable=True,
        )
        self.file_list = ft.ListView(expand=True, spacing=2, padding=10)
        self.content = ft.Column(controls=[self.path_display, self.file_list])
        self.app.content_area.controls = [self.content]
        self.app.content_area.update()

    def load_language(self):
        language = self.app.language_manager.language
        for key in ("storage_page", "base"):
            self._.update(language.get(key, {}))

    async def update_file_list(self):
        try:
            self.path_display.value = self._["current_path"] + ":" + self.current_path
            self.file_list.controls.clear()

            if self.current_path != self.root_path:
                back_button = ft.ElevatedButton(
                    self._["go_back"],
                    icon=ft.icons.ARROW_BACK,
                    on_click=lambda _: self.app.page.run_task(self.navigate_to_parent)
                )
                if self.app.is_mobile:
                    back_item = ft.ListTile(
                        leading=ft.Icon(ft.icons.ARROW_BACK, color=ft.colors.BLUE),
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
                icon = ft.Icon(ft.icons.FOLDER, color=ft.colors.BLUE) if is_dir else ft.Icon(ft.icons.INSERT_DRIVE_FILE)
                item = ft.ListTile(
                    leading=icon,
                    title=ft.Text(name),
                    on_click=lambda e, path=full_path, is_directory=is_dir: self.app.page.run_task(
                        self.navigate_to if is_directory else self.preview_file, 
                        path
                    ),
                )
                buttons.append(item)
            else:
                if is_dir:
                    btn = ft.ElevatedButton(
                        f"📁 {name}",
                        on_click=lambda e, path=full_path: self.app.page.run_task(self.navigate_to, path)
                    )
                else:
                    btn = ft.ElevatedButton(
                        f"📄 {name}",
                        on_click=lambda e, path=full_path: self.app.page.run_task(self.preview_file, path)
                    )
                buttons.append(btn)

        self.file_list.controls.extend(buttons)

    def show_empty_folder_message(self):
        self.file_list.controls.append(
            ft.Card(
                content=ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.icons.FOLDER_OPEN),
                            ft.Text(self._["empty_recording_folder"], size=16, weight=ft.FontWeight.BOLD)
                        ],
                        alignment=ft.MainAxisAlignment.CENTER
                    ),
                    padding=20
                ),
                elevation=2,
                margin=10,
                width=400
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

    async def preview_file(self, file_path, room_url=None):
        import urllib.parse

        from ..components.business.video_player import VideoPlayer

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
