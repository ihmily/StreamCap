import flet as ft


class SearchDialog(ft.AlertDialog):
    def __init__(self, recordings_page, on_close=None):
        self.recordings_page = recordings_page
        self._ = {}
        self.load()

        # Get the name of the current filter condition
        filter_name = self._["filter_all"]
        if self.recordings_page.current_filter == "recording":
            filter_name = self._["filter_recording"]
        elif self.recordings_page.current_filter == "living":
            filter_name = self._["filter_living"]
        elif self.recordings_page.current_filter == "error":
            filter_name = self._["filter_error"]
        elif self.recordings_page.current_filter == "offline":
            filter_name = self._["filter_offline"]
        elif self.recordings_page.current_filter == "stopped":
            filter_name = self._["filter_stopped"]

        search_title = f"{self._['search']} ({filter_name})"

        super().__init__(
            title=ft.Text(search_title, size=20, weight=ft.FontWeight.BOLD),
            content_padding=ft.padding.only(left=20, top=15, right=20, bottom=20),
        )
        self.query = ft.TextField(
            hint_text=self._["search_keyword"],
            expand=True,
            border_radius=5,
            border_color=ft.Colors.GREY_400,
            focused_border_color=ft.Colors.BLUE,
            hint_style=ft.TextStyle(color=ft.Colors.GREY_500, size=14),
        )
        self.actions = [
            ft.TextButton(
                self._["cancel"],
                icon=ft.Icons.CLOSE,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5)),
                on_click=self.close_dlg,
            ),
            ft.TextButton(
                self._["sure"],
                icon=ft.Icons.SEARCH,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5)),
                on_click=self.submit_query,
            ),
        ]
        self.content = ft.Column(
            [self.query, ft.Divider(height=1, thickness=1, color=ft.Colors.GREY_300)],
            tight=True,
            width=400,
            height=300
        )
        self.actions_alignment = ft.MainAxisAlignment.END
        self.on_close = on_close
        self.recordings_page.app.language_manager.add_observer(self)

    def load(self):
        language = self.recordings_page.app.language_manager.language
        for key in ("search_dialog", "recordings_page", "base"):
            self._.update(language.get(key, {}))
        
        # Ensure the language items related to filtering exist
        if "filter_all" not in self._:
            self._["filter_all"] = self._["all"]
            self._["filter_recording"] = self._["recording"]
            self._["filter_offline"] = self._["not_live"]
            self._["filter_error"] = self._["recording_error"]
            self._["filter_stopped"] = self._["stopped"]

    async def close_dlg(self, _e):
        self.open = False
        self.update()

    async def submit_query(self, e):
        query = self.query.value.strip()
        await self.recordings_page.filter_recordings(query)
        await self.close_dlg(e) 