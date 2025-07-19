import abc
import inspect
import re
import threading
from typing import Any, Optional, TypeVar

from streamget import StreamData

T = TypeVar("T", bound="PlatformHandler")
InstanceKey = tuple[str | None, tuple[tuple[str, str], ...] | None, str, str | None]


class PlatformHandler(abc.ABC):
    _registry: dict[str, type["PlatformHandler"]] = {}
    _instances: dict[InstanceKey, "PlatformHandler"] = {}
    _lock: threading.Lock = threading.Lock()

    def __init__(
        self,
        proxy: str | None = None,
        cookies: str | None = None,
        record_quality: str | None = None,
        platform: str | None = None,
        username: str | None = None,
        password: str | None = None,
        account_type: str | None = None,
    ) -> None:
        self.proxy = proxy
        self.cookies = cookies
        self.record_quality = record_quality
        self.platform = platform
        self.username = username
        self.password = password
        self.account_type = account_type

    @abc.abstractmethod
    async def get_stream_info(self, live_url: str) -> StreamData:
        """
        Abstract method to get stream information based on the live URL.
        """
        pass

    @classmethod
    def register(cls: type[T], *patterns: str) -> type[T]:
        """
        Register a platform handler class with one or more URL patterns.
        """
        with cls._lock:
            for pattern in patterns:
                cls._registry[pattern] = cls
        return cls

    @classmethod
    def get_registered_patterns(cls) -> dict[str, type["PlatformHandler"]]:
        """
        Return a copy of the registered URL patterns and their corresponding handler classes.
        """
        with cls._lock:
            return cls._registry.copy()

    @classmethod
    def _get_instance_key(
        cls, proxy: str | None, cookies: str | None, record_quality: str, platform: str | None
    ) -> InstanceKey:
        """
        Generate a unique key for each instance based on the provided parameters.
        """
        return proxy, cookies, record_quality, platform

    @classmethod
    def _get_handler_class(cls, live_url: str) -> type["PlatformHandler"] | None:
        """
        Find the appropriate handler class based on the live URL.
        """
        registered_patterns = cls.get_registered_patterns()
        for pattern, handler_class in registered_patterns.items():
            if re.search(pattern, live_url):
                return handler_class
        return None

    @classmethod
    def get_handler_instance(
        cls,
        live_url: str,
        proxy: str | None = None,
        cookies: str | None = None,
        record_quality: str | None = None,
        platform: str | None = None,
        username: str | None = None,
        password: str | None = None,
        account_type: str | None = None,
    ) -> Optional["PlatformHandler"]:
        """
        Get or create an instance of a platform handler based on the live URL and other parameters.
        """
        handler_class = cls._get_handler_class(live_url)
        if not handler_class:
            return None

        instance_key = cls._get_instance_key(proxy, cookies, record_quality, platform)
        if instance_key not in cls._instances:
            init_signature = inspect.signature(handler_class.__init__)
            handler_kwargs: dict[str, Any] = {
                "proxy": proxy,
                "cookies": cookies,
                "record_quality": record_quality,
                "platform": platform,
                "username": username,
                "password": password,
                "account_type": account_type,
            }
            filtered_kwargs = {k: v for k, v in handler_kwargs.items() if k in init_signature.parameters}
            with cls._lock:
                if instance_key not in cls._instances:
                    cls._instances[instance_key] = handler_class(**filtered_kwargs)

        return cls._instances[instance_key]
