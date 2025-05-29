# GitHub Actions 工作流说明 / GitHub Actions Workflows Documentation

本项目包含两个主要的 GitHub Actions 工作流，用于自动化构建和发布流程。

This project includes two main GitHub Actions workflows for automated build and release processes.

## 工作流文件 / Workflow Files

### 1. `.github/workflows/build.yml` - 自动构建工作流 / Automatic Build Workflow

**触发条件 / Triggers:**
- 推送到 `main` 分支 / Push to `main` branch
- 推送到 `develop` 分支 / Push to `develop` branch
- Pull Request 到 `main` 分支 / Pull Request to `main` branch
- 手动触发 / Manual trigger

**功能 / Features:**
- 🏗️ 多平台构建 (Windows, macOS) / Multi-platform builds (Windows, macOS)
- 📦 自动生成安装包 / Automatic installer generation
- 🧪 运行测试 / Run tests
- 📤 上传构建产物 / Upload build artifacts
- ⚡ 缓存依赖项以加速构建 / Cache dependencies for faster builds

**构建产物 / Build Artifacts:**
- Windows: `.exe` 安装程序和便携版 `.zip`
- macOS: `.dmg` 安装程序

### 2. `.github/workflows/release.yml` - 自动发布工作流 / Automatic Release Workflow

**触发条件 / Triggers:**
- 推送标签 (格式: `v*`) / Push tags (format: `v*`)
- 手动触发 (可选择创建标签) / Manual trigger (with optional tag creation)

**功能 / Features:**
- 🏷️ 自动创建标签 (手动触发时) / Automatic tag creation (when manually triggered)
- 🏗️ 构建发布版本 / Build release versions
- 📋 从配置文件读取更新日志 / Read changelog from config file
- 🚀 创建 GitHub Release / Create GitHub Release
- 📦 上传安装包到 Release / Upload installers to Release
- 🌐 支持中英文发布说明 / Support bilingual release notes

## 使用方法 / Usage

### 自动构建 / Automatic Build

每次向 `main` 或 `develop` 分支推送代码时，构建工作流会自动运行：

The build workflow runs automatically when code is pushed to `main` or `develop` branches:

```bash
git push origin main
```

### 发布新版本 / Release New Version

#### 方法 1: 推送标签 / Method 1: Push Tag

```bash
# 创建并推送标签
git tag v1.0.2
git push origin v1.0.2
```

#### 方法 2: 手动触发 / Method 2: Manual Trigger

1. 访问 GitHub Actions 页面 / Go to GitHub Actions page
2. 选择 "Release" 工作流 / Select "Release" workflow
3. 点击 "Run workflow" / Click "Run workflow"
4. 输入版本号 (如 `v1.0.2`) / Enter version number (e.g., `v1.0.2`)
5. 选择是否创建标签 / Choose whether to create tag

## 版本配置 / Version Configuration

更新日志配置在 `config/version.json` 文件中：

Changelog configuration is in `config/version.json` file:

```json
{
  "current_version": "1.0.1",
  "version_updates": [
    {
      "version": "1.0.1",
      "updates": {
        "en": [
          "Fixed streaming stability issues",
          "Improved user interface",
          "Added new capture formats"
        ],
        "zh_CN": [
          "修复了流媒体稳定性问题",
          "改进了用户界面",
          "添加了新的捕获格式"
        ]
      }
    }
  ]
}
```

## 构建要求 / Build Requirements

### 系统要求 / System Requirements
- Python 3.10+
- Poetry (包管理器 / Package manager)
- Flet (UI 框架 / UI framework)

### Windows 特定要求 / Windows Specific Requirements
- NSIS (可选，用于创建安装程序 / Optional, for installer creation)

### macOS 特定要求 / macOS Specific Requirements
- Xcode Command Line Tools
- hdiutil (系统自带 / Built-in)

## 故障排除 / Troubleshooting

### 常见问题 / Common Issues

1. **构建失败 / Build Failure**
   - 检查 Python 版本兼容性 / Check Python version compatibility
   - 确认依赖项正确安装 / Verify dependencies are correctly installed

2. **发布失败 / Release Failure**
   - 确认标签格式正确 (`v*`) / Verify tag format is correct (`v*`)
   - 检查 GitHub token 权限 / Check GitHub token permissions

3. **安装包问题 / Installer Issues**
   - Windows: 确认 NSIS 可用 / Verify NSIS is available
   - macOS: 检查代码签名设置 / Check code signing settings

### 日志查看 / View Logs

在 GitHub Actions 页面查看详细的构建和发布日志：

View detailed build and release logs in GitHub Actions page:

1. 访问仓库的 Actions 标签 / Go to repository's Actions tab
2. 选择相应的工作流运行 / Select the relevant workflow run
3. 查看各个步骤的日志 / View logs for each step

## 自定义配置 / Custom Configuration

### 修改构建平台 / Modify Build Platforms

在 `.github/workflows/build.yml` 和 `.github/workflows/release.yml` 中修改 `matrix` 配置：

Modify the `matrix` configuration in `.github/workflows/build.yml` and `.github/workflows/release.yml`:

```yaml
strategy:
  matrix:
    include:
      - os: windows-latest
        platform: windows
      - os: macos-latest
        platform: macos
      # 添加更多平台 / Add more platforms
      - os: ubuntu-latest
        platform: linux
```

### 修改触发条件 / Modify Triggers

在工作流文件的 `on` 部分修改触发条件：

Modify triggers in the `on` section of workflow files:

```yaml
on:
  push:
    branches: [ main, develop, feature/* ]
  pull_request:
    branches: [ main ]
```

## 安全注意事项 / Security Considerations

- 🔒 使用 GitHub Secrets 存储敏感信息 / Use GitHub Secrets for sensitive information
- 🛡️ 限制工作流权限 / Limit workflow permissions
- 🔍 定期审查工作流配置 / Regularly review workflow configurations

## 贡献 / Contributing

如需修改工作流配置，请：

To modify workflow configurations:

1. Fork 仓库 / Fork the repository
2. 创建功能分支 / Create a feature branch
3. 修改工作流文件 / Modify workflow files
4. 测试更改 / Test changes
5. 提交 Pull Request / Submit Pull Request

---

📝 **注意**: 工作流配置会影响整个项目的 CI/CD 流程，请谨慎修改。

📝 **Note**: Workflow configurations affect the entire project's CI/CD process, please modify carefully.