import asyncio
import flet as ft
from app.core.platform_handlers.platform_map import get_platform_display_name


class SearchDialog(ft.AlertDialog):
    def __init__(self, home_page, on_close=None):
        self.home_page = home_page
        self._ = {}
        self.load()
        self.search_results = []
        self.result_controls = []

        super().__init__(
            title=ft.Text(self._["search_title"], size=20, weight=ft.FontWeight.BOLD),
            content_padding=ft.padding.only(left=20, top=15, right=20, bottom=20),
        )
        
        # 搜索说明文本
        self.description = ft.Text(
            self._["search_description"],
            size=14,
            color=ft.colors.GREY_700,
            italic=True
        )
        
        # 支持的搜索内容说明文本（使用高亮样式）
        self.search_support = ft.Container(
            content=ft.Text(
                self._["search_support"],
                size=14,
                color=ft.colors.WHITE,
                weight=ft.FontWeight.BOLD,
                text_align=ft.TextAlign.CENTER,
            ),
            bgcolor=ft.colors.BLUE,
            border_radius=5,
            padding=10,
            margin=ft.margin.only(top=5, bottom=10),
            width=450,
            alignment=ft.alignment.center,
        )
        
        # 搜索输入框
        self.query = ft.TextField(
            hint_text=self._["search_keyword"],
            expand=True,
            border_radius=5,
            border_color=ft.Colors.GREY_400,
            focused_border_color=ft.Colors.BLUE,
            cursor_color=ft.Colors.BLACK,
            hint_style=ft.TextStyle(color=ft.Colors.GREY_500, size=14),
            text_style=ft.TextStyle(size=16, color=ft.Colors.BLACK),
            on_submit=self.submit_query,
        )
        
        # 没有结果时的提示文本
        self.no_results_text = ft.Text(
            self._["no_results_found"],
            size=16,
            color=ft.colors.RED_400,
            text_align=ft.TextAlign.CENTER,
            visible=False
        )
        
        # 结果计数文本
        self.result_count_text = ft.Text(
            "",
            size=14,
            color=ft.colors.BLUE_700,
            visible=False
        )
        
        # 结果列表容器
        self.results_container = ft.Container(
            content=ft.ListView(
                controls=[],
                spacing=5,
                auto_scroll=False,
                expand=True,
            ),
            expand=True,
            height=300,
            visible=False,
            border=ft.border.all(1, ft.colors.GREY_300),
            border_radius=5,
            padding=10,
        )
        
        # 清空时的提示文本
        self.empty_reset_text = ft.Text(
            self._["empty_to_reset"],
            size=12,
            color=ft.colors.GREY_500,
            italic=True
        )
        
        self.actions = [
            ft.TextButton(
                self._["cancel"],
                icon=ft.icons.CLOSE,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5)),
                on_click=self.close_dlg,
            ),
            ft.TextButton(
                self._["search"],
                icon=ft.icons.SEARCH,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5)),
                on_click=self.submit_query,
            ),
        ]
        
        self.content = ft.Column(
            [
                self.description,
                self.search_support,  # 添加支持的搜索内容说明
                ft.Row([self.query], tight=True),
                ft.Divider(height=1, thickness=1, color=ft.Colors.GREY_300),
                self.no_results_text,
                self.result_count_text,
                self.results_container,
                self.empty_reset_text
            ],
            tight=True,
            width=500,
            height=500,
            spacing=5
        )
        
        self.actions_alignment = ft.MainAxisAlignment.END
        self.on_close = on_close
        self.home_page.app.language_manager.add_observer(self)

    def load(self):
        language = self.home_page.app.language_manager.language
        for key in ("search_dialog", "home_page", "base"):
            self._.update(language.get(key, {}))

    def normalize_text(self, text):
        """将文本标准化处理，用于忽略大小写和重音符号的搜索"""
        if not text:
            return ""
        # 只做简单的大小写转换处理
        return text.lower()

    def create_result_item(self, recording, index):
        """创建单个搜索结果项"""
        # 获取平台名称显示
        platform_name = ""
        try:
            from app.core.platform_handlers import get_platform_info
            _, platform_key = get_platform_info(recording.url)
            lang = getattr(self.home_page.app, 'language_code', 'zh_CN')
            platform_name = get_platform_display_name(platform_key, lang)
        except:
            platform_name = "未知平台"
            
        # 状态显示
        status_text = self._["filter_offline"]  # 默认显示为未开播
        status_color = ft.colors.AMBER
        
        if recording.recording:
            status_text = self._["filter_recording"]
            status_color = ft.colors.GREEN
        elif recording.is_live and recording.monitor_status:
            status_text = self._["filter_live_monitoring_not_recording"]
            status_color = ft.colors.CYAN
        elif not recording.monitor_status:
            status_text = self._["filter_stopped"]
            status_color = ft.colors.GREY
            
        # 创建点击响应函数
        async def on_item_click(_):
            await self.close_dlg(None)
            await self.navigate_to_recording(recording)
            
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(
                        f"{index+1}. {recording.streamer_name}", 
                        size=16, 
                        weight=ft.FontWeight.BOLD,
                        no_wrap=True,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        expand=True
                    ),
                    ft.Container(
                        content=ft.Text(
                            status_text,
                            size=12,
                            color=ft.colors.WHITE,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        bgcolor=status_color,
                        border_radius=10,
                        padding=ft.padding.only(left=8, right=8, top=3, bottom=3)
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([
                    ft.Text(
                        f"平台: {platform_name}", 
                        size=13, 
                        color=ft.colors.BLUE_GREY_400
                    ),
                    ft.Container(expand=True),
                    ft.Text(
                        self._["click_to_view"],
                        size=12,
                        color=ft.colors.BLUE,
                        italic=True
                    )
                ]),
                ft.Text(
                    recording.live_title or "", 
                    size=13, 
                    color=ft.colors.GREY_700,
                    italic=True,
                    no_wrap=True,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    expand=True
                ),
            ], spacing=2, tight=True),
            border_radius=5,
            border=ft.border.all(1, ft.colors.GREY_300),
            padding=8,
            margin=ft.margin.only(bottom=2),
            ink=True,
            on_click=on_item_click,
            tooltip=self._["click_to_view"]
        )

    async def navigate_to_recording(self, recording):
        """导航到指定的直播间记录"""
        # 1. 切换到对应平台的筛选条件
        try:
            from app.core.platform_handlers import get_platform_info
            _, platform_key = get_platform_info(recording.url)
            # 设置平台筛选为直播间所属平台
            self.home_page.current_platform_filter = platform_key
        except:
            # 如果获取平台失败，则切换到全部平台
            self.home_page.current_platform_filter = "all"
        
        # 应用平台筛选
        await self.home_page.apply_filter()
        
        # 2. 切换到合适的状态筛选标签
        if recording.recording:
            await self.home_page.filter_recording_on_click(None)
        elif recording.is_live and recording.monitor_status and not recording.recording:
            await self.home_page.filter_live_monitoring_not_recording_on_click(None)
        elif not recording.is_live and recording.monitor_status:
            await self.home_page.filter_offline_on_click(None)
        elif not recording.monitor_status:
            await self.home_page.filter_stopped_on_click(None)
        else:
            await self.home_page.filter_all_on_click(None)
            
        # 3. 找到并突出显示该卡片
        card_info = self.home_page.app.record_card_manager.cards_obj.get(recording.rec_id)
        if card_info and card_info.get("card"):
            card = card_info["card"]
            
            # 确保该卡片可见
            card.visible = True
            
            # 设置一个突出显示效果（例如闪烁动画）
            original_bgcolor = card.content.bgcolor
            
            # 闪烁高亮
            for _ in range(3):
                card.content.bgcolor = ft.colors.BLUE_100
                card.update()
                await asyncio.sleep(0.3)
                card.content.bgcolor = original_bgcolor
                card.update()
                await asyncio.sleep(0.3)
                
            # 滚动到该卡片（暂不实现，因为Flet目前不直接支持滚动到特定控件）
            # 未来可能通过实现自定义控件或其他方式实现

    async def search_recordings(self, query):
        """搜索所有直播间，忽略当前筛选条件"""
        # 清空上次搜索结果
        self.search_results = []
        self.results_container.content.controls.clear()
        
        # 如果查询为空，则不进行搜索，直接返回
        if not query.strip():
            self.no_results_text.visible = False
            self.result_count_text.visible = False
            self.results_container.visible = False
            self.update()
            return
            
        recordings = self.home_page.app.record_manager.recordings
        normalized_query = self.normalize_text(query)
        
        # 进行搜索匹配
        for recording in recordings:
            # 标准化处理各种字段以便进行不区分大小写和重音符号的搜索
            normalized_streamer_name = self.normalize_text(recording.streamer_name)
            normalized_url = self.normalize_text(recording.url)
            normalized_live_title = self.normalize_text(recording.live_title)
            
            # 获取平台名称并标准化
            try:
                from app.core.platform_handlers import get_platform_info
                _, platform_key = get_platform_info(recording.url)
                lang = getattr(self.home_page.app, 'language_code', 'zh_CN')
                platform_name = get_platform_display_name(platform_key, lang)
                normalized_platform_name = self.normalize_text(platform_name)
            except:
                platform_name = ""
                normalized_platform_name = ""
                
            # 进行匹配
            if (normalized_query in normalized_streamer_name or
                normalized_query in normalized_url or
                (normalized_live_title and normalized_query in normalized_live_title) or
                (normalized_platform_name and normalized_query in normalized_platform_name)):
                self.search_results.append(recording)
                
        # 显示搜索结果
        if not self.search_results:
            self.no_results_text.visible = True
            self.result_count_text.visible = False
            self.results_container.visible = False
        else:
            self.no_results_text.visible = False
            
            # 更新结果计数
            count = len(self.search_results)
            self.result_count_text.value = self._["result_count"].replace("{count}", str(count))
            self.result_count_text.visible = True
            
            # 创建结果列表
            for i, recording in enumerate(self.search_results):
                result_item = self.create_result_item(recording, i)
                self.results_container.content.controls.append(result_item)
                
            self.results_container.visible = True
            
        self.update()

    async def close_dlg(self, _e):
        """关闭对话框"""
        self.open = False
        self.update()

    async def submit_query(self, e):
        """提交搜索查询"""
        query = self.query.value.strip()
        
        # 如果查询为空，恢复应用当前的筛选条件
        if not query:
            await self.home_page.apply_filter()
            await self.close_dlg(e)
            return
            
        # 执行搜索
        await self.search_recordings(query)
