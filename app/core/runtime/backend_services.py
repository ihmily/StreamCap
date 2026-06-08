from __future__ import annotations

import asyncio
import threading
import weakref
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from ...utils import utils
from ...utils.logger import logger
from ..config.config_manager import ConfigManager
from ..config.language_manager import LanguageManager
from ..config.settings_config import SettingsConfig
from .process_manager import AsyncProcessManager

if TYPE_CHECKING:
    from ..recording.record_manager import RecordingManager


@runtime_checkable
class UIBridge(Protocol):
    """Contract implemented by session-scoped ``App`` instances."""

    def schedule_card_update(self, recording) -> None: ...

    def schedule_card_remove(self, recordings) -> None: ...

    def schedule_snack(self, text: str, **kw: Any) -> None: ...

    def schedule_pubsub(self, topic: str, payload: Any) -> None: ...


class BackendServices:
    _instance: BackendServices | None = None

    def __init__(self, run_path: str):
        self.run_path = run_path
        self.config_manager = ConfigManager(run_path)
        self.settings_config = SettingsConfig(self)
        self.language_manager = LanguageManager.create_headless(self)

        self.process_manager = AsyncProcessManager()
        self.subprocess_start_up_info = utils.get_startup_info()
        self.recording_enabled = True

        # Filled in by ``bootstrap``.
        self.recording_manager: RecordingManager | None = None

        # Filled in by desktop App; not used in headless web mode.
        self.tray_manager = None

        # Active UI sessions (web mode may have 0..N concurrent ones).
        self._ui_bridges: weakref.WeakSet[UIBridge] = weakref.WeakSet()
        self._bridges_lock = threading.Lock()

        # Background loop (only created in web mode).
        self._backend_loop: asyncio.AbstractEventLoop | None = None
        self._backend_thread: threading.Thread | None = None
        self._loop_ready = threading.Event()

    @classmethod
    def get(cls) -> BackendServices:
        if cls._instance is None:
            raise RuntimeError("BackendServices not bootstrapped")
        return cls._instance

    @classmethod
    def get_or_none(cls) -> BackendServices | None:
        return cls._instance

    @classmethod
    def bootstrap(cls, run_path: str) -> BackendServices:
        if cls._instance is not None:
            return cls._instance
        from ..recording.record_manager import RecordingManager

        instance = cls(run_path)
        instance.recording_manager = RecordingManager(instance)
        cls._instance = instance
        return instance

    def start_background_loop(self) -> None:
        """Start the dedicated background asyncio loop in a daemon thread.

        Safe to call multiple times; subsequent calls are no-ops.
        """
        if self._backend_thread is not None and self._backend_thread.is_alive():
            return

        def runner() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._backend_loop = loop
            self._loop_ready.set()
            try:
                if self.recording_manager is not None:
                    rm = self.recording_manager
                    interval = int(rm.loop_time_seconds or 180)
                    loop.create_task(rm.check_free_space())
                    loop.create_task(rm.setup_periodic_live_check(interval))
                logger.info("BackendServices background loop started")
                loop.run_forever()
            except Exception as exc:  # pragma: no cover - defensive
                logger.error(f"BackendServices loop crashed: {exc}")
            finally:
                try:
                    loop.close()
                except Exception:
                    pass

        thread = threading.Thread(target=runner, name="BackendServicesLoop", daemon=True)
        self._backend_thread = thread
        thread.start()
        self._loop_ready.wait(timeout=5.0)

    def stop_background_loop(self) -> None:
        loop = self._backend_loop
        if loop is None or not loop.is_running():
            return
        try:
            loop.call_soon_threadsafe(loop.stop)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(f"Failed to stop BackendServices loop: {exc}")

    @property
    def backend_loop(self) -> asyncio.AbstractEventLoop | None:
        return self._backend_loop

    def run_coro(self, coro):

        if coro is None:
            return None

        loop = self._backend_loop
        if loop is not None and loop.is_running():
            try:
                return asyncio.run_coroutine_threadsafe(coro, loop)
            except Exception as exc:
                logger.warning(f"run_coro: backend loop refused task: {exc}")
                try:
                    coro.close()
                except Exception:
                    pass
                return None
        try:
            current = asyncio.get_running_loop()
            return current.create_task(coro)
        except RuntimeError:
            logger.warning("run_coro: no running loop available, dropping coroutine")
            try:
                coro.close()
            except Exception:
                pass
            return None

    def register_ui_bridge(self, bridge: UIBridge) -> None:
        with self._bridges_lock:
            self._ui_bridges.add(bridge)

    def unregister_ui_bridge(self, bridge: UIBridge) -> None:
        with self._bridges_lock:
            self._ui_bridges.discard(bridge)

    def snapshot_bridges(self) -> list[UIBridge]:
        with self._bridges_lock:
            return list(self._ui_bridges)

    def broadcast_card_update(self, recording) -> None:
        for bridge in self.snapshot_bridges():
            try:
                bridge.schedule_card_update(recording)
            except Exception as exc:
                logger.debug(f"broadcast_card_update failed for {bridge}: {exc}")

    def broadcast_card_remove(self, recordings) -> None:
        for bridge in self.snapshot_bridges():
            try:
                bridge.schedule_card_remove(recordings)
            except Exception as exc:
                logger.debug(f"broadcast_card_remove failed for {bridge}: {exc}")

    def broadcast_snack(self, text: str, **kw: Any) -> None:
        for bridge in self.snapshot_bridges():
            try:
                bridge.schedule_snack(text, **kw)
            except Exception as exc:
                logger.debug(f"broadcast_snack failed for {bridge}: {exc}")

    def broadcast_pubsub(self, topic: str, payload: Any) -> None:
        for bridge in self.snapshot_bridges():
            try:
                bridge.schedule_pubsub(topic, payload)
            except Exception as exc:
                logger.debug(f"broadcast_pubsub failed for {bridge}: {exc}")
