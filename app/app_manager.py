import asyncio
import os
import time

import flet as ft

from . import execute_dir
from .core.runtime.backend_services import BackendServices
from .core.update.update_checker import UpdateChecker
from .initialization.installation_manager import InstallationManager
from .ui.components.business.recording_card import RecordingCardManager
from .ui.components.common.show_snackbar import ShowSnackBar
from .ui.navigation.sidebar import LeftNavigationMenu, NavigationSidebar
from .ui.views.about_view import AboutPage
from .ui.views.home_view import HomePage
from .ui.views.logs_view import LogsPage
from .ui.views.recordings_view import RecordingsPage
from .ui.views.settings_view import SettingsPage
from .ui.views.storage_view import StoragePage
from .utils.logger import logger


class App:
    def __init__(self, page: ft.Page, services: BackendServices | None = None):
        self.page = page
        self.install_progress = None

        if services is None:
            services = BackendServices.get_or_none()
            if services is None:
                services = BackendServices.bootstrap(execute_dir)
        self.services = services

        self.run_path = execute_dir
        self.assets_dir = os.path.join(execute_dir, "assets")

        self.config_manager = services.config_manager
        self.process_manager = services.process_manager
        self.language_manager = services.language_manager
        self.record_manager = services.recording_manager

        self.is_web_mode = False
        self.auth_manager = None
        self.current_username = None
        self.content_area = ft.Column(
            controls=[],
            expand=True,
            alignment=ft.MainAxisAlignment.START,
            horizontal_alignment=ft.CrossAxisAlignment.START,
        )

        self.settings = SettingsPage(self)
        services.settings_config.adopt_user_config(self.settings.user_config)
        services.settings_config.adopt_cookies_config(self.settings.cookies_config)
        services.settings_config.adopt_accounts_config(self.settings.accounts_config)
        services.settings_config.language_code = self.settings.language_code or services.settings_config.language_code
        self.language_code = self.settings.language_code
        self.about = AboutPage(self)
        self.recordings = RecordingsPage(self)
        self.home = HomePage(self)
        self.storage = StoragePage(self)
        self.logs = LogsPage(self)
        self.pages = self.initialize_pages()
        self.sidebar = NavigationSidebar(self)
        self.left_navigation_menu = LeftNavigationMenu(self)

        self.snack_bar_area = ft.Container()
        self.dialog_area = ft.Container()
        self.complete_page = ft.Row(
            expand=True,
            controls=[
                self.left_navigation_menu,
                ft.VerticalDivider(width=1),
                self.content_area,
                self.dialog_area,
                self.snack_bar_area,
            ],
        )
        self.snack_bar = ShowSnackBar(self)
        self.subprocess_start_up_info = services.subprocess_start_up_info
        self.record_card_manager = RecordingCardManager(self)
        self.current_page = None
        self._loading_page = False
        self.install_manager = InstallationManager(self)
        self.update_checker = UpdateChecker(self)
        self.page.run_task(self.install_manager.check_env)
        if self.record_manager is not None:
            self.page.run_task(self.record_manager.check_free_space)
        self.page.run_task(self._check_for_updates)

        services.register_ui_bridge(self)

    @property
    def recording_enabled(self):
        return self.services.recording_enabled

    @recording_enabled.setter
    def recording_enabled(self, value: bool):
        self.services.recording_enabled = value

    @property
    def tray_manager(self):
        return self.services.tray_manager

    @tray_manager.setter
    def tray_manager(self, value):
        self.services.tray_manager = value

    def _get_session_loop(self) -> asyncio.AbstractEventLoop | None:
        """Return the asyncio event loop bound to the current Flet session,
        or ``None`` if the session/connection is dead."""
        try:
            session = self.page.session
            if session is None:
                return None
            connection = getattr(session, "connection", None)
            if connection is None:
                return None
            return getattr(connection, "loop", None)
        except Exception:
            return None

    def schedule_card_update(self, recording) -> None:
        loop = self._get_session_loop()
        if loop is None:
            return
        try:
            asyncio.run_coroutine_threadsafe(self.record_card_manager.update_card(recording), loop)
        except Exception as exc:
            logger.debug(f"schedule_card_update dropped: {exc}")

    def schedule_card_remove(self, recordings) -> None:
        loop = self._get_session_loop()
        if loop is None:
            return
        try:
            asyncio.run_coroutine_threadsafe(self.record_card_manager.remove_recording_card(recordings), loop)
        except Exception as exc:
            logger.debug(f"schedule_card_remove dropped: {exc}")

    def schedule_snack(self, text: str, **kw) -> None:
        loop = self._get_session_loop()
        if loop is None:
            return
        try:
            asyncio.run_coroutine_threadsafe(self.snack_bar.show_snack_bar(text, **kw), loop)
        except Exception as exc:
            logger.debug(f"schedule_snack dropped: {exc}")

    def schedule_pubsub(self, topic: str, payload) -> None:
        try:
            self.page.pubsub.send_others_on_topic(topic, payload)
        except Exception as exc:
            logger.debug(f"schedule_pubsub dropped: {exc}")

    def initialize_pages(self):
        return {
            "settings": self.settings,
            "home": self.home,
            "recordings": self.recordings,
            "storage": self.storage,
            "logs": self.logs,
            "about": self.about,
        }

    async def switch_page(self, page_name):
        if self._loading_page:
            return
        self._loading_page = True

        try:
            await self.clear_content_area()
            if page := self.pages.get(page_name):
                await self.settings.is_changed()
                self.current_page = page
                await page.load()
        finally:
            self._loading_page = False

    async def clear_content_area(self):
        self.content_area.controls.clear()
        self.content_area.update()

    async def cleanup(self):
        self.services.unregister_ui_bridge(self)

        if not self.is_web_mode:
            try:
                await self.process_manager.cleanup()
            except ConnectionError:
                logger.warning("Connection lost, process may have terminated")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")

    def add_ffmpeg_process(self, process):
        self.process_manager.add_process(process)

    async def _check_for_updates(self):
        """Check for updates when the application starts"""
        try:
            if not self.update_checker.update_config["auto_check"]:
                return

            last_check_time = self.settings.user_config.get("last_update_check", 0)
            current_time = time.time()
            check_interval = self.update_checker.update_config["check_interval"]

            if current_time - last_check_time >= check_interval:
                update_info = await self.update_checker.check_for_updates()
                self.settings.user_config["last_update_check"] = current_time
                await self.config_manager.save_user_config(self.settings.user_config)

                if update_info.get("has_update", False):
                    await self.update_checker.show_update_dialog(dict(update_info))
        except Exception as e:
            logger.error(f"Update check failed: {e}")

    async def start_periodic_tasks(self):
        rm = self.record_manager
        if rm is None:
            return
        interval = int(rm.loop_time_seconds or 180)
        await rm.setup_periodic_live_check(interval)
