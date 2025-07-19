import flet as ft


class ShowSnackBar:
    def __init__(self, app):
        self.app = app

    async def show_snack_bar(self, message, bgcolor=None, duration=1500, action=None, emoji=None,
                             show_close_icon=False):
        """Helper method to show a snack bar with optional emoji."""

        message_row = ft.Row(
            controls=[
                ft.Icon(name=ft.icons.NOTIFICATIONS, color=ft.colors.SURFACE_VARIANT, size=20) if not emoji else
                ft.Text(emoji, size=20),
                ft.Text(message, size=14),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )

        snack_bar = ft.SnackBar(
            content=ft.Container(
                content=ft.Row(
                    controls=[
                        message_row,
                        ft.IconButton(
                            icon=ft.icons.CLOSE,
                            icon_size=16,
                            on_click=lambda e: setattr(snack_bar, "open", False),
                            visible=show_close_icon
                        )
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                ),
                padding=10,
                border_radius=8
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
            snack_bar.margin = ft.margin.only(left=self.app.page.width - 300, top=0, right=10, bottom=10)

        snack_bar.open = True
        self.app.snack_bar_area.content = snack_bar
        self.app.page.update() 