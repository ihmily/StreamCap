from __future__ import annotations

import asyncio
import subprocess
import sys
from datetime import datetime, time, timedelta

import flet as ft

from ...utils.logger import logger

DEFAULT_SHUTDOWN_DELAY_SECONDS = 60
MAX_QUICK_SHUTDOWN_HOURS = 168


def parse_shutdown_time(value: str) -> time:
    """Parse the persisted 24-hour shutdown time."""
    return datetime.strptime(value.strip(), "%H:%M").time()


def get_next_shutdown_at(value: str, now: datetime | None = None) -> datetime:
    """Return the next occurrence of ``value`` after ``now``."""
    current = now or datetime.now()
    scheduled_at = datetime.combine(current.date(), parse_shutdown_time(value))
    if scheduled_at <= current:
        scheduled_at += timedelta(days=1)
    return scheduled_at


def get_quick_shutdown_at(hours: int, now: datetime | None = None) -> datetime:
    """Return the target time for a positive hour-based shutdown delay."""
    if not 1 <= hours <= MAX_QUICK_SHUTDOWN_HOURS:
        raise ValueError(f"Shutdown delay must be between 1 and {MAX_QUICK_SHUTDOWN_HOURS} hours")
    return (now or datetime.now()) + timedelta(hours=hours)


class ScheduledShutdownManager:
    """Manage the desktop-only daily Windows shutdown schedule."""

    def __init__(self, app) -> None:
        self.app = app
        self._task: asyncio.Task | None = None
        self._countdown_task: asyncio.Task | None = None
        self._dialog: ft.AlertDialog | None = None
        self._shutdown_requested = False
        self._quick_shutdown_at: datetime | None = None

    @property
    def is_supported(self) -> bool:
        return sys.platform == "win32" and not self.app.page.web

    async def reschedule(self) -> None:
        await self.stop_schedule()
        if not self.is_supported:
            return
        if self.quick_shutdown_at is not None:
            logger.info(f"Daily shutdown paused until quick shutdown at {self.quick_shutdown_at:%Y-%m-%d %H:%M}")
            return

        enabled = self.app.settings.user_config.get("scheduled_shutdown_enabled", False)
        if not enabled:
            return

        shutdown_time = str(self.app.settings.user_config.get("scheduled_shutdown_time", "23:00"))
        try:
            next_shutdown = get_next_shutdown_at(shutdown_time)
        except ValueError:
            logger.error(f"Invalid scheduled shutdown time: {shutdown_time}")
            return

        self._task = asyncio.create_task(self._wait_until(next_shutdown, shutdown_time))
        logger.info(f"Scheduled system shutdown for {next_shutdown:%Y-%m-%d %H:%M}")

    @property
    def quick_shutdown_at(self) -> datetime | None:
        if self._quick_shutdown_at is not None and self._quick_shutdown_at <= datetime.now():
            self._quick_shutdown_at = None
        return self._quick_shutdown_at

    async def start_quick_shutdown(self, hours: int) -> datetime:
        if not self.is_supported:
            raise RuntimeError("Quick shutdown is only supported on Windows desktop")

        target = get_quick_shutdown_at(hours)
        await self.stop_schedule()
        _ = self._translations()
        result = await self._run_shutdown_command(
            delay_seconds=hours * 60 * 60,
            message=_["quick_shutdown_system_message"].format(hours=hours),
        )
        if result.returncode != 0:
            await self.reschedule()
            raise RuntimeError(result.stderr.strip() or str(result.returncode))

        self._quick_shutdown_at = target
        logger.warning(f"Quick system shutdown scheduled for {target:%Y-%m-%d %H:%M}")
        return target

    async def cancel_quick_shutdown(self) -> None:
        if self.quick_shutdown_at is None:
            return

        result = await asyncio.to_thread(
            subprocess.run,
            ["shutdown", "/a"],
            capture_output=True,
            text=True,
            startupinfo=self.app.subprocess_start_up_info,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or str(result.returncode))

        self._quick_shutdown_at = None
        logger.info("Quick shutdown cancelled by user")
        await self.reschedule()

    async def stop_schedule(self) -> None:
        task = self._task
        self._task = None
        if task is None or task.done() or task is asyncio.current_task():
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def stop(self) -> None:
        await self.stop_schedule()
        if self._countdown_task is not None and not self._countdown_task.done():
            self._countdown_task.cancel()
        self._countdown_task = None

    async def _wait_until(self, scheduled_at: datetime, configured_time: str) -> None:
        try:
            delay = max(0.0, (scheduled_at - datetime.now()).total_seconds())
            await asyncio.sleep(delay)

            settings = self.app.settings.user_config
            if not settings.get("scheduled_shutdown_enabled", False):
                return
            if str(settings.get("scheduled_shutdown_time", "23:00")) != configured_time:
                return

            await self._request_shutdown()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error(f"Scheduled shutdown failed: {exc}")

    def _translations(self) -> dict:
        language = self.app.language_manager.language
        return language.get("base", {}) | language.get("settings_page", {})

    async def _run_shutdown_command(self, delay_seconds: int, message: str):
        return await asyncio.to_thread(
            subprocess.run,
            ["shutdown", "/s", "/t", str(delay_seconds), "/c", message],
            capture_output=True,
            text=True,
            startupinfo=self.app.subprocess_start_up_info,
            check=False,
        )

    async def _request_shutdown(self) -> None:
        if self._shutdown_requested:
            return

        _ = self._translations()
        result = await self._run_shutdown_command(
            delay_seconds=DEFAULT_SHUTDOWN_DELAY_SECONDS,
            message=_["scheduled_shutdown_system_message"],
        )
        if result.returncode != 0:
            error = result.stderr.strip() or str(result.returncode)
            logger.error(f"Unable to start scheduled shutdown: {error}")
            await self.app.snack_bar.show_snack_bar(
                _["scheduled_shutdown_failed"].format(error=error),
                bgcolor=ft.Colors.RED,
                duration=5000,
            )
            return

        self._shutdown_requested = True
        logger.warning(f"System shutdown requested in {DEFAULT_SHUTDOWN_DELAY_SECONDS} seconds")
        self._show_countdown_dialog(DEFAULT_SHUTDOWN_DELAY_SECONDS)

    def _show_countdown_dialog(self, seconds: int) -> None:
        _ = self._translations()
        countdown_text = ft.Text(
            _["scheduled_shutdown_countdown"].format(seconds=seconds),
            size=14,
            text_align=ft.TextAlign.CENTER,
        )

        async def cancel_shutdown(_event) -> None:
            result = await asyncio.to_thread(
                subprocess.run,
                ["shutdown", "/a"],
                capture_output=True,
                text=True,
                startupinfo=self.app.subprocess_start_up_info,
                check=False,
            )
            if result.returncode == 0:
                self._shutdown_requested = False
                logger.info("Scheduled shutdown cancelled by user")
                await self.app.snack_bar.show_snack_bar(
                    _["scheduled_shutdown_cancelled"],
                    bgcolor=ft.Colors.PRIMARY,
                )
                await self._close_dialog()
                await self.reschedule()
            else:
                error = result.stderr.strip() or str(result.returncode)
                await self.app.snack_bar.show_snack_bar(
                    _["scheduled_shutdown_cancel_failed"].format(error=error),
                    bgcolor=ft.Colors.RED,
                    duration=5000,
                )

        self._dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(_["scheduled_shutdown"], weight=ft.FontWeight.BOLD),
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.POWER_SETTINGS_NEW, size=36, color=ft.Colors.ERROR),
                    countdown_text,
                ],
                tight=True,
                spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            actions=[
                ft.OutlinedButton(
                    content=_["scheduled_shutdown_cancel"],
                    icon=ft.Icons.CANCEL_SCHEDULE_SEND,
                    on_click=cancel_shutdown,
                )
            ],
            actions_alignment=ft.MainAxisAlignment.CENTER,
        )
        self._dialog.open = True
        self.app.dialog_area.content = self._dialog
        self.app.dialog_area.update()
        self._countdown_task = asyncio.create_task(self._update_countdown(countdown_text, seconds))

    async def _update_countdown(self, countdown_text: ft.Text, seconds: int) -> None:
        _ = self._translations()
        try:
            for remaining in range(seconds - 1, -1, -1):
                await asyncio.sleep(1)
                countdown_text.value = _["scheduled_shutdown_countdown"].format(seconds=remaining)
                countdown_text.update()
        except (asyncio.CancelledError, ft.FletPageDisconnectedException):
            pass

    async def _close_dialog(self) -> None:
        if self._countdown_task is not None and not self._countdown_task.done():
            self._countdown_task.cancel()
        self._countdown_task = None
        if self._dialog is not None:
            self._dialog.open = False
            self.app.dialog_area.update()
        self._dialog = None
