import asyncio
import sys
import os
import logging
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import flet as ft
from app.app_manager import App
from app.utils.logger import logger, setup_logger

# 设置日志
setup_logger(level=logging.DEBUG)


class DiskSpaceWarningTest:
    def __init__(self):
        self.page = None
        self.app = None

    async def test_disk_space_warning(self, page: ft.Page):
        self.page = page
        page.title = "磁盘空间警告测试"
        page.window_width = 1280
        page.window_height = 800
        page.theme_mode = ft.ThemeMode.DARK
        page.scroll = ft.ScrollMode.AUTO
        
        # 确保页面有overlay区域用于显示对话框
        page.overlay.clear()
        
        # 创建app实例
        self.app = App(page)
        
        # 确保dialog_area已添加到页面
        if self.app.dialog_area not in page.overlay:
            page.overlay.append(self.app.dialog_area)
            
        # 确保其他必要的UI元素也已添加到页面
        if self.app.page.snack_bar_area not in page.overlay:
            page.overlay.append(self.app.page.snack_bar_area)

        # 初始化页面
        page.add(ft.Column([
            ft.Text("磁盘空间警告测试", size=24, weight=ft.FontWeight.BOLD),
            ft.Text("此测试用于验证磁盘空间不足警告弹窗功能。", size=16),
            ft.Row([
                ft.ElevatedButton("测试单个警告弹窗", on_click=self.test_single_warning),
                ft.ElevatedButton("测试多个警告弹窗", on_click=self.test_multiple_warnings),
                ft.ElevatedButton("测试更新现有弹窗", on_click=self.test_update_warning),
            ]),
        ]))
        
        # 等待页面完全加载
        await asyncio.sleep(0.5)
        page.update()

    async def test_single_warning(self, _):
        """测试显示单个磁盘空间不足警告弹窗"""
        logger.info("测试单个磁盘空间不足警告弹窗")
        
        # 确保页面已准备好
        self.page.update()
        
        # 重置通知状态，确保对话框能显示
        self.app.disk_space_notification_sent = False
        await self.app.test_disk_space_warning(threshold=2.0, free_space=1.5)
        
        # 更新页面确保对话框显示
        self.page.update()

    async def test_multiple_warnings(self, _):
        """测试多个磁盘空间不足警告弹窗是否会同时显示"""
        logger.info("测试多个磁盘空间不足警告弹窗")
        
        # 确保页面已准备好
        self.page.update()
        
        # 首先显示一个弹窗
        self.app.disk_space_notification_sent = False
        await self.app.test_disk_space_warning(threshold=2.0, free_space=1.5)
        
        # 更新页面确保对话框显示
        self.page.update()
        
        # 等待一小段时间
        await asyncio.sleep(1)
        
        # 尝试显示第二个弹窗，如果修复成功，应该只会更新现有弹窗而不是显示新弹窗
        await self.app.test_disk_space_warning(threshold=2.0, free_space=1.2)
        
        # 更新页面确保对话框更新
        self.page.update()
        
        logger.info("如果修复成功，应该只显示一个已更新的弹窗，而不是多个弹窗")

    async def test_update_warning(self, _):
        """测试更新现有的磁盘空间不足警告弹窗"""
        logger.info("测试更新现有的磁盘空间不足警告弹窗")
        
        # 确保页面已准备好
        self.page.update()
        
        # 首先显示一个弹窗
        self.app.disk_space_notification_sent = False
        await self.app.test_disk_space_warning(threshold=2.0, free_space=1.5)
        
        # 更新页面确保对话框显示
        self.page.update()
        
        # 等待一小段时间
        await asyncio.sleep(1)
        
        # 更新现有弹窗的内容
        await self.app.test_disk_space_warning(threshold=3.0, free_space=0.8)
        
        # 更新页面确保对话框更新
        self.page.update()
        
        logger.info("弹窗内容应该已更新，显示新的阈值和剩余空间")


async def main(page: ft.Page):
    tester = DiskSpaceWarningTest()
    await tester.test_disk_space_warning(page)


if __name__ == "__main__":
    logger.info("开始测试磁盘空间不足警告对话框...")
    ft.app(target=main) 