from asyncio import create_task

from ..utils.logger import logger
from .notification_service import NotificationService


class MessagePusher:
    def __init__(self, settings):
        self.settings = settings
        self.notifier = NotificationService()

    async def push_messages(self, msg_title: str, push_content: str):
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
