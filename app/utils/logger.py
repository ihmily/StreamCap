import os
import sys
import re

from loguru import logger

script_path = os.path.split(os.path.realpath(sys.argv[0]))[0]

# 添加内存清理日志过滤器
def is_memory_cleanup_log(record):
    """检查是否为内存清理相关的日志"""
    message = record["message"]
    memory_cleanup_patterns = [
        r"执行轻量级清理任务",
        r"执行完整清理任务",
        r"轻量级清理",
        r"完整清理",
        r"内存使用率过高",
        r"内存使用详情",
        r"系统统计",
        r"开始执行完整清理",
        r"内存使用率:",
        r"实例清理",
        r"实例统计",
        r"实例管理",
        # 测试脚本中使用的内存相关日志模式
        r"开始内存测试",
        r"内存状态",
        r"创建实例",
        r"内存测试总结",
        r"主动触发垃圾回收",
        r"显式清理未使用的实例",
        r"等待.*秒让自动清理机制工作",
        r"清理实例后",
        r"开始内存优化测试"
    ]
    return any(re.search(pattern, message) for pattern in memory_cleanup_patterns)

# 添加一个普通日志的过滤器
def not_memory_cleanup_log(record):
    return not is_memory_cleanup_log(record)

# 添加一个控制台输出的处理器，用于所有日志（包括内存清理日志）
logger.add(
    sys.stderr,
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}",
    enqueue=True,
)

# 文件日志处理器，排除内存清理日志
logger.add(
    f"{script_path}/logs/streamget.log",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    filter=lambda i: not_memory_cleanup_log(i) and i["level"].name != "STREAM",
    serialize=False,
    enqueue=True,
    retention=3,
    rotation="3 MB",
    encoding="utf-8",
)

logger.level("STREAM", no=22, color="<blue>")
logger.add(
    f"{script_path}/logs/play_url.log",
    level="STREAM",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {message}",
    filter=lambda i: i["level"].name == "STREAM",
    serialize=False,
    enqueue=True,
    retention=1,
    rotation="500 KB",
    encoding="utf-8",
)
