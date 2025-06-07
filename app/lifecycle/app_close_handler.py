import asyncio
import threading
import time
import gc

import flet as ft

from ..utils.logger import logger
from ..utils.window_constants import (
    DEFAULT_WIDTH, DEFAULT_HEIGHT, MIN_WIDTH, MIN_HEIGHT, WINDOW_MARGIN
)


def _safe_destroy_window(page):
    try:
        page.update()
        to_cancel = asyncio.all_tasks(page.loop)
        if not to_cancel:
            return
        for task in to_cancel:
            task.cancel()
    except Exception as ex:
        logger.error(f"关闭窗口错误: {ex}")
    finally:
        page.window.destroy()


async def handle_app_close(page: ft.Page, app, save_progress_overlay) -> None:
    _ = {}
    language = app.language_manager.language
    for key in ("app_close_handler", "base"):
        _.update(language.get(key, {}))

    async def close_dialog_dismissed(e):
        app.recording_enabled = False
        
        # 保存当前窗口大小到用户配置
        try:
            width = page.window.width
            height = page.window.height
            
            # 验证窗口大小有效性
            if (width and height and 
                width >= MIN_WIDTH and 
                height >= MIN_HEIGHT):
                
                # 检查窗口大小是否超出当前屏幕分辨率
                try:
                    from screeninfo import get_monitors
                    screen = get_monitors()[0]
                    
                    # 如果窗口大小超出屏幕分辨率，不保存
                    if width > screen.width or height > screen.height:
                        # 获取正常尺寸比例
                        ratio = DEFAULT_HEIGHT / DEFAULT_WIDTH
                        # 根据屏幕宽度计算合适的高度
                        safe_width = min(width, screen.width - WINDOW_MARGIN)
                        safe_height = int(safe_width * ratio)
                        
                        app.settings.user_config["window_width"] = safe_width
                        app.settings.user_config["window_height"] = safe_height
                        logger.warning(f"窗口大小({width}x{height})超出屏幕分辨率({screen.width}x{screen.height})，调整为: {safe_width}x{safe_height}")
                    else:
                        app.settings.user_config["window_width"] = width
                        app.settings.user_config["window_height"] = height
                        logger.info(f"已保存窗口大小: {width}x{height}")
                except (ImportError, IndexError):
                    # 如果无法获取屏幕信息，直接保存
                    app.settings.user_config["window_width"] = width
                    app.settings.user_config["window_height"] = height
                    logger.info(f"已保存窗口大小: {width}x{height}")
                
                # 立即保存配置
                await app.config_manager.save_user_config(app.settings.user_config)
        except Exception as ex:
            logger.error(f"保存窗口大小时出错: {ex}")
        
        # 立即执行一次完整的资源清理
        try:
            # 在web模式下不执行资源清理
            if not app.is_web_mode:
                await app._perform_full_cleanup()
        except Exception as ex:
            logger.error(f"关闭前清理资源时出错: {ex}")

        # 检查是否有活动录制
        active_recordings = [p for p in app.process_manager.ffmpeg_processes if p.returncode is None]
        active_recordings_count = len(active_recordings)

        if active_recordings_count > 0 and not app.is_web_mode:
            # 创建事件用于通知进程清理完成
            cleanup_completed = threading.Event()
            
            save_progress_overlay.show(_["saving_recordings"].format(active_recordings_count=active_recordings_count), 
                                       cancellable=True)
            page.update()

            def close_app():
                try:
                    logger.info(f"等待 {active_recordings_count} 个录制完成")
                    
                    # 调整基础等待时间，至少2秒，最多10秒
                    base_wait_time = max(2, min(active_recordings_count, 10))
                    logger.info(f"基础等待时间: {base_wait_time} 秒")
                    
                    # 首先等待一小段时间让进程有机会正常终止
                    time.sleep(base_wait_time)
                    
                    # 检查是否还有活动进程
                    remaining_count = len([p for p in app.process_manager.ffmpeg_processes if p.returncode is None])
                    
                    if remaining_count > 0:
                        # 主动触发清理
                        logger.info(f"仍有 {remaining_count} 个录制未完成，尝试强制清理")
                        
                        # 创建异步任务在后台运行
                        async def force_cleanup():
                            try:
                                await app.process_manager.cleanup()
                                # 强制垃圾回收
                                gc.collect(generation=2)
                                # 通知清理完成
                                cleanup_completed.set()
                            except Exception as ex:
                                logger.error(f"强制清理进程时出错: {ex}")
                                cleanup_completed.set()  # 即使出错也设置事件
                        
                        # 在事件循环中调度任务
                        page.loop.create_task(force_cleanup())
                        
                        # 等待清理完成信号，最多等待10秒
                        max_wait_time = 10  # 最大等待10秒
                        cleanup_completed.wait(max_wait_time)
                    else:
                        # 如果没有剩余进程，直接设置事件
                        cleanup_completed.set()
                    
                    # 最后等待0.5秒确保其他资源能够释放
                    time.sleep(0.5)
                    
                except Exception as ex:
                    logger.error(f"关闭窗口时出错: {ex}")
                finally:
                    # 无论如何，确保窗口被销毁
                    page.window.destroy()

            # 在单独的线程中运行关闭逻辑
            threading.Thread(target=close_app, daemon=True).start()
        else:
            # 如果没有活动录制或是web模式，直接关闭窗口
            _safe_destroy_window(page)

        await close_dialog(e)

    async def close_dialog(_):
        confirm_dialog.open = False
        page.update()

    confirm_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text(_["confirm_exit"]),
        content=ft.Text(_["confirm_exit_content"]),
        actions=[
            ft.TextButton(_["cancel"], on_click=close_dialog),
            ft.TextButton(_["confirm"], on_click=close_dialog_dismissed),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    confirm_dialog.open = True
    app.dialog_area.content = confirm_dialog
    page.update()
