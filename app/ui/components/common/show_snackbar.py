import flet as ft


class ShowSnackBar:
    def __init__(self, app):
        self.app = app

    async def show_snack_bar(
        self, message, bgcolor=None, duration=1500, action=None, emoji=None, show_close_icon=False
    ):
        """Helper method to show a snack bar with optional emoji."""

        message_row = ft.Row(
            controls=[
                ft.Icon(icon=ft.Icons.NOTIFICATIONS, color=ft.Colors.ON_SURFACE_VARIANT, size=18)
                if not emoji
                else ft.Text(emoji, size=20, no_wrap=False),
                ft.Text(message, size=14, no_wrap=False),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            wrap=True,
            width=235 if show_close_icon else 285,
            auto_scroll=True,
        )

        snack_bar = ft.SnackBar(
            content=ft.Container(
                content=ft.Row(
                    controls=[message_row],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=10,
                border_radius=8,
            ),
            behavior=ft.SnackBarBehavior.FLOATING,
            action=action,
            bgcolor=bgcolor,
            duration=duration,
            show_close_icon=show_close_icon,
        )

        if self.app.page.theme_mode == ft.ThemeMode.DARK:
            snack_bar.bgcolor = "#F5F5F5"

        if not self.app.is_mobile:
            snack_bar_width = 350
            snack_bar.margin = ft.margin.only(left=self.app.page.width - snack_bar_width, top=0, right=10, bottom=10)

        snack_bar.open = True
        self.app.snack_bar_area.content = snack_bar
        self.app.page.update()
