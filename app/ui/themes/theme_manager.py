import sys

import flet as ft

from .theme import create_dark_theme, create_light_theme


class ThemeManager:
    def __init__(self, app):
        self.page = app.page
        self.app = app
        self.custom_font = None
        self.theme_color = None
        self.assets_dir = app.assets_dir
        self.init_fonts()
        self.page.run_task(self.apply_initial_theme)

    def init_fonts(self):
        """Initialize fonts for the application."""
        custom_font = "AlibabaPuHuiTi Light"
        if sys.platform == "darwin":
            custom_font = "AlibabaPuHuiTi Light Mac"

        self.page.fonts = {
            "AlibabaPuHuiTi Light": "/fonts/AlibabaPuHuiTi-2/AlibabaPuHuiTi-2-45-Light.otf",
            "AlibabaPuHuiTi Light Mac": "/fonts/AlibabaPuHuiTi-2/AlibabaPuHuiTi-2-45-Light-Mac.otf",
        }
        self.custom_font = custom_font

    async def apply_initial_theme(self):
        """Apply initial theme based on saved settings or default to light theme."""
        self.page.theme = create_light_theme(self.custom_font)
        self.page.dark_theme = create_dark_theme(self.custom_font)

        self.theme_color = self.app.settings.user_config.get("theme_color", "blue")
        await self.update_theme_color(self.theme_color)

    async def update_theme_color(self, color):
        """Update the current theme color scheme and save it."""
        self.page.theme.color_scheme_seed = color
        self.page.theme.color_scheme = ft.ColorScheme(primary=color)
        self.page.theme.use_material3 = True
        self.page.update()

        self.app.settings.user_config["theme_color"] = color
        self.page.run_task(self.app.config_manager.save_user_config, self.app.settings.user_config)
