from datetime import timedelta


class Recording:
    def __init__(
        self,
        rec_id,
        url,
        streamer_name,
        record_format,
        quality,
        segment_record,
        segment_time,
        monitor_status,
        scheduled_recording,
        scheduled_start_time,
        monitor_hours,
        recording_dir,
        enabled_message_push,
        only_notify_no_record
    ):
        """
        Initialize a recording object.

        :param rec_id: Unique identifier for the recording task.
        :param url: URL address of the live stream.
        :param streamer_name: Name of the streamer.
        :param record_format: Format of the recorded file, e.g., 'mp4', 'ts', 'mkv'.
        :param quality: Quality of the recorded video, e.g., 'OD', 'UHD', 'HD'.
        :param segment_record: Whether to enable segmented recording.
        :param segment_time: Time interval (in seconds) for segmented recording if enabled.
        :param monitor_status: Monitoring status, whether the live room is being monitored.
        :param scheduled_recording: Whether to enable scheduled recording.
        :param scheduled_start_time: Scheduled start time for recording (string format like '18:30:00').
        :param monitor_hours: Number of hours to monitor from the scheduled recording start time, e.g., 3.
        :param recording_dir: Directory path where the recorded files will be saved.
        :param enabled_message_push: Whether to enable message push.
        :param only_notify_no_record: Whether to only notify when no record is made.
        """

        self.rec_id = rec_id
        self.url = url
        self.quality = quality
        self.record_format = record_format
        self.monitor_status = monitor_status
        self.segment_record = segment_record
        self.segment_time = segment_time
        self.streamer_name = streamer_name
        self.scheduled_recording = scheduled_recording
        self.scheduled_start_time = scheduled_start_time
        self.monitor_hours = monitor_hours
        self.recording_dir = recording_dir
        self.enabled_message_push = enabled_message_push
        self.only_notify_no_record = only_notify_no_record
        self.scheduled_time_range = None
        self.title = f"{streamer_name} - {self.quality}"
        self.speed = "X KB/s"
        self.is_live = False
        self.is_recording = False
        self.start_time = None
        self.manually_stopped = False
        self.platform = None
        self.platform_key = None
        self.notified_live_start = False
        self.notified_live_end = False

        self.cumulative_duration = timedelta()  # Accumulated recording time
        self.last_duration = timedelta()  # Save the total time of the last recording
        self.display_title = self.title
        self.selected = False
        self.is_checking = False
        self.status_info = None
        self.live_title = None
        self.detection_time = None
        self.loop_time_seconds = None
        self.use_proxy = None
        self.record_url = None

    def to_dict(self):
        """Convert the Recording instance to a dictionary for saving."""
        return {
            "rec_id": self.rec_id,
            "url": self.url,
            "streamer_name": self.streamer_name,
            "record_format": self.record_format,
            "quality": self.quality,
            "segment_record": self.segment_record,
            "segment_time": self.segment_time,
            "monitor_status": self.monitor_status,
            "scheduled_recording": self.scheduled_recording,
            "scheduled_start_time": self.scheduled_start_time,
            "monitor_hours": self.monitor_hours,
            "recording_dir": self.recording_dir,
            "enabled_message_push": self.enabled_message_push,
            "platform": self.platform,
            "platform_key": self.platform_key,
            "only_notify_no_record": self.only_notify_no_record
        }

    @classmethod
    def from_dict(cls, data):
        """Create a Recording instance from a dictionary."""
        recording = cls(
            data.get("rec_id"),
            data.get("url"),
            data.get("streamer_name"),
            data.get("record_format"),
            data.get("quality"),
            data.get("segment_record"),
            data.get("segment_time"),
            data.get("monitor_status"),
            data.get("scheduled_recording"),
            data.get("scheduled_start_time"),
            data.get("monitor_hours"),
            data.get("recording_dir"),
            data.get("enabled_message_push"),
            data.get("only_notify_no_record")
        )
        recording.title = data.get("title", recording.title)
        recording.display_title = data.get("display_title", recording.title)
        recording.last_duration_str = data.get("last_duration")
        recording.platform = data.get("platform")
        recording.platform_key = data.get("platform_key")
        if recording.last_duration_str is not None:
            recording.last_duration = timedelta(seconds=float(recording.last_duration_str))
        return recording

    def update_title(self, quality_info, prefix=None):
        """Helper method to update the title."""
        self.title = f"{self.streamer_name} - {quality_info}"
        self.display_title = f"{prefix or ''}{self.title}"

    def update(self, updated_info: dict):
        """Update the recording object with new information."""
        for attr, value in updated_info.items():
            if hasattr(self, attr):
                setattr(self, attr, value)
