import os
import time
import asyncio
import gc
import psutil

import flet as ft

from . import InstallationManager, execute_dir
from .core.config_manager import ConfigManager
from .core.config_validator import ConfigValidator
from .core.language_manager import LanguageManager
from .core.platform_handlers import PlatformHandler
from .core.record_manager import RecordingManager
from .core.update_checker import UpdateChecker
from .process_manager import AsyncProcessManager
from .ui.components.recording_card import RecordingCardManager
from .ui.components.show_snackbar import ShowSnackBar
from .ui.navigation.sidebar import LeftNavigationMenu, NavigationSidebar
from .ui.views.about_view import AboutPage
from .ui.views.home_view import HomePage
from .ui.views.settings_view import SettingsPage
from .ui.views.storage_view import StoragePage
from .utils import utils
from .utils.logger import logger

# 定义内存清理阈值，当内存使用率超过这个值时执行更激进的清理
MEMORY_CLEANUP_THRESHOLD = 75  # 百分比
# 定义内存警告阈值，当内存使用率超过这个值时记录警告日志
MEMORY_WARNING_THRESHOLD = 85  # 百分比
# 定义轻量级清理间隔(秒)
LIGHT_CLEANUP_INTERVAL = 180  # 3分钟
# 定义完整清理间隔(秒)
FULL_CLEANUP_INTERVAL = 1800  # 30分钟


class App:
    def __init__(self, page: ft.Page):
        self.install_progress = None
        self.page = page
        self.run_path = execute_dir
        self.assets_dir = os.path.join(execute_dir, "assets")
        self.process_manager = AsyncProcessManager()
        self.config_manager = ConfigManager(self.run_path)
        self.is_web_mode = False
        self.auth_manager = None
        self.current_username = None
        self.content_area = ft.Column(
            controls=[],
            expand=True,
            alignment=ft.MainAxisAlignment.START,
            horizontal_alignment=ft.CrossAxisAlignment.START,
        )

        # 磁盘空间通知相关状态
        self.disk_space_notification_sent = False
        self.disk_space_last_notification_time = 0

        self.settings = SettingsPage(self)
        self.language_manager = LanguageManager(self)
        self.about = AboutPage(self)
        self.home = HomePage(self)
        self.pages = self.initialize_pages()
        self.language_code = self.settings.language_code
        self.sidebar = NavigationSidebar(self)
        self.left_navigation_menu = LeftNavigationMenu(self)

        self.page.snack_bar_area = ft.Container()
        self.dialog_area = ft.Container()
        self.complete_page = ft.Row(
            expand=True,
            controls=[
                self.left_navigation_menu,
                ft.VerticalDivider(width=1),
                self.content_area,
                self.dialog_area,
                self.page.snack_bar_area,
            ]
        )
        self.snack_bar = ShowSnackBar(self.page)
        self.subprocess_start_up_info = utils.get_startup_info()
        self.record_card_manager = RecordingCardManager(self)
        self.record_manager = RecordingManager(self)
        self.current_page = None
        self._loading_page = False
        self.recording_enabled = True
        self.install_manager = InstallationManager(self)
        self.update_checker = UpdateChecker(self)
        self.config_validator = ConfigValidator(self)
        self._last_light_cleanup = 0
        self._last_full_cleanup = 0
        self._memory_stats = {"peak": 0, "current": 0, "warning_count": 0}
        self.page.run_task(self.install_manager.check_env)
        self.page.run_task(self.record_manager.check_free_space)
        self.page.run_task(self._check_for_updates)
        
        # 只有在非web模式下才启动内存清理任务
        if not self.is_web_mode:
            self.page.run_task(self._setup_periodic_cleanup)
            
        self.page.run_task(self._validate_configs)

    def initialize_pages(self):
        return {
            "settings": self.settings,
            "home": HomePage(self),
            "storage": StoragePage(self),
            "about": AboutPage(self),
        }

    async def switch_page(self, page_name):
        if self._loading_page:
            return

        self._loading_page = True

        try:
            if isinstance(self.current_page, SettingsPage):
                await self.current_page.is_changed()
            await self.clear_content_area()
            if page := self.pages.get(page_name):
                await self.settings.is_changed()
                self.current_page = page
                await page.load()
        finally:
            self._loading_page = False

    async def clear_content_area(self):
        self.content_area.clean()
        self.content_area.update()

    async def cleanup(self):
        # 在web模式下不执行清理
        if self.is_web_mode:
            logger.info("Web模式下不执行清理")
            return
            
        try:
            await self.process_manager.cleanup()
            # 执行更完整的清理
            await self._perform_full_cleanup()
        except ConnectionError:
            logger.warning("连接丢失，进程可能已终止")
        except Exception as e:
            logger.error(f"清理过程中发生错误: {e}")

    async def add_ffmpeg_process(self, process):
        if process is None:
            logger.warning("尝试添加空的ffmpeg进程")
            return
            
        logger.info(f"添加ffmpeg进程: PID={process.pid}")
        await self.process_manager.add_process(process)
        
        # 添加后立即检查活跃进程数
        active_count = await self.process_manager.get_active_processes_count()
        logger.info(f"添加进程后，当前活跃进程数: {active_count}")

    async def _validate_configs(self):
        """验证配置项并修复无效的配置"""
        try:
            # 等待一小段时间，确保应用程序完全初始化
            await asyncio.sleep(1)
            
            # 验证所有配置项
            fixed_items = await self.config_validator.validate_all_configs()
            
            # 如果有配置项被修复，更新录制项
            if fixed_items:
                await self.config_validator.update_recordings_with_valid_config(fixed_items)
                
                # 如果当前页面是主页，刷新录制卡片
                if isinstance(self.current_page, HomePage) and hasattr(self.current_page, "refresh_cards_on_click"):
                    await self.current_page.refresh_cards_on_click(None)
                    
                # 显示提示
                await self.snack_bar.show_snack_bar(
                    f"已自动修复 {len(fixed_items)} 个无效的配置项",
                    bgcolor=ft.Colors.AMBER,
                    duration=3000
                )
        except Exception as e:
            logger.error(f"配置验证失败: {e}")

    async def _setup_periodic_cleanup(self):
        """设置定期清理任务，管理内存使用并清理未使用的资源"""
        # 在web模式下不执行内存清理
        if self.is_web_mode:
            logger.info("Web模式下不执行内存清理")
            return
            
        # 初始化最后清理时间
        self._last_light_cleanup = time.time()
        self._last_full_cleanup = time.time()
        
        while True:
            try:
                # 每10秒检查一次
                await asyncio.sleep(10)
                current_time = time.time()
                
                # 获取当前内存使用情况
                memory_info = self._get_memory_usage()
                self._memory_stats["current"] = memory_info["percent"]
                
                # 更新峰值内存使用
                if memory_info["percent"] > self._memory_stats["peak"]:
                    self._memory_stats["peak"] = memory_info["percent"]
                
                # 检查是否需要执行轻量级清理
                if current_time - self._last_light_cleanup >= LIGHT_CLEANUP_INTERVAL:
                    logger.info(f"执行轻量级清理任务 - 当前内存使用率: {memory_info['percent']:.1f}%")
                    await self._perform_light_cleanup()
                    self._last_light_cleanup = current_time
                
                # 检查是否需要执行完整清理
                if (current_time - self._last_full_cleanup >= FULL_CLEANUP_INTERVAL or 
                    memory_info["percent"] >= MEMORY_CLEANUP_THRESHOLD):
                    logger.info(f"执行完整清理任务 - 当前内存使用率: {memory_info['percent']:.1f}%")
                    await self._perform_full_cleanup()
                    self._last_full_cleanup = current_time
                
                # 如果内存使用超过警告阈值，记录警告并提供详细统计
                if memory_info["percent"] >= MEMORY_WARNING_THRESHOLD:
                    self._memory_stats["warning_count"] += 1
                    logger.warning(f"内存使用率过高: {memory_info['percent']:.1f}%, "
                                  f"已使用: {memory_info['used_mb']:.1f}MB, "
                                  f"总计: {memory_info['total_mb']:.1f}MB")
                    logger.warning(f"高内存使用警告计数: {self._memory_stats['warning_count']}, "
                                  f"峰值内存使用率: {self._memory_stats['peak']:.1f}%")
                    # 记录详细的进程信息
                    running_processes = await self.process_manager.get_running_processes_info()
                    active_processes_count = await self.process_manager.get_active_processes_count()
                    logger.warning(f"当前运行进程数: {active_processes_count}")
                    for proc in running_processes:
                        logger.warning(f"进程 PID={proc['pid']} 运行时间: {proc['running_time_str']}")
                    
                    # 记录实例统计信息
                    instance_stats = PlatformHandler.get_instance_stats()
                    logger.warning(f"平台处理器实例统计: 当前={instance_stats.get('current_count', 0)}, "
                                  f"不活跃={instance_stats.get('inactive_count', 0)}, "
                                  f"总创建={instance_stats.get('total_created', 0)}, "
                                  f"总访问={instance_stats.get('total_accessed', 0)}, "
                                  f"使用时间记录数={instance_stats.get('usage_records', 0)}, "
                                  f"强引用实例数={instance_stats.get('strong_refs', 0)}")
                    
            except Exception as e:
                logger.error(f"定期清理任务出错: {e}")
    
    async def _perform_light_cleanup(self):
        """执行轻量级清理任务，清理未使用的平台处理器实例和触发垃圾回收"""
        before_count = PlatformHandler.get_instances_count()
        logger.info(f"轻量级清理 - 清理前平台处理器实例数: {before_count}")
        
        # 清理未使用的平台处理器实例
        PlatformHandler.clear_unused_instances()
        
        # 主动触发垃圾回收
        collected = gc.collect()
        
        after_count = PlatformHandler.get_instances_count()
        logger.info(f"轻量级清理 - 清理后平台处理器实例数: {after_count}, "
                   f"减少: {before_count - after_count}, 垃圾回收对象数: {collected}")
        
        # 添加系统统计信息
        active_processes = await self.process_manager.get_active_processes_count()
        logger.info(f"系统统计 - 录制任务数: {len(self.record_manager.recordings)}, "
                   f"活跃进程数: {active_processes}")
                   
        # 检查系统中的进程
        await self.process_manager.check_system_processes()
    
    async def _perform_full_cleanup(self):
        """执行完整清理任务，包括清理平台处理器实例、进程和触发垃圾回收"""
        logger.info("开始执行完整清理...")
        
        # 记录清理前状态
        before_memory = self._get_memory_usage()
        before_instances = PlatformHandler.get_instances_count()
        
        # 1. 清理平台处理器实例
        PlatformHandler.clear_unused_instances()
        
        # 2. 强制垃圾回收
        gc.collect(generation=2)  # 强制完整垃圾回收
        
        # 3. 清理未引用的全局对象缓存
        # 注意：这是一个示例，实际上需要根据具体情况清理
        # 在此处可以添加清理特定缓存的代码
        
        # 4. 记录清理后状态
        after_memory = self._get_memory_usage()
        after_instances = PlatformHandler.get_instances_count()
        
        # 5. 日志记录清理结果
        memory_change = before_memory["percent"] - after_memory["percent"]
        logger.info(f"完整清理完成 - 内存使用率: {before_memory['percent']:.1f}% -> {after_memory['percent']:.1f}% "
                   f"(减少: {memory_change:.1f}%)")
        logger.info(f"完整清理完成 - 平台处理器实例: {before_instances} -> {after_instances} "
                   f"(减少: {before_instances - after_instances})")
        
        # 添加详细的内存使用信息
        logger.info(f"内存使用详情 - 已使用: {after_memory['used_mb']:.1f}MB, "
                   f"总计: {after_memory['total_mb']:.1f}MB, "
                   f"可用: {after_memory['available_mb']:.1f}MB")
        
        # 添加进程和实例统计信息
        active_processes = await self.process_manager.get_active_processes_count()
        instance_stats = PlatformHandler.get_instance_stats()
        logger.info(f"系统状态 - 录制任务数: {len(self.record_manager.recordings)}, "
                   f"活跃进程数: {active_processes}, "
                   f"实例数: {instance_stats.get('current_count', 0)}, "
                   f"强引用实例数: {instance_stats.get('strong_refs', 0)}, "
                   f"使用时间记录数: {instance_stats.get('usage_records', 0)}")
                   
        # 检查系统中的进程
        await self.process_manager.check_system_processes()
    
    def _get_memory_usage(self):
        """获取当前进程的内存使用情况"""
        try:
            process = psutil.Process()
            process_memory = process.memory_info()
            
            # 获取系统内存信息
            system_memory = psutil.virtual_memory()
            
            return {
                "percent": system_memory.percent,
                "used_mb": system_memory.used / (1024 * 1024),
                "total_mb": system_memory.total / (1024 * 1024),
                "available_mb": system_memory.available / (1024 * 1024),
                "process_mb": process_memory.rss / (1024 * 1024)
            }
        except Exception as e:
            logger.error(f"获取内存使用信息时出错: {e}")
            return {"percent": 0, "used_mb": 0, "total_mb": 0, "available_mb": 0, "process_mb": 0}

    async def _check_for_updates(self):
        """Check for updates when the application starts"""
        try:
            if not self.update_checker.update_config["auto_check"]:
                return
                
            last_check_time = self.settings.user_config.get("last_update_check", 0)
            current_time = time.time()
            check_interval = self.update_checker.update_config["check_interval"]
            
            if current_time - last_check_time >= check_interval:
                update_info = await self.update_checker.check_for_updates()
                self.settings.user_config["last_update_check"] = current_time
                await self.config_manager.save_user_config(self.settings.user_config)

                if update_info.get("has_update", False):
                    await self.update_checker.show_update_dialog(update_info)
        except Exception as e:
            logger.error(f"Update check failed: {e}")
            
    async def show_disk_space_warning_dialog(self, threshold: float, free_space: float):
        """显示磁盘空间不足警告对话框"""
        from .ui.components.disk_space_dialog import DiskSpaceDialog
        
        try:
            # 检查是否已经有一个磁盘空间警告弹窗在显示
            existing_dialog = None
            if (hasattr(self.dialog_area, "content") and 
                self.dialog_area.content and 
                isinstance(self.dialog_area.content, DiskSpaceDialog)):
                existing_dialog = self.dialog_area.content
            
            # 确保dialog_area存在
            if not hasattr(self, "dialog_area") or not self.dialog_area:
                self.dialog_area = ft.Container()
                self.page.overlay.append(self.dialog_area)
                self.dialog_area.update()
            
            if existing_dialog and hasattr(existing_dialog, "open") and existing_dialog.open:
                # 如果已有警告弹窗，更新其内容而不是创建新的
                logger.info(f"已有磁盘空间不足警告弹窗，更新其内容: 阈值={threshold}GB, 剩余={free_space:.2f}GB")
                existing_dialog.threshold = threshold
                existing_dialog.free_space = free_space
                existing_dialog.update_content()
                return
            
            # 创建对话框
            dialog = DiskSpaceDialog(self, threshold, free_space)
            dialog.open = True
            
            # 设置内容并显示
            self.dialog_area.content = dialog
            self.dialog_area.visible = True
            self.dialog_area.update()
            self.page.update()
            
            logger.info(f"显示磁盘空间不足警告对话框: 阈值={threshold}GB, 剩余={free_space:.2f}GB")
        except Exception as e:
            logger.error(f"显示磁盘空间不足警告对话框时出错: {e}", exc_info=True)

    async def test_disk_space_warning(self, threshold=None, free_space=None):
        """测试磁盘空间不足警告对话框
        
        Args:
            threshold: 可选，测试用的阈值
            free_space: 可选，测试用的剩余空间
        """
        if threshold is None:
            threshold = float(self.settings.user_config.get("recording_space_threshold", 2.0))
        
        if free_space is None:
            # 使用比阈值小的值作为测试
            free_space = threshold - 0.5
            
        logger.info(f"测试磁盘空间不足警告对话框: 阈值={threshold}GB, 模拟剩余={free_space}GB")
        
        # 重置通知状态，确保对话框能显示
        self.disk_space_notification_sent = False
        
        # 直接显示对话框
        await self.show_disk_space_warning_dialog(threshold, free_space)
