from ...models.recording.recording_status_model import RecordingStatus
from ..components.state.recording_card_state import RecordingCardState


class RecordingFilters:

    @staticmethod
    def _is_error_status(recording) -> bool:
        return recording.status_info in RecordingCardState.ERROR_STATUSES
    
    @staticmethod
    def _is_live_status(recording) -> bool:
        return (recording.is_live 
                and recording.monitor_status 
                and not recording.is_recording
                and recording.status_info not in RecordingCardState.ERROR_STATUSES
                and recording.status_info != RecordingStatus.NOT_IN_SCHEDULED_CHECK)
    
    @staticmethod
    def _is_offline_status(recording) -> bool:
        return (not recording.is_live
                and recording.monitor_status
                and recording.status_info not in RecordingCardState.ERROR_STATUSES
                and recording.status_info != RecordingStatus.NOT_IN_SCHEDULED_CHECK)
    
    @staticmethod
    def _is_stopped_status(recording) -> bool:
        return (not recording.monitor_status
                or recording.status_info == RecordingStatus.NOT_IN_SCHEDULED_CHECK)

    STATUS_FILTER_MAP = {
        "all": lambda rec: True,
        "recording": lambda rec: rec.is_recording,
        "living": lambda rec: RecordingFilters._is_live_status(rec),
        "error": lambda rec: RecordingFilters._is_error_status(rec),
        "offline": lambda rec: RecordingFilters._is_offline_status(rec),
        "stopped": lambda rec: RecordingFilters._is_stopped_status(rec)
    }

    @classmethod
    def get_status_filter_result(cls, recording, filter_type) -> bool:
        filter_func = cls.STATUS_FILTER_MAP.get(filter_type, lambda _: False)
        return filter_func(recording)

    @classmethod
    def get_platform_filter_result(cls, recording, platform_filter) -> bool:
        return platform_filter in ("all", recording.platform_key)

    @classmethod
    def should_show_recording(cls, filter_type, platform_filter, recording) -> bool:
        status_visible = cls.get_status_filter_result(recording, filter_type)
        platform_visible = cls.get_platform_filter_result(recording, platform_filter)
        return status_visible and platform_visible
