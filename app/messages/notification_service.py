import asyncio
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

    async def _async_post(self, url: str, json_data: dict[str, Any], proxy: str | None = None) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(proxy=proxy) as client:
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
                logger.info(f"WeChat push failed, push address: {api},  Failure message: {json_data.get('msg')}")
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
        timeout: float = 15.0,
    ) -> dict[str, Any]:
        receivers = [address.strip() for address in (to_email or "").replace("，", ",").split(",") if address.strip()]
        if not receivers:
            return {"success": [], "error": []}

        message = MIMEMultipart()
        send_name = base64.b64encode((sender_name or "").encode("utf-8")).decode()
        message["From"] = f"=?UTF-8?B?{send_name}?= <{sender_email}>"
        message["To"] = ", ".join(receivers)
        message["Subject"] = Header(title, "utf-8")
        message.attach(MIMEText(content, "plain", "utf-8"))

        def send_sync() -> dict[str, list[str]]:
            port = int(smtp_port or (465 if open_ssl else 25))
            smtp_class = smtplib.SMTP_SSL if open_ssl else smtplib.SMTP
            with smtp_class(email_host, port, timeout=timeout) as smtp_obj:
                smtp_obj.login(login_email, password)
                refused = smtp_obj.sendmail(sender_email, receivers, message.as_string())

            refused_recipients = set(refused)
            return {
                "success": [receiver for receiver in receivers if receiver not in refused_recipients],
                "error": [receiver for receiver in receivers if receiver in refused_recipients],
            }

        try:
            overall_timeout = max(timeout * 4, timeout + 5)
            return await asyncio.wait_for(asyncio.to_thread(send_sync), timeout=overall_timeout)
        except asyncio.TimeoutError:
            logger.error(f"Email push timed out, SMTP server: {email_host}")
        except (smtplib.SMTPException, OSError, ValueError) as e:
            logger.error(f"Email push failed, SMTP server: {email_host}, Error message: {e}")

        return {"success": [], "error": receivers}

    async def send_to_telegram(
        self, chat_id: int, token: str, content: str, proxy: Optional[str] = None
    ) -> dict[str, Any]:
        try:
            json_data = {"chat_id": chat_id, "text": content}
            url = "https://api.telegram.org/bot" + token + "/sendMessage"
            resp = await self._async_post(url, json_data, proxy or None)
            # _async_post swallows every exception and returns {"error": ...},
            # and the Telegram API reports failures as HTTP 200 + {"ok": false}
            # — both must be treated as failures, not as a successful push.
            if isinstance(resp, dict) and resp.get("ok") is True:
                return {"success": [1], "error": []}
            error_detail = resp.get("description") or resp.get("error") if isinstance(resp, dict) else resp
            logger.info(f"Telegram push failed, chat ID: {chat_id}, Error message: {error_detail}")
            return {"success": [], "error": [1]}
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
                logger.info(f"Bark push failed, push address: {_api},  Failure message: {json_data.get('message')}")
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
                logger.info(f"Ntfy push failed, push address: {_api},  Failure message: {json_data.get('error')}")
        return results

    async def send_to_serverchan(
        self,
        sendkey: str,
        title: str = "message",
        content: str = "test",
        short: str = "",
        channel: int = 9,
        tags: str = "partying_face",
    ) -> dict[str, Any]:

        results = {"success": [], "error": []}
        sendkey_list = sendkey.replace("，", ",").split(",") if sendkey.strip() else []

        for key in sendkey_list:
            if key.startswith("sctp"):
                match = re.match(r"sctp(\d+)t", key)
                if match:
                    num = match.group(1)
                    url = f"https://{num}.push.ft07.com/send/{key}.send"
                else:
                    logger.error(f"Invalid sendkey format for sctp: {key}")
                    results["error"].append(key)
                    continue
            else:
                url = f"https://sctapi.ftqq.com/{key}.send"

            json_data = {"title": title, "desp": content, "short": short, "channel": channel, "tags": tags}
            resp = await self._async_post(url, json_data)
            if resp.get("code") == 0:
                results["success"].append(key)
            else:
                results["error"].append(key)
                logger.info(f"ServerChan push failed, SCKEY/SendKey: {key}, Error message: {resp.get('message')}")

        return results

    async def send_to_feishu(self, url: str, content: str) -> dict[str, list[str]]:
        results = {"success": [], "error": []}
        api_list = [u.strip() for u in url.replace("，", ",").split(",") if u.strip()]
        for api in api_list:
            json_data = {"msg_type": "text", "content": {"text": content}}
            resp = await self._async_post(api, json_data)
            if resp.get("msg") == "success":
                results["success"].append(api)
            else:
                results["error"].append(api)
        return results
