# -*- mode: python ; coding: utf-8 -*-
import os
import sys
import shutil
from pathlib import Path

# 图标路径
icon_path = os.path.join('assets', 'icon.ico')

# 要包含的文件夹列表
folders_to_include = ['assets', 'config', 'downloads', 'locales', 'logs']

# 确保文件夹存在
for folder in folders_to_include:
    if not os.path.exists(folder):
        os.makedirs(folder)
        print(f"创建文件夹: {folder}")

# 文件夹将通过build.bat脚本复制
print("\n以下文件夹将通过build.bat脚本复制到StreamCap目录:")
for folder in folders_to_include:
    print(f"  {folder}/")

# 检查图标文件是否存在
if os.path.exists(icon_path):
    print(f"使用图标: {icon_path}")
else:
    print(f"警告: 图标文件不存在: {icon_path}")
    icon_path = None

# 替换日志处理模块
logger_fix_path = os.path.join('app', 'utils', 'logger_fix.py')
logger_path = os.path.join('app', 'utils', 'logger.py')
if os.path.exists(logger_fix_path):
    # 备份原始logger.py
    if os.path.exists(logger_path):
        backup_path = logger_path + '.bak'
        if not os.path.exists(backup_path):
            shutil.copy2(logger_path, backup_path)
            print(f"已备份原始日志模块到: {backup_path}")
    
    # 复制修复版本
    shutil.copy2(logger_fix_path, logger_path)
    print(f"已应用日志模块修复")
    print(f"GUI模式下，内存清理日志将写入到 logs/memory_clean.log 文件")

# 检查Python版本
if sys.version_info < (3, 10):
    print(f"警告: 当前Python版本为 {sys.version}，但项目要求 Python 3.10 或更高版本")
    print("请使用Python 3.10或更高版本运行此脚本")
    # 不终止，但给出警告

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],  # 不在这里添加文件夹，将通过build.bat复制
    hiddenimports=[
        'streamget',  # 添加streamget模块依赖
        'psutil',     # 添加psutil模块依赖
        'tzdata',     # 添加tzdata模块依赖
        'flet',
        'flet_core',
        'httpx',
        'screeninfo',
        'aiofiles',
        'python_dotenv',
        'cachetools',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='StreamCap',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # GUI模式，不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,  # 添加图标
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='StreamCap',
) 