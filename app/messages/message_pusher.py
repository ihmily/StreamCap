from asyncio import create_task, Queue, Task, sleep as asyncio_sleep
import time
from typing import Dict, List, Tuple

from ..utils.logger import logger
from .notification_service import NotificationService


class MessagePusher:
    # 静态队列用于存储待发送的消息
    _message_queue: Queue = Queue()
    # 标记队列处理是否已启动
    _queue_processing: bool = False
    # 跟踪已发送的消息，避免重复发送
    # 键为 "标题+内容" 的哈希，值为发送时间戳
    _sent_messages: Dict[str, float] = {}
    # 消息去重的时间窗口（秒）
    _deduplication_window: int = 30

    def __init__(self, settings):
        self.settings = settings
        self.notifier = NotificationService()

    @classmethod
    def _get_message_hash(cls, title: str, content: str) -> str:
        """生成消息的唯一标识，用于去重"""
        return f"{title}:{content}"

    @classmethod
    async def _process_message_queue(cls):
        """处理消息队列中的所有消息"""
        if cls._queue_processing:
            return
        
        cls._queue_processing = True
        logger.info("开始处理消息队列")
        
        try:
            while not cls._message_queue.empty():
                msg_data = await cls._message_queue.get()
                pusher, msg_title, push_content = msg_data
                
                # 执行实际的消息推送
                await pusher._push_messages_impl(msg_title, push_content)
                
                # 标记任务完成
                cls._message_queue.task_done()
                
                # 短暂延迟，避免过快发送消息
                await asyncio_sleep(0.5)
        except Exception as e:
            logger.error(f"处理消息队列时出错: {str(e)}")
        finally:
            cls._queue_processing = False
            logger.info("消息队列处理完毕")

    async def push_messages(self, msg_title: str, push_content: str):
        """将消息加入队列进行推送"""
        logger.info(f"接收到推送请求: {msg_title}")
        
        # 检查是否是重复消息
        msg_hash = self._get_message_hash(msg_title, push_content)
        current_time = time.time()
        
        # 清理过期的已发送消息记录
        expired_hashes = [h for h, t in self._sent_messages.items() 
                         if current_time - t > self._deduplication_window]
        for h in expired_hashes:
            self._sent_messages.pop(h, None)
        
        # 检查是否在去重窗口内已经发送过相同消息
        if msg_hash in self._sent_messages:
            logger.info(f"跳过重复消息: {msg_title} (在{self._deduplication_window}秒内已发送)")
            return []
        
        # 记录此消息已请求发送
        self._sent_messages[msg_hash] = current_time
        
        # 将消息放入队列
        await self._message_queue.put((self, msg_title, push_content))
        
        # 启动队列处理（如果尚未启动）
        if not self._queue_processing:
            create_task(self._process_message_queue())
            
        # 返回一个空任务列表，因为实际任务会在队列处理中创建
        # 这是为了保持API兼容性
        return []

    async def _push_messages_impl(self, msg_title: str, push_content: str):
        """实际执行消息推送的内部方法"""
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
        
        if user_config.get("serverchan_enabled"):
            sendkey = user_config.get("serverchan_sendkey", "")
            if sendkey.strip():
                logger.info("准备推送ServerChan消息")
                task = create_task(
                    self.notifier.send_to_serverchan(
                        sendkey=sendkey,
                        title=msg_title,
                        content=push_content,
                    )
                )
                tasks.append(task)
                logger.info("ServerChan消息推送任务已创建")
            else:
                logger.warning("ServerChan推送已启用，但未配置SendKey")
        
        if not tasks:
            logger.warning("没有创建任何推送任务，可能是因为所有渠道都未启用或配置不正确")
            
        # 等待所有推送任务完成
        for task in tasks:
            try:
                await task
            except Exception as e:
                logger.error(f"执行推送任务时发生错误: {str(e)}")
        
        logger.info(f"消息 '{msg_title}' 推送完成")
        return tasks
