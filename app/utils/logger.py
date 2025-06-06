import os
import sys
import re

from loguru import logger

# 获取应用程序根目录
def get_application_root():
    """获取应用程序根目录，支持PyInstaller打包和开发环境"""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # PyInstaller打包环境
        base_path = os.path.dirname(sys.executable)
    else:
        # 开发环境
        base_path = os.path.split(os.path.realpath(sys.argv[0]))[0]
    return base_path

# 获取日志目录
def get_logs_dir():
    """获取或创建日志目录"""
    root_dir = get_application_root()
    logs_dir = os.path.join(root_dir, "logs")
    
    # 确保日志目录存在
    if not os.path.exists(logs_dir):
        try:
            os.makedirs(logs_dir, exist_ok=True)
            print(f"Created logs directory: {logs_dir}")
        except Exception as e:
            print(f"Error creating logs directory: {e}")
            # 使用当前目录作为备用
            logs_dir = os.path.join(os.getcwd(), "logs")
            os.makedirs(logs_dir, exist_ok=True)
            print(f"Using fallback logs directory: {logs_dir}")
    
    return logs_dir

# 创建日志文件路径
def get_log_file_path(filename):
    """获取日志文件的完整路径"""
    logs_dir = get_logs_dir()
    return os.path.join(logs_dir, filename)

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

# 初始化日志目录
logs_dir = get_logs_dir()
print(f"Using logs directory: {logs_dir}")

# 添加一个控制台输出的处理器，用于所有日志（包括内存清理日志）
logger.add(
    sys.stderr,
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}",
    enqueue=True,
)

try:
    # 文件日志处理器，排除内存清理日志
    streamget_log_path = get_log_file_path("streamget.log")
    logger.add(
        streamget_log_path,
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        filter=lambda i: not_memory_cleanup_log(i) and i["level"].name != "STREAM",
        serialize=False,
        enqueue=True,
        retention=3,
        rotation="3 MB",
        encoding="utf-8",
    )
    print(f"Added streamget log handler: {streamget_log_path}")

    # 添加自定义日志级别
    logger.level("STREAM", no=22, color="<blue>")
    
    # 播放URL日志处理器
    play_url_log_path = get_log_file_path("play_url.log")
    logger.add(
        play_url_log_path,
        level="STREAM",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {message}",
        filter=lambda i: i["level"].name == "STREAM",
        serialize=False,
        enqueue=True,
        retention=1,
        rotation="500 KB",
        encoding="utf-8",
    )
    print(f"Added play_url log handler: {play_url_log_path}")
except Exception as e:
    # 捕获任何日志初始化错误，但不影响程序运行
    print(f"Error initializing log handlers: {e}")
    # 仅使用控制台日志
    logger.warning(f"Failed to initialize file logs, using console logging only: {e}")
