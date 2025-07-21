import asyncio
import uuid

import flet as ft

from ...core.platforms.platform_handlers import get_platform_info
from ...models.recording.recording_model import Recording
from ...utils.logger import logger
from ..base_page import PageBase
from ..components.business.recording_dialog import RecordingDialog
from ..components.dialogs.help_dialog import HelpDialog
from ..components.dialogs.search_dialog import SearchDialog
from ..filters import RecordingFilters


class RecordingsPage(PageBase):
    def __init__(self, app):
        super().__init__(app)
        self.page_name = "recordings"
        self.recording_card_area = None
        self.add_recording_dialog = None
        self.is_grid_view = app.settings.user_config.get("is_grid_view", True)
        self.loading_indicator = None
        self.app.language_manager.add_observer(self)
        self.load_language()
        self.current_filter = "all"
        self.current_platform_filter = "all"
        self.platform_buttons = {}
        self.init()

    def load_language(self):
        language = self.app.language_manager.language
        for key in ("recordings_page", "video_quality", "base"):
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
        """Load the recordings page content."""
        self.content_area.controls.extend(
            [
                self.create_recordings_title_area(),
                self.create_filter_area(),
                self.create_recordings_content_area()
            ]
        )
        self.content_area.update()
        
        if not self.recording_card_area.content.controls:
            self.recording_card_area.content.controls.clear()
            await self.add_record_cards()
        else:
            # if cards exist, apply filter
            await self.apply_filter()
        
        if self.is_grid_view:
            await self.recalculate_grid_columns()
        
        self.page.on_keyboard_event = self.on_keyboard
        self.page.on_resized = self.update_grid_layout

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
                self.create_recordings_title_area(),
                self.create_filter_area(),
                self.create_recordings_content_area()
            ]
        )
        self.content_area.update()
        
        self.app.settings.user_config["is_grid_view"] = self.is_grid_view
        self.page.run_task(self.app.config_manager.save_user_config, self.app.settings.user_config)

    def create_recordings_title_area(self):
        toggle_view_mode_button = ft.IconButton(
            icon=ft.Icons.GRID_VIEW if self.is_grid_view else ft.Icons.LIST,
            tooltip=self._["toggle_view"],
            on_click=self.toggle_view_mode
        )

        title_controls = [
            ft.Text(self._["recording_list"], theme_style=ft.TextThemeStyle.TITLE_MEDIUM),
            ft.Container(expand=True),
        ]
        
        if not self.app.is_mobile:
            title_controls.append(toggle_view_mode_button)

        batch_controls = [
            ft.IconButton(icon=ft.Icons.SEARCH, tooltip=self._["search"], on_click=self.search_on_click),
            ft.IconButton(icon=ft.Icons.ADD, tooltip=self._["add_record"], on_click=self.add_recording_on_click),
            ft.IconButton(icon=ft.Icons.REFRESH, tooltip=self._["refresh"], on_click=self.refresh_cards_on_click),
            ft.IconButton(
                icon=ft.Icons.PLAY_ARROW,
                tooltip=self._["batch_start"],
                on_click=self.start_monitor_recordings_on_click,
            ),
            ft.IconButton(
                icon=ft.Icons.STOP, 
                tooltip=self._["batch_stop"], 
                on_click=self.stop_monitor_recordings_on_click
            ),
            ft.IconButton(
                icon=ft.Icons.DELETE_SWEEP,
                tooltip=self._["batch_delete"],
                on_click=self.delete_monitor_recordings_on_click,
            ),
        ]
        
        if self.app.is_mobile:
            first_row = ft.Row(
                title_controls,
                alignment=ft.MainAxisAlignment.START,
            )
            second_row = ft.Row(
                [
                    ft.Text(self._["operations"] + ":", size=14),
                    *batch_controls,
                ],
                alignment=ft.MainAxisAlignment.START,
                spacing=2,
                scroll=ft.ScrollMode.HIDDEN
            )
            
            return ft.Column(
                [first_row, second_row],
                spacing=5,
            )
        else:
            return ft.Row(
                [*title_controls, *batch_controls],
                alignment=ft.MainAxisAlignment.START,
            )
    
    def create_filter_area(self):
        """Create the filter area"""

        filter_buttons = [
            ft.Text(self._["status_filter"] + ":" if not self.app.is_mobile else self._["filter"] + ":", size=14),
            ft.ElevatedButton(
                self._["filter_all"],
                on_click=self.filter_all_on_click,
                bgcolor=ft.Colors.BLUE if self.current_filter == "all" else None,
                color=ft.Colors.WHITE if self.current_filter == "all" else None,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=5),
                ),
            ),
            ft.ElevatedButton(
                self._["filter_recording"],
                on_click=self.filter_recording_on_click,
                bgcolor=ft.Colors.GREEN if self.current_filter == "recording" else None,
                color=ft.Colors.WHITE if self.current_filter == "recording" else None,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=5),
                ),
            ),
            ft.ElevatedButton(
                self._["filter_living"],
                on_click=self.filter_living_on_click,
                bgcolor=ft.Colors.BLUE if self.current_filter == "living" else None,
                color=ft.Colors.WHITE if self.current_filter == "living" else None,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=5),
                ),
            ),
            ft.ElevatedButton(
                self._["filter_offline"],
                on_click=self.filter_offline_on_click,
                bgcolor=ft.Colors.AMBER if self.current_filter == "offline" else None,
                color=ft.Colors.WHITE if self.current_filter == "offline" else None,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=5),
                ),
            ),
            ft.ElevatedButton(
                self._["filter_error"],
                on_click=self.filter_error_on_click,
                bgcolor=ft.Colors.RED if self.current_filter == "error" else None,
                color=ft.Colors.WHITE if self.current_filter == "error" else None,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=5),
                ),
            ),
            ft.ElevatedButton(
                self._["filter_stopped"],
                on_click=self.filter_stopped_on_click,
                bgcolor=ft.Colors.GREY if self.current_filter == "stopped" else None,
                color=ft.Colors.WHITE if self.current_filter == "stopped" else None,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=5),
                ),
            ),
        ]
        
        platforms = {}
        for recording in self.app.record_manager.recordings:
            if recording.platform and recording.platform_key:
                platforms[recording.platform_key] = recording.platform
        
        platform_options = [
            ft.dropdown.Option(key="all", text=self._["filter_all"])
        ]
        
        for key, name in platforms.items():
            platform_options.append(ft.dropdown.Option(key=key, text=name))
        
        current_platform_keys = ["all"] + list(platforms.keys())
        if self.current_platform_filter not in current_platform_keys:
            self.current_platform_filter = "all"
        
        platform_dropdown = ft.Dropdown(
            options=platform_options,
            value=self.current_platform_filter,
            on_change=self.on_platform_dropdown_change,
            width=120,
            text_size=14,
            content_padding=ft.padding.only(top=8, bottom=8, left=10, right=10),
            border_radius=5,
            border_color=ft.Colors.OUTLINE,
            focused_border_color=ft.colors.PRIMARY,
            dense=True,
        )
        if len(current_platform_keys) > 8:
            platform_dropdown.menu_height = 320
        
        platform_filter_area = ft.Row(
            [
                ft.Text(self._["platform_filter"] + ":", size=14),
                platform_dropdown
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        
        if self.app.is_mobile:
            status_filter_row = ft.Row(
                filter_buttons,
                alignment=ft.MainAxisAlignment.START,
                spacing=3,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                scroll=ft.ScrollMode.HIDDEN
            )
            
            platform_filter_row = ft.Row(
                [platform_filter_area],
                alignment=ft.MainAxisAlignment.START,
                spacing=5,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
            
            return ft.Column(
                [
                    status_filter_row,
                    platform_filter_row
                ],
                spacing=5,
                alignment=ft.MainAxisAlignment.START,
                horizontal_alignment=ft.CrossAxisAlignment.START,
            )
        else:
            return ft.Row(
                [
                    *filter_buttons,
                    ft.Container(expand=True),
                    platform_filter_area
                ],
                alignment=ft.MainAxisAlignment.START,
                spacing=5,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
    
    async def filter_all_on_click(self, _):
        self.current_filter = "all"
        await self.apply_filter()
    
    async def filter_recording_on_click(self, _):
        self.current_filter = "recording"
        await self.apply_filter()
    
    async def filter_living_on_click(self, _):
        self.current_filter = "living"
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
    
    async def apply_filter(self):
        if len(self.content_area.controls) > 1:
            self.content_area.controls[1] = self.create_filter_area()
        else:
            self.content_area.controls.append(self.create_filter_area())
        
        cards_obj = self.app.record_card_manager.cards_obj
        recordings = self.app.record_manager.recordings
        
        for recording in recordings:
            card_info = cards_obj.get(recording.rec_id)
            if not card_info:
                continue
            
            status_visible = RecordingFilters.get_status_filter_result(recording, self.current_filter)
            platform_visible = RecordingFilters.get_platform_filter_result(recording, self.current_platform_filter)
            
            visible = status_visible and platform_visible
            card_info["card"].visible = visible
        
        self.content_area.update()
        self.recording_card_area.update()

    async def reset_cards_visibility(self):
        cards_obj = self.app.record_card_manager.cards_obj
        for card_info in cards_obj.values():
            if not card_info["card"].visible:
                card_info["card"].visible = True
                card_info["card"].update()

    async def filter_recordings(self, query):
        recordings = self.app.record_manager.recordings
        cards_obj = self.app.record_card_manager.cards_obj

        if not query.strip():
            await self.apply_filter()
            return {}
        else:
            lower_query = query.strip().lower()
            search_ids = {
                rec.rec_id
                for rec in recordings
                if lower_query in str(rec.to_dict()).lower() or lower_query in rec.display_title
            }
            
            filtered_ids = set()
            
            for rec_id in search_ids:
                recording = self.app.record_manager.find_recording_by_id(rec_id)
                if not recording:
                    continue

                if RecordingFilters.should_show_recording(self.current_filter, self.current_platform_filter, recording):
                    filtered_ids.add(rec_id)

            for card_info in cards_obj.values():
                card_info["card"].visible = card_info["card"].key in filtered_ids
                card_info["card"].update()

            if not filtered_ids:
                await self.app.snack_bar.show_snack_bar(self._["not_search_result"], duration=2000)
            return filtered_ids

    def create_recordings_content_area(self):
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
            scroll=ft.ScrollMode.AUTO if not self.app.is_mobile else ft.ScrollMode.HIDDEN,
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
                for card in existing_cards:
                    self.recording_card_area.content.controls.append(card)

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
            if recording_info.get("record_format"):
                recording = Recording(
                    rec_id=str(uuid.uuid4()),
                    url=recording_info["url"],
                    streamer_name=recording_info["streamer_name"],
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
                    only_notify_no_record=recording_info["only_notify_no_record"],
                    flv_use_direct_download=recording_info["flv_use_direct_download"],
                )
            else:
                recording = Recording(
                    rec_id=str(uuid.uuid4()),
                    url=recording_info["url"],
                    streamer_name=recording_info["streamer_name"],
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
                    only_notify_no_record=user_config.get("only_notify_no_record"),
                    flv_use_direct_download=user_config.get("flv_use_direct_download"),
                )

            platform, platform_key = get_platform_info(recording.url)
            if platform and platform_key:
                recording.platform = platform
                recording.platform_key = platform_key

            recording.loop_time_seconds = int(user_config.get("loop_time_seconds", 300))
            recording.update_title(self._[recording.quality])
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
            
            self.content_area.controls[1] = self.create_filter_area()
            self.content_area.update()

        await self.app.snack_bar.show_snack_bar(self._["add_recording_success_tip"], bgcolor=ft.Colors.GREEN)

    async def search_on_click(self, _e):
        """Open the search dialog when the search button is clicked."""
        search_dialog = SearchDialog(recordings_page=self)
        search_dialog.open = True
        self.app.dialog_area.content = search_dialog
        self.app.dialog_area.update()

    async def add_recording_on_click(self, _e):
        await self.add_recording_dialog.show_dialog()

    async def refresh_cards_on_click(self, _e):
        
        self.loading_indicator.visible = True
        self.loading_indicator.update()
        
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
        
        self.content_area.controls[1] = self.create_filter_area()
        self.content_area.update()
        
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

            self.content_area.controls[1] = self.create_filter_area()
            self.content_area.update()
            
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
        
        self.current_platform_filter = "all"
        
        self.content_area.controls[1] = self.create_filter_area()
        self.content_area.update()

    async def subscribe_del_all_cards(self, *_):
        await self.delete_all_recording_cards()

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

        if self.app.is_mobile:
            column_width = 250
            child_aspect_ratio = 2.5
        else:
            column_width = 350
            child_aspect_ratio = 2.3

        runs_count = max(1, int(self.page.width / column_width))

        if isinstance(self.recording_card_area.content, ft.GridView):
            grid_view = self.recording_card_area.content
            grid_view.runs_count = runs_count
            
            grid_view.child_aspect_ratio = child_aspect_ratio
            
            if self.app.is_mobile:
                grid_view.spacing = 5
                grid_view.run_spacing = 5
            
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

    def on_platform_dropdown_change(self, e):
        self.current_platform_filter = e.control.value
        self.page.run_task(self.apply_filter)
