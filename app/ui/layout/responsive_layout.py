import flet as ft

from ...app_manager import App
from ...utils.logger import logger


def is_mobile_device(page: ft.Page) -> bool:
    return page.width < 768


def setup_responsive_layout(page: ft.Page, app: App) -> None:
    _ = app.language_manager.language.get("sidebar", {})

    if is_mobile_device(page):
        logger.info("mobile device detected, enable mobile layout")
        app.is_mobile = True
        app.left_navigation_menu.width = 0
        app.left_navigation_menu.visible = False

        app.bottom_navigation = ft.NavigationBar(
            destinations=[
                ft.NavigationBarDestination(icon=ft.Icons.HOME, label=_["home"]),
                ft.NavigationBarDestination(icon=ft.Icons.DASHBOARD_ROUNDED, label=_["recordings"]),
                ft.NavigationBarDestination(icon=ft.Icons.SETTINGS, label=_["settings"]),
                ft.NavigationBarDestination(icon=ft.Icons.DRIVE_FILE_MOVE, label=_["storage"]),
                ft.NavigationBarDestination(icon=ft.Icons.INFO, label=_["about"]),
            ],
            on_change=lambda e: page.go(
                f"/{['home', 'recordings', 'settings', 'storage', 'about'][e.control.selected_index]}"
            ),
        )

        app.content_area.expand = True

        app.complete_page = ft.Column(
            expand=True,
            spacing=0,
            controls=[app.content_area, app.bottom_navigation, app.dialog_area, app.snack_bar_area],
        )
    else:
        logger.info("desktop device detected, enable desktop layout")
        app.is_mobile = False
        app.complete_page = ft.Row(
            expand=True,
            controls=[
                app.left_navigation_menu,
                ft.VerticalDivider(width=1),
                app.content_area,
                app.dialog_area,
                app.snack_bar_area,
            ],
        )
