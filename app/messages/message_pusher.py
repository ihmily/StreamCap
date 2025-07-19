from asyncio import create_task
from typing import Optional

from ..models.recording.recording_model import Recording
from ..ui.views.settings_view import SettingsPage
from ..utils.logger import logger
from .notification_service import NotificationService


class MessagePusher:
    def __init__(self, settings: SettingsPage):
        self.settings = settings
        self.notifier = NotificationService()

    def _get_proxy(self) -> str | None:
        if self.settings.user_config.get("enable_proxy"):
            return self.settings.user_config.get("proxy_address")

    def is_any_push_channel_enabled(self) -> bool:
        """Check if any push channel is enabled"""
        push_channels = [
            "dingtalk_enabled",
            "wechat_enabled",
            "bark_enabled",
            "ntfy_enabled",
            "telegram_enabled",
            "email_enabled",
            "serverchan_enabled"
        ]
        
        return any(self.settings.user_config.get(channel) for channel in push_channels)

    @staticmethod
    def should_push_message(
        settings: SettingsPage,
        recording: Recording,
        check_manually_stopped: bool = False,
        message_type: Optional[str] = None
    ) -> bool:
        """
        Check if message should be pushed
        """
        if not recording.enabled_message_push:
            return False
            
        user_config = settings.user_config
        should_only_notify_no_record = user_config.get("only_notify_no_record")
        is_stream_start_enabled = user_config.get("stream_start_notification_enabled")
        is_stream_end_enabled = user_config.get("stream_end_notification_enabled")
        
        if message_type is None:
            if hasattr(recording, 'is_recording') and recording.is_recording:
                message_type = 'end'
            else:
                message_type = 'start'

        if message_type == 'start' and should_only_notify_no_record and is_stream_start_enabled:
            return True

        if message_type == 'start' and not is_stream_start_enabled:
            return False
        
        if message_type == 'end' and not is_stream_end_enabled:
            return False

        push_channels = [
            "dingtalk_enabled",
            "wechat_enabled",
            "bark_enabled",
            "ntfy_enabled",
            "telegram_enabled",
            "email_enabled",
            "serverchan_enabled"
        ]
        
        any_channel_enabled = any(user_config.get(channel) for channel in push_channels)
        
        if not any_channel_enabled:
            return False
            
        if message_type == 'end' and check_manually_stopped and recording.manually_stopped:
            return False
        return True

    async def push_messages(self, msg_title: str, push_content: str) -> None:
        """Push messages to all enabled notification services"""
        if self.settings.user_config.get("dingtalk_enabled"):
            create_task(
                self.notifier.send_to_dingtalk(
                    url=self.settings.user_config.get("dingtalk_webhook_url"),
                    content=push_content,
                    number=self.settings.user_config.get("dingtalk_at_objects"),
                    is_atall=self.settings.user_config.get("dingtalk_at_all"),
                )
            )
            logger.info("Push DingTalk message successfully")

        if self.settings.user_config.get("wechat_enabled"):
            create_task(
                self.notifier.send_to_wechat(
                    url=self.settings.user_config.get("wechat_webhook_url"), title=msg_title, content=push_content
                )
            )
            logger.info("Push Wechat message successfully")

        if self.settings.user_config.get("bark_enabled"):
            create_task(
                self.notifier.send_to_bark(
                    api=self.settings.user_config.get("bark_webhook_url"),
                    title=msg_title,
                    content=push_content,
                    level=self.settings.user_config.get("bark_interrupt_level"),
                    sound=self.settings.user_config.get("bark_sound"),
                )
            )
            logger.info("Push Bark message successfully")

        if self.settings.user_config.get("ntfy_enabled"):
            create_task(
                self.notifier.send_to_ntfy(
                    api=self.settings.user_config.get("ntfy_server_url"),
                    title=msg_title,
                    content=push_content,
                    tags=self.settings.user_config.get("ntfy_tags"),
                    action_url=self.settings.user_config.get("ntfy_action_url"),
                    email=self.settings.user_config.get("ntfy_email"),
                )
            )
            logger.info("Push Ntfy message successfully")

        if self.settings.user_config.get("telegram_enabled"):
            create_task(
                self.notifier.send_to_telegram(
                    chat_id=self.settings.user_config.get("telegram_chat_id"),
                    token=self.settings.user_config.get("telegram_api_token"),
                    content=push_content,
                    proxy=self._get_proxy(),
                )
            )
            logger.info("Push Telegram message successfully")

        if self.settings.user_config.get("email_enabled"):
            create_task(
                self.notifier.send_to_email(
                    email_host=self.settings.user_config.get("smtp_server"),
                    login_email=self.settings.user_config.get("email_username"),
                    password=self.settings.user_config.get("email_password"),
                    sender_email=self.settings.user_config.get("sender_email"),
                    sender_name=self.settings.user_config.get("sender_name"),
                    to_email=self.settings.user_config.get("recipient_email"),
                    title=msg_title,
                    content=push_content,
                )
            )
            logger.info("Push Email message successfully")

        if self.settings.user_config.get("serverchan_enabled"):
            create_task(
                self.notifier.send_to_serverchan(
                    sendkey=self.settings.user_config.get("serverchan_sendkey"),
                    title=msg_title,
                    content=push_content,
                    channel=self.settings.user_config.get("serverchan_channel", 9),
                    tags=self.settings.user_config.get("serverchan_tags", "直播通知"),
                )
            )
            logger.info("Push ServerChan message successfully")
