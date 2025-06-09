import os
import time
import datetime
import glob
import shutil
from pathlib import Path
import sys
import json

# 获取当前脚本路径
script_path = os.path.split(os.path.realpath(sys.argv[0]))[0]
log_dir = os.path.join(script_path, "logs", "test_cleanup")
config_path = os.path.join(script_path, "config")
user_config_path = os.path.join(config_path, "user_settings.json")

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

def backup_user_config():
    """备份用户配置文件"""
    if os.path.exists(user_config_path):
        backup_path = user_config_path + ".bak"
        shutil.copy2(user_config_path, backup_path)
        print(f"已备份用户配置文件到: {backup_path}")
        with open(user_config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def restore_user_config(backup_config):
    """恢复用户配置文件"""
    backup_path = user_config_path + ".bak"
    if os.path.exists(backup_path):
        shutil.copy2(backup_path, user_config_path)
        os.remove(backup_path)
        print(f"已恢复用户配置文件")
    else:
        # 如果没有备份文件，则写入备份的配置
        with open(user_config_path, 'w', encoding='utf-8') as f:
            json.dump(backup_config, f, ensure_ascii=False, indent=4)
        print(f"已重新写入用户配置文件")

def update_user_config(retention_days, auto_clean=True):
    """更新用户配置文件中的日志清理设置"""
    try:
        # 读取现有配置
        if os.path.exists(user_config_path):
            with open(user_config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            config = {}
        
        # 更新日志清理设置
        config["log_retention_days"] = retention_days
        config["auto_clean_logs"] = auto_clean
        
        # 写入配置文件
        with open(user_config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        
        print(f"已更新用户配置: log_retention_days={retention_days}, auto_clean_logs={auto_clean}")
        
        # 验证配置是否正确写入
        with open(user_config_path, 'r', encoding='utf-8') as f:
            updated_config = json.load(f)
        if updated_config.get("auto_clean_logs") != auto_clean or updated_config.get("log_retention_days") != retention_days:
            print(f"警告: 配置可能未正确更新。当前值: auto_clean_logs={updated_config.get('auto_clean_logs')}, log_retention_days={updated_config.get('log_retention_days')}")
    except Exception as e:
        print(f"更新配置文件出错: {e}")

def list_log_files():
    """列出当前的日志文件"""
    files = glob.glob(os.path.join(log_dir, "*.*"))
    print(f"\n当前日志文件 ({len(files)}):")
    for file in files:
        file_time = os.path.getmtime(file)
        file_date = datetime.datetime.fromtimestamp(file_time)
        print(f"  {os.path.basename(file)} - {file_date.strftime('%Y-%m-%d %H:%M:%S')}")
    return files

def get_file_types(files):
    """获取文件类型列表"""
    file_types = set()
    for file in files:
        base_name = os.path.basename(file)
        # 从文件名中提取类型
        file_type = base_name.split('.')[0]
        file_types.add(file_type)
    return file_types

def test_config_cleanup():
    """测试通过配置触发的日志清理功能"""
    # 导入日志模块
    sys.path.insert(0, script_path)
    from app.utils.logger import cleanup_old_logs
    
    # 备份当前用户配置
    backup_config = backup_user_config()
    
    try:
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
        
        # 更新用户配置 - 确保启用自动清理
        update_user_config(retention_days, True)
        
        # 列出清理前的文件
        before_files = list_log_files()
        before_types = get_file_types(before_files)
        print(f"\n检测到的日志类型: {', '.join(before_types)}")
        
        # 模拟程序启动时的日志清理过程
        print("\n模拟程序启动时的日志清理过程...")
        try:
            # 直接调用清理函数，避免重新导入logger模块
            print("直接调用清理函数测试...")
            from app.core.config_manager import ConfigManager
            config_manager = ConfigManager(script_path)
            user_config = config_manager.load_user_config()
            
            # 检查配置是否正确加载
            print(f"从配置文件加载的设置: auto_clean_logs={user_config.get('auto_clean_logs')}, log_retention_days={user_config.get('log_retention_days')}")
            
            # 如果配置文件中auto_clean_logs不是True，强制设置为True进行测试
            if not user_config.get("auto_clean_logs", False):
                print("警告: 配置文件中auto_clean_logs设置为False，将临时强制启用进行测试")
                user_config["auto_clean_logs"] = True
            
            if user_config.get("auto_clean_logs", False):
                if "log_retention_days" in user_config:
                    try:
                        retention_days = int(user_config["log_retention_days"])
                        # 确保是正整数
                        if retention_days <= 0:
                            print(f"警告: 日志保留天数 {retention_days} 无效（必须大于0），使用默认值: 7天")
                            retention_days = 7
                    except (ValueError, TypeError) as e:
                        print(f"警告: 日志保留天数格式无效: {e}，使用默认值: 7天")
                        retention_days = 7
                    print(f"使用配置: log_retention_days={retention_days}, auto_clean_logs=True")
                    cleanup_old_logs(days=retention_days, log_dir=log_dir)
                else:
                    print("未找到日志保留天数设置，跳过清理")
            else:
                print("日志自动清理功能未开启，跳过清理")
            
        except Exception as e:
            print(f"模拟清理过程出错: {e}")
        
        # 列出清理后的文件
        after_files = list_log_files()
        after_types = get_file_types(after_files)
        
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
        if remaining_types == before_types:
            print("\n✅ 测试通过: 每种日志类型都至少保留了一个最新文件")
        else:
            missing_types = before_types - remaining_types
            print(f"\n❌ 测试失败: 以下日志类型没有保留文件: {', '.join(missing_types)}")
        
        # 计算删除的文件
        deleted_files = set(os.path.basename(f) for f in before_files) - set(os.path.basename(f) for f in after_files)
        print(f"\n已删除 {len(deleted_files)} 个文件:")
        for file in deleted_files:
            print(f"  {file}")
        
        # 测试关闭自动清理功能
        print("\n测试关闭自动清理功能...")
        update_user_config(retention_days, False)
        
        # 创建新的测试文件
        print("\n再次创建测试文件...")
        create_test_logs()
        
        # 列出清理前的文件
        before_files = list_log_files()
        before_types = get_file_types(before_files)
        print(f"\n检测到的日志类型: {', '.join(before_types)}")
        
        # 模拟程序启动时的日志清理过程
        print("\n模拟程序启动时的日志清理过程(已关闭自动清理)...")
        try:
            # 直接调用清理函数，避免重新导入logger模块
            print("直接调用清理函数测试...")
            config_manager = ConfigManager(script_path)
            user_config = config_manager.load_user_config()
            
            # 检查配置是否正确加载
            print(f"从配置文件加载的设置: auto_clean_logs={user_config.get('auto_clean_logs')}, log_retention_days={user_config.get('log_retention_days')}")
            
            # 确保auto_clean_logs设置为False
            if user_config.get("auto_clean_logs", True):
                print("警告: 配置文件中auto_clean_logs应为False但设置为True，将修正")
                user_config["auto_clean_logs"] = False
            
            if user_config.get("auto_clean_logs", False):
                if "log_retention_days" in user_config:
                    try:
                        retention_days = int(user_config["log_retention_days"])
                        # 确保是正整数
                        if retention_days <= 0:
                            print(f"警告: 日志保留天数 {retention_days} 无效（必须大于0），使用默认值: 7天")
                            retention_days = 7
                    except (ValueError, TypeError) as e:
                        print(f"警告: 日志保留天数格式无效: {e}，使用默认值: 7天")
                        retention_days = 7
                    print(f"使用配置: log_retention_days={retention_days}, auto_clean_logs=True")
                    cleanup_old_logs(days=retention_days, log_dir=log_dir)
                else:
                    print("未找到日志保留天数设置，跳过清理")
            else:
                print("日志自动清理功能未开启，跳过清理")
            
            # 再次测试，但这次强制执行清理（忽略auto_clean_logs设置）
            print("\n测试强制执行清理（忽略auto_clean_logs设置）...")
            if "log_retention_days" in user_config:
                try:
                    retention_days_value = user_config["log_retention_days"]
                    # 检查是否为空字符串
                    if retention_days_value == "":
                        print("警告: 日志保留天数设置为空，使用默认值: 7天")
                        retention_days = 7
                    else:
                        retention_days = int(retention_days_value)
                        # 确保是正整数
                        if retention_days <= 0:
                            print(f"警告: 日志保留天数 {retention_days} 无效（必须大于0），使用默认值: 7天")
                            retention_days = 7
                except (ValueError, TypeError) as e:
                    print(f"警告: 日志保留天数格式无效: {e}，使用默认值: 7天")
                    retention_days = 7
                print(f"使用配置中的保留天数: {retention_days}天")
                cleanup_old_logs(days=retention_days, log_dir=log_dir)
            
        except Exception as e:
            print(f"模拟清理过程出错: {e}")
        
        # 列出清理后的文件
        after_files = list_log_files()
        after_types = get_file_types(after_files)
        
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
        if remaining_types == before_types:
            print("\n✅ 测试通过: 每种日志类型都至少保留了一个最新文件")
        else:
            missing_types = before_types - remaining_types
            print(f"\n❌ 测试失败: 以下日志类型没有保留文件: {', '.join(missing_types)}")
        
        # 计算删除的文件
        deleted_files = set(os.path.basename(f) for f in before_files) - set(os.path.basename(f) for f in after_files)
        print(f"\n已删除 {len(deleted_files)} 个文件:")
        for file in deleted_files:
            print(f"  {file}")
        
        if len(deleted_files) == 0:
            print("自动清理功能已关闭，没有文件被删除，测试通过!")
        
    finally:
        # 恢复用户配置
        restore_user_config(backup_config)
        
        # 清理测试目录的选项
        cleanup = input("\n测试完成，是否删除测试目录? (y/n): ")
        if cleanup.lower() == 'y':
            shutil.rmtree(log_dir)
            print(f"已删除测试目录: {log_dir}")

def test_direct_cleanup():
    """直接测试日志清理功能，绕过配置文件"""
    # 导入日志模块
    sys.path.insert(0, script_path)
    from app.utils.logger import cleanup_old_logs
    
    try:
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
        
        # 列出清理前的文件
        before_files = list_log_files()
        before_types = get_file_types(before_files)
        print(f"\n检测到的日志类型: {', '.join(before_types)}")
        
        # 直接执行清理，不使用配置文件
        print(f"\n直接执行清理，保留天数: {retention_days}...")
        cleanup_old_logs(days=retention_days, log_dir=log_dir)
        
        # 列出清理后的文件
        after_files = list_log_files()
        after_types = get_file_types(after_files)
        
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
        if remaining_types == before_types:
            print("\n✅ 测试通过: 每种日志类型都至少保留了一个最新文件")
        else:
            missing_types = before_types - remaining_types
            print(f"\n❌ 测试失败: 以下日志类型没有保留文件: {', '.join(missing_types)}")
        
        # 计算删除的文件
        deleted_files = set(os.path.basename(f) for f in before_files) - set(os.path.basename(f) for f in after_files)
        print(f"\n已删除 {len(deleted_files)} 个文件:")
        for file in deleted_files:
            print(f"  {file}")
        
    finally:
        # 清理测试目录的选项
        cleanup = input("\n测试完成，是否删除测试目录? (y/n): ")
        if cleanup.lower() == 'y':
            shutil.rmtree(log_dir)
            print(f"已删除测试目录: {log_dir}")

if __name__ == "__main__":
    print("请选择测试模式:")
    print("1. 通过配置文件测试日志清理功能")
    print("2. 直接测试日志清理功能（绕过配置文件）")
    
    choice = input("\n请输入选项编号: ")
    if choice == "2":
        test_direct_cleanup()
    else:
        test_config_cleanup() 