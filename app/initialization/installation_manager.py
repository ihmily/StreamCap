import flet as ft

from ..scripts.ffmpeg_install import check_ffmpeg_installed, install_ffmpeg
from ..scripts.node_install import check_nodejs_installed, install_nodejs
from ..utils.logger import logger


class InstallationManager:
    def __init__(self, app):
        self.app = app
        self.page: ft.Page = app.page
        self.install_dialog = None
        self.components_to_install = []
        self.completed_components = set()
        self.failed_components = set()
        self.app.language_manager.add_observer(self)
        self._ = {}
        self.load()

    def load(self):
        language = self.app.language_manager.language
        for key in ("base", "install_manager"):
            self._.update(language.get(key, {}))

    async def get_install_components(self):
        components = [
            {"name": "FFmpeg", "check_func": check_ffmpeg_installed, "install_func": install_ffmpeg},
            {"name": "Node.js", "check_func": check_nodejs_installed, "install_func": install_nodejs},
        ]
        for component in components:
            is_install = await component["check_func"]()
            if not is_install:
                self.components_to_install.append(component)

    async def install_component(self, component_info):
        install_func = component_info["name"]
        try:
            result = await component_info["install_func"](
                lambda progress, status: self.update_component_progress(install_func, progress, status)
            )
            if result:
                await self.update_component_progress(install_func, 1.0, self._["complete"])
                self.completed_components.add(install_func)
        except Exception as e:
            await self.update_component_progress(install_func, 0, f"{self._['error']}: {str(e)}")
            self.failed_components.add(install_func)

    async def install_components(self):
        left_btn = self.install_dialog.actions[0]
        right_btn = self.install_dialog.actions[1]

        left_btn.disabled = True
        left_btn.text = self._["installing"]
        self.page.update()

        for component in self.components_to_install:
            if component["name"] not in self.completed_components:
                await self.install_component(component)

        if len(self.completed_components) + len(self.failed_components) == len(self.components_to_install):
            right_btn.text = self._["close"]

            if self.failed_components:
                left_btn.icon = ft.Icons.REFRESH
                left_btn.text = self._["reinstall"]
                left_btn.disabled = False

                right_btn.icon = ft.Icons.ERROR_OUTLINED
                right_btn.style = ft.ButtonStyle(
                    color=ft.Colors.WHITE, bgcolor=ft.Colors.RED_400, icon_color=ft.Colors.RED_600)
            else:
                left_btn.text = self._["installed"]

                right_btn.icon = ft.Icons.CHECK_CIRCLE_OUTLINED
                right_btn.style = ft.ButtonStyle(
                    color=ft.Colors.WHITE, bgcolor=ft.Colors.GREEN_400, icon_color=ft.Colors.GREEN_600)
            self.page.update()

    async def update_component_progress(self, component_name, progress, status):
        components_container = self.install_dialog.content.controls[4]
        components_list = components_container.content

        for item in components_list.controls:
            if isinstance(item, ft.Row) and item.controls[0].controls[0].value == component_name:
                item.controls[1].controls[0].value = progress
                item.controls[1].controls[1].value = f"{int(progress * 100)}%"
                item.controls[0].controls[1].value = status
                if progress >= 1.0:
                    item.controls[1].controls[0].color = ft.Colors.GREEN_700
                self.page.update()
                break

    async def show_install_dialog(self):
        if self.page.web:
            components_list = ft.Column(spacing=10, tight=True)
        else:
            components_list = ft.ListView(expand=1, spacing=10, padding=20, auto_scroll=True)

        for component in self.components_to_install:
            progress_ring = ft.ProgressRing(width=40, height=40, stroke_width=3)
            status_text = ft.Text(f"{component['name']} - {self._['wait_install']}...", size=14, no_wrap=False)
            component_item = ft.Row(
                controls=[
                    ft.Column([ft.Text(component["name"], size=16), status_text],
                              alignment=ft.MainAxisAlignment.START, expand=True),
                    ft.Column([progress_ring, ft.Text("0%", size=12)], horizontal_alignment=ft.CrossAxisAlignment.END),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
            components_list.controls.append(component_item)

        dialog_height = int(self.page.window.height * 0.6) if not self.page.web else int(self.page.height * 0.5)
        dialog_width = int(self.page.window.height * 0.5) if not self.page.web else int(self.page.height * 0.5)

        components_container = ft.Container(
            content=components_list,
            expand=True,
        )

        dialog_content = ft.Column(
            controls=[
                ft.Icon(ft.Icons.DOWNLOADING, size=40, color=ft.Colors.BLUE_700),
                ft.Text(self._["install_guide"], size=20),
                ft.Divider(height=20),
                ft.Text(self._["install_tip"], size=14),
                components_container,
                ft.Row(
                    [ft.Checkbox(label=self._["dont_show_again"], value=False, on_change=self.on_dont_show_again)],
                    alignment=ft.MainAxisAlignment.START,
                )
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=15,
            height=dialog_height,
            width=dialog_width,
        )

        self.install_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(self._["lack_components"]),
            content=dialog_content,
            actions=[
                ft.TextButton(
                    text=self._["install_now"],
                    icon=ft.Icons.DOWNLOAD,
                    style=ft.ButtonStyle(
                        color=ft.Colors.WHITE, bgcolor=ft.Colors.BLUE_600, overlay_color=ft.Colors.BLUE_800
                    ),
                    on_click=self.on_install_clicked,
                ),
                ft.TextButton(
                    text=self._["later_on"],
                    icon=ft.Icons.ACCESS_TIME,
                    style=ft.ButtonStyle(color=ft.Colors.GREY_700),
                    on_click=self.close_dialog,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        self.page.overlay.append(self.install_dialog)
        self.install_dialog.open = True
        self.page.update()

    async def close_dialog(self, _):
        if self.install_dialog and self.install_dialog.open:
            self.install_dialog.open = False
            self.page.update()

    async def on_install_clicked(self, _):
        await self.install_components()

    async def on_dont_show_again(self, e):
        user_config = self.app.settings.user_config
        user_config["hide_install_dialog"] = e.control.value
        await self.app.config_manager.save_user_config(user_config)

    async def check_env(self):
        if not self.app.settings.user_config.get("hide_install_dialog", False):
            await self.get_install_components()
            if self.components_to_install:
                logger.info(f"Missing components: {[i['name'] for i in self.components_to_install]}")
                self.page.run_task(self.show_install_dialog)
        else:
            from ..scripts import ffmpeg_install, node_install
            ffmpeg_install.update_env_path()
            node_install.update_env_path()
            