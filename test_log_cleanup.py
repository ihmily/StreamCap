import os
import time
import datetime
import glob
import shutil
from pathlib import Path
import sys

# 获取当前脚本路径
script_path = os.path.split(os.path.realpath(sys.argv[0]))[0]
log_dir = os.path.join(script_path, "logs", "test_cleanup")

def create_test_logs():
    """创建测试日志文件，并设置不同的修改时间"""
    # 确保测试目录存在
    os.makedirs(log_dir, exist_ok=True)
    
    # 清理之前的测试文件
    for old_file in glob.glob(os.path.join(log_dir, "*.*")):
        os.remove(old_file)
    
    # 获取当前时间
    now = time.time()
    
    # 创建不同天数的日志文件
    days_list = [1, 3, 5, 7, 10, 15, 30]
    
    # 创建三种类型的日志文件：streamget、play_url、memory_clean
    log_types = ["streamget", "play_url", "memory_clean"]
    
    for log_type in log_types:
        for days in days_list:
            # 计算文件时间戳
            file_time = now - (days * 24 * 60 * 60)
            file_date = datetime.datetime.fromtimestamp(file_time)
            
            # 使用指定格式创建文件名：[类型].[年-月-日_时-分-秒_微秒].log
            timestamp = file_date.strftime("%Y-%m-%d_%H-%M-%S_%f")
            file_name = f"{log_type}.{timestamp}.log"
            
            # 创建文件
            file_path = os.path.join(log_dir, file_name)
            with open(file_path, "w") as f:
                f.write(f"This is a {log_type} log file from {days} days ago")
            
            # 修改文件的访问时间和修改时间
            os.utime(file_path, (file_time, file_time))
            
            # 验证文件时间是否设置成功
            actual_time = os.path.getmtime(file_path)
            actual_date = datetime.datetime.fromtimestamp(actual_time)
            print(f"创建{log_type}类型测试文件: {file_path}")
            print(f"  设置时间为: {actual_date.strftime('%Y-%m-%d %H:%M:%S')} ({days} 天前)")
    
    print(f"\n测试日志文件已创建在: {log_dir}")
    return days_list

def test_cleanup(retention_days):
    """测试清理指定天数前的日志文件"""
    from app.utils.logger import cleanup_old_logs
    
    print(f"\n开始测试清理 {retention_days} 天前的日志文件...")
    
    # 列出清理前的所有文件
    print("清理前的文件:")
    before_files = glob.glob(os.path.join(log_dir, "*.*"))
    for file in before_files:
        file_time = os.path.getmtime(file)
        file_date = datetime.datetime.fromtimestamp(file_time)
        print(f"  {os.path.basename(file)} - {file_date.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 获取文件类型列表
    file_types = set()
    for file in before_files:
        base_name = os.path.basename(file)
        # 从文件名中提取类型
        file_type = base_name.split('.')[0]
        file_types.add(file_type)
    
    print(f"\n检测到的日志类型: {', '.join(file_types)}")
    
    # 执行清理
    cleanup_old_logs(days=retention_days, log_dir=log_dir)
    
    # 列出清理后的所有文件
    print("\n清理后的文件:")
    after_files = glob.glob(os.path.join(log_dir, "*.*"))
    for file in after_files:
        file_time = os.path.getmtime(file)
        file_date = datetime.datetime.fromtimestamp(file_time)
        print(f"  {os.path.basename(file)} - {file_date.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 计算删除的文件
    deleted_files = set(os.path.basename(f) for f in before_files) - set(os.path.basename(f) for f in after_files)
    print(f"\n已删除 {len(deleted_files)} 个文件:")
    for file in deleted_files:
        print(f"  {file}")
    
    # 验证每种类型是否至少保留了一个文件
    remaining_files_by_type = {}
    for file in after_files:
        base_name = os.path.basename(file)
        # 从文件名中提取类型
        file_type = base_name.split('.')[0]
        
        if file_type not in remaining_files_by_type:
            remaining_files_by_type[file_type] = []
        remaining_files_by_type[file_type].append(base_name)
    
    print("\n每种类型保留的文件:")
    for file_type, files in remaining_files_by_type.items():
        print(f"  {file_type}: {', '.join(files)}")
    
    # 检查是否所有类型都至少保留了一个文件
    remaining_types = set(remaining_files_by_type.keys())
    if remaining_types == file_types:
        print("\n✅ 测试通过: 每种日志类型都至少保留了一个最新文件")
    else:
        missing_types = file_types - remaining_types
        print(f"\n❌ 测试失败: 以下日志类型没有保留文件: {', '.join(missing_types)}")
    
    return len(deleted_files)

def main():
    """主测试函数"""
    print("===== 日志自动删除功能测试 =====")
    
    # 创建测试日志文件
    days_list = create_test_logs()
    
    # 让用户选择要测试的天数
    print("\n请选择要测试的日志保留天数:")
    for i, days in enumerate(days_list):
        print(f"{i+1}. {days} 天")
    print(f"{len(days_list)+1}. 自定义天数")
    
    choice = input("\n请输入选项编号: ")
    try:
        choice = int(choice)
        if 1 <= choice <= len(days_list):
            retention_days = days_list[choice-1]
        else:
            try:
                retention_days = int(input("请输入自定义的日志保留天数: "))
                # 确保是正整数
                if retention_days <= 0:
                    print(f"输入的天数 {retention_days} 无效（必须大于0），使用默认值7天")
                    retention_days = 7
            except ValueError:
                print("输入无效，使用默认值7天")
                retention_days = 7
    except ValueError:
        print("输入无效，使用默认值7天")
        retention_days = 7
    
    # 测试清理功能
    test_cleanup(retention_days)
    
    # 清理测试目录的选项
    cleanup = input("\n测试完成，是否删除测试目录? (y/n): ")
    if cleanup.lower() == 'y':
        shutil.rmtree(log_dir)
        print(f"已删除测试目录: {log_dir}")

if __name__ == "__main__":
    main() 