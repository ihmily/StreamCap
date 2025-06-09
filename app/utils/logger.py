import os
import sys
import re
import logging
import time
import datetime
import glob
import shutil
import asyncio
import threading

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

# 日志定时清理任务类
class LogCleanupScheduler:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = LogCleanupScheduler()
        return cls._instance
    
    def __init__(self):
        self.is_running = False
        self.scheduler_thread = None
        self.next_cleanup_time = None
        self._lock = threading.Lock()
    
    def start(self, config_manager=None):
        """启动定时清理任务"""
        with self._lock:
            if self.is_running:
                return
            
            self.is_running = True
            self.config_manager = config_manager
            
            # 先计算下次清理时间，确保self.next_cleanup_time不为None
            self._calculate_next_cleanup_time()
            
            self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
            self.scheduler_thread.start()
            logger.info("日志定时清理任务已启动")
            logger.info(f"下次日志清理时间: {self.next_cleanup_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    def _calculate_next_cleanup_time(self):
        """计算下次清理时间（凌晨3点）"""
        now = datetime.datetime.now()
        # 今天凌晨3点
        today_3am = now.replace(hour=3, minute=0, second=0, microsecond=0)
        
        # 如果当前时间已经过了今天凌晨3点，则设置为明天凌晨3点
        if now > today_3am:
            self.next_cleanup_time = today_3am + datetime.timedelta(days=1)
        else:
            self.next_cleanup_time = today_3am
    
    def _scheduler_loop(self):
        """定时器循环，检查是否到达清理时间"""
        while self.is_running:
            try:
                now = datetime.datetime.now()
                
                # 确保next_cleanup_time不为None
                if self.next_cleanup_time is None:
                    self._calculate_next_cleanup_time()
                    logger.info(f"重新计算清理时间: {self.next_cleanup_time.strftime('%Y-%m-%d %H:%M:%S')}")
                
                # 检查是否到达清理时间
                if now >= self.next_cleanup_time:
                    logger.info("开始执行定时日志清理")
                    
                    # 从配置中获取日志保留天数和是否启用自动清理
                    retention_days = None  # 不设置默认值，使用cleanup_old_logs函数中的默认逻辑
                    auto_clean_enabled = False  # 默认不启用
                    
                    # 如果有配置管理器，从配置中获取保留天数和是否启用自动清理
                    if self.config_manager:
                        try:
                            user_config = self.config_manager.load_user_config()
                            auto_clean_enabled = user_config.get("auto_clean_logs", False)
                            if "log_retention_days" in user_config:
                                retention_days = int(user_config["log_retention_days"])
                                logger.info(f"从配置中获取日志保留天数: {retention_days}")
                            else:
                                logger.info("配置中未设置日志保留天数，将使用默认值")
                        except Exception as e:
                            logger.error(f"加载用户配置时出错: {e}")
                    
                    # 如果启用了自动清理，执行清理
                    if auto_clean_enabled:
                        if retention_days is not None:
                            logger.info(f"执行定时日志清理，保留 {retention_days} 天")
                            cleanup_old_logs(days=retention_days)
                        else:
                            # 使用cleanup_old_logs函数的默认逻辑
                            logger.info("执行定时日志清理，使用默认保留天数")
                            cleanup_old_logs(days=7)  # 默认保留7天
                    else:
                        logger.info("日志自动清理功能未开启，跳过清理")
                    
                    # 计算下次清理时间
                    self._calculate_next_cleanup_time()
                    logger.info(f"下次日志清理时间: {self.next_cleanup_time.strftime('%Y-%m-%d %H:%M:%S')}")
                
                # 每小时检查一次
                time.sleep(60)
            except Exception as e:
                logger.error(f"日志定时清理任务出错: {e}")
                # 出错后等待10分钟再继续
                time.sleep(600)

# 清理旧日志文件
def cleanup_old_logs(days, log_dir=None):
    """
    清理指定天数之前的日志文件，但每种日志类型至少保留一个最新文件
    
    Args:
        days: 保留的天数
        log_dir: 日志目录，默认为None，使用script_path/logs
    """
    if log_dir is None:
        log_dir = os.path.join(script_path, "logs")
    
    if not os.path.exists(log_dir):
        return
    
    # 计算截止时间
    cutoff_time = time.time() - (days * 24 * 60 * 60)
    cutoff_date = datetime.datetime.fromtimestamp(cutoff_time)
    
    # 获取所有日志文件
    log_files = glob.glob(os.path.join(log_dir, "*.*"))
    
    # 按日志类型分组文件
    log_types = {}
    for log_file in log_files:
        base_name = os.path.basename(log_file)
        
        # 处理新格式的日志文件名: [类型].[年-月-日_时-分-秒_微秒].log
        if '.' in base_name:
            parts = base_name.split('.')
            if len(parts) >= 2:
                # 第一部分是日志类型
                log_type = parts[0]
                
                # 检查是否是我们关心的三种日志类型之一或其他日志文件
                if log_type not in log_types:
                    log_types[log_type] = []
                log_types[log_type].append(log_file)
                continue
        
        # 处理旧格式的日志文件
        if "_days_ago" in base_name:
            # 测试文件格式: test_log_X_days_ago.log
            if base_name.startswith("test_log_"):
                log_type = "test_log"  # 所有测试日志视为同一类型
            else:
                # 其他测试文件如app_X_days_ago.log，使用前缀作为类型
                log_type = base_name.split('_')[0]
        else:
            # 正常日志文件，使用完整基本名称作为类型
            log_type = base_name.split('.log')[0]
        
        if log_type not in log_types:
            log_types[log_type] = []
        log_types[log_type].append(log_file)
    
    deleted_count = 0
    preserved_files = []
    
    for log_type, files in log_types.items():
        # 按修改时间排序文件（最新的在前）
        try:
            sorted_files = sorted(files, key=os.path.getmtime, reverse=True)
            
            # 保留每种类型的最新文件
            if sorted_files:
                newest_file = sorted_files[0]
                # 记录最新文件信息
                file_mtime = os.path.getmtime(newest_file)
                file_date = datetime.datetime.fromtimestamp(file_mtime)
                # 如果最新文件也超过了截止日期，记录它被保留的信息
                if file_date < cutoff_date:
                    preserved_files.append(f"{os.path.basename(newest_file)} ({file_date.strftime('%Y-%m-%d %H:%M:%S')})")
                
                # 检查其余文件是否过期
                files_to_check = sorted_files[1:]
                for log_file in files_to_check:
                    try:
                        # 获取文件修改时间
                        file_mtime = os.path.getmtime(log_file)
                        file_date = datetime.datetime.fromtimestamp(file_mtime)
                        
                        # 如果文件修改时间早于截止时间，则删除
                        if file_date < cutoff_date:
                            os.remove(log_file)
                            deleted_count += 1
                    except Exception as e:
                        logger.error(f"清理日志文件 {log_file} 时出错: {e}")
        except Exception as e:
            logger.error(f"处理日志类型 {log_type} 时出错: {e}")
    
    if deleted_count > 0:
        logger.info(f"已清理 {deleted_count} 个超过 {days} 天的旧日志文件")
    
    if preserved_files:
        logger.info(f"为保留历史记录，以下{len(preserved_files)}个超过保留期限的日志文件被保留: {', '.join(preserved_files)}")

# 为测试脚本提供的日志设置函数
def setup_logger(level=logging.INFO):
    """为测试脚本设置日志
    
    Args:
        level: 日志级别，默认为INFO
    """
    # 确保日志目录存在
    os.makedirs(f"{script_path}/logs", exist_ok=True)
    
    # 清除所有已有的处理器
    logger.remove()
    
    # 添加控制台输出
    logger.add(
        sys.stderr,
        level=level,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}",
        enqueue=True,
    )
    
    # 添加测试日志文件处理器
    logger.add(
        f"{script_path}/logs/test.log",
        level=level,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        serialize=False,
        enqueue=True,
        retention=1,
        rotation="1 MB",
        encoding="utf-8",
    )
    
    return logger

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

# 尝试清理旧日志文件
try:
    # 尝试从配置管理器中获取用户配置
    config_manager = None
    try:
        from ..core.config_manager import ConfigManager
        config_manager = ConfigManager(script_path)
        user_config = config_manager.load_user_config()
        
        # 检查是否启用自动清理日志，默认为False（不清理）
        if user_config.get("auto_clean_logs", False):
            # 获取日志保留天数，必须从用户配置中获取
            if "log_retention_days" in user_config:
                retention_days = int(user_config["log_retention_days"])
                logger.info(f"开始清理 {retention_days} 天前的日志文件")
                cleanup_old_logs(days=retention_days)
            else:
                logger.info("未找到日志保留天数设置，跳过清理")
        else:
            logger.info("日志自动清理功能未开启，跳过清理")
            
        # 启动定时清理任务
        log_cleanup_scheduler = LogCleanupScheduler.get_instance()
        log_cleanup_scheduler.start(config_manager)
        
    except ImportError:
        # 如果无法导入ConfigManager，则不执行清理
        logger.info("无法导入配置管理器，跳过日志清理")
        
        # 仍然启动定时清理任务，但不传入配置管理器
        log_cleanup_scheduler = LogCleanupScheduler.get_instance()
        log_cleanup_scheduler.start()
except Exception as e:
    logger.error(f"清理旧日志文件时出错: {e}") 