import functools
import hashlib
import json
import os
import random
import re
import shutil
import string
import subprocess
import sys
import traceback
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import execjs

from .logger import logger

OptionalStr = str | None
OptionalDict = dict | None


class Color:
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    RESET = "\033[0m"

    @staticmethod
    def print_colored(text, color):
        print(f"{color}{text}{Color.RESET}")


def trace_error_decorator(func: callable) -> callable:
    @functools.wraps(func)
    async def wrapper(*args: list, **kwargs: dict) -> Any:
        try:
            return await func(*args, **kwargs)
        except execjs.ProgramError:
            logger.warning("Failed to execute JS code. Please check if the Node.js environment")
            return None
        except json.JSONDecodeError as e:
            # 专门处理JSON解析错误
            error_line = traceback.extract_tb(e.__traceback__)[-1].lineno
            error_info = f"Type: {type(e).__name__}, {e} in function {func.__name__} at line: {error_line}"
            
            # 函数名用于判断错误上下文
            function_name = func.__name__
            
            # 记录详细错误日志
            logger.error(error_info)
            
            # 针对不同错误位置的处理
            json_error_position = str(e)
            
            # 检查是否涉及代理错误
            proxy_error = False
            for arg in args:
                if hasattr(arg, 'proxy') and arg.proxy and arg.proxy.startswith('http://'):
                    proxy_error = True
                    logger.warning(f"JSON解析错误: 可能与代理有关，当前使用的代理: {arg.proxy}")
                    break
            
            # 如果是空响应导致的错误（line 1 column 1 (char 0)）
            if "line 1 column 1 (char 0)" in json_error_position:
                if proxy_error:
                    logger.warning(f"JSON解析错误: 收到空响应，可能是代理连接问题")
                else:
                    logger.warning(f"JSON解析错误: 收到空响应，可能是网络连接问题或API暂时不可用")
            # 如果是JSON格式错误（如只有 { 或 [）
            elif "line 1 column 2 (char 1)" in json_error_position:
                logger.warning(f"JSON解析错误: 收到不完整或损坏的JSON响应，只有开始字符")
            else:
                logger.warning(f"JSON解析错误: 位置 {json_error_position}, 可能是API返回了非JSON格式的数据")
            
            # 如果是直播源获取函数，创建默认的StreamData对象
            if function_name == "get_stream_info":
                try:
                    # 导入StreamData类
                    from app.core.platform_handlers.base import StreamData
                    
                    # 根据参数获取平台信息（如果可用）
                    platform = "unknown"
                    anchor_name = "未知主播"
                    
                    # 尝试从参数中提取平台和主播信息
                    if len(args) > 0 and hasattr(args[0], 'platform'):
                        platform = args[0].platform
                    if len(args) > 0 and hasattr(args[0], 'anchor_name'):
                        anchor_name = args[0].anchor_name
                    
                    # 创建表示未开播状态的StreamData对象
                    stream_data = StreamData(
                        platform=platform,
                        anchor_name=anchor_name,
                        is_live=False,
                        title="获取直播信息失败",
                        quality=None,
                        m3u8_url=None,
                        flv_url=None,
                        record_url=None,
                        new_cookies=None,
                        new_token=None,
                        extra=None
                    )
                    
                    logger.info(f"为函数 {function_name} 创建了默认的StreamData对象，标记为未开播状态")
                    return stream_data
                except Exception as inner_e:
                    logger.error(f"创建默认StreamData对象时出错: {inner_e}")
                    return None
            
            # 其他函数返回None
            return None
        except Exception as e:
            error_line = traceback.extract_tb(e.__traceback__)[-1].lineno
            error_info = f"Type: {type(e).__name__}, {e} in function {func.__name__} at line: {error_line}"
            logger.error(error_info)
            # 返回None而不是空列表，以便调用者知道这是一个错误状态
            return None

    return wrapper


def check_md5(file_path: str | Path) -> str:
    with open(file_path, "rb") as fp:
        file_md5 = hashlib.md5(fp.read()).hexdigest()
    return file_md5


def dict_to_cookie_str(cookies_dict: dict) -> str:
    cookie_str = "; ".join([f"{key}={value}" for key, value in cookies_dict.items()])
    return cookie_str


def get_file_paths(directory: str) -> list:
    file_paths = []
    for root, _dirs, files in os.walk(directory):
        for file in files:
            file_paths.append(os.path.join(root, file))
    return file_paths


def remove_emojis(text: str, replace_text: str = "") -> str:
    emoji_pattern = re.compile(
        "["
        "\U0001f1e0-\U0001f1ff"  # flags (iOS)
        "\U0001f300-\U0001f5ff"  # symbols & pictographs
        "\U0001f600-\U0001f64f"  # emoticons
        "\U0001f680-\U0001f6ff"  # transport & map symbols
        "\U0001f700-\U0001f77f"  # alchemical symbols
        "\U0001f780-\U0001f7ff"  # Geometric Shapes Extended
        "\U0001f800-\U0001f8ff"  # Supplemental Arrows-C
        "\U0001f900-\U0001f9ff"  # Supplemental Symbols and Pictographs
        "\U0001fa00-\U0001fa6f"  # Chess Symbols
        "\U0001fa70-\U0001faff"  # Symbols and Pictographs Extended-A
        "\U00002702-\U000027b0"  # Dingbats
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub(replace_text, text)


def check_disk_capacity(file_path: str | Path, show: bool = False) -> float:
    absolute_path = os.path.abspath(file_path)
    directory = os.path.dirname(absolute_path)
    disk_usage = shutil.disk_usage(directory)
    disk_root = Path(directory).anchor
    free_space_gb = disk_usage.free / (1024**3)
    if show:
        print(
            f"{disk_root} Total: {disk_usage.total / (1024**3): .2f} GB "
            f"Used: {disk_usage.used / (1024**3): .2f} GB "
            f"Free: {free_space_gb: .2f} GB\n"
        )
    return free_space_gb


def handle_proxy_addr(proxy_addr):
    if proxy_addr:
        proxy_addr = proxy_addr.strip()
        # 如果代理地址不以协议前缀开头，添加http://前缀
        if not proxy_addr.startswith(('http://')):
            proxy_addr = f"http://{proxy_addr}"
        return proxy_addr
    else:
        return None


def generate_random_string(length: int) -> str:
    characters = string.ascii_uppercase + string.digits
    random_string = "".join(random.choices(characters, k=length))
    return random_string


def jsonp_to_json(jsonp_str: str) -> OptionalDict:
    pattern = r"(\w+)\((.*)\);?$"
    match = re.search(pattern, jsonp_str)

    if match:
        _, json_str = match.groups()
        json_obj = json.loads(json_str)
        return json_obj
    else:
        raise Exception("No JSON data found in JSONP response.")


def open_folder(directory_path: str) -> bool:
    try:
        if sys.platform == "win32":
            os.startfile(directory_path)
        elif sys.platform == "darwin":
            subprocess.run(["open", directory_path], check=True)
        else:
            subprocess.run(["xdg-open", directory_path], check=True)
        return True
    except FileNotFoundError:
        logger.error("Unable to open folder. The command may not be available on this system.")
    except subprocess.CalledProcessError:
        logger.error(f"Failed to open folder '{directory_path}'. Please ensure the path is valid and accessible.")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
    return False


def add_hours_to_time(time_str: str, hours_to_add: float) -> str:
    time_formats: list[str] = ["%H:%M:%S", "%H:%M"]
    for time_format in time_formats:
        try:
            time_obj: datetime = datetime.strptime(time_str, time_format)
            new_time_obj: datetime = time_obj + timedelta(hours=hours_to_add)
            new_time_str: str = new_time_obj.strftime(time_formats[0])
            return new_time_str
        except ValueError:
            pass
    raise ValueError("Invalid time format provided.")


def is_time_greater_than_now(time_str: str) -> bool:
    time_format: str = "%H:%M:%S"
    input_time: time = datetime.strptime(time_str, time_format).time()
    current_time: time = datetime.now().time()
    return input_time > current_time


def is_current_time_within_range(time_range_str: str):
    start_str, end_str = time_range_str.split("~")
    time_format = "%H:%M:%S"

    start_time = datetime.strptime(start_str.strip(), time_format).time()
    end_time = datetime.strptime(end_str.strip(), time_format).time()
    now = datetime.now().time()

    if end_time < start_time:
        return now >= start_time or now <= end_time
    else:
        return start_time <= now <= end_time


def is_time_interval_exceeded(last_check_time, interval_seconds=60):
    """
    Check if the time interval between the current time and the last check time exceeds the specified seconds.

    :param last_check_time: The time of the last check. type: datetime.Time
    :param interval_seconds: The time interval in seconds. Default is 60 seconds. type: int
    :return: Returns True if the time interval exceeds the specified seconds, otherwise returns False.
    """
    now = datetime.now().time()
    if not last_check_time or last_check_time > now:
        return True
    last_check_datetime = datetime.combine(datetime.today(), last_check_time)
    time_diff = datetime.combine(datetime.today(), now) - last_check_datetime
    return time_diff.total_seconds() > interval_seconds


def clean_name(input_text, default=None):
    if input_text and input_text.strip():
        rstr = r"[\/\\\:\*\？?\"\<\>\|&#.。,， ~！· ]"
        cleaned_name = input_text.strip().replace("（", "(").replace("）", ")")
        cleaned_name = re.sub(rstr, "_", cleaned_name)
        cleaned_name = remove_emojis(cleaned_name, "_").replace("__", "_").strip("_")
        return cleaned_name or default
    return default


def is_valid_url(url):
    try:
        result = urlparse(url)
        if not all([result.scheme, result.netloc]):
            return False
        url_pattern = re.compile(
            r"^(https?://)"
            r"([a-zA-Z0-9-]+\.)+[a-zA-Z0-9]{1,6}"
            r"(:\d+)?"
            r"(/\S*)?$"
        )
        return bool(url_pattern.match(url))
    except ValueError:
        return False


def contains_url(text):
    url_pattern = re.compile(
        r"(?i)\bhttps?://"
        r"(?:[a-zA-Z0-9-]+\.)+[a-zA-Z0-9]{1,6}"
        r"(?::\d+)?"
        r"(?:/\S*)?"
    )
    try:
        return bool(url_pattern.search(text))
    except ValueError:
        return False


def get_startup_info(system_type: str | None = None):
    """
    Get startup info for subprocesses to hide console windows on Windows.
    """
    if system_type == "nt" or sys.platform == "win32":
        startup_info = subprocess.STARTUPINFO()
        startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    else:
        startup_info = None
    return startup_info


def is_valid_video_file(source: str) -> bool:
    video_extensions = ['.mp4', '.mov', '.mkv', '.ts', '.flv', '.mp3', '.m4a', '.wav', '.aac', '.wma']
    return Path(source).suffix.lower() in video_extensions
