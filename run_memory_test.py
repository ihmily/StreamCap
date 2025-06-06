#!/usr/bin/env python3
"""
内存优化效果测试脚本
用于测试StreamCap的内存管理优化效果
"""

import os
import sys
import time
import argparse
from datetime import datetime

def print_title(title):
    """打印格式化的标题"""
    print("\n" + "=" * 70)
    print(f" {title} ".center(70, "="))
    print("=" * 70)

def print_step(step, description):
    """打印格式化的步骤"""
    print(f"\n>>> 步骤 {step}: {description}")
    print("-" * 70)

def create_log_dir():
    """创建日志目录"""
    os.makedirs("logs", exist_ok=True)
    print(f"日志目录已准备: {os.path.abspath('logs')}")

def run_test(test_type, duration=120):
    """运行指定类型的测试"""
    if test_type == "memory":
        print_step(1, "运行内存管理测试")
        print("此测试将创建多个平台处理器实例并监控内存使用情况")
        os.system(f"python test_memory_optimization.py")
    
    elif test_type == "close":
        print_step(1, "运行应用关闭测试")
        print("此测试将模拟应用关闭过程，验证资源清理机制")
        os.system(f"python test_app_close.py")
    
    elif test_type == "full":
        print_step(1, "启动应用并运行完整测试")
        print(f"应用将运行 {duration} 秒，然后检查内存使用情况")
        print("\n请执行以下操作:")
        print("1. 添加5-10个直播间进行监控")
        print("2. 等待应用自动进行内存清理")
        print("3. 观察日志输出中的内存使用情况")
        
        # 启动应用
        start_time = datetime.now()
        print(f"\n启动时间: {start_time.strftime('%H:%M:%S')}")
        print(f"应用将运行至: {(start_time + timedelta(seconds=duration)).strftime('%H:%M:%S')}")
        
        # 在这里可以添加启动应用的代码
        # 例如: os.system("python main.py")
        
        print("\n请手动启动应用，完成测试操作后回到此窗口按 Ctrl+C 结束测试")
        try:
            time.sleep(duration)
        except KeyboardInterrupt:
            print("\n测试被手动中断")
    
    else:
        print(f"未知的测试类型: {test_type}")
        return False
    
    return True

def analyze_logs():
    """分析日志文件"""
    print_step(2, "分析日志文件")
    
    log_files = []
    for file in os.listdir("logs"):
        if file.endswith(".log"):
            log_files.append(os.path.join("logs", file))
    
    if not log_files:
        print("未找到日志文件")
        return
    
    # 按修改时间排序，获取最新的日志
    log_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    latest_log = log_files[0]
    
    print(f"最新的日志文件: {latest_log}")
    print("\n日志内容摘要:")
    
    # 提取关键信息
    memory_stats = []
    instance_counts = []
    cleanup_events = []
    
    with open(latest_log, 'r', encoding='utf-8') as f:
        for line in f:
            if "内存状态" in line:
                memory_stats.append(line.strip())
            elif "实例数" in line:
                instance_counts.append(line.strip())
            elif "清理" in line:
                cleanup_events.append(line.strip())
    
    # 打印内存使用情况
    if memory_stats:
        print("\n内存使用情况:")
        for i, stat in enumerate(memory_stats[:5]):
            print(f"  {stat}")
        if len(memory_stats) > 10:
            print(f"  ... 共 {len(memory_stats)} 条记录 ...")
            for stat in memory_stats[-5:]:
                print(f"  {stat}")
    else:
        print("\n注意：内存清理相关日志不再写入日志文件，只在控制台输出")
    
    # 打印实例数量变化
    if instance_counts:
        print("\n实例数量变化:")
        for count in instance_counts:
            print(f"  {count}")
    else:
        print("\n没有找到实例数量变化记录")
    
    # 打印清理事件
    if cleanup_events:
        print("\n清理事件:")
        for event in cleanup_events:
            print(f"  {event}")
    else:
        print("\n没有找到清理事件记录，因为内存清理相关日志只在控制台输出")
    
    print(f"\n完整日志文件位于: {os.path.abspath(latest_log)}")
    print("\n注意：请查看控制台输出以获取完整的内存清理信息")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="StreamCap内存优化测试工具")
    parser.add_argument('--type', choices=['memory', 'close', 'full'], default='memory',
                      help='测试类型: memory(内存管理), close(应用关闭), full(完整应用)')
    parser.add_argument('--duration', type=int, default=120,
                      help='完整测试的运行时间(秒)')
    
    args = parser.parse_args()
    
    print_title("StreamCap 内存优化测试")
    
    create_log_dir()
    
    if run_test(args.type, args.duration):
        analyze_logs()
        
        print_title("测试结果分析")
        print("""
测试完成后，请检查以下几点来验证优化是否有效:

1. 内存使用情况:
   - 内存使用量是否稳定，没有持续增长
   - 内存增长率是否随时间降低
   - 清理后内存是否有明显下降

2. 实例管理:
   - 未使用的实例是否被正确清理
   - 实例数量是否在创建后减少

3. 进程管理:
   - 进程是否能够被正确终止
   - 应用关闭时资源是否被正确释放

4. 长时间运行:
   - 应用是否能够稳定运行较长时间
   - 内存使用是否保持在合理范围内
        """)
    
    print_title("测试完成")

if __name__ == "__main__":
    from datetime import timedelta
    main() 