# GitHub Actions 工作流文档

本文档描述了StreamCap项目的自动化构建和发布工作流。

## 📋 工作流概览

| 工作流 | 文件 | 触发条件 | 功能 |
|--------|------|----------|------|
| Build Application | `build.yml` | 推送/PR/手动 | 构建多平台安装包 |
| Release Application | `release.yml` | 标签推送/手动 | 创建GitHub Release |
| Auto Release | `auto-release.yml` | 版本文件变更 | 自动发布新版本 |

## 🔧 工作流详情

### 1. Build Application (`build.yml`)

**目的**: 为Windows、macOS和Linux平台构建应用程序

**触发条件**:
- 推送到 `main`, `master`, `develop` 分支
- 针对 `main`, `master` 分支的Pull Request
- 手动触发

**构建矩阵**:
- **Windows**: 使用PyInstaller生成.exe文件，打包为.zip
- **macOS**: 生成.app包，创建.dmg安装文件
- **Linux**: 打包源代码为.tar.gz（Web模式）

**产物**:
- `StreamCap-Windows.zip`
- `StreamCap-macOS.dmg`
- `StreamCap-Linux.tar.gz`

**依赖**:
- Python 3.12
- FFmpeg
- PyInstaller
- dmgbuild (macOS)

### 2. Release Application (`release.yml`)

**目的**: 创建GitHub Release并上传构建产物

**触发条件**:
- 推送以 `v` 开头的标签 (如: `v1.0.1`)
- 手动触发（可指定版本号）

**流程**:
1. 更新版本文件
2. 调用构建工作流
3. 生成发布说明
4. 创建GitHub Release
5. 上传所有平台的安装包

**输入参数** (手动触发):
- `version`: 发布版本号
- `prerelease`: 是否为预发布版本

### 3. Auto Release (`auto-release.yml`)

**目的**: 检测版本变更并自动触发发布

**触发条件**:
- 推送到主分支且修改了版本文件
- 手动触发

**逻辑**:
1. 检测 `pyproject.toml` 或 `config/version.json` 的版本变更
2. 如果版本号发生变化，创建对应的Git标签
3. 触发Release工作流

## 🚀 使用指南

### 方式一：自动发布（推荐）

1. **更新版本**:
   ```bash
   python scripts/update_version.py 1.0.2 \
     --updates-zh "修复录制问题" "优化界面" \
     --updates-en "Fix recording issues" "UI improvements"
   ```

2. **提交并推送**:
   ```bash
   git add .
   git commit -m "feat: release v1.0.2"
   git push
   ```

3. **自动流程**:
   - 系统检测到版本变更
   - 自动创建 `v1.0.2` 标签
   - 触发构建和发布流程

### 方式二：手动标签发布

1. **创建标签**:
   ```bash
   git tag v1.0.2
   git push origin v1.0.2
   ```

2. **自动触发**: Release工作流自动运行

### 方式三：GitHub界面手动发布

1. 进入 Actions → Release Application
2. 点击 "Run workflow"
3. 输入版本号和选项
4. 点击 "Run workflow"

## 📁 文件结构

```
.github/
├── workflows/
│   ├── build.yml           # 构建工作流
│   ├── release.yml         # 发布工作流
│   ├── auto-release.yml    # 自动发布工作流
│   ├── docker-build.yml    # Docker构建（已存在）
│   ├── python-lint.yml     # 代码检查（已存在）
│   └── test.yml           # 测试工作流（已存在）
├── ISSUE_TEMPLATE/        # Issue模板
├── PULL_REQUEST_TEMPLATE.md
├── dependabot.yml
└── WORKFLOWS.md          # 本文档
```

## 🔍 监控和调试

### 查看工作流状态
1. 进入GitHub仓库
2. 点击 "Actions" 标签
3. 选择对应的工作流查看运行状态

### 常见问题

**构建失败**:
- 检查依赖是否正确安装
- 确认FFmpeg在PATH中
- 查看具体的错误日志

**发布失败**:
- 确认有仓库写权限
- 检查标签格式是否正确
- 验证版本号格式

**自动发布未触发**:
- 确认版本文件确实发生了变更
- 检查提交信息是否包含版本关键词
- 验证分支是否为主分支

### 调试技巧

1. **本地测试构建**:
   ```bash
   # 测试Windows构建
   pip install pyinstaller
   pyinstaller --onedir --windowed main.py
   
   # 测试版本更新
   python scripts/test_version_update.py
   ```

2. **查看工作流日志**:
   - 点击失败的工作流
   - 展开具体的步骤查看详细日志
   - 注意红色的错误信息

3. **手动触发测试**:
   - 使用 `workflow_dispatch` 手动触发
   - 在测试分支上验证工作流

## 📊 性能指标

| 平台 | 构建时间 | 包大小 | 依赖数量 |
|------|----------|--------|----------|
| Windows | ~8-12分钟 | ~150MB | 50+ |
| macOS | ~10-15分钟 | ~120MB | 45+ |
| Linux | ~3-5分钟 | ~50MB | 40+ |

## 🔒 安全考虑

1. **权限控制**:
   - 工作流只在主分支和标签上运行
   - 使用GitHub提供的 `GITHUB_TOKEN`
   - 不暴露敏感信息

2. **代码签名**:
   - Windows: 可配置代码签名证书
   - macOS: 可配置开发者证书
   - 当前版本未启用，可根据需要添加

3. **依赖安全**:
   - 使用固定版本的Actions
   - 定期更新依赖版本
   - 启用Dependabot自动更新

## 🔄 维护和更新

### 定期维护任务

1. **更新Actions版本**:
   ```yaml
   # 从 v3 更新到 v4
   - uses: actions/checkout@v4
   - uses: actions/setup-python@v4
   ```

2. **更新Python版本**:
   ```yaml
   env:
     PYTHON_VERSION: '3.12'  # 更新到最新稳定版
   ```

3. **优化构建缓存**:
   - 定期清理过期缓存
   - 优化缓存键策略

### 扩展功能

1. **添加代码签名**:
   ```yaml
   - name: Sign Windows executable
     if: runner.os == 'Windows'
     run: |
       # 添加代码签名逻辑
   ```

2. **添加自动测试**:
   ```yaml
   - name: Run tests
     run: |
       python -m pytest tests/
   ```

3. **添加通知**:
   ```yaml
   - name: Notify on success
     uses: 8398a7/action-slack@v3
     with:
       status: success
   ```

## 📞 支持

如需帮助或有问题：

1. 查看GitHub Actions日志
2. 阅读本文档的故障排除部分
3. 在GitHub Issues中报告问题
4. 联系项目维护者

---

*最后更新: 2024年*