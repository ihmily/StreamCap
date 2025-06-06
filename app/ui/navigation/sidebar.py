import flet as ft

from ..themes import PopupColorItem, ThemeManager


class ControlGroup:
    def __init__(self, icon, label, index, name, selected_icon):
        self.icon = icon
        self.label = label
        self.index = index
        self.name = name
        self.selected_icon = selected_icon


class NavigationItem(ft.Container):
    def __init__(self, destination, item_clicked):
        super().__init__()
        self.ink = True
        self.padding = 10
        self.border_radius = 5
        self.destination = destination
        self.icon = destination.icon
        self.text = destination.label
        self.content = ft.Row([ft.Icon(self.icon), ft.Text(self.text)])
        self.on_click = lambda e: item_clicked(e)


class NavigationColumn(ft.Column):
    def __init__(self, sidebar, page, app):
        super().__init__()
        self.expand = 4
        self.spacing = 0
        self.scroll = ft.ScrollMode.ALWAYS
        self.sidebar = sidebar
        self.selected_index = 0
        self.page = page
        self.app = app
        self.controls = self.get_navigation_items()

    def get_navigation_items(self):
        return [
            NavigationItem(destination, item_clicked=self.item_clicked) for destination in self.sidebar.control_groups
        ]

    def item_clicked(self, e):
        self.selected_index = e.control.destination.index
        self.update_selected_item()
        self.page.go(f"/{e.control.destination.name}")

    def update_selected_item(self):
        for item in self.controls:
            item.bgcolor = None
            item.content.controls[0].icon = item.destination.icon
        if 0 <= self.selected_index < len(self.controls):
            self.controls[self.selected_index].bgcolor = ft.Colors.SECONDARY_CONTAINER
            self.controls[self.selected_index].content.controls[0].icon = self.controls[
                self.selected_index
            ].destination.selected_icon


class LeftNavigationMenu(ft.Column):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.sidebar = app.sidebar
        self.page = app.page
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
        self.rail = NavigationColumn(sidebar=self.sidebar, page=self.page, app=self.app)

        if self.page.theme_mode == ft.ThemeMode.DARK:
            self.dark_light_text = ft.Text(self._["dark_theme"])
            self.dark_light_icon = ft.IconButton(
                icon=ft.Icons.BRIGHTNESS_HIGH_OUTLINED,
                tooltip=self._["toggle_day_theme"],
                on_click=self.theme_changed,
            )
        else:
            self.dark_light_text = ft.Text(self._["light_theme"])
            self.dark_light_icon = ft.IconButton(
                icon=ft.Icons.BRIGHTNESS_2_OUTLINED,
                tooltip=self._["toggle_night_theme"],
                on_click=self.theme_changed,
            )

        color_names = {
            "deeppurple": {"zh": "深紫色", "en": "Deep purple"},
            "purple": {"zh": "紫色", "en": "Purple"},
            "indigo": {"zh": "靛蓝", "en": "Indigo"},
            "blue": {"zh": "蓝色", "en": "Blue"},
            "teal": {"zh": "蓝绿色", "en": "Teal"},
            "deeporange": {"zh": "深橙色", "en": "Deep orange"},
            "orange": {"zh": "橙色", "en": "Orange"},
            "pink": {"zh": "粉色", "en": "Pink"},
            "brown": {"zh": "棕色", "en": "Brown"},
            "bluegrey": {"zh": "蓝灰色", "en": "Blue Grey"},
            "green": {"zh": "绿色", "en": "Green"},
            "cyan": {"zh": "青色", "en": "Cyan"},
            "lightblue": {"zh": "浅蓝色", "en": "Light Blue"},
            "": {"zh": "默认", "en": "Default"},
        }
        lang = self.app.language_code if hasattr(self.app, 'language_code') else 'zh_CN'
        if lang.startswith('zh'):
            lang_key = 'zh'
        else:
            lang_key = 'en'
        colors_list = [(color, color_names[color].get(lang_key, color_names[color]["en"])) for color in color_names]

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
                            tooltip=self._["colors"],
                            items=[PopupColorItem(color=color, name=name) for color, name in colors_list],
                        ),
                        ft.Text(self._["theme_color"]),
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
        self.page.run_task(self.app.config_manager.save_user_config, self.app.settings.user_config)
        await self.on_theme_change()
        page.update()

    async def on_theme_change(self):
        """When the theme changes, recreate the content and update the page"""
        if self.app.current_page.page_name == "about":
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
                icon=ft.Icons.SETTINGS,
                label=self._["settings"],
                index=1,
                name="settings",
                selected_icon=ft.Icons.SETTINGS,
            ),
            ControlGroup(
                icon=ft.Icons.DRIVE_FILE_MOVE,
                label=self._["storage"],
                index=2,
                name="storage",
                selected_icon=ft.Icons.DRIVE_FILE_MOVE_OUTLINE
            ),
            ControlGroup(icon=ft.Icons.INFO, label=self._["about"], index=3, name="about", selected_icon=ft.Icons.INFO),
        ]
        self.selected_control_group = self.control_groups[0]
