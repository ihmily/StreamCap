import flet as ft


class PageBase:
    def __init__(self, app):
        """Initialize the base page class.

        :param app: The main application object.
        """
        self.app = app
        self.page: ft.Page = app.page
        self.content_area = app.content_area
        self._ = {}

    async def load(self):
        """Load page content into the content area."""
        raise NotImplementedError("Subclasses must implement this method")
