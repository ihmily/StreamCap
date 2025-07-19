import flet as ft

from ....messages.message_pusher import MessagePusher


class CardDialog(ft.AlertDialog):
    def __init__(self, app, recording):
        self.app = app
        self._ = {}
        self.load()
        super().__init__(
            title=ft.Text(self._["recording_info"]),
            content=self.get_content(recording),
            actions=[
                ft.TextButton(self._["close"], on_click=self.close_panel),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            modal=False,
        )

    def load(self):
        language = self.app.language_manager.language
        for key in ("recording_card", "recording_manager", "base", "video_quality", "recording_dialog"):
            self._.update(language.get(key, {}))

    def get_content(self, recording):
        """Record card information content"""
        anchor_name = recording.streamer_name
        platform_name = recording.platform
        live_link = recording.url
        live_title = recording.live_title or self._["none"]
        record_format = recording.record_format
        quality_info = self._[recording.quality]
        use_proxy = self._["yes"] if recording.use_proxy else self._["no"]
        segment_record_status = self._["enabled"] if recording.segment_record else self._["disabled"]
        segment_time = f"{recording.segment_time}{self._['seconds']}"
        monitor_status = self._["enabled"] if recording.monitor_status else self._["disabled"]
        scheduled_recording_status = self._["enabled"] if recording.scheduled_recording else self._["disabled"]
        scheduled_time_range = recording.scheduled_time_range or self._["none"]
        save_path = recording.recording_dir or self._["no_recording_dir_tip"]
        recording_status_info = self._[recording.status_info]
        should_push_message = MessagePusher.should_push_message(self.app.settings, recording)
        message_push = self._["enabled"] if should_push_message else self._["disabled"]
        only_notify_no_record = self._["enabled"] if recording.only_notify_no_record else self._["disabled"]

        dialog_content = ft.Column(
            [
                ft.Text(f"{self._['anchor_name']}: {anchor_name}", size=14, selectable=True),
                ft.Text(f"{self._['platform_name']}: {platform_name}", size=14, selectable=True),
                ft.Text(f"{self._['live_link']}: {live_link}", size=14, selectable=True),
                ft.Text(f"{self._['live_title']}: {live_title}", size=14, selectable=True),
                ft.Text(f"{self._['record_format']}: {record_format}", size=14),
                ft.Text(f"{self._['record_quality']}: {quality_info}", size=14),
                ft.Text(f"{self._['use_proxy']}: {use_proxy}", size=14),
                ft.Text(f"{self._['segment_record']}: {segment_record_status}", size=14),
                ft.Text(f"{self._['segment_time']}: {segment_time}", size=14),
                ft.Text(f"{self._['monitor_status']}: {monitor_status}", size=14),
                ft.Text(f"{self._['scheduled_recording']}: {scheduled_recording_status}", size=14),
                ft.Text(f"{self._['scheduled_time_range']}: {scheduled_time_range}", size=14),
                ft.Text(f"{self._['message_push']}: {message_push}", size=14),
                ft.Text(f"{self._['only_notify_no_record']}: {only_notify_no_record}", size=14),
                ft.Text(f"{self._['save_path']}: {save_path}", size=14, selectable=True),
                ft.Text(f"{self._['recording_status']}: {recording_status_info}", size=14),
            ],
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
        )
        return dialog_content

    def close_panel(self, _):
        self.open = False
        self.update()
