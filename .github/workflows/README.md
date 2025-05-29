# GitHub Actions 工作流说明

本项目包含两个主要的GitHub Actions工作流文件：

## 1. build.yml - 自动构建工作流

### 触发条件
- 推送到 `main` 或 `develop` 分支
- 向 `main` 分支提交Pull Request
- 手动触发 (workflow_dispatch)

### 功能
- 自动构建Windows、macOS和Linux平台的安装包
- 使用Poetry管理依赖
- 构建产物保存为artifacts，保留30天

### 构建平台
- **Windows**: 生成Windows可执行文件和安装包
- **macOS**: 生成macOS应用程序包
- **Linux**: 生成Linux可执行文件

## 2. release.yml - 自动发布工作流

### 触发条件
- 推送带有 `v*` 格式的标签 (如: v1.0.2)
- 手动触发，需要输入版本号

### 功能
1. **版本准备**: 
   - 自动更新 `pyproject.toml` 中的版本号
   - 更新 `config/version.json` 中的版本信息
   - 提交版本更新到仓库

2. **多平台构建**:
   - 并行构建Windows、macOS、Linux安装包
   - 创建压缩包便于分发

3. **自动发布**:
   - 创建GitHub Release
   - 上传所有平台的安装包
   - 生成中英文发布说明

### 发布包命名
- Windows: `StreamCap-Windows-x64.zip`
- macOS: `StreamCap-macOS-x64.zip`
- Linux: `StreamCap-Linux-x64.tar.gz`

## 使用方法

### 自动构建
每次向主分支推送代码时，会自动触发构建流程。

### 发布新版本
有两种方式发布新版本：

#### 方法1: 创建标签 (推荐)
```bash
git tag v1.0.2
git push origin v1.0.2
```

#### 方法2: 手动触发
1. 进入GitHub仓库的Actions页面
2. 选择"Release"工作流
3. 点击"Run workflow"
4. 输入版本号 (如: v1.0.2)
5. 点击"Run workflow"

## 注意事项

1. **版本号格式**: 必须以 `v` 开头，如 `v1.0.2`
2. **权限要求**: 需要仓库的写权限来创建release和推送版本更新
3. **依赖管理**: 使用Poetry管理Python依赖，确保pyproject.toml配置正确
4. **构建时间**: 多平台构建可能需要10-20分钟完成

## 故障排除

如果构建失败，请检查：
1. pyproject.toml中的依赖配置是否正确
2. Python版本兼容性 (当前使用Python 3.11)
3. Flet框架版本是否支持目标平台
4. 系统依赖是否正确安装 (特别是Linux平台的GTK依赖)