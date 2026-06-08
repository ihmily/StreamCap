from __future__ import annotations

import os
from typing import Any


class SettingsConfig:
    def __init__(self, services):
        self.services = services
        cm = services.config_manager
        self.user_config: dict = cm.load_user_config() or {}
        self.default_config: dict = cm.load_default_config() or {}
        self.cookies_config: dict = cm.load_cookies_config() or {}
        self.accounts_config: dict = cm.load_accounts_config() or {}
        self.language_option: dict = cm.load_language_config() or {}

        select_language = self.user_config.get("language")
        if select_language and select_language in self.language_option:
            self.language_code: str = self.language_option[select_language]
        elif self.language_option:
            self.language_code = next(iter(self.language_option.values()))
        else:
            self.language_code = "zh_CN"

    def get_config_value(self, key: str, default: Any = None) -> Any:
        return self.user_config.get(key, self.default_config.get(key, default))

    def get_cookies_value(self, key: str, default: str = "") -> str:
        return self.cookies_config.get(key, default)

    def get_accounts_value(self, key: str, default: Any = None) -> Any:
        try:
            k1, k2 = key.split("_", maxsplit=1)
        except ValueError:
            return default
        return self.accounts_config.get(k1, {}).get(k2, default)

    def get_video_save_path(self) -> str:
        live_save_path = self.get_config_value("live_save_path")
        if not live_save_path:
            live_save_path = os.path.join(self.services.run_path, "downloads")
        return live_save_path

    def adopt_user_config(self, user_config: dict) -> None:
        """Replace ``user_config`` reference (used when the UI rebuilds it)."""
        self.user_config = user_config

    def adopt_cookies_config(self, cookies_config: dict) -> None:
        self.cookies_config = cookies_config

    def adopt_accounts_config(self, accounts_config: dict) -> None:
        self.accounts_config = accounts_config
