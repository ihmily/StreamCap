import asyncio
import os
import threading
import time
import signal
import psutil

from .utils.logger import logger


class BackgroundService:

    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = BackgroundService()
        return cls._instance
    
    def __init__(self):
        self.tasks = []
        self.is_running = False
        self.worker_thread = None
        self._lock = threading.Lock()
    
    def add_task(self, task_func, *args, **kwargs):
        with self._lock:
            self.tasks.append((task_func, args, kwargs))
            logger.info(f"添加后台任务: {task_func.__name__}")
        
        if not self.is_running:
            self.start()
    
    def start(self):
        if self.is_running:
            return
        
        with self._lock:
            if not self.is_running:  # 双重检查锁定
                self.is_running = True
                self.worker_thread = threading.Thread(target=self._process_tasks, daemon=False)
                self.worker_thread.start()
                logger.info("后台服务已启动")
    
    def _process_tasks(self):
        while True:
            task = None
            with self._lock:
                if not self.tasks:
                    self.is_running = False
                    logger.info("所有后台任务已完成，服务停止")
                    break
                task_func, args, kwargs = self.tasks.pop(0)
                task = (task_func, args, kwargs)
            
            if task:
                task_func, args, kwargs = task
                try:
                    logger.info(f"执行后台任务: {task_func.__name__}")
                    task_func(*args, **kwargs)
                    logger.info(f"后台任务完成: {task_func.__name__}")
                except Exception as e:
                    logger.error(f"后台任务执行失败: {e}")


class AsyncProcessManager:
    def __init__(self):
        self.ffmpeg_processes = []
        self._lock = asyncio.Lock()
        self._process_start_time = {}  # 记录进程启动时间

    async def add_process(self, process):
        async with self._lock:
            self.ffmpeg_processes.append(process)
            self._process_start_time[process.pid] = time.time()
            logger.info(f"进程管理 - 添加新进程: PID={process.pid}, 当前进程数: {len(self.ffmpeg_processes)}")

    async def cleanup(self):
        """清理所有进程，确保它们被正确终止"""
        async with self._lock:
            processes_to_clean = self.ffmpeg_processes.copy()
            self.ffmpeg_processes.clear()
            
        cleanup_tasks = []
        for process in processes_to_clean:
            task = asyncio.create_task(self._cleanup_process(process))
            cleanup_tasks.append(task)
        
        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks)
            logger.debug(f"所有进程清理完成，共清理 {len(cleanup_tasks)} 个进程")
    
    async def _cleanup_process(self, process):
        """清理单个进程，使用更可靠的方法确保进程终止"""
        try:
            if process.returncode is None:
                pid = process.pid
                logger.debug(f"正在终止进程 PID={pid}")
                
                # 首先尝试正常退出FFmpeg
                if os.name == "nt":
                    if process.stdin:
                        try:
                            process.stdin.write(b"q")
                            await asyncio.wait_for(process.stdin.drain(), timeout=2.0)
                        except (asyncio.TimeoutError, ConnectionError, BrokenPipeError):
                            # 如果无法通过stdin退出，则继续使用信号
                            pass
                
                # 发送SIGTERM信号
                try:
                    process.terminate()
                except ProcessLookupError:
                    # 进程可能已经不存在
                    logger.debug(f"进程 PID={pid} 不存在，可能已经终止")
                    return
                
                # 等待进程正常终止
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                    logger.debug(f"进程 PID={pid} 已正常终止")
                    return
                except asyncio.TimeoutError:
                    logger.warning(f"进程 PID={pid} 未能在超时时间内终止，尝试强制终止")
                
                # 如果进程仍在运行，尝试发送SIGKILL信号
                try:
                    process.kill()
                    await asyncio.wait_for(process.wait(), timeout=3.0)
                    logger.debug(f"进程 PID={pid} 已被强制终止")
                except (asyncio.TimeoutError, ProcessLookupError):
                    # 如果进程仍然无法终止，尝试使用psutil
                    self._force_kill_process(pid)
            
            # 移除进程启动时间记录
            if process.pid in self._process_start_time:
                del self._process_start_time[process.pid]
                
        except Exception as e:
            logger.error(f"进程清理出错: {e}")
    
    def _force_kill_process(self, pid):
        """使用psutil强制终止进程及其子进程"""
        try:
            # 检查进程是否仍然存在
            if not psutil.pid_exists(pid):
                logger.debug(f"进程 PID={pid} 不存在，无需强制终止")
                return
            
            # 获取进程对象
            p = psutil.Process(pid)
            
            # 先终止子进程
            children = p.children(recursive=True)
            for child in children:
                try:
                    child.kill()
                    logger.debug(f"已终止子进程 PID={child.pid}")
                except psutil.NoSuchProcess:
                    pass
            
            # 终止主进程
            p.kill()
            logger.debug(f"已通过psutil强制终止进程 PID={pid}")
        except psutil.NoSuchProcess:
            logger.debug(f"进程 PID={pid} 不存在，可能已经终止")
        except Exception as e:
            logger.error(f"使用psutil终止进程 PID={pid} 时出错: {e}")
    
    async def get_running_processes_info(self):
        """获取所有运行中进程的信息，包括运行时间"""
        running_processes = []
        current_time = time.time()
        
        async with self._lock:
            for process in self.ffmpeg_processes:
                if process.returncode is None:
                    start_time = self._process_start_time.get(process.pid, current_time)
                    running_time = current_time - start_time
                    running_processes.append({
                        "pid": process.pid,
                        "running_time": running_time,
                        "running_time_str": self._format_time(running_time)
                    })
        
        return running_processes
    
    @staticmethod
    def _format_time(seconds):
        """将秒数格式化为可读的时间字符串"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        
        if hours > 0:
            return f"{hours}小时 {minutes}分钟 {seconds}秒"
        elif minutes > 0:
            return f"{minutes}分钟 {seconds}秒"
        else:
            return f"{seconds}秒"
