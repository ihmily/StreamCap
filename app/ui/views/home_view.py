import asyncio
import uuid

import flet as ft

from ...core.platform_handlers import get_platform_info
from ...models.recording_model import Recording
from ...models.recording_status_model import RecordingStatus
from ...utils.logger import logger
from ..base_page import PageBase
from ..components.help_dialog import HelpDialog
from ..components.recording_dialog import RecordingDialog
from ..components.search_dialog import SearchDialog
from app.core.platform_handlers.platform_map import get_platform_display_name


class HomePage(PageBase):
    def __init__(self, app):
        super().__init__(app)
        self.page_name = "home"
        self.recording_card_area = None
        self.add_recording_dialog = None
        self.is_grid_view = app.settings.user_config.get("is_grid_view", True)
        self.loading_indicator = None
        self.app.language_manager.add_observer(self)
        self.load_language()
        self.current_filter = "all"
        self.current_platform_filter = "all"
        self.platform_dropdown = None
        self.init()

    def load_language(self):
        language = self.app.language_manager.language
        for key in ("home_page", "video_quality", "base"):
            self._.update(language.get(key, {}))

    def init(self):
        self.loading_indicator = ft.ProgressRing(
            width=40, 
            height=40, 
            stroke_width=3,
            visible=False
        )
        
        if self.is_grid_view:
            initial_content = ft.GridView(
                expand=True,
                runs_count=3,
                spacing=10,
                run_spacing=10,
                child_aspect_ratio=2.3,
                controls=[]
            )
        else:
            initial_content = ft.Column(
                controls=[], 
                spacing=5, 
                expand=True
            )
        
        self.recording_card_area = ft.Container(
            content=initial_content,
            expand=True
        )
        self.add_recording_dialog = RecordingDialog(self.app, self.add_recording)
        self.pubsub_subscribe()

    async def load(self):
        """Load the home page content."""
        self.content_area.controls.extend(
            [
                self.create_home_title_area(),
                self.create_filter_area(),
                self.create_home_content_area()
            ]
        )
        self.content_area.update()
        
        self.recording_card_area.content.controls.clear()
        await self.add_record_cards()
        
        if self.is_grid_view:
            await self.recalculate_grid_columns()
        
        self.page.on_keyboard_event = self.on_keyboard
        self.page.on_resized = self.update_grid_layout
        
        # 确保录制卡片显示正确的格式和分段时间
        if hasattr(self.app, "config_validator"):
            self.page.run_task(self.app.config_validator.update_recording_cards)

    def pubsub_subscribe(self):
        self.app.page.pubsub.subscribe_topic('add', self.subscribe_add_cards)
        self.app.page.pubsub.subscribe_topic('delete_all', self.subscribe_del_all_cards)

    async def toggle_view_mode(self, _):
        self.is_grid_view = not self.is_grid_view
        current_content = self.recording_card_area.content
        current_controls = current_content.controls if hasattr(current_content, 'controls') else []

        column_width = 350
        runs_count = max(1, int(self.page.width / column_width))

        if self.is_grid_view:
            new_content = ft.GridView(
                expand=True,
                runs_count=runs_count,
                spacing=10,
                run_spacing=10,
                child_aspect_ratio=2.3,
                controls=current_controls
            )
        else:
            new_content = ft.Column(
                controls=current_controls,
                spacing=5,
                expand=True
            )

        self.recording_card_area.content = new_content
        self.content_area.clean()
        self.content_area.controls.extend(
            [
                self.create_home_title_area(),
                self.create_filter_area(),
                self.create_home_content_area()
            ]
        )
        self.content_area.update()
        
        self.app.settings.user_config["is_grid_view"] = self.is_grid_view
        self.page.run_task(self.app.config_manager.save_user_config, self.app.settings.user_config)

    def create_home_title_area(self):
        return ft.Row(
            [
                ft.Text(self._["recording_list"], theme_style=ft.TextThemeStyle.TITLE_MEDIUM),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.Icons.GRID_VIEW if self.is_grid_view else ft.Icons.LIST,
                    tooltip=self._["toggle_view"],
                    on_click=self.toggle_view_mode
                ),
                ft.IconButton(icon=ft.Icons.SEARCH, tooltip=self._["search"], on_click=self.search_on_click),
                ft.IconButton(icon=ft.Icons.ADD, tooltip=self._["add_record"], on_click=self.add_recording_on_click),
                ft.IconButton(icon=ft.Icons.REFRESH, tooltip=self._["refresh"], on_click=self.refresh_cards_on_click),
                ft.IconButton(
                    icon=ft.Icons.PLAY_ARROW,
                    tooltip=self._["batch_start"],
                    on_click=self.start_monitor_recordings_on_click,
                ),
                ft.IconButton(
                    icon=ft.Icons.STOP, tooltip=self._["batch_stop"], on_click=self.stop_monitor_recordings_on_click
                ),
                ft.IconButton(
                    icon=ft.Icons.DELETE_SWEEP,
                    tooltip=self._["batch_delete"],
                    on_click=self.delete_monitor_recordings_on_click,
                ),
            ],
            alignment=ft.MainAxisAlignment.START,
        )
    
    def create_filter_area(self):
        """Create the filter area"""
        platforms = self.get_available_platforms()
        style = self.app.settings.user_config.get("platform_filter_style", "tile")
        lang = getattr(self.app, 'language_code', 'zh_CN')
        def get_display_name(key):
            return get_platform_display_name(key, lang)

        if style == "dropdown":
            # 下拉框风格
            platform_dropdown = ft.Dropdown(
            value=self.current_platform_filter,
            options=[
                ft.dropdown.Option(key="all", text=self._["filter_all_platforms"]),
                    *[ft.dropdown.Option(key=platform[1], text=get_display_name(platform[1])) for platform in platforms]
            ],
            on_change=self.on_platform_filter_change,
                width=200,
            )
            platform_filter_control = platform_dropdown
        else:
            # 平铺按钮组风格
            platform_buttons = [
                ft.ElevatedButton(
                    self._["filter_all_platforms"],
                    on_click=self.filter_all_platforms_on_click,
                    bgcolor=ft.colors.BLUE if self.current_platform_filter == "all" else None,
                    color=ft.colors.WHITE if self.current_platform_filter == "all" else None,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5)),
                )
            ]
            for name, key in platforms:
                selected = self.current_platform_filter == key
                platform_buttons.append(
                    ft.ElevatedButton(
                        get_display_name(key),
                        on_click=lambda e, k=key: self.on_platform_button_click(k),
                        bgcolor=ft.colors.BLUE if selected else None,
                        color=ft.colors.WHITE if selected else None,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5)),
                    )
                )
            platform_filter_control = ft.Container(
                content=ft.Row(
                    platform_buttons,
                    alignment=ft.MainAxisAlignment.START,
                    spacing=5,
                    scroll=ft.ScrollMode.AUTO,
                    wrap=False
                ),
                expand=True,
        )
        
        return ft.Column(
            controls=[
                ft.Row(
                    [
                        ft.Text(self._["filter"] + ":", size=14),
                        ft.ElevatedButton(
                            self._["filter_all"],
                            on_click=self.filter_all_on_click,
                            bgcolor=ft.colors.BLUE if self.current_filter == "all" else None,
                            color=ft.colors.WHITE if self.current_filter == "all" else None,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5)),
                        ),
                        ft.ElevatedButton(
                            self._["filter_recording"],
                            on_click=self.filter_recording_on_click,
                            bgcolor=ft.colors.GREEN if self.current_filter == "recording" else None,
                            color=ft.colors.WHITE if self.current_filter == "recording" else None,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5)),
                            ),
                        ft.ElevatedButton(
                            self._["filter_live_monitoring_not_recording"],
                            on_click=self.filter_live_monitoring_not_recording_on_click,
                            bgcolor=ft.colors.CYAN if self.current_filter == "live_monitoring_not_recording" else None,
                            color=ft.colors.WHITE if self.current_filter == "live_monitoring_not_recording" else None,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5)),
                        ),
                        ft.ElevatedButton(
                            self._["filter_offline"],
                            on_click=self.filter_offline_on_click,
                            bgcolor=ft.colors.AMBER if self.current_filter == "offline" else None,
                            color=ft.colors.WHITE if self.current_filter == "offline" else None,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5)),
                        ),
                        ft.ElevatedButton(
                            self._["filter_error"],
                            on_click=self.filter_error_on_click,
                            bgcolor=ft.colors.RED if self.current_filter == "error" else None,
                            color=ft.colors.WHITE if self.current_filter == "error" else None,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5)),
                        ),
                        ft.ElevatedButton(
                            self._["filter_stopped"],
                            on_click=self.filter_stopped_on_click,
                            bgcolor=ft.colors.GREY if self.current_filter == "stopped" else None,
                            color=ft.colors.WHITE if self.current_filter == "stopped" else None,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5)),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    spacing=5,
                ),
                ft.Row(
                    [
                        ft.Text(self._["platform_filter"] + ":", size=14),
                        platform_filter_control
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    spacing=5,
                ),
            ],
            spacing=5,
        )
    
    def get_available_platforms(self):
        platforms = set()
        recordings = self.app.record_manager.recordings
        
        for recording in recordings:
            if hasattr(recording, 'url') and recording.url:
                platform_name, platform_key = get_platform_info(recording.url)
                if platform_name and platform_key:
                    platforms.add((platform_name, platform_key))
        
        return sorted(list(platforms), key=lambda x: x[0])
    
    async def on_platform_filter_change(self, e):
        self.current_platform_filter = e.control.value
        await self.apply_filter()

    async def filter_all_on_click(self, _):
        self.current_filter = "all"
        await self.apply_filter()
    
    async def filter_recording_on_click(self, _):
        self.current_filter = "recording"
        await self.apply_filter()
    
    async def filter_error_on_click(self, _):
        self.current_filter = "error"
        await self.apply_filter()
    
    async def filter_offline_on_click(self, _):
        self.current_filter = "offline"
        await self.apply_filter()
    
    async def filter_stopped_on_click(self, _):
        self.current_filter = "stopped"
        await self.apply_filter()
    
    async def filter_live_monitoring_not_recording_on_click(self, _):
        self.current_filter = "live_monitoring_not_recording"
        await self.apply_filter()
    
    async def apply_filter(self):
        self.content_area.controls[1] = self.create_filter_area()
        
        cards_obj = self.app.record_card_manager.cards_obj
        recordings = self.app.record_manager.recordings
        
        for recording in recordings:
            card_info = cards_obj.get(recording.rec_id)
            if not card_info:
                continue
                
            visible = self.should_show_recording(self.current_filter, recording, self.current_platform_filter)
            card_info["card"].visible = visible
        
        self.recording_card_area.content.update()
        self.content_area.update()

    async def reset_cards_visibility(self):
        cards_obj = self.app.record_card_manager.cards_obj
        for card_info in cards_obj.values():
            if not card_info["card"].visible:
                card_info["card"].visible = True
                card_info["card"].update()

    @staticmethod
    def should_show_recording(filter_type, recording, platform_filter="all"):
        if platform_filter != "all":
            _, platform_key = get_platform_info(recording.url)
            if platform_key != platform_filter:
                return False
        
        if filter_type == "all":
            return True
        elif filter_type == "recording":
            return recording.recording
        elif filter_type == "live_monitoring_not_recording":
            return recording.is_live and recording.monitor_status and not recording.recording
        elif filter_type == "error":
            return recording.status_info == RecordingStatus.RECORDING_ERROR
        elif filter_type == "offline":
            return not recording.is_live and recording.monitor_status
        elif filter_type == "stopped":
            return not recording.monitor_status
        return True

    async def filter_recordings(self, query):
        cards_obj = self.app.record_card_manager.cards_obj
        recordings = self.app.record_manager.recordings
        
        for recording in recordings:
            card_info = cards_obj.get(recording.rec_id)
            if not card_info:
                continue
                
            match_query = (
                query.lower() in recording.streamer_name.lower()
                or query.lower() in recording.url.lower()
                or (recording.live_title and query.lower() in recording.live_title.lower())
            )
            
            match_platform = True
            if self.current_platform_filter != "all":
                _, platform_key = get_platform_info(recording.url)
                match_platform = (platform_key == self.current_platform_filter)
                
            visible = match_query and match_platform
            card_info["card"].visible = visible
        
        self.recording_card_area.content.update()

    def create_home_content_area(self):
        return ft.Column(
            expand=True,
            controls=[
                ft.Divider(height=1),
                ft.Container(
                    content=self.loading_indicator,
                    alignment=ft.alignment.center
                ),
                self.recording_card_area,
            ],
            scroll=ft.ScrollMode.AUTO,
        )

    async def add_record_cards(self):
        
        self.loading_indicator.visible = True
        self.loading_indicator.update()

        cards_to_create = []
        existing_cards = []
        
        for recording in self.app.record_manager.recordings:
            if recording.rec_id not in self.app.record_card_manager.cards_obj:
                cards_to_create.append(recording)
            else:
                existing_card = self.app.record_card_manager.cards_obj[recording.rec_id]["card"]
                existing_card.visible = True
                existing_cards.append(existing_card)
        
        async def create_card_with_time_range(_recording: Recording):
            _card = await self.app.record_card_manager.create_card(_recording)
            _recording.scheduled_time_range = await self.app.record_manager.get_scheduled_time_range(
                _recording.scheduled_start_time, _recording.monitor_hours
            )
            return _card, _recording
        
        if cards_to_create:
            results = await asyncio.gather(*[
                create_card_with_time_range(recording)
                for recording in cards_to_create
            ])
            
            for card, recording in results:
                self.recording_card_area.content.controls.append(card)
                self.app.record_card_manager.cards_obj[recording.rec_id]["card"] = card
        
        if existing_cards:
            self.recording_card_area.content.controls.extend(existing_cards)

        self.loading_indicator.visible = False
        self.loading_indicator.update()
        self.recording_card_area.update()
        
        if not self.app.record_manager.periodic_task_started:
            self.page.run_task(
                self.app.record_manager.setup_periodic_live_check,
                self.app.record_manager.loop_time_seconds
            )
        
        await self.apply_filter()

    async def show_all_cards(self):
        cards_obj = self.app.record_card_manager.cards_obj
        for card in cards_obj.values():
            card["card"].visible = True
        self.recording_card_area.update()
        
        await self.apply_filter()

    async def add_recording(self, recordings_info):
        user_config = self.app.settings.user_config
        logger.info(f"Add items: {len(recordings_info)}")
        
        new_recordings = []
        for recording_info in recordings_info:
            streamer_name = recording_info.get("streamer_name")
            live_title = recording_info.get("live_title")
            title = recording_info.get("title")
            display_title = recording_info.get("display_title")
            if recording_info.get("record_format"):
                recording = Recording(
                    rec_id=str(uuid.uuid4()),
                    url=recording_info["url"],
                    streamer_name=streamer_name,
                    quality=recording_info["quality"],
                    record_format=recording_info["record_format"],
                    segment_record=recording_info["segment_record"],
                    segment_time=recording_info["segment_time"],
                    monitor_status=recording_info["monitor_status"],
                    scheduled_recording=recording_info["scheduled_recording"],
                    scheduled_start_time=recording_info["scheduled_start_time"],
                    monitor_hours=recording_info["monitor_hours"],
                    recording_dir=recording_info["recording_dir"],
                    enabled_message_push=recording_info["enabled_message_push"],
                    record_mode=recording_info.get("record_mode", "auto")
                )
            else:
                recording = Recording(
                    rec_id=str(uuid.uuid4()),
                    url=recording_info["url"],
                    streamer_name=streamer_name,
                    quality=recording_info["quality"],
                    record_format=user_config.get("video_format", "TS"),
                    segment_record=user_config.get("segmented_recording_enabled", False),
                    segment_time=user_config.get("video_segment_time", "1800"),
                    monitor_status=True,
                    scheduled_recording=user_config.get("scheduled_recording", False),
                    scheduled_start_time=user_config.get("scheduled_start_time"),
                    monitor_hours=user_config.get("monitor_hours"),
                    recording_dir=None,
                    enabled_message_push=False,
                    record_mode=recording_info.get("record_mode", "auto")
                )
            recording.live_title = live_title
            if title:
                recording.title = title
            if display_title:
                recording.display_title = display_title
            recording.loop_time_seconds = int(user_config.get("loop_time_seconds", 300))
            await self.app.record_manager.add_recording(recording)
            new_recordings.append(recording)

        if new_recordings:
            async def create_card_with_time_range(rec):
                _card = await self.app.record_card_manager.create_card(rec)
                rec.scheduled_time_range = await self.app.record_manager.get_scheduled_time_range(
                    rec.scheduled_start_time, rec.monitor_hours
                )
                return _card, rec

            results = await asyncio.gather(*[
                create_card_with_time_range(rec)
                for rec in new_recordings
            ])

            for card, recording in results:
                self.recording_card_area.content.controls.append(card)
                self.app.record_card_manager.cards_obj[recording.rec_id]["card"] = card
                self.app.page.pubsub.send_others_on_topic("add", recording)
            
            self.recording_card_area.update()

        await self.app.snack_bar.show_snack_bar(self._["add_recording_success_tip"], bgcolor=ft.Colors.GREEN)
        self.content_area.controls[1] = self.create_filter_area()
        self.content_area.update()

    async def search_on_click(self, _e):
        """Open the search dialog when the search button is clicked."""
        search_dialog = SearchDialog(home_page=self)
        search_dialog.open = True
        self.app.dialog_area.content = search_dialog
        self.app.dialog_area.update()

    async def add_recording_on_click(self, _e):
        await self.add_recording_dialog.show_dialog()

    async def refresh_cards_on_click(self, _e):
        self.loading_indicator.visible = True
        self.loading_indicator.update()

        self.app.record_card_manager.load()

        cards_obj = self.app.record_card_manager.cards_obj
        recordings = self.app.record_manager.recordings
        selected_cards = self.app.record_card_manager.selected_cards
        new_ids = {rec.rec_id for rec in recordings}
        to_remove = []
        for card_id, card in cards_obj.items():
            if card_id not in new_ids:
                to_remove.append(card)
                continue
            if card_id in selected_cards:
                selected_cards[card_id].selected = False
                card["card"].content.bgcolor = None
                card["card"].update()

        for card in to_remove:
            card_key = card["card"].key
            cards_obj.pop(card_key, None)
            self.recording_card_area.controls.remove(card["card"])
        await self.show_all_cards()

        for recording in recordings:
            await self.app.record_card_manager.update_card(recording)
            await asyncio.sleep(0.05)

        self.loading_indicator.visible = False
        self.loading_indicator.update()

        await self.app.snack_bar.show_snack_bar(self._["refresh_success_tip"], bgcolor=ft.Colors.GREEN)

    async def start_monitor_recordings_on_click(self, _):
        await self.app.record_manager.check_free_space()
        if self.app.recording_enabled:
            await self.app.record_manager.start_monitor_recordings()
            await self.app.snack_bar.show_snack_bar(self._["start_recording_success_tip"], bgcolor=ft.Colors.GREEN)

    async def stop_monitor_recordings_on_click(self, _):
        await self.app.record_manager.stop_monitor_recordings()
        await self.app.snack_bar.show_snack_bar(self._["stop_recording_success_tip"])

    async def delete_monitor_recordings_on_click(self, _):
        selected_recordings = await self.app.record_manager.get_selected_recordings()
        tips = self._["batch_delete_confirm_tip"] if selected_recordings else self._["clear_all_confirm_tip"]

        async def confirm_dlg(_):

            if selected_recordings:
                await self.app.record_manager.stop_monitor_recordings(selected_recordings)
                await self.app.record_manager.delete_recording_cards(selected_recordings)
            else:
                await self.app.record_manager.stop_monitor_recordings(self.app.record_manager.recordings)
                await self.app.record_manager.clear_all_recordings()
                await self.delete_all_recording_cards()
                self.app.page.pubsub.send_others_on_topic("delete_all", None)

            self.recording_card_area.update()
            await self.app.snack_bar.show_snack_bar(
                self._["delete_recording_success_tip"], bgcolor=ft.Colors.GREEN, duration=2000
            )
            await close_dialog(None)

        async def close_dialog(_):
            batch_delete_alert_dialog.open = False
            batch_delete_alert_dialog.update()

        batch_delete_alert_dialog = ft.AlertDialog(
            title=ft.Text(self._["confirm"]),
            content=ft.Text(tips),
            actions=[
                ft.TextButton(text=self._["cancel"], on_click=close_dialog),
                ft.TextButton(text=self._["sure"], on_click=confirm_dlg),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            modal=False,
        )

        batch_delete_alert_dialog.open = True
        self.app.dialog_area.content = batch_delete_alert_dialog
        self.page.update()

    async def delete_all_recording_cards(self):
        self.recording_card_area.content.controls.clear()
        self.recording_card_area.update()
        self.app.record_card_manager.cards_obj = {}
        self.content_area.controls[1] = self.create_filter_area()
        self.content_area.update()

    async def subscribe_del_all_cards(self, *_):
        await self.delete_all_recording_cards()
        self.content_area.controls[1] = self.create_filter_area()
        self.content_area.update()

    async def subscribe_add_cards(self, _, recording: Recording):
        """Handle the subscription of adding cards from other clients"""
        
        self.loading_indicator.visible = True
        self.loading_indicator.update()
        
        if recording.rec_id not in self.app.record_card_manager.cards_obj:
            card = await self.app.record_card_manager.create_card(recording)
            recording.scheduled_time_range = await self.app.record_manager.get_scheduled_time_range(
                recording.scheduled_start_time, recording.monitor_hours
            )
            
            self.recording_card_area.content.controls.append(card)
            self.app.record_card_manager.cards_obj[recording.rec_id]["card"] = card
            
            self.loading_indicator.visible = False
            self.loading_indicator.update()
            
            self.recording_card_area.update()
            self.content_area.controls[1] = self.create_filter_area()
            self.content_area.update()

    async def update_grid_layout(self, _):
        self.page.run_task(self.recalculate_grid_columns)

    async def recalculate_grid_columns(self):
        if not self.is_grid_view:
            return

        column_width = 350
        runs_count = max(1, int(self.page.width / column_width))

        if isinstance(self.recording_card_area.content, ft.GridView):
            grid_view = self.recording_card_area.content
            grid_view.runs_count = runs_count
            grid_view.update()

    async def on_keyboard(self, e: ft.KeyboardEvent):
        if e.alt and e.key == "H":
            self.app.dialog_area.content = HelpDialog(self.app)
            self.app.dialog_area.content.open = True
            self.app.dialog_area.update()
        if self.app.current_page == self:
            if e.ctrl and e.key == "F":
                self.page.run_task(self.search_on_click, e)
            elif e.ctrl and e.key == "R":
                self.page.run_task(self.refresh_cards_on_click, e)
            elif e.alt and e.key == "N":
                self.page.run_task(self.add_recording_on_click, e)
            elif e.alt and e.key == "B":
                self.page.run_task(self.start_monitor_recordings_on_click, e)
            elif e.alt and e.key == "P":
                self.page.run_task(self.stop_monitor_recordings_on_click, e)
            elif e.alt and e.key == "D":
                self.page.run_task(self.delete_monitor_recordings_on_click, e)

    def filter_all_platforms_on_click(self, _):
        self.current_platform_filter = "all"
        self.page.run_task(self.apply_filter)

    def on_platform_button_click(self, key):
        self.current_platform_filter = key
        self.page.run_task(self.apply_filter)
