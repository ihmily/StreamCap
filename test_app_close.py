import asyncio
import logging
import os
import signal
import subprocess
import sys
import time
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"logs/app_close_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

class MockProcess:
    """模拟FFmpeg进程"""
    def __init__(self, pid, cmd):
        self.pid = pid
        self.cmd = cmd
        self.returncode = None
        self.stdin = None
        self._start_time = time.time()
    
    @property
    def running_time(self):
        return time.time() - self._start_time


async def create_mock_ffmpeg_process():
    """创建一个模拟的FFmpeg进程"""
    # 根据操作系统创建一个长时间运行的进程
    if sys.platform == "win32":
        cmd = "ping -t localhost"
    else:
        cmd = "ping localhost"
    
    process = subprocess.Popen(
        cmd, 
        shell=True, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE
    )
    
    return MockProcess(process.pid, cmd)


async def test_app_close_cleanup():
    """测试应用关闭时的资源清理功能"""
    from app.lifecycle.app_close_handler import handle_app_close
    from app.process_manager import AsyncProcessManager
    from app.core.platform_handlers import PlatformHandler
    import flet as ft
    
    logger.info("模拟应用关闭过程...")
    
    # 创建模拟的页面对象
    class MockPage:
        def __init__(self):
            self.loop = asyncio.get_event_loop()
            self.window = MockWindow()
            self.update_called = 0
            self.dialog_area = None
            
        def update(self):
            self.update_called += 1
            logger.info(f"页面更新被调用 (次数: {self.update_called})")
    
    class MockWindow:
        def __init__(self):
            self.destroy_called = False
            
        def destroy(self):
            self.destroy_called = True
            logger.info("窗口销毁被调用")
    
    class MockApp:
        def __init__(self):
            self.process_manager = AsyncProcessManager()
            self.recording_enabled = True
            self.dialog_area = MockDialogArea()
            self.language_manager = MockLanguageManager()
            
        async def _perform_full_cleanup(self):
            logger.info("执行完整清理...")
            # 模拟清理延迟
            await asyncio.sleep(0.5)
            logger.info("完整清理完成")
    
    class MockDialogArea:
        def __init__(self):
            self.content = None
    
    class MockLanguageManager:
        def __init__(self):
            self.language = {
                "app_close_handler": {
                    "confirm_exit": "确认退出",
                    "confirm_exit_content": "确定要退出应用吗？",
                    "saving_recordings": "正在保存 {active_recordings_count} 个录制...",
                },
                "base": {
                    "cancel": "取消",
                    "confirm": "确认",
                }
            }
    
    class MockSaveProgressOverlay:
        def __init__(self):
            self.visible = False
            self.message = ""
            self.cancellable = False
            
        def show(self, message, cancellable=False):
            self.visible = True
            self.message = message
            self.cancellable = cancellable
            logger.info(f"显示保存进度覆盖层: {message}, 可取消: {cancellable}")
    
    # 创建模拟对象
    page = MockPage()
    app = MockApp()
    save_progress_overlay = MockSaveProgressOverlay()
    
    # 创建一些模拟的FFmpeg进程
    logger.info("创建模拟的录制进程...")
    for i in range(3):
        mock_process = await create_mock_ffmpeg_process()
        await app.process_manager.add_process(mock_process)
        logger.info(f"创建模拟进程 {i+1}/3: PID={mock_process.pid}")
    
    # 模拟点击确认关闭按钮
    logger.info("模拟点击确认关闭按钮...")
    await handle_app_close(page, app, save_progress_overlay)
    
    # 模拟点击确认对话框中的确认按钮
    logger.info("模拟点击确认对话框中的确认按钮...")
    confirm_dialog = app.dialog_area.content
    
    # 查找确认按钮并模拟点击
    confirm_button = None
    for action in confirm_dialog.actions:
        if hasattr(action, 'text') and action.text == "确认":
            confirm_button = action
            break
    
    if confirm_button and hasattr(confirm_button, 'on_click'):
        # 模拟点击确认按钮
        mock_event = type('obj', (object,), {})
        await confirm_button.on_click(mock_event)
        logger.info("模拟点击确认按钮完成")
    else:
        logger.error("无法找到确认按钮")
    
    # 等待一段时间让清理过程完成
    logger.info("等待清理过程完成...")
    await asyncio.sleep(10)
    
    # 检查结果
    logger.info(f"页面更新次数: {page.update_called}")
    logger.info(f"窗口销毁状态: {page.window.destroy_called}")
    logger.info(f"保存进度覆盖层显示: {save_progress_overlay.visible}")
    if save_progress_overlay.visible:
        logger.info(f"保存进度覆盖层消息: {save_progress_overlay.message}")
    
    return {
        "page_updated": page.update_called > 0,
        "window_destroyed": page.window.destroy_called,
        "overlay_shown": save_progress_overlay.visible
    }


async def main():
    """主测试函数"""
    logger.info("开始应用关闭测试...")
    
    # 确保日志目录存在
    os.makedirs("logs", exist_ok=True)
    
    try:
        # 测试应用关闭过程
        result = await test_app_close_cleanup()
        
        # 输出测试结果
        logger.info("=" * 50)
        logger.info("应用关闭测试结果")
        logger.info("=" * 50)
        for key, value in result.items():
            logger.info(f"{key}: {value}")
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error(f"测试过程中出错: {e}", exc_info=True)
    
    logger.info("应用关闭测试完成")


if __name__ == "__main__":
    asyncio.run(main()) 