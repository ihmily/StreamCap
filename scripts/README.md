# StreamCap 自动化构建和发布系统

本目录包含了StreamCap项目的自动化构建和发布工具。

## 🚀 工作流概述

### 1. Build Workflow (`build.yml`)
- **触发条件**: 推送到主分支、Pull Request、手动触发
- **功能**: 
  - 构建Windows可执行文件 (.exe + .zip)
  - 构建macOS应用程序 (.dmg)
  - 构建Linux版本 (.tar.gz)
- **产物**: 构建的安装包作为GitHub Artifacts保存

### 2. Release Workflow (`release.yml`)
- **触发条件**: 推送标签 (v*) 或手动触发
- **功能**:
  - 自动更新版本号
  - 调用构建工作流
  - 创建GitHub Release
  - 上传所有平台的安装包
  - 生成发布说明

### 3. Auto Release Workflow (`auto-release.yml`)
- **触发条件**: 版本文件变更时自动触发
- **功能**:
  - 检测版本变更
  - 自动创建标签
  - 触发发布流程

## 📋 使用方法

### 方法一：手动发布 (推荐)

1. **更新版本号**:
   ```bash
   # 使用脚本更新版本
   python scripts/update_version.py 1.0.2 \
     --kernel-version 4.0.6 \
     --updates-zh "修复录制bug" "优化界面" \
     --updates-en "Fix recording bugs" "UI improvements"
   ```

2. **提交更改**:
   ```bash
   git add .
   git commit -m "chore: bump version to 1.0.2"
   git push
   ```

3. **创建标签并发布**:
   ```bash
   git tag v1.0.2
   git push origin v1.0.2
   ```

### 方法二：GitHub界面手动触发

1. 进入GitHub仓库的Actions页面
2. 选择"Release Application"工作流
3. 点击"Run workflow"
4. 输入版本号 (如: v1.0.2)
5. 选择是否为预发布版本
6. 点击"Run workflow"

### 方法三：自动发布

1. 直接修改 `pyproject.toml` 中的版本号
2. 修改 `config/version.json` 中的版本信息
3. 提交并推送到主分支
4. 系统会自动检测版本变更并触发发布

## 📁 文件结构

```
.github/workflows/
├── build.yml           # 构建工作流
├── release.yml         # 发布工作流
└── auto-release.yml    # 自动发布工作流

scripts/
├── update_version.py   # 版本更新脚本
└── README.md          # 本文档
```

## 🔧 版本更新脚本使用

### 基本用法
```bash
python scripts/update_version.py 1.0.2
```

### 完整用法
```bash
python scripts/update_version.py 1.0.2 \
  --kernel-version 4.0.6 \
  --updates-zh "修复录制问题" "优化性能" \
  --updates-en "Fix recording issues" "Performance improvements"
```

### 参数说明
- `version`: 新版本号 (必需)
- `--kernel-version`: 内核版本号 (可选，默认: 4.0.5)
- `--updates-zh`: 中文更新说明 (可选)
- `--updates-en`: 英文更新说明 (可选)

## 🏗️ 构建产物

### Windows
- **文件**: `StreamCap-Windows.zip`
- **内容**: 可执行文件 + 依赖库 + 资源文件
- **安装**: 解压后直接运行 `StreamCap.exe`

### macOS
- **文件**: `StreamCap-macOS.dmg`
- **内容**: macOS应用程序包
- **安装**: 打开DMG文件，拖拽到Applications文件夹

### Linux
- **文件**: `StreamCap-Linux.tar.gz`
- **内容**: 源代码 + 依赖配置
- **运行**: 解压后执行 `python main.py --web`

## 🔍 故障排除

### 构建失败
1. 检查依赖是否正确安装
2. 确认FFmpeg在构建环境中可用
3. 查看构建日志中的错误信息

### 发布失败
1. 确认有足够的GitHub权限
2. 检查版本号格式是否正确
3. 确认所有构建产物都已生成

### 版本检测失败
1. 确认版本文件格式正确
2. 检查提交信息是否包含版本关键词
3. 验证Git历史记录

## 📝 注意事项

1. **版本号格式**: 必须遵循语义化版本规范 (如: 1.0.2)
2. **标签格式**: 必须以 'v' 开头 (如: v1.0.2)
3. **权限要求**: 需要仓库的写权限来创建标签和发布
4. **构建时间**: 完整构建可能需要10-20分钟
5. **存储空间**: 构建产物会占用GitHub Actions存储空间

## 🤝 贡献指南

如需修改工作流配置：

1. Fork仓库
2. 在本地测试工作流
3. 提交Pull Request
4. 等待代码审查

## 📞 支持

如遇到问题，请：

1. 查看GitHub Actions日志
2. 检查本文档的故障排除部分
3. 在GitHub Issues中报告问题