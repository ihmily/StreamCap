import base64
import re
import smtplib
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Optional

import httpx

from ..utils.logger import logger


class NotificationService:
    def __init__(self):
        self.headers = {"Content-Type": "application/json"}

    async def _async_post(self, url: str, json_data: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=json_data, headers=self.headers)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.info(f"Push failed, push address: {url},  Error message: {e}")
            return {"error": str(e)}

    async def send_to_dingtalk(
        self, url: str, content: str, number: Optional[str] = None, is_atall: bool = False
    ) -> dict[str, list[str]]:
        results = {"success": [], "error": []}
        api_list = [u.strip() for u in url.replace("，", ",").split(",") if u.strip()]
        for api in api_list:
            json_data = {
                "msgtype": "text",
                "text": {"content": content},
                "at": {"atMobiles": [number] if number else [], "isAtAll": is_atall},
            }
            resp = await self._async_post(api, json_data)
            if resp.get("errcode") == 0:
                results["success"].append(api)
            else:
                results["error"].append(api)
        return results

    async def send_to_wechat(self, url: str, title: str, content: str) -> dict[str, Any]:
        results = {"success": [], "error": []}
        api_list = url.replace("，", ",").split(",") if url.strip() else []
        for api in api_list:
            json_data = {"title": title, "content": content}
            resp = await self._async_post(api, json_data)
            if resp.get("code") == 200:
                results["success"].append(api)
            else:
                results["error"].append(api)
                logger.info(f"WeChat push failed, push address: {api},  Failure message: {json_data['msg']}")
        return results

    @staticmethod
    async def send_to_email(
        email_host: str,
        login_email: str,
        password: str,
        sender_email: str,
        sender_name: str,
        to_email: str,
        title: str,
        content: str,
        smtp_port: str | None = None,
        open_ssl: bool = True,
    ) -> dict[str, Any]:
        receivers = to_email.replace("，", ",").split(",") if to_email.strip() else []

        try:
            message = MIMEMultipart()
            send_name = base64.b64encode(sender_name.encode("utf-8")).decode()
            message["From"] = f"=?UTF-8?B?{send_name}?= <{sender_email}>"
            message["Subject"] = Header(title, "utf-8")
            if len(receivers) == 1:
                message["To"] = receivers[0]

            t_apart = MIMEText(content, "plain", "utf-8")
            message.attach(t_apart)

            if open_ssl:
                smtp_port = smtp_port or 465
                smtp_obj = smtplib.SMTP_SSL(email_host, int(smtp_port))
            else:
                smtp_port = smtp_port or 25
                smtp_obj = smtplib.SMTP(email_host, int(smtp_port))
            smtp_obj.login(login_email, password)
            smtp_obj.sendmail(sender_email, receivers, message.as_string())
            return {"success": receivers, "error": []}
        except smtplib.SMTPException as e:
            logger.info(f"Email push failed, push email: {to_email},  Error message: {e}")
            return {"success": [], "error": receivers}

    async def send_to_telegram(self, chat_id: int, token: str, content: str) -> dict[str, Any]:
        try:
            json_data = {"chat_id": chat_id, "text": content}
            url = "https://api.telegram.org/bot" + token + "/sendMessage"
            _resp = await self._async_post(url, json_data)
            return {"success": [1], "error": []}
        except Exception as e:
            logger.info(f"Telegram push failed, chat ID: {chat_id},  Error message: {e}")
            return {"success": [], "error": [1]}

    async def send_to_bark(
        self,
        api: str,
        title: str = "message",
        content: str = "test",
        level: str = "active",
        badge: int = 1,
        auto_copy: int = 1,
        sound: str = "",
        icon: str = "",
        group: str = "",
        is_archive: int = 1,
        url: str = "",
    ) -> dict[str, Any]:
        results = {"success": [], "error": []}
        api_list = api.replace("，", ",").split(",") if api.strip() else []
        for _api in api_list:
            json_data = {
                "title": title,
                "body": content,
                "level": level,
                "badge": badge,
                "autoCopy": auto_copy,
                "sound": sound,
                "icon": icon,
                "group": group,
                "isArchive": is_archive,
                "url": url,
            }
            resp = await self._async_post(_api, json_data)
            if resp.get("code") == 200:
                results["success"].append(_api)
            else:
                results["error"].append(_api)
                logger.info(f"Bark push failed, push address: {_api},  Failure message: {json_data['message']}")
        return results

    async def send_to_ntfy(
        self,
        api: str,
        title: str = "message",
        content: str = "test",
        tags: str = "tada",
        priority: int = 3,
        action_url: str = "",
        attach: str = "",
        filename: str = "",
        click: str = "",
        icon: str = "",
        delay: str = "",
        email: str = "",
        call: str = "",
    ) -> dict[str, Any]:
        results = {"success": [], "error": []}
        api_list = api.replace("，", ",").split(",") if api.strip() else []
        tags = tags.replace("，", ",").split(",") if tags else ["partying_face"]
        actions = [{"action": "view", "label": "view live", "url": action_url}] if action_url else []
        for _api in api_list:
            server, topic = _api.rsplit("/", maxsplit=1)
            json_data = {
                "topic": topic,
                "title": title,
                "message": content,
                "tags": tags,
                "priority": priority,
                "attach": attach,
                "filename": filename,
                "click": click,
                "actions": actions,
                "markdown": False,
                "icon": icon,
                "delay": delay,
                "email": email,
                "call": call,
            }

            resp = await self._async_post(_api, json_data)
            if "error" not in resp:
                results["success"].append(_api)
            else:
                results["error"].append(_api)
                logger.info(f"Ntfy push failed, push address: {_api},  Failure message: {json_data['error']}")
        return results

    async def send_to_serverchan(
            self, 
            sendkey: str,
            title: str = "message",
            content: str = "test",
            short: str = "",
            channel: int = 9,
            tags: str = "partying_face"
        ) -> dict[str, Any]:
            """发送消息到ServerChan服务
            
            参数:
                sckey: ServerChan的SCKEY，多个用逗号分隔
                title: 消息标题
                content: 消息内容
                short: 短消息内容
                channel: 消息通道
            
            返回:
                包含成功和失败SCKEY的字典
            """
            results = {"success": [], "error": []}
            sendkey_list = sendkey.replace("，", ",").split(",") if sendkey.strip() else []

            for key in sendkey_list:
                # 根据SCKEY类型构造URL
                if key.startswith('sctp'):
                    match = re.match(r'sctp(\d+)t', key)
                    if match:
                        num = match.group(1)
                        url = f'https://{num}.push.ft07.com/send/{key}.send'
                    else:
                        logger.error(f"Invalid sendkey format for sctp: {key}")
                        results["error"].append(key)
                        continue
                else:
                    url = f'https://sctapi.ftqq.com/{key}.send'
                
                json_data = {
                "title": title,
                "desp": content,
                "short": short,
                "channel": channel,
                "tags": tags
                }
                resp = await self._async_post(url, json_data)
                if resp.get("code") == 0:
                    results["success"].append(key)
                else:
                    results["error"].append(key)
                    logger.info(f"ServerChan push failed, SCKEY: {key}, Error message: {resp.get('message')}")
            
            return results
