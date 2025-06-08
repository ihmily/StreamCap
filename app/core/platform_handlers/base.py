import abc
import inspect
import re
import threading
import weakref
import gc
import time
from typing import Any, Optional, TypeVar

from streamget import StreamData as OriginalStreamData
from ...utils.logger import logger

# 扩展StreamData类，添加get方法以避免'str' object has no attribute 'get'错误
class StreamData(OriginalStreamData):
    def get(self, key, default=None):
        """添加get方法以兼容处理字典类型数据"""
        if hasattr(self, key):
            return getattr(self, key)
        return default

T = TypeVar("T", bound="PlatformHandler")
InstanceKey = tuple[str | None, tuple[tuple[str, str], ...] | None, str, str | None]


class PlatformHandler(abc.ABC):
    _registry: dict[str, type["PlatformHandler"]] = {}
    _instances: weakref.WeakValueDictionary = weakref.WeakValueDictionary()
    _instance_last_used: dict[InstanceKey, float] = {}  # 记录实例最后使用时间
    _lock: threading.Lock = threading.Lock()
    _instance_creation_count = 0  # 跟踪创建的实例总数
    _instance_access_count = 0    # 跟踪访问实例的次数
    _INACTIVE_THRESHOLD = 300    # 5分钟不活跃的实例将被标记为可清理
    _active_instances = {}       # 强引用字典，防止实例被过早回收

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
        # 记录实例创建的平台信息，用于日志
        self._platform_info = f"{platform or 'unknown'}-{record_quality or 'default'}"
        self._created_at = time.time()
        self._last_accessed = time.time()

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
        with cls._lock:
            cls._instance_access_count += 1
        
        handler_class = cls._get_handler_class(live_url)
        if not handler_class:
            logger.warning(f"实例管理 - 未找到匹配的处理器类: {live_url}")
            return None

        instance_key = cls._get_instance_key(proxy, cookies, record_quality, platform)
        instance_exists = instance_key in cls._instances
        
        if instance_exists:
            logger.info(f"实例管理 - 复用现有实例: {platform or 'unknown'}-{record_quality or 'default'}")
            # 更新最后使用时间
            with cls._lock:
                cls._instance_last_used[instance_key] = time.time()
                instance = cls._instances[instance_key]
                instance._last_accessed = time.time()
                # 确保实例在强引用字典中
                cls._active_instances[instance_key] = instance
        
        if not instance_exists:
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
                    cls._instance_creation_count += 1
                    instance = handler_class(**filtered_kwargs)
                    cls._instances[instance_key] = instance
                    # 同时在强引用字典中保存一份
                    cls._active_instances[instance_key] = instance
                    cls._instance_last_used[instance_key] = time.time()
                    logger.info(f"实例管理 - 创建新实例: {platform or 'unknown'}-{record_quality or 'default'}, "
                               f"总创建数: {cls._instance_creation_count}, 当前缓存数: {len(cls._instances)}")

        return cls._instances[instance_key]
    
    @classmethod
    def clear_unused_instances(cls):
        """
        清理未使用的实例缓存，主动移除长时间未使用的实例和已不再被引用的实例
        """
        with cls._lock:
            before_count = len(cls._instances)
            current_time = time.time()
            
            # 首先，移除长时间未使用的实例引用
            inactive_keys = [
                key for key, last_used in cls._instance_last_used.items()
                if current_time - last_used > cls._INACTIVE_THRESHOLD
            ]
            
            for key in inactive_keys:
                if key in cls._instances:
                    logger.info(f"实例清理 - 移除长时间未使用的实例: {key[2]}-{key[3] or 'default'}")
                    # 从WeakValueDictionary中移除引用，允许GC回收
                    del cls._instances[key]
                    # 同时从强引用字典中移除
                    if key in cls._active_instances:
                        del cls._active_instances[key]
                    
                # 从使用时间记录中移除
                if key in cls._instance_last_used:
                    del cls._instance_last_used[key]
            
            # 清理_instance_last_used中不存在于_instances的键
            orphaned_keys = [key for key in list(cls._instance_last_used.keys()) if key not in cls._instances]
            for key in orphaned_keys:
                del cls._instance_last_used[key]
                if key in cls._active_instances:
                    del cls._active_instances[key]
            
            # 手动触发垃圾回收
            gc.collect()
            
            after_count = len(cls._instances)
            logger.info(f"实例清理 - 清理前: {before_count}, 清理后: {after_count}, "
                       f"减少: {before_count - after_count}, 主动清理: {len(inactive_keys)}")
            logger.info(f"实例统计 - 总创建数: {cls._instance_creation_count}, "
                       f"总访问数: {cls._instance_access_count}, "
                       f"使用时间记录数: {len(cls._instance_last_used)}, "
                       f"强引用实例数: {len(cls._active_instances)}")
            
    @classmethod
    def get_instances_count(cls) -> int:
        """
        获取当前缓存的实例数量，用于监控
        """
        return len(cls._instances)
        
    @classmethod
    def get_instance_stats(cls) -> dict:
        """
        获取实例统计信息
        """
        inactive_count = 0
        current_time = time.time()
        
        with cls._lock:
            for key, last_used in cls._instance_last_used.items():
                if current_time - last_used > cls._INACTIVE_THRESHOLD:
                    inactive_count += 1
        
        return {
            "current_count": len(cls._instances),
            "inactive_count": inactive_count,
            "total_created": cls._instance_creation_count,
            "total_accessed": cls._instance_access_count,
            "usage_records": len(cls._instance_last_used),
            "strong_refs": len(cls._active_instances)
        }
