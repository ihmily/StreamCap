from asyncio import create_task

from ..utils.logger import logger
from .notification_service import NotificationService


class MessagePusher:
    def __init__(self, settings):
        self.settings = settings
        self.notifier = NotificationService()

    async def push_messages(self, msg_title: str, push_content: str):
        """Push messages to all enabled notification services"""
        logger.info(f"开始推送消息: {msg_title}")
        
        user_config = self.settings.user_config
        tasks = []
        
        if user_config.get("dingtalk_enabled"):
            webhook_url = user_config.get("dingtalk_webhook_url", "")
            if webhook_url.strip():
                logger.info("准备推送钉钉消息")
                task = create_task(
                    self.notifier.send_to_dingtalk(
                        url=webhook_url,
                        content=push_content,
                        number=user_config.get("dingtalk_at_objects"),
                        is_atall=user_config.get("dingtalk_at_all"),
                    )
                )
                tasks.append(task)
                logger.info("钉钉消息推送任务已创建")
            else:
                logger.warning("钉钉推送已启用，但未配置Webhook URL")

        if user_config.get("wechat_enabled"):
            webhook_url = user_config.get("wechat_webhook_url", "")
            if webhook_url.strip():
                logger.info("准备推送微信消息")
                task = create_task(
                    self.notifier.send_to_wechat(
                        url=webhook_url, title=msg_title, content=push_content
                    )
                )
                tasks.append(task)
                logger.info("微信消息推送任务已创建")
            else:
                logger.warning("微信推送已启用，但未配置Webhook URL")

        if user_config.get("bark_enabled"):
            bark_url = user_config.get("bark_webhook_url", "")
            if bark_url.strip():
                logger.info(f"准备推送Bark消息，URL: {bark_url}")
                task = create_task(
                    self.notifier.send_to_bark(
                        api=bark_url,
                        title=msg_title,
                        content=push_content,
                        level=user_config.get("bark_interrupt_level"),
                        sound=user_config.get("bark_sound"),
                    )
                )
                tasks.append(task)
                logger.info("Bark消息推送任务已创建")
            else:
                logger.warning("Bark推送已启用，但未配置Webhook URL")

        if user_config.get("ntfy_enabled"):
            ntfy_url = user_config.get("ntfy_server_url", "")
            if ntfy_url.strip():
                logger.info("准备推送Ntfy消息")
                task = create_task(
                    self.notifier.send_to_ntfy(
                        api=ntfy_url,
                        title=msg_title,
                        content=push_content,
                        tags=user_config.get("ntfy_tags"),
                        action_url=user_config.get("ntfy_action_url"),
                        email=user_config.get("ntfy_email"),
                    )
                )
                tasks.append(task)
                logger.info("Ntfy消息推送任务已创建")
            else:
                logger.warning("Ntfy推送已启用，但未配置Server URL")

        if user_config.get("telegram_enabled"):
            chat_id = user_config.get("telegram_chat_id")
            token = user_config.get("telegram_api_token", "")
            if chat_id and token.strip():
                logger.info("准备推送Telegram消息")
                task = create_task(
                    self.notifier.send_to_telegram(
                        chat_id=chat_id,
                        token=token,
                        content=push_content,
                    )
                )
                tasks.append(task)
                logger.info("Telegram消息推送任务已创建")
            else:
                logger.warning("Telegram推送已启用，但未配置完整的Chat ID或API Token")

        if user_config.get("email_enabled"):
            email_host = user_config.get("smtp_server", "")
            login_email = user_config.get("email_username", "")
            password = user_config.get("email_password", "")
            sender_email = user_config.get("sender_email", "")
            to_email = user_config.get("recipient_email", "")
            
            if email_host.strip() and login_email.strip() and password.strip() and sender_email.strip() and to_email.strip():
                logger.info("准备推送Email消息")
                task = create_task(
                    self.notifier.send_to_email(
                        email_host=email_host,
                        login_email=login_email,
                        password=password,
                        sender_email=sender_email,
                        sender_name=user_config.get("sender_name", "StreamCap"),
                        to_email=to_email,
                        title=msg_title,
                        content=push_content,
                    )
                )
                tasks.append(task)
                logger.info("Email消息推送任务已创建")
            else:
                logger.warning("Email推送已启用，但配置不完整")
        
        if not tasks:
            logger.warning("没有创建任何推送任务，可能是因为所有渠道都未启用或配置不正确")
            
        # 返回所有推送任务
        return tasks
