from __future__ import annotations

from collections.abc import Callable
from typing import cast

import flet as ft

from ..themes import PopupColorItem, ThemeManager


class ControlGroup:
    def __init__(self, icon, label: str, index: int, name: str, selected_icon):
        self.icon = icon
        self.label = label
        self.index = index
        self.name = name
        self.selected_icon = selected_icon


class NavigationItem(ft.Container):
    def __init__(self, destination: ControlGroup, item_clicked: Callable[[ft.Event[ft.Container]], None]):
        super().__init__()
        self.ink = True
        self.padding = 10
        self.border_radius = 5
        self.destination = destination
        self.icon = destination.icon
        self.text = destination.label
        self.icon_control = ft.Icon(destination.icon, color=ft.Colors.PRIMARY)
        self.label_control = ft.Text(destination.label, color=ft.Colors.PRIMARY)
        self.content = ft.Row([self.icon_control, self.label_control])
        self.on_click = item_clicked


class NavigationColumn(ft.Column):
    def __init__(self, sidebar, page, app):
        super().__init__()
        self.expand = 4
        self.spacing = 0
        self.scroll = ft.ScrollMode.ALWAYS
        self.sidebar = sidebar
        self.selected_index = 0
        self.flet_page = page
        self.app = app
        self.navigation_items = self.get_navigation_items()
        self.controls = cast(list[ft.Control], self.navigation_items)

    def get_navigation_items(self) -> list[NavigationItem]:
        return [
            NavigationItem(destination, item_clicked=self.item_clicked) for destination in self.sidebar.control_groups
        ]

    def item_clicked(self, e: ft.Event[ft.Container]):
        control = cast(NavigationItem, e.control)
        self.selected_index = control.destination.index
        self.update_selected_item()
        self.flet_page.go(f"/{control.destination.name}")

    def update_selected_item(self):
        for item in self.navigation_items:
            item.bgcolor = None
            item.icon_control.icon = item.destination.icon
        if 0 <= self.selected_index < len(self.navigation_items):
            selected_item = self.navigation_items[self.selected_index]
            selected_item.bgcolor = ft.Colors.SECONDARY_CONTAINER
            selected_item.icon_control.icon = selected_item.destination.selected_icon


class LeftNavigationMenu(ft.Column):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.sidebar = app.sidebar
        self.flet_page = app.page
        self.rail = None
        self.dark_light_text = None
        self.dark_light_icon = None
        self.bottom_controls = None
        self.first_run = True
        self.theme_manager = ThemeManager(self.app)
        self.app.language_manager.add_observer(self)
        self._ = {}
        self.load()

    def load(self):
        self._ = self.app.language_manager.language.get("sidebar")
        self.rail = NavigationColumn(sidebar=self.sidebar, page=self.flet_page, app=self.app)

        if self.flet_page.theme_mode == ft.ThemeMode.DARK:
            self.dark_light_text = ft.Text(self._["dark_theme"], color=ft.Colors.PRIMARY)
            self.dark_light_icon = ft.IconButton(
                icon=ft.Icons.BRIGHTNESS_HIGH_OUTLINED,
                tooltip=self._["toggle_day_theme"],
                on_click=self.theme_changed,
                icon_color=ft.Colors.PRIMARY,
            )
        else:
            self.dark_light_text = ft.Text(self._["light_theme"], color=ft.Colors.PRIMARY)
            self.dark_light_icon = ft.IconButton(
                icon=ft.Icons.BRIGHTNESS_2_OUTLINED,
                tooltip=self._["toggle_night_theme"],
                on_click=self.theme_changed,
                icon_color=ft.Colors.PRIMARY,
            )

        colors_list = [
            ("deeppurple", "Deep purple"),
            ("purple", "Purple"),
            ("indigo", "Indigo"),
            ("blue", "Blue"),
            ("teal", "Teal"),
            ("deeporange", "Deep orange"),
            ("orange", "Orange"),
            ("pink", "Pink"),
            ("brown", "Brown"),
            ("bluegrey", "Blue Grey"),
            ("green", "Green"),
            ("cyan", "Cyan"),
            ("lightblue", "Light Blue"),
            ("", "Default"),
        ]

        self.bottom_controls = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        self.dark_light_icon,
                        self.dark_light_text,
                    ],
                    alignment=ft.MainAxisAlignment.START,
                ),
                ft.Row(
                    controls=[
                        ft.PopupMenuButton(
                            icon=ft.Icons.COLOR_LENS_OUTLINED,
                            icon_color=ft.Colors.PRIMARY,
                            tooltip=self._["colors"],
                            items=[PopupColorItem(color=color, name=name) for color, name in colors_list],
                        ),
                        ft.Text(self._["theme_color"], color=ft.Colors.PRIMARY),
                    ],
                    alignment=ft.MainAxisAlignment.START,
                ),
            ],
            alignment=ft.MainAxisAlignment.END,
        )

        self.controls = [
            self.rail,
            ft.Container(expand=True),
            self.bottom_controls,
        ]

        self.width = 160
        self.spacing = 0
        self.alignment = ft.MainAxisAlignment.START

    async def theme_changed(self, _):
        page = self.app.page
        self._ = self.app.language_manager.language.get("sidebar")
        if page.theme_mode == ft.ThemeMode.LIGHT:
            page.theme_mode = ft.ThemeMode.DARK
            self.dark_light_text.value = self._["dark_theme"]
            self.dark_light_icon.icon = ft.Icons.BRIGHTNESS_HIGH_OUTLINED
            self.dark_light_icon.tooltip = self._["toggle_day_theme"]
            self.app.settings.user_config["theme_mode"] = "dark"
        else:
            page.theme_mode = ft.ThemeMode.LIGHT
            self.dark_light_text.value = self._["light_theme"]
            self.dark_light_icon.icon = ft.Icons.BRIGHTNESS_2_OUTLINED
            self.dark_light_icon.tooltip = self._["toggle_night_theme"]
            self.app.settings.user_config["theme_mode"] = "light"
        self.app.services.run_coro(self.app.config_manager.save_user_config(self.app.settings.user_config))
        await self.on_theme_change()
        page.update()

    async def on_theme_change(self):
        """When the theme changes, recreate the content and update the page"""
        page_list = ["home", "about"]
        if self.app.current_page.page_name in page_list:
            await self.app.current_page.load()


class NavigationSidebar:
    def __init__(self, app):
        self.app = app
        self.control_groups = []
        self.selected_control_group = None
        self.app.language_manager.add_observer(self)
        self._ = {}
        self.load()

    def load(self):
        self._ = self.app.language_manager.language.get("sidebar")
        self.control_groups = [
            ControlGroup(icon=ft.Icons.HOME, label=self._["home"], index=0, name="home", selected_icon=ft.Icons.HOME),
            ControlGroup(
                icon=ft.Icons.DASHBOARD,
                label=self._["recordings"],
                index=1,
                name="recordings",
                selected_icon=ft.Icons.DASHBOARD_ROUNDED,
            ),
            ControlGroup(
                icon=ft.Icons.SETTINGS,
                label=self._["settings"],
                index=2,
                name="settings",
                selected_icon=ft.Icons.SETTINGS,
            ),
            ControlGroup(
                icon=ft.Icons.DRIVE_FILE_MOVE,
                label=self._["storage"],
                index=3,
                name="storage",
                selected_icon=ft.Icons.DRIVE_FILE_MOVE_OUTLINE,
            ),
            ControlGroup(
                icon=ft.Icons.HISTORY,
                label=self._["logs"],
                index=4,
                name="logs",
                selected_icon=ft.Icons.HISTORY,
            ),
            ControlGroup(icon=ft.Icons.INFO, label=self._["about"], index=5, name="about", selected_icon=ft.Icons.INFO),
        ]
        self.selected_control_group = self.control_groups[0]
