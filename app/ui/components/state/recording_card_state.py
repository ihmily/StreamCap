import flet as ft

from ....models.recording.recording_model import Recording
from ....models.recording.recording_status_model import CardStateType, RecordingStatus


class RecordingCardState:
    
    ERROR_STATUSES = [RecordingStatus.RECORDING_ERROR, RecordingStatus.LIVE_STATUS_CHECK_ERROR]
    
    @staticmethod
    def get_card_state(recording: Recording) -> CardStateType:
        if recording.is_recording:
            return CardStateType.RECORDING
        elif recording.status_info in RecordingCardState.ERROR_STATUSES:
            return CardStateType.ERROR
        elif recording.is_live and recording.monitor_status and not recording.is_recording:
            return CardStateType.LIVE
        elif (not recording.is_live and recording.monitor_status and 
              recording.status_info != RecordingStatus.NOT_IN_SCHEDULED_CHECK):
            return CardStateType.OFFLINE
        elif (not recording.monitor_status or 
              recording.status_info == RecordingStatus.NOT_IN_SCHEDULED_CHECK):
            return CardStateType.STOPPED
        return CardStateType.UNKNOWN
    
    @staticmethod
    def get_border_color(recording: Recording) -> ft.Colors:
        state = RecordingCardState.get_card_state(recording)
        color_map = {
            CardStateType.RECORDING: ft.Colors.GREEN,
            CardStateType.ERROR: ft.Colors.RED,
            CardStateType.LIVE: ft.Colors.BLUE,
            CardStateType.OFFLINE: ft.Colors.AMBER,
            CardStateType.STOPPED: ft.Colors.GREY,
        }
        return color_map.get(state, ft.Colors.TRANSPARENT)
    
    @staticmethod
    def get_status_label_config(recording: Recording, language_dict: dict) -> dict:
        state = RecordingCardState.get_card_state(recording)
        
        configs = {
            CardStateType.RECORDING: {
                "text": language_dict.get("recording"),
                "bgcolor": ft.Colors.GREEN,
                "text_color": ft.Colors.WHITE,
            },
            CardStateType.ERROR: {
                "text": language_dict.get("recording_error"),
                "bgcolor": ft.Colors.RED,
                "text_color": ft.Colors.WHITE,
            },
            CardStateType.LIVE: {
                "text": language_dict.get("live_broadcasting"),
                "bgcolor": ft.Colors.BLUE,
                "text_color": ft.Colors.WHITE,
            },
            CardStateType.OFFLINE: {
                "text": language_dict.get("offline"),
                "bgcolor": ft.Colors.AMBER,
                "text_color": ft.Colors.BLACK,
            },
            CardStateType.STOPPED: {
                "text": language_dict.get("no_monitor"),
                "bgcolor": ft.Colors.GREY,
                "text_color": ft.Colors.WHITE,
            },
        }
        
        return configs.get(state, {})
    
    @staticmethod
    def get_display_title(recording: Recording, language_dict: dict) -> str:
        status_prefix = ""
        if not recording.monitor_status:
            status_prefix = f"[{language_dict.get('monitor_stopped')}] "
        return f"{status_prefix}{recording.title}"
    
    @staticmethod
    def get_title_weight(recording: Recording) -> ft.FontWeight:
        return ft.FontWeight.BOLD if recording.is_recording or recording.is_live else None
    
    @staticmethod
    def get_recording_icon(recording: Recording) -> ft.Icons:
        return ft.Icons.STOP_CIRCLE if recording.is_recording else ft.Icons.PLAY_CIRCLE
    
    @staticmethod
    def get_monitor_icon(recording: Recording) -> ft.Icons:
        return ft.Icons.VISIBILITY if recording.monitor_status else ft.Icons.VISIBILITY_OFF
