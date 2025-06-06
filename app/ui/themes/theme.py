import flet as ft


class PopupColorItem(ft.PopupMenuItem):
    def __init__(self, color, name):
        super().__init__()
        icon_color = "#36618e" if color == "" else color
        self.content = ft.Row(
            controls=[
                ft.Icon(name=ft.Icons.COLOR_LENS_OUTLINED, color=icon_color),
                ft.Text(name),
            ],
        )
        self.on_click = lambda e: self.seed_color_changed(e)
        self.data = color

    def seed_color_changed(self, e):
        page = e.page
        page.theme.color_scheme_seed = self.data
        page.theme.color_scheme = ft.ColorScheme(primary=self.data)
        page.update()
        self.save_theme_color(e)

    def save_theme_color(self, e):
        page = e.page
        app = page.data
        app.settings.user_config["theme_color"] = self.data
        page.run_task(app.config_manager.save_user_config, app.settings.user_config)


def create_light_theme(custom_font: str) -> ft.Theme:
    """Define light colored theme"""
    return ft.Theme(
        font_family=custom_font,
        text_theme=ft.TextTheme(
            body_medium=ft.TextStyle(color=ft.Colors.BLACK, font_family=custom_font),
            body_large=ft.TextStyle(color=ft.Colors.BLACK, font_family=custom_font),
            display_small=ft.TextStyle(color=ft.Colors.BLACK, font_family=custom_font),
            display_medium=ft.TextStyle(color=ft.Colors.BLACK, font_family=custom_font),
            display_large=ft.TextStyle(color=ft.Colors.BLACK, font_family=custom_font),
            headline_small=ft.TextStyle(color=ft.Colors.BLACK, font_family=custom_font),
            headline_medium=ft.TextStyle(color=ft.Colors.BLACK, font_family=custom_font),
            headline_large=ft.TextStyle(color=ft.Colors.BLACK, font_family=custom_font),
            title_small=ft.TextStyle(color=ft.Colors.BLACK, font_family=custom_font),
            title_medium=ft.TextStyle(color=ft.Colors.BLACK, font_family=custom_font),
            title_large=ft.TextStyle(color=ft.Colors.BLACK, font_family=custom_font),
            label_small=ft.TextStyle(color=ft.Colors.BLACK, font_family=custom_font),
            label_medium=ft.TextStyle(color=ft.Colors.BLACK, font_family=custom_font),
            label_large=ft.TextStyle(color=ft.Colors.BLACK, font_family=custom_font),
        ),
    )


def create_dark_theme(custom_font: str) -> ft.Theme:
    """Define dark theme"""
    return ft.Theme(
        font_family=custom_font,
        text_theme=ft.TextTheme(
            body_medium=ft.TextStyle(color=ft.Colors.WHITE, font_family=custom_font),
            body_large=ft.TextStyle(color=ft.Colors.WHITE, font_family=custom_font),
            display_small=ft.TextStyle(color=ft.Colors.WHITE, font_family=custom_font),
            display_medium=ft.TextStyle(color=ft.Colors.WHITE, font_family=custom_font),
            display_large=ft.TextStyle(color=ft.Colors.WHITE, font_family=custom_font),
            headline_small=ft.TextStyle(color=ft.Colors.WHITE, font_family=custom_font),
            headline_medium=ft.TextStyle(color=ft.Colors.WHITE, font_family=custom_font),
            headline_large=ft.TextStyle(color=ft.Colors.WHITE, font_family=custom_font),
            title_small=ft.TextStyle(color=ft.Colors.WHITE, font_family=custom_font),
            title_medium=ft.TextStyle(color=ft.Colors.WHITE, font_family=custom_font),
            title_large=ft.TextStyle(color=ft.Colors.WHITE, font_family=custom_font),
            label_small=ft.TextStyle(color=ft.Colors.WHITE, font_family=custom_font),
            label_medium=ft.TextStyle(color=ft.Colors.WHITE, font_family=custom_font),
            label_large=ft.TextStyle(color=ft.Colors.WHITE, font_family=custom_font),
        ),
    )
