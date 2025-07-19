from enum import Enum


class CardStateType(Enum):
    RECORDING = "recording"
    ERROR = "error"
    LIVE = "live"
    OFFLINE = "offline"
    STOPPED = "stopped"
    UNKNOWN = "unknown"


class RecordingStatus:
    STOPPED_MONITORING = "STOPPED_MONITORING"
    MONITORING = "MONITORING"
    RECORDING = "RECORDING"
    NOT_RECORDING = "NOT_RECORDING"
    STATUS_CHECKING = "STATUS_CHECKING"
    NOT_IN_SCHEDULED_CHECK = "NOT_IN_SCHEDULED_CHECK"
    PREPARING_RECORDING = "PREPARING_RECORDING"
    RECORDING_ERROR = "RECORDING_ERROR"
    NOT_RECORDING_SPACE = "NOT_RECORDING_SPACE"
    LIVE_STATUS_CHECK_ERROR = "LIVE_STATUS_CHECK_ERROR"
    LIVE_BROADCASTING = "LIVE_BROADCASTING"

    @classmethod
    def get_status(cls):
        """Get all properties of the RecordingStatus class"""
        attributes = cls.__dict__
        recording_status = [value for name, value in attributes.items() if name.isupper()]
        return recording_status
