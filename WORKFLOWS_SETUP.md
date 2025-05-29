# StreamCap GitHub Actions 工作流配置完成

## 📋 已创建的文件

### 1. 构建工作流 - `.github/workflows/build.yml`
- **功能**: 自动构建多平台安装包
- **触发条件**: 
  - 推送到 `main` 或 `develop` 分支
  - 向 `main` 分支提交 Pull Request
  - 手动触发
- **构建平台**: Windows、macOS、Linux
- **输出**: 各平台的可执行文件和安装包

### 2. 发布工作流 - `.github/workflows/release.yml`
- **功能**: 自动发布新版本
- **触发条件**:
  - 推送 `v*` 格式的标签 (如: `v1.0.2`)
  - 手动触发 (需要输入版本号)
- **功能流程**:
  1. 准备发布信息
  2. 并行构建所有平台安装包
  3. 创建 GitHub Release
  4. 上传安装包到 Release

### 3. 说明文档
- `.github/workflows/README.md` - 详细使用说明
- `test_workflows.py` - 工作流配置测试脚本
- `WORKFLOWS_SETUP.md` - 本文档

## 🚀 使用方法

### 自动构建
每次向 `main` 或 `develop` 分支推送代码时，会自动触发构建流程：

```bash
git add .
git commit -m "Update features"
git push origin main
```

### 发布新版本

#### 方法1: 创建标签 (推荐)
```bash
# 创建并推送标签
git tag v1.0.2
git push origin v1.0.2
```

#### 方法2: 手动触发
1. 进入 GitHub 仓库的 Actions 页面
2. 选择 "Release" 工作流
3. 点击 "Run workflow"
4. 输入版本号 (如: `v1.0.2`)
5. 点击 "Run workflow"

## 📦 构建产物

### 构建工作流产物
- 保存为 GitHub Actions Artifacts
- 保留时间: 30天
- 包含: Windows、macOS、Linux 可执行文件

### 发布工作流产物
- 自动创建 GitHub Release
- 包含安装包:
  - `StreamCap-Windows-x64.zip`
  - `StreamCap-macOS-x64.zip`
  - `StreamCap-Linux-x64.tar.gz`

## ⚙️ 技术配置

### 依赖管理
- **Python**: 3.11
- **包管理器**: Poetry
- **UI框架**: Flet
- **构建工具**: `flet build`

### 系统依赖
- **Windows**: 无额外依赖
- **macOS**: 无额外依赖
- **Linux**: GTK3, GStreamer

### GitHub Actions
- **checkout@v4**: 代码检出
- **setup-python@v4**: Python 环境设置
- **snok/install-poetry@v1**: Poetry 安装
- **upload-artifact@v4**: 构建产物上传
- **download-artifact@v4**: 构建产物下载
- **softprops/action-gh-release@v1**: GitHub Release 创建

## 🔧 故障排除

### 常见问题

1. **构建失败**
   - 检查 `pyproject.toml` 依赖配置
   - 确认 Python 版本兼容性
   - 查看 Actions 日志获取详细错误信息

2. **发布失败**
   - 确认有仓库写权限
   - 检查标签格式是否正确 (`v*`)
   - 确认 `GITHUB_TOKEN` 权限

3. **Linux 构建失败**
   - 通常是系统依赖问题
   - 检查 GTK 和 GStreamer 安装

### 调试方法

1. **本地测试**:
   ```bash
   python3 test_workflows.py
   ```

2. **查看工作流日志**:
   - 进入 GitHub Actions 页面
   - 点击失败的工作流
   - 查看详细日志

3. **手动构建测试**:
   ```bash
   poetry install
   poetry run flet build windows  # 或 macos/linux
   ```

## 📝 版本管理

### 版本号格式
- 使用语义化版本: `v主版本.次版本.修订版本`
- 示例: `v1.0.0`, `v1.2.3`, `v2.0.0-beta.1`

### 发布说明
- 自动生成中英文发布说明
- 包含安装指南
- 可在 GitHub Release 页面手动编辑

## 🎯 下一步

1. **测试工作流**: 创建一个测试标签验证发布流程
2. **自定义配置**: 根据需要调整构建参数
3. **添加测试**: 考虑添加自动化测试步骤
4. **优化性能**: 使用缓存加速构建过程

## 📞 支持

如果遇到问题，请：
1. 查看 GitHub Actions 日志
2. 运行 `test_workflows.py` 检查配置
3. 参考 `.github/workflows/README.md` 详细说明
4. 在项目 Issues 中报告问题

---

✅ **工作流配置已完成，可以开始使用自动化构建和发布功能！**