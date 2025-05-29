#!/usr/bin/env python3
"""
测试脚本：验证GitHub Actions工作流配置
"""

import yaml
import os
import sys

def test_workflow_syntax():
    """测试工作流文件的YAML语法"""
    workflows_dir = ".github/workflows"
    workflow_files = ["build.yml", "release.yml"]
    
    print("🔍 检查工作流文件语法...")
    
    for workflow_file in workflow_files:
        file_path = os.path.join(workflows_dir, workflow_file)
        if not os.path.exists(file_path):
            print(f"❌ 文件不存在: {file_path}")
            return False
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                yaml.safe_load(f)
            print(f"✅ {workflow_file} 语法正确")
        except yaml.YAMLError as e:
            print(f"❌ {workflow_file} 语法错误: {e}")
            return False
    
    return True

def test_workflow_structure():
    """测试工作流文件的结构"""
    print("\n🔍 检查工作流文件结构...")
    
    # 测试 build.yml
    with open(".github/workflows/build.yml", 'r') as f:
        build_config = yaml.safe_load(f)
    
    # 检查触发条件 (YAML中on可能被解析为True)
    trigger_config = build_config.get('on') or build_config.get(True)
    if not trigger_config:
        print("❌ build.yml 缺少触发条件")
        return False
    
    # 检查是否有推送触发条件
    if isinstance(trigger_config, dict):
        if 'push' not in trigger_config and 'workflow_dispatch' not in trigger_config:
            print("❌ build.yml 缺少推送或手动触发条件")
            return False
    
    # 检查作业
    if 'jobs' not in build_config:
        print("❌ build.yml 缺少作业定义")
        return False
    
    expected_jobs = ['build-windows', 'build-macos', 'build-linux']
    for job in expected_jobs:
        if job not in build_config['jobs']:
            print(f"❌ build.yml 缺少作业: {job}")
            return False
    
    print("✅ build.yml 结构正确")
    
    # 测试 release.yml
    with open(".github/workflows/release.yml", 'r') as f:
        release_config = yaml.safe_load(f)
    
    # 检查触发条件 (YAML中on可能被解析为True)
    trigger_config = release_config.get('on') or release_config.get(True)
    if not trigger_config:
        print("❌ release.yml 缺少触发条件")
        return False
    
    # 检查作业
    if 'jobs' not in release_config:
        print("❌ release.yml 缺少作业定义")
        return False
    
    expected_jobs = ['prepare-release', 'build-windows', 'build-macos', 'build-linux', 'create-release']
    for job in expected_jobs:
        if job not in release_config['jobs']:
            print(f"❌ release.yml 缺少作业: {job}")
            return False
    
    print("✅ release.yml 结构正确")
    
    return True

def test_dependencies():
    """测试项目依赖配置"""
    print("\n🔍 检查项目依赖配置...")
    
    # 检查 pyproject.toml
    if not os.path.exists("pyproject.toml"):
        print("❌ 缺少 pyproject.toml 文件")
        return False
    
    with open("pyproject.toml", 'r') as f:
        content = f.read()
        if 'flet' not in content:
            print("❌ pyproject.toml 中缺少 flet 依赖")
            return False
    
    print("✅ pyproject.toml 配置正确")
    
    # 检查版本配置文件
    if not os.path.exists("config/version.json"):
        print("⚠️  缺少 config/version.json 文件（可选）")
    else:
        print("✅ config/version.json 存在")
    
    return True

def main():
    """主函数"""
    print("🚀 开始测试 StreamCap GitHub Actions 工作流配置\n")
    
    # 切换到项目根目录
    if os.path.basename(os.getcwd()) != "Stream-Cap":
        if os.path.exists("Stream-Cap"):
            os.chdir("Stream-Cap")
        else:
            print("❌ 请在 Stream-Cap 项目目录中运行此脚本")
            sys.exit(1)
    
    tests = [
        test_workflow_syntax,
        test_workflow_structure,
        test_dependencies
    ]
    
    all_passed = True
    for test in tests:
        if not test():
            all_passed = False
    
    print("\n" + "="*50)
    if all_passed:
        print("🎉 所有测试通过！工作流配置正确。")
        print("\n📋 使用说明:")
        print("1. 推送代码到 main/develop 分支会自动触发构建")
        print("2. 创建 v* 标签会自动触发发布流程")
        print("3. 可以在 GitHub Actions 页面手动触发工作流")
    else:
        print("❌ 部分测试失败，请检查配置。")
        sys.exit(1)

if __name__ == "__main__":
    main()