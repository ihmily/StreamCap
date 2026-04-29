import os
from datetime import datetime

import flet as ft

from ..base_page import PageBase


class HomePage(PageBase):
    def __init__(self, app):
        super().__init__(app)
        self.page_name = "home"
        self.app.language_manager.add_observer(self)
        self.load_language()
        self.init()

    def load_language(self):
        language = self.app.language_manager.language
        for key in ("home_page", "base"):
            self._.update(language.get(key, {}))

    def init(self):
        pass

    async def load(self):
        self.content_area.controls.clear()

        home_content = ft.Column(
            controls=[
                self.create_home_header(),
                self.create_quick_action_area(),
                self.create_announcements_area(),
                self.create_stats_area(),
                self.create_features_area(),
            ],
            spacing=20,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        self.content_area.controls.append(home_content)
        self.content_area.update()

    def create_home_header(self):
        logo_path = os.path.join("icons", "loading-animation.png")

        logo = ft.Image(
            src=logo_path,
            width=120,
            height=120,
            fit=ft.BoxFit.CONTAIN,
        )

        current_hour = datetime.now().hour
        greeting = self._["greeting_afternoon"]
        if 5 <= current_hour < 12:
            greeting = self._["greeting_morning"]
        elif current_hour >= 18 or current_hour < 5:
            greeting = self._["greeting_evening"]

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=logo,
                        alignment=ft.alignment.Alignment.CENTER,
                        margin=ft.margin.only(top=30, bottom=10),
                    ),
                    ft.Text(
                        f"{greeting}，{self._['welcome']}",
                        size=32,
                        weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        self._["tagline"],
                        size=18,
                        color=(
                            ft.Colors.BLACK87 if self.app.page.theme_mode == ft.ThemeMode.LIGHT else ft.Colors.WHITE70
                        ),
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        self._["version"] + ":" + self.app.about.about_config["version_updates"][0]["version"],
                        size=14,
                        color=(
                            ft.Colors.BLACK54 if self.app.page.theme_mode == ft.ThemeMode.LIGHT else ft.Colors.WHITE60
                        ),
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=10,
            ),
            alignment=ft.alignment.Alignment.CENTER,
            padding=ft.padding.only(bottom=20),
        )

    def create_quick_action_area(self):
        is_mobile = self.app.is_mobile or self.page.width < 600

        button_width = 150 if is_mobile else 180
        button_height = 50 if is_mobile else 60
        button_spacing = 10 if is_mobile else 20

        if is_mobile:
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                self.create_action_button(
                                    self._["start_recording"],
                                    ft.Icons.PLAY_CIRCLE_FILL_ROUNDED,
                                    ft.Colors.GREEN,
                                    self.on_start_recording_click,
                                    width=button_width,
                                    height=button_height,
                                ),
                                self.create_action_button(
                                    self._["recording_list"],
                                    ft.Icons.STORAGE_ROUNDED,
                                    ft.Colors.BLUE,
                                    self.on_browse_recordings_click,
                                    width=button_width,
                                    height=button_height,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            spacing=button_spacing,
                            wrap=True,
                        ),
                        ft.Row(
                            controls=[
                                self.create_action_button(
                                    self._["browse_recordings"],
                                    ft.Icons.FOLDER_OPEN_ROUNDED,
                                    ft.Colors.AMBER,
                                    self.on_manage_storage_click,
                                    width=button_width,
                                    height=button_height,
                                ),
                                self.create_action_button(
                                    self._["settings"],
                                    ft.Icons.SETTINGS_ROUNDED,
                                    ft.Colors.GREY,
                                    self.on_settings_click,
                                    width=button_width,
                                    height=button_height,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            spacing=button_spacing,
                            wrap=True,
                        ),
                        ft.Container(
                            content=self.create_action_button(
                                self._["about"],
                                ft.Icons.INFO_ROUNDED,
                                ft.Colors.PURPLE,
                                self.on_about_click,
                                width=button_width,
                                height=button_height,
                            ),
                            alignment=ft.alignment.Alignment.CENTER,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=10,
                ),
                alignment=ft.alignment.Alignment.CENTER,
                padding=ft.padding.only(bottom=20),
            )
        else:
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Container(
                            content=ft.Row(
                                controls=[
                                    self.create_action_button(
                                        self._["start_recording"],
                                        ft.Icons.PLAY_CIRCLE_FILL_ROUNDED,
                                        ft.Colors.GREEN,
                                        self.on_start_recording_click,
                                        width=button_width,
                                        height=button_height,
                                    ),
                                    self.create_action_button(
                                        self._["recording_list"],
                                        ft.Icons.STORAGE_ROUNDED,
                                        ft.Colors.BLUE,
                                        self.on_browse_recordings_click,
                                        width=button_width,
                                        height=button_height,
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.CENTER,
                                spacing=button_spacing,
                            ),
                            margin=ft.margin.only(bottom=10),
                        ),
                        ft.Container(
                            content=ft.Row(
                                controls=[
                                    self.create_action_button(
                                        self._["browse_recordings"],
                                        ft.Icons.FOLDER_OPEN_ROUNDED,
                                        ft.Colors.AMBER,
                                        self.on_manage_storage_click,
                                        width=button_width,
                                        height=button_height,
                                    ),
                                    self.create_action_button(
                                        self._["settings"],
                                        ft.Icons.SETTINGS_ROUNDED,
                                        ft.Colors.GREY,
                                        self.on_settings_click,
                                        width=button_width,
                                        height=button_height,
                                    ),
                                    self.create_action_button(
                                        self._["about"],
                                        ft.Icons.INFO_ROUNDED,
                                        ft.Colors.PURPLE,
                                        self.on_about_click,
                                        width=button_width,
                                        height=button_height,
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.CENTER,
                                spacing=button_spacing,
                            ),
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                alignment=ft.alignment.Alignment.CENTER,
                padding=ft.padding.only(bottom=20),
            )

    @staticmethod
    def create_action_button(text: str, icon: ft.IconData, color: ft.Colors, on_click: callable, width=180, height=60):
        return ft.Button(
            content=ft.Row(
                controls=[
                    ft.Icon(icon, color=ft.Colors.WHITE),
                    ft.Text(
                        text,
                        color=ft.Colors.WHITE,
                        size=14,
                        weight=ft.FontWeight.W_500,
                    ),
                ],
                spacing=8,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=ft.padding.all(15),
                bgcolor=color,
                elevation=5,
            ),
            on_click=on_click,
            height=height,
            width=width,
        )

    def create_announcements_area(self):
        def create_announcement_card(title: str, content: str, icon: ft.IconData, color: ft.Colors):
            return ft.Card(
                content=ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Icon(icon, color=color, size=24),
                                    ft.Text(
                                        title,
                                        weight=ft.FontWeight.BOLD,
                                        size=16,
                                    ),
                                ],
                                spacing=10,
                            ),
                            ft.Container(
                                content=ft.Text(
                                    content,
                                    size=14,
                                    color=(
                                        ft.Colors.BLACK87
                                        if self.app.page.theme_mode == ft.ThemeMode.LIGHT
                                        else ft.Colors.WHITE70
                                    ),
                                ),
                                margin=ft.margin.only(left=34),
                            ),
                        ],
                        spacing=5,
                    ),
                    padding=ft.padding.all(15),
                ),
                elevation=2,
                margin=ft.margin.only(bottom=5),
            )

        announcement_list = self.app.about.about_config["version_updates"][0]["announcement"][self.app.language_code]
        announcements = [
            create_announcement_card(
                announcement_list[0]["title"],
                announcement_list[0]["content"],
                ft.Icons.NEW_RELEASES_ROUNDED,
                ft.Colors.GREEN,
            ),
            create_announcement_card(
                announcement_list[1]["title"],
                announcement_list[1]["content"],
                ft.Icons.LIGHTBULB_OUTLINE_ROUNDED,
                ft.Colors.AMBER,
            ),
            create_announcement_card(
                announcement_list[2]["title"],
                announcement_list[2]["content"],
                ft.Icons.UPCOMING_ROUNDED,
                ft.Colors.BLUE,
            ),
        ]

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        self._["announcement"],
                        size=20,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Container(
                        content=ft.Column(
                            controls=announcements,
                            spacing=5,
                        ),
                        padding=ft.padding.only(top=5),
                    ),
                ],
                spacing=5,
            ),
            padding=ft.padding.only(left=20, right=20),
        )

    def create_stats_area(self):
        total_recordings = len(self.app.record_manager.recordings)
        active_recordings = len([r for r in self.app.record_manager.recordings if r.is_recording])

        stopped_recordings = total_recordings - active_recordings

        def create_stat_item(title, value, icon, color):
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(icon, size=36, color=color),
                        ft.Text(str(value), size=24, weight=ft.FontWeight.BOLD),
                        ft.Text(title, size=14),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=5,
                ),
                padding=ft.padding.all(15),
                border_radius=10,
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                width=150,
                height=130,
            )

        recent_recordings = []
        if total_recordings > 0:
            sorted_recordings = sorted(
                self.app.record_manager.recordings,
                key=lambda r: r.last_updated if hasattr(r, "last_updated") else 0,
                reverse=True,
            )[-3:][::-1]

            for rec in sorted_recordings:
                status_icon = ft.Icons.CIRCLE
                status_color = ft.Colors.GREY

                if hasattr(rec, "status"):
                    if rec.status == "recording":
                        status_icon = ft.Icons.CIRCLE
                        status_color = ft.Colors.GREEN
                    elif rec.status == "living":
                        status_icon = ft.Icons.LIVE_TV
                        status_color = ft.Colors.BLUE
                    elif rec.status == "error":
                        status_icon = ft.Icons.ERROR_OUTLINE
                        status_color = ft.Colors.RED
                    elif rec.status == "offline":
                        status_icon = ft.Icons.OFFLINE_BOLT
                        status_color = ft.Colors.AMBER

                recent_recordings.append(
                    ft.Row(
                        controls=[
                            ft.Icon(status_icon, color=status_color, size=16),
                            ft.Text(
                                rec.streamer_name if hasattr(rec, "streamer_name") else "未命名录制",
                                size=14,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ],
                        spacing=10,
                    )
                )
        else:
            recent_recordings.append(
                ft.Text(
                    self._["no_recordings"],
                    size=14,
                    italic=True,
                    color=ft.Colors.BLACK45 if self.app.page.theme_mode == ft.ThemeMode.LIGHT else ft.Colors.WHITE60,
                )
            )

        recent_recordings_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        self._["recent_added_recordings"],
                        size=16,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Container(
                        content=ft.Column(
                            controls=recent_recordings,
                            spacing=8,
                        ),
                        padding=ft.padding.only(top=5),
                    ),
                ],
                spacing=5,
                alignment=ft.MainAxisAlignment.START,
                horizontal_alignment=ft.CrossAxisAlignment.START,
            ),
            padding=ft.padding.all(15),
            border_radius=10,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            expand=True,
            height=130,
        )

        is_mobile = self.app.is_mobile or self.page.width < 600

        if is_mobile:
            stat_row1 = ft.Row(
                controls=[
                    create_stat_item(
                        self._["total_rooms"],
                        total_recordings,
                        ft.Icons.VIDEO_FILE_ROUNDED,
                        ft.Colors.BLUE,
                    ),
                    create_stat_item(
                        self._["active_recordings"],
                        active_recordings,
                        ft.Icons.FIBER_MANUAL_RECORD_ROUNDED,
                        ft.Colors.GREEN,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                spacing=10,
            )

            stat_row2 = ft.Row(
                controls=[
                    create_stat_item(
                        self._["stop_monitoring"],
                        stopped_recordings,
                        ft.Icons.STOP_CIRCLE,
                        ft.Colors.RED,
                    ),
                ],
                alignment=ft.MainAxisAlignment.START,
                spacing=10,
            )

            stats_content = ft.Column(
                controls=[
                    stat_row1,
                    stat_row2,
                    recent_recordings_card,
                ],
                spacing=10,
            )
        else:
            stats_content = ft.Row(
                controls=[
                    create_stat_item(
                        self._["total_rooms"],
                        total_recordings,
                        ft.Icons.VIDEO_FILE_ROUNDED,
                        ft.Colors.BLUE,
                    ),
                    create_stat_item(
                        self._["active_recordings"],
                        active_recordings,
                        ft.Icons.FIBER_MANUAL_RECORD_ROUNDED,
                        ft.Colors.GREEN,
                    ),
                    create_stat_item(
                        self._["stop_monitoring"],
                        stopped_recordings,
                        ft.Icons.STOP_CIRCLE,
                        ft.Colors.RED,
                    ),
                    recent_recordings_card,
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=15,
            )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        self._["stats"],
                        size=20,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Container(
                        content=stats_content,
                        padding=ft.padding.only(top=10),
                    ),
                ],
                spacing=5,
            ),
            padding=ft.padding.only(left=20, right=20),
        )

    def create_features_area(self):
        is_mobile = self.app.is_mobile or self.page.width < 600

        def create_feature_card(title, description, icon, color):
            return ft.Card(
                content=ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(
                                icon,
                                size=40,
                                color=color,
                            ),
                            ft.Text(
                                title,
                                size=16,
                                weight=ft.FontWeight.BOLD,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            ft.Text(
                                description,
                                size=13,
                                text_align=ft.TextAlign.CENTER,
                                color=(
                                    ft.Colors.BLACK54
                                    if self.app.page.theme_mode == ft.ThemeMode.LIGHT
                                    else ft.Colors.WHITE70
                                ),
                            ),
                        ],
                        spacing=8,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    padding=ft.padding.all(15),
                    alignment=ft.alignment.Alignment.CENTER,
                    width=None if is_mobile else 220,
                    expand=is_mobile,
                ),
                elevation=3,
            )

        if is_mobile:
            feature_cards = ft.Column(
                controls=[
                    create_feature_card(
                        self._["feature_title_1"],
                        self._["feature_desc_1"],
                        ft.Icons.VIDEO_CAMERA_BACK_ROUNDED,
                        ft.Colors.GREEN,
                    ),
                    create_feature_card(
                        self._["feature_title_2"],
                        self._["feature_desc_2"],
                        ft.Icons.MESSAGE_ROUNDED,
                        ft.Colors.BLUE,
                    ),
                    create_feature_card(
                        self._["feature_title_3"],
                        self._["feature_desc_3"],
                        ft.Icons.QUEUE_ROUNDED,
                        ft.Colors.PURPLE,
                    ),
                    create_feature_card(
                        self._["feature_title_4"],
                        self._["feature_desc_4"],
                        ft.Icons.SCHEDULE_ROUNDED,
                        ft.Colors.ORANGE,
                    ),
                ],
                spacing=10,
                expand=True,
            )
        else:
            feature_cards = ft.Row(
                controls=[
                    create_feature_card(
                        self._["feature_title_1"],
                        self._["feature_desc_1"],
                        ft.Icons.VIDEO_CAMERA_BACK_ROUNDED,
                        ft.Colors.GREEN,
                    ),
                    create_feature_card(
                        self._["feature_title_2"],
                        self._["feature_desc_2"],
                        ft.Icons.NOTIFICATIONS_ACTIVE_ROUNDED,
                        ft.Colors.BLUE,
                    ),
                    create_feature_card(
                        self._["feature_title_3"],
                        self._["feature_desc_3"],
                        ft.Icons.QUEUE_ROUNDED,
                        ft.Colors.PURPLE,
                    ),
                    create_feature_card(
                        self._["feature_title_4"],
                        self._["feature_desc_4"],
                        ft.Icons.SCHEDULE_ROUNDED,
                        ft.Colors.ORANGE,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                spacing=15,
                wrap=True,
            )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        self._["main_features"],
                        size=20,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Container(
                        content=feature_cards,
                        padding=ft.padding.only(top=10),
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.START,
            ),
            alignment=ft.alignment.Alignment.BOTTOM_LEFT,
            padding=ft.padding.only(left=20, right=20, bottom=30),
        )

    async def on_start_recording_click(self, _):
        self.app.page.go("/recordings")
        await self.app.recordings.add_recording_on_click(None)

    async def on_browse_recordings_click(self, _):
        self.app.page.go("/recordings")

    async def on_manage_storage_click(self, _):
        self.app.page.go("/storage")

    async def on_settings_click(self, _):
        self.app.page.go("/settings")

    async def on_about_click(self, _):
        self.app.page.go("/about")
