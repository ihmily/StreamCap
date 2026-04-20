import asyncio

import flet as ft

from ..core.runtime.process_manager import BackgroundService
from ..utils.logger import logger
from .tray_manager import TrayManager


def _safe_destroy_window(page):
    try:
        page.update()
        to_cancel = asyncio.all_tasks(page.loop)
        if not to_cancel:
            return
        for task in to_cancel:
            task.cancel()
    except Exception as ex:
        logger.error(f"close window error: {ex}")
    finally:
        page.window.destroy()


async def handle_app_close(page: ft.Page, app, save_progress_overlay) -> None:
    _ = {}
    language = app.language_manager.language
    for key in ("app_close_handler", "base"):
        _.update(language.get(key, {}))

    if not getattr(app, "is_web_mode", False) and not hasattr(app, "tray_manager"):
        app.tray_manager = TrayManager(app)

    async def minimize_to_tray(e):
        page.window.visible = False
        page.update()
        await close_dialog(e)

    async def close_dialog_dismissed(e):
        app.recording_enabled = False
        
        app.settings.user_config["last_route"] = page.route
        await app.config_manager.save_user_config(app.settings.user_config)
        logger.info(f"Saved last route: {page.route}")

        # check if there are active recordings
        active_recordings = [p for p in app.process_manager.ffmpeg_processes if p.returncode is None]
        active_recordings_count = len(active_recordings)

        await close_dialog(e)

        if active_recordings_count > 0:
            save_progress_overlay.show(_["saving_recordings"].format(active_recordings_count=active_recordings_count), 
                                       cancellable=True)
            page.update()

            cleanup_timeout = max(15, min(active_recordings_count * 6, 60))
            logger.info(
                f"Waiting for {active_recordings_count} recording processes to flush and exit "
                f"(timeout: {cleanup_timeout}s)"
            )

            try:
                await asyncio.wait_for(app.cleanup(), timeout=cleanup_timeout)
            except asyncio.TimeoutError:
                logger.warning("Timed out while waiting for FFmpeg processes to exit during shutdown")
            except Exception as ex:
                logger.error(f"close window error: {ex}")

            post_process_timeout = max(10, min(active_recordings_count * 6, 90))
            logger.info(
                f"Waiting for recording shutdown tasks to finish "
                f"(timeout: {post_process_timeout}s)"
            )
            try:
                runtime_tasks_done = await asyncio.wait_for(
                    app.record_manager.wait_for_runtime_tasks(),
                    timeout=post_process_timeout,
                )
                if not runtime_tasks_done:
                    logger.warning("Some recording shutdown tasks are still pending after the wait window")
            except asyncio.TimeoutError:
                logger.warning("Timed out while waiting for recording shutdown tasks during shutdown")
            except Exception as ex:
                logger.error(f"Failed while waiting for recording shutdown tasks: {ex}")

            background_service = BackgroundService.get_instance()
            if background_service.has_pending_work():
                background_timeout = max(10, min(active_recordings_count * 8, 120))
                logger.info(
                    f"Waiting for background conversion tasks to finish "
                    f"(timeout: {background_timeout}s)"
                )
                try:
                    background_done = await asyncio.to_thread(
                        background_service.wait_for_completion,
                        background_timeout,
                    )
                    if not background_done:
                        logger.warning("Timed out while waiting for background conversion tasks during shutdown")
                except Exception as ex:
                    logger.error(f"Failed while waiting for background conversion tasks: {ex}")

            remaining = len([p for p in app.process_manager.ffmpeg_processes if p.returncode is None])
            if remaining > 0:
                logger.warning(f"{remaining} recording processes are still active during shutdown")

            if not getattr(app, "is_web_mode", False) and hasattr(app, "tray_manager"):
                app.tray_manager.stop()
            _safe_destroy_window(page)
        else:
            if not getattr(app, "is_web_mode", False) and hasattr(app, "tray_manager"):
                app.tray_manager.stop()
            _safe_destroy_window(page)

    async def close_dialog(_):
        close_confirm_dialog.open = False
        page.update()

    close_confirm_controls = [
        ft.Text(
            _["confirm_exit_content"],
            size=14,
            text_align=ft.TextAlign.CENTER,
        ),
        ft.Container(height=10)
    ]

    if page.platform.value != 'macos':
        close_confirm_controls.append(
            ft.Container(
                content=ft.Text(
                    _["minimize_to_tray_tip"],
                    size=12,
                    color=ft.colors.GREY_500,
                    text_align=ft.TextAlign.CENTER,
                ),
                padding=ft.padding.all(8),
                border_radius=5,
                bgcolor=ft.colors.with_opacity(0.1, ft.colors.BLUE_GREY),
            )
        )

    close_confirm_actions = [
        ft.TextButton(
            content=ft.Text(_["cancel"], size=14),
            on_click=close_dialog,
            style=ft.ButtonStyle(
                color=ft.colors.PRIMARY,
            ),
        ),
        ft.OutlinedButton(
            content=ft.Text(_["exit_program"], size=14),
            on_click=close_dialog_dismissed,
            style=ft.ButtonStyle(
                color=ft.colors.ERROR,
            ),
        ),
    ]
    if page.platform.value != 'macos':
        close_confirm_actions.insert(
            1, ft.TextButton(
                content=ft.Text(_["minimize_to_tray"], size=14),
                on_click=minimize_to_tray,
                style=ft.ButtonStyle(
                    color=ft.colors.PRIMARY,
                ),
            ))

    close_confirm_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text(
            _["confirm_exit"],
            size=18,
            weight=ft.FontWeight.BOLD,
            text_align=ft.TextAlign.CENTER,
        ),
        content=ft.Container(
            content=ft.Column(
                controls=close_confirm_controls,
                spacing=5,
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=20, vertical=10),
            width=400 if page.platform.value != 'macos' else None,
        ),
        actions=close_confirm_actions,
        actions_alignment=ft.MainAxisAlignment.END,
        shape=ft.RoundedRectangleBorder(radius=10),
    )

    close_confirm_dialog.open = True
    app.dialog_area.content = close_confirm_dialog
    app.close_confirm_dialog = close_confirm_dialog
    page.update()
