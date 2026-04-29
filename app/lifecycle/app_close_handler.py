import os
import threading
import time

import flet as ft

from ..utils.logger import logger
from .tray_manager import TrayManager


async def _safe_destroy_window(page):
    try:
        await page.window.destroy()
    except Exception as ex:
        logger.error(f"close window error: {ex}")
    finally:
        os._exit(0)


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

        if active_recordings_count > 0:
            save_progress_overlay.show(
                _["saving_recordings"].format(active_recordings_count=active_recordings_count), cancellable=True
            )
            page.update()

            def close_app():
                try:
                    # adjust wait time based on the number of recordings, at least 2 seconds
                    base_wait_time = max(2, min(active_recordings_count, 10))
                    logger.info(
                        f"waiting for {active_recordings_count} recordings to finish, waiting {base_wait_time} seconds"
                    )

                    time.sleep(base_wait_time)

                    # check again if there are active processes
                    remaining = len([p for p in app.process_manager.ffmpeg_processes if p.returncode is None])
                    if remaining > 0:
                        logger.info(f"still {remaining} recordings are not finished, waiting for extra time")
                        time.sleep(min(remaining, 5))

                    time.sleep(0.5)

                except Exception as ex:
                    logger.error(f"close window error: {ex}")
                finally:
                    if not getattr(app, "is_web_mode", False) and hasattr(app, "tray_manager"):
                        app.tray_manager.stop()
                    page.run_task(page.window.destroy)
                    time.sleep(0.3)
                    os._exit(0)

            threading.Thread(target=close_app, daemon=True).start()
        else:
            if not getattr(app, "is_web_mode", False) and hasattr(app, "tray_manager"):
                app.tray_manager.stop()
            await _safe_destroy_window(page)

        await close_dialog(e)

    async def close_dialog(_):
        close_confirm_dialog.open = False
        page.update()

    close_confirm_controls = [
        ft.Text(
            _["confirm_exit_content"],
            size=14,
            text_align=ft.TextAlign.CENTER,
        ),
        ft.Container(height=10),
    ]

    if page.platform.value != "macos":
        close_confirm_controls.append(
            ft.Container(
                content=ft.Text(
                    _["minimize_to_tray_tip"],
                    size=12,
                    color=ft.Colors.GREY_500,
                    text_align=ft.TextAlign.CENTER,
                ),
                padding=ft.padding.all(8),
                border_radius=5,
                bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.BLUE_GREY),
            )
        )

    close_confirm_actions = [
        ft.TextButton(
            content=ft.Text(_["cancel"], size=14),
            on_click=close_dialog,
            style=ft.ButtonStyle(
                color=ft.Colors.PRIMARY,
            ),
        ),
        ft.OutlinedButton(
            content=ft.Text(_["exit_program"], size=14),
            on_click=close_dialog_dismissed,
            style=ft.ButtonStyle(
                color=ft.Colors.ERROR,
            ),
        ),
    ]
    if page.platform.value != "macos":
        close_confirm_actions.insert(
            1,
            ft.TextButton(
                content=ft.Text(_["minimize_to_tray"], size=14),
                on_click=minimize_to_tray,
                style=ft.ButtonStyle(
                    color=ft.Colors.PRIMARY,
                ),
            ),
        )

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
            width=400 if page.platform.value != "macos" else None,
        ),
        actions=close_confirm_actions,
        actions_alignment=ft.MainAxisAlignment.END,
        shape=ft.RoundedRectangleBorder(radius=10),
    )

    close_confirm_dialog.open = True
    app.dialog_area.content = close_confirm_dialog
    app.close_confirm_dialog = close_confirm_dialog
    page.update()
