import os
import threading

import flet as ft

from ..utils.logger import logger


class TrayManager:
    def __init__(self, app):
        self.app = app
        self.icon = None
        self.icon_path = None
        self.tray_thread = None
        self.is_running = False
        self.execute_dir = getattr(app, "run_path", os.getcwd())
        self.assets_dir = "assets"

    def create_image(self):
        try:
            from PIL import Image

            self.icon_path = os.path.join(self.execute_dir, self.assets_dir, "icons", "tray_icon.ico")
            if os.path.exists(self.icon_path):
                return Image.open(self.icon_path)
        except Exception as e:
            logger.error(f"Failed to load icon file: {e}")
            try:
                from PIL import Image

                image = Image.new("RGB", (32, 32), color=(255, 255, 255))
                return image
            except Exception as e:
                logger.error("PIL not available, unable to create tray icon")
                raise e

    def create_tray_icon(self, page: ft.Page):
        if self.is_running:
            return

        try:
            import pystray

            def on_restore(_icon, _item):
                page.window.visible = True
                page.window.minimized = False
                page.update()

            def on_exit(_icon, _item):
                self.is_running = False
                on_restore(_icon, _item)
                if hasattr(self.app, "close_confirm_dialog"):
                    self.app.close_confirm_dialog.open = True
                    page.update()

            language = self.app.language_manager.language
            _ = {}
            for key in ("tray_manager", "base"):
                _.update(language.get(key, {}))

            menu = pystray.Menu(pystray.MenuItem(_["restore"], on_restore), pystray.MenuItem(_["exit"], on_exit))

            self.icon = pystray.Icon("StreamCap", self.create_image(), "StreamCap", menu)
            self.is_running = True
            self.icon.run()
        except ImportError as e:
            logger.error(e)
            self.is_running = False
            page.window.destroy()
            raise e

    def start(self, page: ft.Page):
        if getattr(self.app, "is_web_mode", False):
            logger.info("Tray icon not available in web mode")
            return False

        if self.tray_thread is None or not self.tray_thread.is_alive():
            self.tray_thread = threading.Thread(target=self.create_tray_icon, args=(page,), daemon=True)
            self.tray_thread.start()
            return True
        return False

    def stop(self):
        if self.icon and self.is_running:
            self.is_running = False
            try:
                self.icon.stop()
                return True
            except Exception as e:
                logger.error(f"Error stopping tray icon: {e}")
        return False
