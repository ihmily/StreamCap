import asyncio
import gc
import os
import time
import psutil
from datetime import datetime

# 使用项目的logger
from app.utils.logger import logger

class MemoryTestHelper:
    def __init__(self):
        self.process = psutil.Process()
        self.start_memory = None
        self.memory_samples = []
        self.test_start_time = None
    
    def start_monitoring(self):
        """开始内存监控"""
        self.test_start_time = time.time()
        self.start_memory = self.get_memory_usage()
        self.memory_samples = [self.start_memory]
        logger.info(f"开始内存测试 - 初始内存: {self.start_memory['process_mb']:.2f}MB, 系统内存使用率: {self.start_memory['system_percent']:.1f}%")
        
    def get_memory_usage(self):
        """获取当前内存使用情况"""
        try:
            # 刷新内存信息
            self.process.memory_info()
            
            # 获取进程内存信息
            process_info = self.process.memory_info()
            process_mb = process_info.rss / (1024 * 1024)
            
            # 获取系统内存信息
            system_memory = psutil.virtual_memory()
            system_percent = system_memory.percent
            system_used_mb = system_memory.used / (1024 * 1024)
            
            # 计算测试持续时间
            duration = time.time() - self.test_start_time if self.test_start_time else 0
            
            return {
                "timestamp": time.time(),
                "process_mb": process_mb,
                "system_percent": system_percent,
                "system_used_mb": system_used_mb,
                "duration": duration
            }
        except Exception as e:
            logger.error(f"获取内存使用信息时出错: {e}")
            return {
                "timestamp": time.time(),
                "process_mb": 0,
                "system_percent": 0,
                "system_used_mb": 0,
                "duration": 0
            }
    
    def take_memory_sample(self):
        """记录一次内存样本"""
        current = self.get_memory_usage()
        self.memory_samples.append(current)
        return current
    
    def log_memory_status(self, event_name="常规检查"):
        """记录当前内存状态"""
        current = self.take_memory_sample()
        
        if self.start_memory:
            memory_change = current["process_mb"] - self.start_memory["process_mb"]
            change_text = f"变化: {memory_change:+.2f}MB"
            
            # 计算内存增长率
            growth_rate = 0
            if len(self.memory_samples) > 5:  # 至少需要多个样本才能计算趋势
                recent_samples = self.memory_samples[-5:]
                if recent_samples[0]["duration"] != recent_samples[-1]["duration"]:
                    time_diff = recent_samples[-1]["duration"] - recent_samples[0]["duration"]
                    memory_diff = recent_samples[-1]["process_mb"] - recent_samples[0]["process_mb"]
                    growth_rate = (memory_diff / time_diff) * 60  # 每分钟增长率
            
            growth_text = f"增长率: {growth_rate:.2f}MB/分钟"
        else:
            change_text = ""
            growth_text = ""
        
        logger.info(f"内存状态 [{event_name}] - "
                   f"进程: {current['process_mb']:.2f}MB {change_text}, "
                   f"系统: {current['system_percent']:.1f}%, "
                   f"已运行: {int(current['duration']//60)}分{int(current['duration']%60)}秒, "
                   f"{growth_text}")
        
        return current
    
    def summarize_test(self):
        """总结测试结果"""
        if not self.memory_samples or len(self.memory_samples) < 2:
            logger.warning("没有足够的内存样本进行总结")
            return
        
        start = self.memory_samples[0]
        end = self.memory_samples[-1]
        
        # 找出最大内存使用
        max_sample = max(self.memory_samples, key=lambda x: x["process_mb"])
        
        # 计算最终内存变化
        total_change = end["process_mb"] - start["process_mb"]
        percent_change = (total_change / start["process_mb"]) * 100 if start["process_mb"] > 0 else 0
        
        # 计算整体增长率
        total_duration = end["duration"] - start["duration"]
        growth_rate = (total_change / total_duration) * 60 if total_duration > 0 else 0  # 每分钟
        
        # 记录摘要
        logger.info("=" * 50)
        logger.info("内存测试总结")
        logger.info("=" * 50)
        logger.info(f"测试持续时间: {int(total_duration//60)}分{int(total_duration%60)}秒")
        logger.info(f"初始内存使用: {start['process_mb']:.2f}MB")
        logger.info(f"最终内存使用: {end['process_mb']:.2f}MB")
        logger.info(f"最大内存使用: {max_sample['process_mb']:.2f}MB (时间点: {int(max_sample['duration']//60)}分{int(max_sample['duration']%60)}秒)")
        logger.info(f"内存变化量: {total_change:+.2f}MB ({percent_change:+.1f}%)")
        logger.info(f"平均增长率: {growth_rate:.2f}MB/分钟")
        logger.info(f"采样次数: {len(self.memory_samples)}")
        logger.info(f"系统内存占用变化: {start['system_percent']:.1f}% -> {end['system_percent']:.1f}%")
        logger.info("=" * 50)


async def test_optimized_memory_management():
    """测试优化后的内存管理"""
    # 导入应用程序组件
    from app.core.platform_handlers import PlatformHandler
    from app.process_manager import AsyncProcessManager
    
    # 创建测试帮助器
    memory_helper = MemoryTestHelper()
    memory_helper.start_monitoring()
    
    # 记录初始状态
    memory_helper.log_memory_status("测试开始")
    
    # 模拟创建多个平台处理器实例
    logger.info("创建平台处理器实例...")
    for i in range(30):
        # 模拟不同的URL和配置
        test_url = f"https://www.douyin.com/test{i}"
        proxy = f"http://127.0.0.1:{8000+i}" if i % 3 == 0 else None
        cookies = f"cookie{i}=value{i}" if i % 2 == 0 else None
        quality = ["default", "uhd", "fhd", "hd", "sd"][i % 5]
        
        # 获取实例
        handler = PlatformHandler.get_handler_instance(
            test_url, proxy, cookies, quality, "douyin"
        )
        if handler:
            logger.info(f"创建实例 {i+1}/30: {quality}")
        else:
            logger.warning(f"无法创建实例 {i+1}")
        
        # 每10个实例检查一次内存
        if (i+1) % 10 == 0:
            memory_helper.log_memory_status(f"创建了 {i+1} 个实例")
        
        # 暂停一小段时间模拟实际使用
        await asyncio.sleep(0.1)
    
    # 记录实例创建后的内存状态
    instance_count = PlatformHandler.get_instances_count()
    memory_helper.log_memory_status(f"创建实例完成，当前实例数: {instance_count}")
    
    # 主动触发一次垃圾回收
    logger.info("主动触发垃圾回收...")
    gc.collect()
    memory_helper.log_memory_status("垃圾回收后")
    
    # 等待一段时间让自动清理生效
    logger.info("等待30秒让自动清理机制工作...")
    await asyncio.sleep(30)
    memory_helper.log_memory_status("等待30秒后")
    
    # 显式清理未使用的实例
    logger.info("显式清理未使用的实例...")
    before_count = PlatformHandler.get_instances_count()
    PlatformHandler.clear_unused_instances()
    after_count = PlatformHandler.get_instances_count()
    memory_helper.log_memory_status(f"清理实例后 (减少: {before_count - after_count})")
    
    # 获取实例统计信息
    instance_stats = PlatformHandler.get_instance_stats()
    logger.info(f"实例统计: {instance_stats}")
    
    # 再次等待一段时间
    logger.info("再次等待30秒观察稳定性...")
    await asyncio.sleep(30)
    memory_helper.log_memory_status("第二次等待后")
    
    # 测试总结
    memory_helper.summarize_test()
    
    return memory_helper


async def main():
    """主测试函数"""
    logger.info("开始内存优化测试...")
    
    # 确保日志目录存在
    os.makedirs("logs", exist_ok=True)
    
    try:
        # 优化后的内存管理测试
        await test_optimized_memory_management()
    except Exception as e:
        logger.error(f"测试过程中出错: {e}", exc_info=True)
    
    logger.info("内存优化测试完成")


if __name__ == "__main__":
    asyncio.run(main()) 