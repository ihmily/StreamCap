import flet as ft

from ..base_page import PageBase
from ..components.dialogs.help_dialog import HelpDialog


class AboutPage(PageBase):
    def __init__(self, app):
        super().__init__(app)
        self.page_name = "about"
        self.about_config = {}
        self.app.language_manager.add_observer(self)
        self.load_language()
        self.page.on_keyboard_event = self.on_keyboard

    def load_language(self):
        self._ = self.app.language_manager.language.get("about_page")
        self.about_config = self.app.config_manager.load_about_config()

    async def load(self):
        """Load the about page content."""
        self.content_area.clean()

        is_mobile = self.app.is_mobile

        # Dynamically set colors based on the current theme mode
        theme_mode = self.page.theme_mode
        if theme_mode == ft.ThemeMode.DARK:
            card_bg_color = None
            text_color = None
            text_color_500 = None
            text_color_600 = None
            text_color_700 = None
        else:
            card_bg_color = ft.Colors.WHITE
            text_color = ft.Colors.GREY_800
            text_color_500 = ft.Colors.GREY_500
            text_color_600 = ft.Colors.GREY_600
            text_color_700 = ft.Colors.GREY_700

        language_code = self.app.language_code
        version_updates = self.about_config["version_updates"][0]
        open_source_license = self.about_config["open_source_license"]

        if is_mobile:
            feature_highlights = ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Column(
                                controls=[
                                    ft.Icon(ft.Icons.VIDEO_LIBRARY, color=ft.Colors.BLUE),
                                    ft.Text(self._["support_platforms"],
                                            size=12,
                                            color=text_color_700,
                                            text_align=ft.TextAlign.CENTER),
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=5,
                                width=95,
                            ),
                            ft.Column(
                                controls=[
                                    ft.Icon(ft.Icons.SETTINGS, color=ft.Colors.GREEN),
                                    ft.Text(self._["customize_recording"],
                                            size=12,
                                            color=text_color_700,
                                            text_align=ft.TextAlign.CENTER),
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=5,
                                width=95,
                            ),
                            ft.Column(
                                controls=[
                                    ft.Icon(ft.Icons.LIGHTBULB, color=ft.Colors.ORANGE),
                                    ft.Text(self._["open_source"],
                                            size=12,
                                            color=text_color_700,
                                            text_align=ft.TextAlign.CENTER),
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=5,
                                width=95,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_AROUND,
                        spacing=5,
                    ),
                    ft.Row(
                        controls=[
                            ft.Column(
                                controls=[
                                    ft.Icon(ft.Icons.AUTORENEW, color=ft.Colors.PURPLE),
                                    ft.Text(self._["automatic_transcoding"],
                                            size=12,
                                            color=text_color_700,
                                            text_align=ft.TextAlign.CENTER),
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=5,
                                width=140,
                            ),
                            ft.Column(
                                controls=[
                                    ft.Icon(ft.Icons.NOTIFICATIONS_ACTIVE, color=ft.Colors.RED),
                                    ft.Text(self._["status_push"],
                                            size=12,
                                            color=text_color_700,
                                            text_align=ft.TextAlign.CENTER),
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=5,
                                width=140,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_AROUND,
                        spacing=5,
                    ),
                ],
                spacing=20,
                alignment=ft.MainAxisAlignment.CENTER,
            )
        else:
            feature_highlights = ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.VIDEO_LIBRARY, color=ft.Colors.BLUE),
                            ft.Text(self._["support_platforms"], size=14, color=text_color_700),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.SETTINGS, color=ft.Colors.GREEN),
                            ft.Text(self._["customize_recording"], size=14, color=text_color_700),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.LIGHTBULB, color=ft.Colors.ORANGE),
                            ft.Text(self._["open_source"], size=14, color=text_color_700),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.AUTORENEW, color=ft.Colors.PURPLE),
                            ft.Text(self._["automatic_transcoding"], size=14, color=text_color_700),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.NOTIFICATIONS_ACTIVE, color=ft.Colors.RED),
                            ft.Text(self._["status_push"], size=14, color=text_color_700),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=100,
            )

        if is_mobile:
            developer_buttons = ft.Column(
                controls=[
                    ft.ElevatedButton(
                        text=self._["view_update"],
                        icon=ft.Icons.CODE,
                        on_click=self.open_update_page,
                        width=float("inf"),
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=8),
                            padding=10,
                        ),
                    ),
                    ft.ElevatedButton(
                        text=self._["view_docs"],
                        icon=ft.Icons.DESCRIPTION,
                        on_click=self.open_dos_page,
                        width=float("inf"),
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=8),
                            padding=10,
                        ),
                    ),
                    ft.ElevatedButton(
                        text=self.app.language_manager.language.get("update", {}).get("check_update"),
                        icon=ft.Icons.UPDATE,
                        on_click=self._check_for_updates,
                        width=float("inf"),
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=8),
                            padding=10,
                        ),
                    ),
                ],
                spacing=10,
                alignment=ft.MainAxisAlignment.CENTER,
                width=float("inf"),
            )
        else:
            developer_buttons = ft.Row(
                controls=[
                    ft.TextButton(
                        self._["view_update"],
                        icon=ft.Icons.CODE,
                        on_click=self.open_update_page,
                    ),
                    ft.TextButton(
                        self._["view_docs"],
                        icon=ft.Icons.DESCRIPTION,
                        on_click=self.open_dos_page,
                    ),
                    ft.TextButton(
                        self.app.language_manager.language.get("update", {}).get("check_update"),
                        icon=ft.Icons.UPDATE,
                        on_click=self._check_for_updates,
                    ),
                ],
                alignment=ft.MainAxisAlignment.START,
            )

        about_page_layout = ft.Container(
            content=ft.Column(
                scroll=ft.ScrollMode.AUTO if not is_mobile else ft.ScrollMode.HIDDEN,
                controls=[
                    # Title and version information
                    ft.Text(
                        self._["about_project"],
                        size=32,
                        weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.CENTER,
                        color=ft.Colors.PRIMARY,
                    ),
                    ft.Text(
                        f"{self._['ui_version']}: {version_updates['version']} | "
                        f"{self._['kernel_version']}: {version_updates['kernel_version']} | "
                        f"{self._['license']}: {open_source_license}",
                        size=14 if not is_mobile else 12,
                        text_align=ft.TextAlign.CENTER,
                        color=text_color_500,
                    ),
                    # Software Introduction Card
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(self._["introduction"], size=20, weight=ft.FontWeight.W_600, color=text_color),
                                ft.Text(
                                    self.about_config["introduction"].get(language_code),
                                    size=16,
                                    text_align=ft.TextAlign.JUSTIFY,
                                    color=text_color_600,
                                ),
                            ],
                            spacing=15,
                            expand=True,
                        ),
                        padding=20,
                        margin=ft.margin.symmetric(0, 10),
                        bgcolor=card_bg_color,
                        border_radius=15,
                        shadow=ft.BoxShadow(
                            spread_radius=1,
                            blur_radius=10,
                            color=ft.Colors.BLACK26,
                            offset=ft.Offset(0, 4),
                        ),
                    ),
                    # Feature Highlights Card
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(self._["feature"], size=20, weight=ft.FontWeight.W_600, color=text_color),
                                feature_highlights,
                            ],
                            spacing=15,
                            expand=True,
                        ),
                        padding=20,
                        margin=10,
                        bgcolor=card_bg_color,
                        border_radius=15,
                        shadow=ft.BoxShadow(
                            spread_radius=1,
                            blur_radius=10,
                            color=ft.Colors.BLACK26,
                            offset=ft.Offset(0, 4),
                        ),
                    ),
                    # Developer Information Card
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(self._["developer"], size=20, weight=ft.FontWeight.W_600, color=text_color),
                                ft.ListTile(
                                    leading=ft.Icon(ft.Icons.PERSON, color=ft.Colors.GREY_800),
                                    title=ft.Text("Hmily", size=18, weight=ft.FontWeight.W_500, color=text_color_700),
                                    subtitle=ft.Text(self._["author"], size=14, color=text_color_500),
                                ),
                                developer_buttons,
                            ],
                            spacing=10,
                            expand=True,
                        ),
                        padding=20,
                        margin=10,
                        bgcolor=card_bg_color,
                        border_radius=15,
                        shadow=ft.BoxShadow(
                            spread_radius=1,
                            blur_radius=10,
                            color=ft.Colors.BLACK26,
                            offset=ft.Offset(0, 4),
                        ),
                    ),
                    # Version update content card
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(self._["update"], size=20, weight=ft.FontWeight.W_600, color=text_color),
                                ft.ListView(
                                    controls=[
                                        ft.Text(update, size=16, text_align=ft.TextAlign.JUSTIFY, color=text_color_600)
                                        for update in version_updates["updates"][language_code]
                                    ],
                                    spacing=10,
                                    padding=0,
                                    expand=True,
                                ),
                            ],
                            spacing=15,
                            expand=True,
                        ),
                        padding=20,
                        margin=10,
                        bgcolor=card_bg_color,
                        border_radius=15,
                        shadow=ft.BoxShadow(
                            spread_radius=1,
                            blur_radius=10,
                            color=ft.Colors.BLACK26,
                            offset=ft.Offset(0, 4),
                        ),
                    ),
                    ft.Container(expand=True),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
            ),
            expand=True,
            padding=20,
        )

        self.content_area.controls.append(about_page_layout)
        self.content_area.update()

    @staticmethod
    async def open_update_page(e):
        url = "https://github.com/ihmily/StreamCap/releases"
        e.page.launch_url(url)

    @staticmethod
    async def open_dos_page(e):
        url = "https://github.com/ihmily/StreamCap/wiki"
        e.page.launch_url(url)

    async def on_keyboard(self, e: ft.KeyboardEvent):
        if e.alt and e.key == "H":
            self.app.dialog_area.content = HelpDialog(self.app)
            self.app.dialog_area.content.open = True
            self.app.dialog_area.update()
            
    async def _check_for_updates(self, _):
        _ = self.app.language_manager.language.get("update", {})
        await self.app.snack_bar.show_snack_bar(_.get("checking_update"))
        
        update_info = await self.app.update_checker.check_for_updates()
        
        if update_info.get("has_update", False):
            await self.app.update_checker.show_update_dialog(update_info)
        else:
            if "error" in update_info:
                await self.app.snack_bar.show_snack_bar(
                    f"{_.get('update_check_failed')}: {update_info.get('error', '')}")
            else:
                await self.app.snack_bar.show_snack_bar(_.get("no_update_available"))
