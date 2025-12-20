import argparse
import asyncio
import multiprocessing
import os

import flet as ft
from dotenv import load_dotenv
from screeninfo import get_monitors

from app.app_manager import App, execute_dir
from app.auth.auth_manager import AuthManager
from app.lifecycle.app_close_handler import handle_app_close
from app.lifecycle.tray_manager import TrayManager
from app.ui.components.common.save_progress_overlay import SaveProgressOverlay
from app.ui.layout.responsive_layout import setup_responsive_layout
from app.ui.views.login_view import LoginPage
from app.utils.logger import logger

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 6006
WINDOW_SCALE = 0.65
MIN_WIDTH = 950
ASSETS_DIR = "assets"


def _parse_int(value, default: int | None = None) -> int | None:
    try:
        if value is None:
            return default
        if isinstance(value, bool):
            return default
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        value_str = str(value).strip()
        if not value_str:
            return default
        return int(float(value_str))
    except (TypeError, ValueError):
        return default


def setup_window(page: ft.Page, is_web: bool, user_config: dict | None = None) -> None:
    page.window.icon = os.path.join(execute_dir, ASSETS_DIR, "icon.ico")
    page.window.to_front()
    page.window.skip_task_bar = False
    page.window.always_on_top = False
    page.focused = True

    if is_web:
        return

    if not (user_config or {}).get("window_state_enabled", True):
        try:
            screen = get_monitors()[0]
            page.window.width = int(screen.width * WINDOW_SCALE)
            page.window.height = int(screen.height * WINDOW_SCALE)
            page.window.center()
        except IndexError:
            logger.warning("No monitors detected, using default window size.")
        return

    try:
        screen = get_monitors()[0]
        screen_width = int(screen.width)
        screen_height = int(screen.height)
    except Exception:
        screen_width = 0
        screen_height = 0

    default_width = int(screen_width * WINDOW_SCALE) if screen_width else int(MIN_WIDTH / WINDOW_SCALE)
    default_height = int(screen_height * WINDOW_SCALE) if screen_height else int(MIN_WIDTH * WINDOW_SCALE)

    window_width = _parse_int((user_config or {}).get("window_width"), default_width) or default_width
    window_height = _parse_int((user_config or {}).get("window_height"), default_height) or default_height
    window_left = _parse_int((user_config or {}).get("window_left"), None)
    window_top = _parse_int((user_config or {}).get("window_top"), None)
    window_maximized = bool((user_config or {}).get("window_maximized"))

    min_height = int(MIN_WIDTH * WINDOW_SCALE)
    window_width = max(MIN_WIDTH, window_width)
    window_height = max(min_height, window_height)
    if screen_width:
        window_width = min(window_width, screen_width)
    if screen_height:
        window_height = min(window_height, screen_height)

    page.window.width = window_width
    page.window.height = window_height

    if window_left is not None and window_top is not None and screen_width and screen_height:
        max_left = max(0, screen_width - window_width)
        max_top = max(0, screen_height - window_height)
        page.window.left = max(0, min(window_left, max_left))
        page.window.top = max(0, min(window_top, max_top))
    else:
        page.window.center()

    try:
        page.window.maximized = window_maximized
    except Exception:
        pass


def get_route_handler() -> dict[str, str]:
    return {
        "/": "home",
        "/home": "home",
        "/recordings": "recordings",
        "/settings": "settings",
        "/storage": "storage",
        "/about": "about",
    }


def handle_route_change(page: ft.Page, app: App) -> callable:
    route_map = get_route_handler()

    def route_change(e: ft.RouteChangeEvent) -> None:
        tr = ft.TemplateRoute(e.route)
        page_name = route_map.get(tr.route)
        if page_name:
            page.run_task(app.switch_page, page_name)
        else:
            logger.warning(f"Unknown route: {e.route}, redirecting to /")
            page.go("/")

    return route_change


def handle_window_event(page: ft.Page, app: App, save_progress_overlay: 'SaveProgressOverlay') -> callable:
    save_timer = {"task": None}

    async def save_window_state_after_delay(delay: float) -> None:
        await asyncio.sleep(delay)
        if getattr(app, "is_web_mode", False):
            return
        user_config = app.settings.user_config
        if not user_config.get("window_state_enabled", True):
            return

        maximized = bool(getattr(page.window, "maximized", False))
        user_config["window_maximized"] = maximized
        if not maximized:
            user_config["window_width"] = str(getattr(page.window, "width", "") or "")
            user_config["window_height"] = str(getattr(page.window, "height", "") or "")
            user_config["window_left"] = str(getattr(page.window, "left", "") or "")
            user_config["window_top"] = str(getattr(page.window, "top", "") or "")

        await app.config_manager.save_user_config(user_config)

    def schedule_save_window_state() -> None:
        if save_timer["task"] is not None:
            try:
                save_timer["task"].cancel()
            except Exception:
                pass
        save_timer["task"] = page.run_task(save_window_state_after_delay, 1.0)

    async def on_window_event(e: ft.ControlEvent) -> None:
        if e.data == "close":
            await handle_app_close(page, app, save_progress_overlay)
            return

        if e.data in ("move", "resize"):
            schedule_save_window_state()

    return on_window_event


def handle_disconnect(page: ft.Page) -> callable:
    """Handle disconnection for web mode."""

    def disconnect(_: ft.ControlEvent) -> None:
        page.pubsub.unsubscribe_all()

    return disconnect


def handle_page_resize(page: ft.Page, app: App) -> callable:
    """handle page resize"""
    
    def on_resize(_: ft.ControlEvent) -> None:
        setup_responsive_layout(page, app)
        page.update()
    
    return on_resize 


async def main(page: ft.Page) -> None:

    page.title = "StreamCap"
    page.window.min_width = MIN_WIDTH
    page.window.min_height = MIN_WIDTH * WINDOW_SCALE

    is_web = args.web or platform == "web"
    app = App(page)
    page.data = app
    app.is_web_mode = is_web
    app.is_mobile = False
    setup_window(page, is_web, app.settings.user_config)

    silent_start = False
    if not is_web:
        silent_start = bool(getattr(args, "silent", False)) or bool(app.settings.user_config.get("silent_start_enabled"))
    
    if not is_web:
        try:
            app.tray_manager = TrayManager(app)
            logger.info("Tray manager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize tray manager: {e}")
    
    theme_mode = app.settings.user_config.get("theme_mode", "light")
    if theme_mode == "dark":
        page.theme_mode = ft.ThemeMode.DARK
    else:
        page.theme_mode = ft.ThemeMode.LIGHT
    
    save_progress_overlay = SaveProgressOverlay(app)
    page.overlay.append(save_progress_overlay.overlay)
    
    async def load_app():
        if is_web:
            setup_responsive_layout(page, app)
            page.on_resize = handle_page_resize(page, app)

        page.add(app.complete_page)
        
        page.on_route_change = handle_route_change(page, app)
        page.window.prevent_close = True
        page.window.on_event = handle_window_event(page, app, save_progress_overlay)
        tray_started = False
        if is_web:
            page.on_disconnect = handle_disconnect(page)
        elif page.platform.value == "windows":
            if hasattr(app, "tray_manager"):
                try:
                    tray_started = bool(app.tray_manager.start(page))
                except Exception as err:
                    logger.error(f"Failed to start tray manager: {err}")

        if silent_start:
            if tray_started:
                page.window.visible = False
            else:
                try:
                    page.window.minimized = True
                except Exception:
                    pass

        page.update()
        page.on_route_change(ft.RouteChangeEvent(route=page.route))

    if is_web:
        auth_manager = AuthManager(app)
        app.auth_manager = auth_manager
        await auth_manager.initialize()
        
        login_required = app.settings.get_config_value("login_required", False)
        
        if login_required:
            session_token = await page.client_storage.get_async("session_token")
            if not session_token or not auth_manager.validate_session(session_token):
                async def on_login_success(token):
                    _session_info = auth_manager.active_sessions.get(token, {})
                    app.current_username = _session_info.get("username")
                    
                    page.clean()
                    await load_app()
                
                page.clean()
                
                login_page = LoginPage(page, auth_manager, on_login_success)
                page.add(login_page.get_view())
                return
            else:
                session_info = auth_manager.active_sessions.get(session_token, {})
                app.current_username = session_info.get("username")
        else:
            app.current_username = "admin"
    
    await load_app()


if __name__ == "__main__":
    load_dotenv()
    platform = os.getenv("PLATFORM")
    default_host = os.getenv("HOST", DEFAULT_HOST)
    default_port = int(os.getenv("PORT", DEFAULT_PORT))

    parser = argparse.ArgumentParser(description="Run the Flet app with optional web mode.")
    parser.add_argument("--web", action="store_true", help="Run the app in web mode")
    parser.add_argument("--silent", action="store_true", help="Start minimized/hidden (desktop)")
    parser.add_argument("--host", type=str, default=default_host, help=f"Host address (default: {default_host})")
    parser.add_argument("--port", type=int, default=default_port, help=f"Port number (default: {default_port})")
    args = parser.parse_args()

    multiprocessing.freeze_support()
    if args.web or platform == "web":
        logger.debug("Running in web mode on http://" + args.host + ":" + str(args.port))
        ft.app(
            target=main,
            view=ft.AppView.WEB_BROWSER,
            host=args.host,
            port=args.port,
            assets_dir=ASSETS_DIR,
            use_color_emoji=True,
            web_renderer=ft.WebRenderer.CANVAS_KIT
        )

    else:
        ft.app(target=main, assets_dir=ASSETS_DIR)
