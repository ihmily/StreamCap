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
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

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
        except Exception as e:
            error_line = traceback.extract_tb(e.__traceback__)[-1].lineno
            error_info = f"Type: {type(e).__name__}, {e} in function {func.__name__} at line: {error_line}"
            logger.error(error_info)
            return []

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
        if not proxy_addr.startswith("http"):
            proxy_addr = "http://" + proxy_addr
    else:
        proxy_addr = None
    return proxy_addr


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
        rstr = r"[\/\\\:：\*\？?\"\<\>\|&#.。,， ~！· ]"
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
    video_extensions = [".mp4", ".mov", ".mkv", ".nut", ".ts", ".flv", ".mp3", ".m4a", ".wav", ".aac", ".wma"]
    return Path(source).suffix.lower() in video_extensions


def get_query_params(url: str, param_name: Optional[str] = None) -> dict | list[str]:
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)

    if param_name is None:
        return query_params
    else:
        values = query_params.get(param_name, [])
        return values
