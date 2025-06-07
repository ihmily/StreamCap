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
        r"系统状态",
        r"开始执行完整清理",
        r"内存使用率:",
        r"实例清理",
        r"实例统计",
        r"实例管理",
        r"平台处理器实例统计",
        r"进程管理 -",
        r"添加ffmpeg进程",
        r"添加进程后",
        r"当前活跃进程数",
        r"当前所有进程PID列表",
        r"检测到已终止的进程",
        r"开始清理所有进程",
        r"进程管理器初始化完成",
        r"系统信息:",
        r"系统进程验证通过",
        r"进程状态验证",
        r"开始验证所有进程状态",
        r"打包环境中检测到进程不存在",
        r"进程不存在于系统中",
        r"进程在系统中不存在",
        r"在打包环境中，手动将进程标记为已终止",
        r"验证进程时出错",
        r"验证进程状态时出错",
        r"准备启动FFmpeg进程",
        r"FFmpeg进程已创建",
        r"FFmpeg进程状态验证",
        r"FFmpeg进程不存在于系统中",
        r"FFmpeg进程已不存在于系统中",
        r"验证FFmpeg进程状态时出错",
        r"开始检查系统中的所有进程",
        r"发现FFmpeg进程",
        r"系统中发现.*个FFmpeg进程",
        r"系统中发现.*个Python进程",
        r"我们的进程列表中PID=",
        r"检查系统进程时出错",
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

# 确保日志目录存在
os.makedirs(f"{script_path}/logs", exist_ok=True)

# 检查是否为GUI模式（没有控制台）
is_gui_mode = False
try:
    # 尝试写入stderr，如果失败则认为是GUI模式
    sys.stderr.write("")
except Exception:
    is_gui_mode = True

# 根据模式选择日志配置
if not is_gui_mode:
    # 控制台模式：添加控制台输出处理器
    logger.add(
        sys.stderr,
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}",
        enqueue=True,
    )
else:
    # GUI模式：添加内存清理日志文件处理器
    logger.add(
        f"{script_path}/logs/memory_clean.log",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        filter=lambda i: is_memory_cleanup_log(i),
        serialize=False,
        enqueue=True,
        retention=3,
        rotation="3 MB",
        encoding="utf-8",
    )
    print(f"内存清理日志将写入: {script_path}/logs/memory_clean.log")

# 无论何种模式，都添加文件日志处理器
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