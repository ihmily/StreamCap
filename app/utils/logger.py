import os
import sys

from loguru import logger

script_path = os.path.split(os.path.realpath(sys.argv[0]))[0]
log_path = os.path.join(script_path, "log")
os.makedirs(log_path, exist_ok=True)

logger.add(
    os.path.join(log_path, "streamget.log"),
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    filter=lambda i: i["level"].name != "STREAM",
    serialize=False,
    enqueue=True,
    retention=3,
    rotation="3 MB",
    encoding="utf-8",
)

logger.level("STREAM", no=22, color="<blue>")
logger.add(
    os.path.join(log_path, "play_url.log"),
    level="STREAM",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {message}",
    filter=lambda i: i["level"].name == "STREAM",
    serialize=False,
    enqueue=True,
    retention=1,
    rotation="500 KB",
    encoding="utf-8",
)
