import flet as ft


class CardDialog(ft.AlertDialog):
    def __init__(self, app, recording, final_push_enabled=None):
        self.app = app
        self.final_push_enabled = final_push_enabled
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
        # 优先合并recording_dialog，保证录制模式相关文本一致
        for key in ("recording_dialog", "recording_card", "recording_manager", "base", "video_quality"):
            self._.update(language.get(key, {}))

    def get_content(self, recording):
        """Record card information content"""
        anchor_name = recording.streamer_name
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
        # 获取录制状态信息
        if recording.recording:
            recording_status_info = self._["recording"]
        elif recording.is_live and recording.monitor_status and not recording.recording:
            recording_status_info = self._["live_monitoring_not_recording"]
        else:
            recording_status_info = self._["offline"]
        # 优先用final_push_enabled
        if self.final_push_enabled is not None:
            message_push = self._["enabled"] if self.final_push_enabled else self._["disabled"]
        else:
            message_push = self._["enabled"] if recording.enabled_message_push else self._["disabled"]
        # 获取录制模式信息
        record_mode_info = (
            self._["auto_record"] if getattr(recording, "record_mode", "auto") == "auto"
            else self._["manual_record"]
        )

        dialog_content = ft.Column(
            [
                ft.Text(f"{self._['anchor_name']}: {anchor_name}", size=14, selectable=True),
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
                ft.Text(f"{self._['save_path']}: {save_path}", size=14, selectable=True),
                ft.Text(f"{self._['recording_status']}: {recording_status_info}", size=14),
                ft.Text(f"{self._['record_mode']}: {record_mode_info}", size=14),
            ],
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
        )
        return dialog_content

    def close_panel(self, _):
        self.open = False
        self.update()
