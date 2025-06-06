# StreamCap GitHub Actions 工作流

本项目使用以下GitHub Actions工作流自动化开发和发布流程：

## CI Pipeline (ci.yml)

持续集成工作流，在代码推送到main分支或创建PR时自动运行：

- **代码检查**：使用ruff检查Python代码质量
- **自动测试**：运行项目的单元测试
- **构建验证**：验证Docker镜像构建是否成功

触发条件：
- 推送到main分支
- 创建或更新PR
- 手动触发

## 版本更新 (version-bump.yml)

自动更新项目版本号并创建对应的Git标签：

- **版本类型**：支持patch（补丁）、minor（次要）和major（主要）版本更新
- **自动提交**：更新pyproject.toml文件中的版本号并提交
- **创建标签**：自动创建并推送新版本的Git标签

使用方法：
1. 在GitHub仓库页面，进入"Actions"标签
2. 选择"Version Bump"工作流
3. 点击"Run workflow"
4. 选择版本更新类型（patch/minor/major）
5. 点击"Run workflow"开始执行

## 发布工作流 (release.yml)

当推送新的版本标签（格式为v*）时自动创建发布版本：

- **自动生成更新日志**：基于Git提交记录生成更新日志
- **创建GitHub Release**：自动创建新的发布版本
- **构建Windows应用**：构建Windows可执行文件并打包为ZIP
- **构建macOS应用**：构建macOS应用并打包为DMG
- **构建Docker镜像**：构建并推送Docker镜像到Docker Hub

触发条件：
- 推送以"v"开头的标签（如v1.0.0）

## 完整发布流程

1. 使用"Version Bump"工作流更新版本号并创建标签
2. 标签推送后自动触发"Release"工作流
3. Release工作流自动构建各平台应用并发布到GitHub Releases

## 注意事项

- Docker镜像发布需要在GitHub仓库设置中配置以下Secrets：
  - `DOCKER_HUB_USERNAME`：Docker Hub用户名
  - `DOCKER_HUB_TOKEN`：Docker Hub访问令牌 