import asyncio
from app.utils.logger import logger

class DelayedTaskExecutor:
    def __init__(self, app, settings, delay=3):
        self.app = app
        self.settings = settings
        self.save_timers = {}
        self.delay = delay
        self.pending_tasks = {}

    async def start_task_timer(self, task, delay: int | None = None):
        """使用防抖动机制启动定时器，相同类型的任务只会保留最新的一个"""
        task_name = task.__name__
        
        if task_name in self.save_timers and self.save_timers[task_name]:
            self.save_timers[task_name].cancel()
            
        self.pending_tasks[task_name] = task
            
        self.save_timers[task_name] = self.app.page.run_task(
            self._execute_task, 
            task_name, 
            delay or self.delay
        )
    
    async def _execute_task(self, task_name, delay):
        """执行实际的任务，并处理可能的异常"""
        await asyncio.sleep(delay)
        if task_name in self.pending_tasks:
            task = self.pending_tasks[task_name]
            try:
                await task(delay)
                if task_name in self.pending_tasks:
                    del self.pending_tasks[task_name]
            except Exception as e:
                logger.error(f"执行延迟任务时出错: {e}")
