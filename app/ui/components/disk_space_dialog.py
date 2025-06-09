import flet as ft
from ...utils.logger import logger
import time


class DiskSpaceDialog(ft.AlertDialog):
    """磁盘空间不足警告对话框"""
    
    def __init__(self, app, threshold, free_space):
        self.app = app
        self._ = {}
        self.threshold = threshold
        self.free_space = free_space
        self.load()

        super().__init__(
            title=ft.Text(self._["disk_space_insufficient_title"], size=20, weight=ft.FontWeight.BOLD),
            content_padding=ft.padding.only(left=20, top=15, right=20, bottom=20),
            modal=True,  # 确保对话框为模态
        )
        
        self.content = self._create_content()
        
        self.actions = [
            ft.TextButton(
                self._["check_later"],
                icon=ft.Icons.TIMER,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5)),
                on_click=self.close_dialog,
            ),
            ft.TextButton(
                self._["processed"],
                icon=ft.Icons.CHECK_CIRCLE,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5)),
                on_click=self.confirm_processed,
            ),
        ]
        self.actions_alignment = ft.MainAxisAlignment.END
    
    def _create_content(self):
        """创建对话框内容"""
        return ft.Column(
            [
                ft.Text(
                    self._["disk_space_insufficient_content"].replace("[threshold]", str(self.threshold)),
                    size=16,
                ),
                ft.Text(
                    f"{self._['current_free_space']}: {self.free_space:.2f}GB",
                    size=16,
                    color=ft.colors.RED,
                ),
                ft.Divider(height=1, thickness=1, color=ft.Colors.GREY_300),
                ft.Text(
                    self._["disk_space_warning_suggestion"],
                    size=14,
                    color=ft.colors.GREY_700,
                ),
            ],
            tight=True,
            width=450,
            spacing=10,
        )
        
    def update_content(self):
        """更新对话框内容，用于已存在的弹窗"""
        try:
            # 更新内容区域
            self.content = self._create_content()
            
            # 更新标题，确保使用最新的语言资源
            self.title = ft.Text(self._["disk_space_insufficient_title"], size=20, weight=ft.FontWeight.BOLD)
            
            # 更新按钮文本
            if len(self.actions) >= 2:
                self.actions[0].text = self._["check_later"]
                self.actions[1].text = self._["processed"]
            
            # 尝试更新对话框
            try:
                self.update()
            except Exception as e:
                # 如果对话框还没有添加到页面，可能会抛出异常
                # 但我们已经更新了内容，所以在对话框添加到页面后内容会是最新的
                logger.debug(f"更新对话框失败，可能是对话框还未添加到页面: {e}")
                pass
                
            logger.info(f"更新磁盘空间不足警告弹窗内容: 阈值={self.threshold}GB, 剩余={self.free_space:.2f}GB")
        except Exception as e:
            logger.error(f"更新磁盘空间不足警告弹窗内容失败: {e}", exc_info=True)
        
    def load(self):
        """加载语言资源"""
        try:
            language = self.app.language_manager.language
            for key in ["base", "recording_manager"]:
                self._.update(language.get(key, {}))
                
            # 如果不存在必要的翻译项，添加默认值
            if "disk_space_warning_suggestion" not in self._:
                self._["disk_space_warning_suggestion"] = "请清理磁盘空间后点击\"已处理\"按钮，或者点击\"稍后处理\"按钮稍后再处理。"
            if "check_later" not in self._:
                self._["check_later"] = "稍后处理"
            if "processed" not in self._:
                self._["processed"] = "已处理"
            if "current_free_space" not in self._:
                self._["current_free_space"] = "当前剩余空间"
            if "disk_space_insufficient_title" not in self._:
                self._["disk_space_insufficient_title"] = "磁盘空间不足警告"
            if "disk_space_insufficient_content" not in self._:
                self._["disk_space_insufficient_content"] = "磁盘空间不足，录制功能已停用。当前剩余空间低于设定阈值[threshold]GB，请及时清理磁盘空间。"
        except Exception as e:
            logger.error(f"加载语言资源失败: {e}", exc_info=True)
            # 设置默认值
            self._["disk_space_insufficient_title"] = "磁盘空间不足警告"
            self._["disk_space_insufficient_content"] = "磁盘空间不足，录制功能已停用。当前剩余空间低于设定阈值[threshold]GB，请及时清理磁盘空间。"
            self._["disk_space_warning_suggestion"] = "请清理磁盘空间后点击\"已处理\"按钮，或者点击\"稍后处理\"按钮稍后再处理。"
            self._["check_later"] = "稍后处理"
            self._["processed"] = "已处理"
            self._["current_free_space"] = "当前剩余空间"
            
    async def close_dialog(self, _e):
        """关闭对话框但不重置通知标记"""
        logger.info("用户选择稍后处理磁盘空间不足问题")
        
        # 设置最后一次通知时间以遵循推送间隔机制
        # 但不重置disk_space_notification_sent标志，这样点击按钮时仍会显示弹窗
        self.app.disk_space_last_notification_time = time.time()
        
        # 关键修改：保持通知状态为True，但使用一个新标志记录用户已点击稍后处理
        # 这样用户再次点击录制或监控按钮时，仍会显示警告对话框
        self.app.disk_space_notification_sent = True
        
        # 关闭对话框
        self.open = False
        self.update()
        
    async def confirm_processed(self, _e):
        """用户确认已处理磁盘空间问题，重置通知标记"""
        logger.info("用户确认已处理磁盘空间不足问题，重置通知标记")
        
        # 重置磁盘空间通知标记
        self.app.disk_space_notification_sent = False
        
        # 关闭对话框
        self.open = False
        self.update()
        
        # 立即检查空间是否已恢复
        await self.app.record_manager.check_free_space() 