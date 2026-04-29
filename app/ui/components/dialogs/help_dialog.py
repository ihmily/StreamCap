import flet as ft


class HelpDialog(ft.AlertDialog):
    def __init__(self, app):
        self.app = app
        self.app.language_manager.add_observer(self)
        self._ = {}
        self.load()
        super().__init__(
            title=ft.Text(self._["shortcut_key_help"]),
            content=self.get_content(),
            actions=[ft.TextButton(self._["close"], on_click=self.close_panel)],
            actions_alignment=ft.MainAxisAlignment.END,
            modal=False,
        )

    def load(self):
        language = self.app.language_manager.language
        for key in ("help_dialog", "base"):
            self._.update(language.get(key, {}))

    def get_content(self):
        """Help card information content"""
        help_text_list = [
            self._["description"],
            f"\n{self._['main_page']}",
            self._["search_recording"],
            self._["refresh_list"],
            self._["add_new_recording"],
            self._["start_all"],
            self._["stop_all"],
            self._["delete_all"],
            f"\n{self._['settings_page']}",
            self._["save_configuration"],
            f"\n{self._['view_help']}",
        ]
        return ft.Text("\n".join(help_text_list))

    def close_panel(self, _):
        self.open = False
        self.update()
