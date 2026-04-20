import asyncio
import json
import re
import threading
from urllib.parse import quote, urlsplit, urlunsplit

import httpx

from ...utils.logger import logger


class ProxyManager:
    SUBSCRIPTION_REFRESH_SECONDS = 300
    SUBSCRIPTION_TIMEOUT_SECONDS = 15.0

    def __init__(self, app):
        self.app = app
        self.current_proxy_address = None
        self.current_proxy_username = ""
        self.current_proxy_password = ""
        self.subscription_proxy_addresses = []
        self.subscription_proxy_username = ""
        self.subscription_proxy_password = ""
        self._subscription_proxy_index = 0
        self._subscription_task = None
        self._refresh_lock = asyncio.Lock()
        self._subscription_proxy_lock = threading.Lock()

    @staticmethod
    def is_subscription_url(proxy_address: str | None) -> bool:
        if not proxy_address:
            return False
        proxy_address = proxy_address.strip().lower()
        return proxy_address.startswith("http://") or proxy_address.startswith("https://")

    @staticmethod
    def _normalize_list_value(raw_value) -> list[str]:
        if raw_value is None:
            return []

        if isinstance(raw_value, list):
            values = raw_value
        else:
            values = [raw_value]

        normalized_values = []
        for value in values:
            text = str(value).strip().strip('"').strip("'")
            if text:
                normalized_values.append(text)
        return normalized_values

    @classmethod
    def _parse_subscription_payload(cls, payload_text: str) -> tuple[list[str], str, str]:
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            payload = None

        if isinstance(payload, dict):
            return (
                cls._normalize_list_value(payload.get("ip")),
                str(payload.get("user") or "").strip(),
                str(payload.get("pwd") or "").strip(),
            )

        ip_match = re.search(r'"ip"\s*:\s*\[(.*?)\]', payload_text, re.S)
        user_match = re.search(r'"user"\s*:\s*"([^"]*)"', payload_text)
        pwd_match = re.search(r'"pwd"\s*:\s*"([^"]*)"', payload_text)

        ip_values = []
        if ip_match:
            ip_values = cls._normalize_list_value(ip_match.group(1).split(","))

        return (
            ip_values,
            user_match.group(1).strip() if user_match else "",
            pwd_match.group(1).strip() if pwd_match else "",
        )

    @staticmethod
    def _build_proxy_value(address: str | None, username: str = "", password: str = "") -> str | None:
        if not address:
            return None

        address = str(address).strip()
        username = str(username or "").strip()
        password = str(password or "").strip()

        if not username and not password:
            return address

        auth = quote(username, safe="")
        if password:
            auth = f"{auth}:{quote(password, safe='')}"

        if "://" in address:
            parsed = urlsplit(address)
            host = parsed.hostname or ""
            if parsed.port:
                host = f"{host}:{parsed.port}"
            netloc = f"{auth}@{host}" if auth else host
            return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))

        return f"http://{auth}@{address}"

    @classmethod
    def _build_subscription_proxy_value(
        cls,
        address: str | None,
        username: str = "",
        password: str = "",
    ) -> str | None:
        proxy_value = cls._build_proxy_value(address, username, password)
        if not proxy_value:
            return None

        if "://" in proxy_value:
            return proxy_value

        return f"http://{proxy_value}"

    @staticmethod
    def _resolve_credentials(
        subscription_username: str,
        subscription_password: str,
        fallback_username: str,
        fallback_password: str,
    ) -> tuple[str, str]:
        subscription_username = str(subscription_username or "").strip()
        subscription_password = str(subscription_password or "").strip()
        fallback_username = str(fallback_username or "").strip()
        fallback_password = str(fallback_password or "").strip()

        if subscription_username and subscription_password:
            return subscription_username, subscription_password

        return fallback_username, fallback_password

    @staticmethod
    def mask_proxy_value(proxy_value: str | None) -> str | None:
        if not proxy_value:
            return None

        if "@" not in proxy_value:
            return proxy_value

        if "://" in proxy_value:
            scheme, remainder = proxy_value.split("://", maxsplit=1)
            _, host = remainder.rsplit("@", maxsplit=1)
            return f"{scheme}://***@{host}"

        _, host = proxy_value.rsplit("@", maxsplit=1)
        return f"***@{host}"

    def _set_current_proxy(self, address: str | None, username: str = "", password: str = "") -> None:
        self.current_proxy_address = address.strip() if isinstance(address, str) else address
        self.current_proxy_username = str(username or "").strip()
        self.current_proxy_password = str(password or "").strip()

    def _set_subscription_proxies(self, addresses: list[str], username: str = "", password: str = "") -> None:
        normalized_addresses = self._normalize_list_value(addresses)
        self.subscription_proxy_addresses = normalized_addresses
        self.subscription_proxy_username = str(username or "").strip()
        self.subscription_proxy_password = str(password or "").strip()

        with self._subscription_proxy_lock:
            if not normalized_addresses:
                self._subscription_proxy_index = 0
            else:
                self._subscription_proxy_index %= len(normalized_addresses)

    def _clear_subscription_proxies(self) -> None:
        self.subscription_proxy_addresses = []
        self.subscription_proxy_username = ""
        self.subscription_proxy_password = ""
        with self._subscription_proxy_lock:
            self._subscription_proxy_index = 0

    def clear(self) -> None:
        self._clear_subscription_proxies()
        self._set_current_proxy(None)

    def get_proxy(self) -> str | None:
        if not self.app.settings.user_config.get("enable_proxy"):
            return None
        return self._build_proxy_value(
            self.current_proxy_address,
            self.current_proxy_username,
            self.current_proxy_password,
        )

    def is_subscription_active(self) -> bool:
        if not self.app.settings.user_config.get("enable_proxy"):
            return False

        proxy_address = str(self.app.settings.user_config.get("proxy_address") or "").strip()
        return self.is_subscription_url(proxy_address) and bool(self.subscription_proxy_addresses)

    def get_status_check_proxy(self) -> str | None:
        if not self.app.settings.user_config.get("enable_proxy"):
            return None

        if not self.is_subscription_active():
            return self.get_proxy()

        with self._subscription_proxy_lock:
            if not self.subscription_proxy_addresses:
                return self.get_proxy()

            selected_proxy = self.subscription_proxy_addresses[self._subscription_proxy_index]
            self._subscription_proxy_index = (self._subscription_proxy_index + 1) % len(self.subscription_proxy_addresses)

        return self._build_subscription_proxy_value(
            selected_proxy,
            self.subscription_proxy_username,
            self.subscription_proxy_password,
        )

    async def sync_from_settings(self) -> None:
        async with self._refresh_lock:
            proxy_enabled = self.app.settings.user_config.get("enable_proxy")
            proxy_address = str(self.app.settings.user_config.get("proxy_address") or "").strip()
            proxy_username = str(self.app.settings.user_config.get("proxy_username") or "").strip()
            proxy_password = str(self.app.settings.user_config.get("proxy_password") or "").strip()

            if not proxy_enabled or not proxy_address:
                self.clear()
                return

            if self.is_subscription_url(proxy_address):
                await self._refresh_subscription_locked(proxy_address, proxy_username, proxy_password)
                return

            self._clear_subscription_proxies()
            self._set_current_proxy(proxy_address, proxy_username, proxy_password)

    async def _refresh_subscription_locked(
        self,
        subscription_url: str,
        fallback_username: str = "",
        fallback_password: str = "",
    ) -> None:
        try:
            timeout = httpx.Timeout(self.SUBSCRIPTION_TIMEOUT_SECONDS, connect=self.SUBSCRIPTION_TIMEOUT_SECONDS)
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.get(subscription_url)
                response.raise_for_status()
                payload_text = response.text

            ip_list, subscription_user, subscription_password = self._parse_subscription_payload(payload_text)
            if not ip_list:
                logger.warning(f"Proxy subscription returned no proxy endpoints: {subscription_url}")
                return

            username, password = self._resolve_credentials(
                subscription_user,
                subscription_password,
                fallback_username,
                fallback_password,
            )
            self._set_subscription_proxies(ip_list, username, password)
            selected_proxy = self.subscription_proxy_addresses[0]
            self._set_current_proxy(selected_proxy, username, password)
            logger.info(
                "Proxy subscription updated successfully: "
                f"{len(self.subscription_proxy_addresses)} proxies, "
                f"default={self.mask_proxy_value(self.get_proxy())}"
            )
        except Exception as e:
            logger.warning(f"Failed to refresh proxy subscription {subscription_url}: {e}")

    async def refresh_subscription(self) -> None:
        async with self._refresh_lock:
            proxy_enabled = self.app.settings.user_config.get("enable_proxy")
            proxy_address = str(self.app.settings.user_config.get("proxy_address") or "").strip()
            proxy_username = str(self.app.settings.user_config.get("proxy_username") or "").strip()
            proxy_password = str(self.app.settings.user_config.get("proxy_password") or "").strip()

            if not proxy_enabled or not self.is_subscription_url(proxy_address):
                return

            await self._refresh_subscription_locked(proxy_address, proxy_username, proxy_password)

    async def _subscription_refresh_loop(self) -> None:
        while True:
            await asyncio.sleep(self.SUBSCRIPTION_REFRESH_SECONDS)
            await self.refresh_subscription()

    async def start(self) -> None:
        await self.sync_from_settings()
        if self._subscription_task is None or self._subscription_task.done():
            self._subscription_task = asyncio.create_task(self._subscription_refresh_loop())
