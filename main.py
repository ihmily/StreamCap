import argparse
import multiprocessing
import os
import sys
import platform as sys_platform

import flet as ft
from dotenv import load_dotenv
from screeninfo import get_monitors

from app.app_manager import App, execute_dir
from app.auth.auth_manager import AuthManager
from app.lifecycle.app_close_handler import handle_app_close
from app.ui.components.save_progress_overlay import SaveProgressOverlay
from app.ui.views.login_view import LoginPage
from app.utils.logger import logger
from app.utils.window_constants import (
    DEFAULT_WIDTH, DEFAULT_HEIGHT, MIN_WIDTH, MIN_HEIGHT,
    SCALE_2K, SCALE_4K, WINDOW_MARGIN
)

# 服务器配置常量
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 6006
ASSETS_DIR = "assets"

# 模块级变量，用于存储命令行参数和平台信息
_args = None
_platform = None


def get_scale_factor():
    """仅Windows下获取主显示器DPI缩放比例，其他平台返回1.0"""
    if sys_platform.system() == "Windows":
        try:
            import ctypes
            user32 = ctypes.windll.user32
            user32.SetProcessDPIAware()
            # 获取主显示器DPI
            dpi = user32.GetDpiForSystem()
            return dpi / 96  # 96为100%缩放
        except Exception as e:
            logger.warning(f"获取DPI缩放比例失败: {e}")
            return 1.0
    return 1.0


def setup_window(page: ft.Page, is_web: bool, user_config: dict = None) -> None:
    try:
        page.window.icon = os.path.join(execute_dir, ASSETS_DIR, "icon.ico")
        page.window.to_front()
        page.skip_task_bar = True
        page.always_on_top = True
        page.focused = True

        if not is_web:
            try:
                # 获取主显示器信息
                screen = get_monitors()[0]
                scale_factor = get_scale_factor()
                # 逻辑分辨率（考虑DPI缩放）
                logical_width = int(screen.width / scale_factor)
                logical_height = int(screen.height / scale_factor)
                # 设置默认窗口大小，并根据分辨率进行适配
                width = DEFAULT_WIDTH
                height = DEFAULT_HEIGHT
                # 对高分辨率屏幕进行适配的默认值
                if logical_width >= 3840:  # 4K分辨率
                    adapted_width = int(DEFAULT_WIDTH * SCALE_4K)
                    adapted_height = int(DEFAULT_HEIGHT * SCALE_4K)
                elif logical_width >= 2560:  # 2K分辨率
                    adapted_width = int(DEFAULT_WIDTH * SCALE_2K)
                    adapted_height = int(DEFAULT_HEIGHT * SCALE_2K)
                else:
                    adapted_width = DEFAULT_WIDTH
                    adapted_height = DEFAULT_HEIGHT
                # 优先使用用户配置中保存的窗口大小
                if user_config and user_config.get("window_width") and user_config.get("window_height"):
                    try:
                        saved_width = int(user_config["window_width"])
                        saved_height = int(user_config["window_height"])
                        # 检查保存的窗口大小是否超出屏幕分辨率（留出任务栏和标题栏的空间）
                        max_safe_width = logical_width - WINDOW_MARGIN
                        max_safe_height = logical_height - WINDOW_MARGIN
                        # 如果窗口尺寸过大，重新调整到合理大小
                        if saved_width > max_safe_width or saved_height > max_safe_height:
                            # 计算超出比例
                            width_ratio = saved_width / max_safe_width if saved_width > max_safe_width else 1
                            height_ratio = saved_height / max_safe_height if saved_height > max_safe_height else 1
                            # 取较大的比例进行等比例缩放
                            scale_ratio = max(width_ratio, height_ratio)
                            # 调整窗口大小
                            width = int(saved_width / scale_ratio)
                            height = int(saved_height / scale_ratio)
                            logger.warning(f"保存的窗口大小({saved_width}x{saved_height})超出屏幕分辨率({logical_width}x{logical_height})，已调整为: {width}x{height}")
                        else:
                            width = saved_width
                            height = saved_height
                            logger.info(f"使用用户保存的窗口大小: {width}x{height}")
                    except (ValueError, TypeError) as e:
                        logger.warning(f"无效的窗口大小配置: {e}，使用适配的默认值")
                        width = adapted_width
                        height = adapted_height
                else:
                    # 使用根据分辨率适配的大小
                    width = adapted_width
                    height = adapted_height
                # 确保窗口尺寸不小于最小尺寸
                width = max(width, MIN_WIDTH)
                height = max(height, MIN_HEIGHT)
                # 应用窗口大小
                page.window.width = width
                page.window.height = height
                # 确保窗口左上角位置在合理范围内
                page.window.left = max(0, min(logical_width - width, int((logical_width - width) / 2)))
                page.window.top = max(0, min(logical_height - height, int((logical_height - height) / 2)))
            except IndexError:
                logger.warning("No monitors detected, using default window size.")
                page.window.width = DEFAULT_WIDTH
                page.window.height = DEFAULT_HEIGHT
            except Exception as e:
                logger.error(f"设置窗口大小时发生错误: {e}")
                page.window.width = DEFAULT_WIDTH
                page.window.height = DEFAULT_HEIGHT
    except Exception as e:
        logger.error(f"设置窗口属性时发生错误: {e}")


def get_route_handler() -> dict[str, str]:
    return {
        "/": "home",
        "/home": "home",
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

    async def on_window_event(e: ft.ControlEvent) -> None:
        if e.data == "close":
            await handle_app_close(page, app, save_progress_overlay)

    return on_window_event


def handle_disconnect(page: ft.Page) -> callable:
    """Handle disconnection for web mode."""

    def disconnect(_: ft.ControlEvent) -> None:
        page.pubsub.unsubscribe_all()

    return disconnect


def handle_window_resize(page: ft.Page, app: App) -> callable:
    """处理窗口大小调整事件，保存窗口大小到用户配置"""
    
    def on_window_resize(e: ft.ControlEvent) -> None:
        # 获取当前窗口大小
        width = page.window.width
        height = page.window.height
        
        # 只有当窗口大小有效且发生变化时才保存
        if (width and height and 
            width >= MIN_WIDTH and
            height >= MIN_HEIGHT and
            (width != app.settings.user_config.get("window_width") or 
             height != app.settings.user_config.get("window_height"))):
            
            # 更新用户配置
            app.settings.user_config["window_width"] = width
            app.settings.user_config["window_height"] = height
            
            # 记录窗口大小变更
            logger.debug(f"窗口大小已调整为: {width}x{height}")
            
            # 保存配置（使用延迟保存以避免频繁写入）
            if hasattr(app.settings, "delay_handler"):
                page.run_task(
                    app.settings.delay_handler.start_task_timer, 
                    app.settings.save_user_config_after_delay, 
                    None
                )
            else:
                # 如果没有延迟处理器，直接保存
                page.run_task(app.config_manager.save_user_config, app.settings.user_config)
    
    return on_window_resize


async def main(page: ft.Page) -> None:
    # 使用模块级变量
    global _args, _platform
    
    # 如果模块变量未初始化，则使用全局变量
    if _args is None:
        _args = args
    if _platform is None:
        _platform = platform

    page.title = "StreamCap"
    page.window.min_width = MIN_WIDTH
    page.window.min_height = MIN_HEIGHT

    is_web = _args.web or _platform == "web"
    
    try:
        # 先创建App实例以获取用户配置
        app = App(page)
        page.data = app
        app.is_web_mode = is_web
        
        # 使用用户配置设置窗口
        setup_window(page, is_web, app.settings.user_config)
        
        theme_mode = app.settings.user_config.get("theme_mode", "light")
        if theme_mode == "dark":
            page.theme_mode = ft.ThemeMode.DARK
        else:
            page.theme_mode = ft.ThemeMode.LIGHT
        
        save_progress_overlay = SaveProgressOverlay(app)
        page.overlay.append(save_progress_overlay.overlay)
        
        # 添加窗口大小调整事件处理
        page.window.on_resize = handle_window_resize(page, app)
        
        async def load_app():
            try:
                page.add(app.complete_page)
                page.on_route_change = handle_route_change(page, app)
                page.window.prevent_close = True
                page.window.on_event = handle_window_event(page, app, save_progress_overlay)
                
                if is_web:
                    page.on_disconnect = handle_disconnect(page)
                
                page.update()
                page.on_route_change(ft.RouteChangeEvent(route=page.route))
            except Exception as e:
                logger.error(f"加载应用时发生错误: {e}")

        if is_web:
            try:
                auth_manager = AuthManager(app)
                app.auth_manager = auth_manager
                await auth_manager.initialize()
                
                session_token = await page.client_storage.get_async("session_token")
                if not session_token or not auth_manager.validate_session(session_token):
                    async def on_login_success(token):
                        try:
                            _session_info = auth_manager.active_sessions.get(token, {})
                            app.current_username = _session_info.get("username")
                            
                            # 更新客户端存储中的token
                            await page.client_storage.set_async("session_token", token)
                            
                            page.clean()
                            await load_app()
                        except Exception as e:
                            logger.error(f"登录成功后处理时发生错误: {e}")
                    
                    page.clean()
                    
                    login_page = LoginPage(page, auth_manager, on_login_success)
                    page.add(login_page.get_view())
                    return
                else:
                    session_info = auth_manager.active_sessions.get(session_token, {})
                    app.current_username = session_info.get("username")
            except Exception as e:
                logger.error(f"Web模式认证处理时发生错误: {e}")
        
        await load_app()
    except Exception as e:
        logger.error(f"应用初始化过程中发生错误: {e}")


if __name__ == "__main__":
    load_dotenv()
    platform = os.getenv("PLATFORM")
    default_host = os.getenv("HOST", DEFAULT_HOST)
    default_port = int(os.getenv("PORT", DEFAULT_PORT))

    parser = argparse.ArgumentParser(description="Run the Flet app with optional web mode.")
    parser.add_argument("--web", action="store_true", help="Run the app in web mode")
    parser.add_argument("--host", type=str, default=default_host, help=f"Host address (default: {default_host})")
    parser.add_argument("--port", type=int, default=default_port, help=f"Port number (default: {default_port})")
    args = parser.parse_args()
    
    # 初始化模块级变量，供main函数使用
    _args = args
    _platform = platform

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
        )
    else:
        ft.app(target=main, assets_dir=ASSETS_DIR)
