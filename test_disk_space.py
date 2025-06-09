import os
import sys
import asyncio
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("disk_space_test")

async def test_disk_space_check():
    """测试磁盘空间不足检查功能"""
    try:
        # 导入必要的模块
        logger.info("导入必要的模块...")
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        
        # 导入应用
        from app.utils import utils
        from app.core.record_manager import RecordingManager
        from app.app_manager import App
        
        # 模拟磁盘空间不足
        logger.info("准备模拟磁盘空间不足...")
        
        # 保存原始方法
        original_check_disk_capacity = utils.check_disk_capacity
        
        # 模拟方法
        def mock_check_disk_capacity(path):
            """模拟磁盘空间检查，返回一个小于阈值的值"""
            logger.info(f"模拟检查磁盘空间，路径: {path}")
            # 直接返回一个较小的值，例如1.5GB
            return 1.5
        
        # 替换方法
        utils.check_disk_capacity = mock_check_disk_capacity
        
        # 启动应用并触发检查
        import flet as ft
        
        async def main(page: ft.Page):
            logger.info("创建测试应用...")
            
            # 创建一个简单的页面
            page.title = "磁盘空间检查测试"
            page.padding = 20
            
            # 创建App实例
            from main import create_app
            app = create_app(page)
            
            # 创建测试按钮
            async def test_check(_):
                logger.info("手动触发磁盘空间检查...")
                result = await app.record_manager.check_free_space()
                logger.info(f"检查结果: {'磁盘空间不足' if not result else '磁盘空间充足'}")
                
            test_button = ft.ElevatedButton(
                "测试磁盘空间检查", 
                on_click=test_check,
                style=ft.ButtonStyle(
                    color=ft.Colors.WHITE,
                    bgcolor=ft.Colors.RED_500,
                    shape=ft.RoundedRectangleBorder(radius=10),
                ),
                width=250,
                height=50,
            )
            
            # 添加按钮到页面
            page.add(
                ft.Column([
                    ft.Text("磁盘空间不足检查测试工具", size=30, weight=ft.FontWeight.BOLD),
                    ft.Text("点击下方按钮测试磁盘空间不足检查", size=16),
                    ft.Container(height=20),
                    test_button,
                ])
            )
            
            # 更新页面
            page.update()
            
            # 自动触发一次检查
            await test_check(None)
        
        # 启动应用
        logger.info("启动测试应用...")
        await ft.app_async(target=main, view=ft.AppView.FLET_APP)
        
        # 恢复原始方法
        utils.check_disk_capacity = original_check_disk_capacity
        
    except Exception as e:
        logger.error(f"测试过程中出错: {e}", exc_info=True)
        
        # 确保恢复原始方法
        if 'original_check_disk_capacity' in locals():
            utils.check_disk_capacity = original_check_disk_capacity

if __name__ == "__main__":
    # 运行测试
    logger.info("开始测试磁盘空间不足检查...")
    asyncio.run(test_disk_space_check()) 