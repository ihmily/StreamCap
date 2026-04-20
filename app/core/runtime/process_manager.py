import asyncio
import os
import threading
import time

from ...utils.logger import logger


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
    
    def add_task(self, task_func, *args, **kwargs):
        self.tasks.append((task_func, args, kwargs))
        logger.info(f"Added background task: {task_func.__name__}")
        
        if not self.is_running:
            self.start()
    
    def start(self):
        if self.is_running:
            return
            
        self.is_running = True
        self.worker_thread = threading.Thread(target=self._process_tasks, daemon=False)
        self.worker_thread.start()
        logger.info("Background service started")
    
    def _process_tasks(self):
        while self.tasks:
            task_func, args, kwargs = self.tasks.pop(0)
            try:
                logger.info(f"Executing background task: {task_func.__name__}")
                task_func(*args, **kwargs)
                logger.info(f"Background task completed: {task_func.__name__}")
            except Exception as e:
                logger.error(f"Background task execution failed: {e}")
        
        logger.info("All background tasks completed, service stopped")
        self.is_running = False

    def has_pending_work(self) -> bool:
        return bool(self.tasks) or bool(self.worker_thread and self.worker_thread.is_alive())

    def wait_for_completion(self, timeout: float | None = None, poll_interval: float = 0.1) -> bool:
        deadline = None if timeout is None else time.monotonic() + timeout

        while self.has_pending_work():
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                wait_time = min(poll_interval, remaining)
            else:
                wait_time = poll_interval

            if self.worker_thread and self.worker_thread.is_alive():
                self.worker_thread.join(wait_time)
            else:
                time.sleep(wait_time)

        return True


class AsyncProcessManager:
    def __init__(self):
        self.ffmpeg_processes = []

    def add_process(self, process):
        self.ffmpeg_processes.append(process)

    async def cleanup(self):
        for process in self.ffmpeg_processes[:]:
            try:
                if process.returncode is None:
                    logger.debug(f"Terminating process {process.pid}")
                    if os.name == "nt":
                        if process.stdin:
                            process.stdin.write(b"q")
                            await process.stdin.drain()
                    else:
                        process.terminate()

                    try:
                        await asyncio.wait_for(process.wait(), timeout=5.0)
                    except asyncio.TimeoutError:
                        logger.warning(f"Process {process.pid} did not terminate, killing it")
                        process.kill()
                        await process.wait()

                self.ffmpeg_processes.remove(process)
            except Exception as e:
                logger.error(f"Error cleaning up process: {e}")
                if process in self.ffmpeg_processes:
                    self.ffmpeg_processes.remove(process)

        logger.debug("All processes cleaned up")
