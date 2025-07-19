import os

from ...utils.logger import logger
from .config_manager import ConfigManager


class LanguageManager:
    """
    Manages language settings and loads internationalization (i18n) configurations.
    """

    def __init__(self, app):
        self._observers = []
        self.language = {}
        self.app = app
        self.load()

    def load(self):
        """
        Initialize the LanguageManager with settings and load the language configuration.
        """
        config_manager = ConfigManager(self.app.run_path)
        logger.info(f"Language Code: {self.app.settings.language_code}")
        i18n_filename = f"{self.app.settings.language_code}.json"
        i18n_file_path = os.path.join(self.app.run_path, "locales", i18n_filename)
        self.language = config_manager.load_i18n_config(i18n_file_path)
        return self.language

    def add_observer(self, observer):
        """Add an observer that will be notified when the language changes."""
        if observer not in self._observers:
            self._observers.append(observer)

    def remove_observer(self, observer):
        """Remove an observer."""
        if observer in self._observers:
            self._observers.remove(observer)

    def notify_observers(self):
        """Notify all observers that the language has changed."""
        for observer in self._observers:
            if hasattr(observer, "page_name"):
                observer.load_language()
            else:
                observer.load()
