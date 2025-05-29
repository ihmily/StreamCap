# 🚀 StreamCap 自动化工作流指南

本指南介绍如何使用 StreamCap 项目的自动化构建和发布系统。

## 📋 工作流概述

### 🔄 自动化流程
```
代码提交 → 自动构建 → 版本检测 → 自动发布
```

1. **代码更新** → 触发构建工作流
2. **构建成功** → 检查是否有版本更新
3. **版本更新** → 自动触发发布工作流
4. **创建发布** → 生成安装包和发布说明

## 🛠️ 使用方法

### 方法一：自动发布（推荐）

1. **更新版本号**
   ```bash
   # 编辑 pyproject.toml
   [project]
   version = "1.0.2"  # 更新版本号
   ```

2. **添加更新说明**
   ```bash
   # 编辑 config/version.json
   {
     "version_updates": [
       {
         "version": "1.0.2",
         "updates": {
           "en": ["新功能描述"],
           "zh_CN": ["新功能描述"]
         }
       }
     ]
   }
   ```

3. **提交代码**
   ```bash
   git add .
   git commit -m "bump version to 1.0.2"  # 包含版本关键词
   git push origin main
   ```

4. **等待自动发布** ✨
   - 构建工作流自动运行
   - 检测到版本更新后自动触发发布
   - 生成 Windows 和 macOS 安装包

### 方法二：手动发布

#### 使用 Git 标签
```bash
git tag v1.0.2
git push origin v1.0.2
```

#### 使用 GitHub Actions 界面
1. 进入 **Actions** → **Release**
2. 点击 **Run workflow**
3. 输入版本号（如：`v1.0.2`）
4. 点击 **Run workflow**

### 方法三：强制构建
如果需要重新构建而不修改代码：
1. 进入 **Actions** → **Build Application**
2. 点击 **Run workflow**
3. 勾选 **Force build** 选项
4. 点击 **Run workflow**

## 📝 版本管理最佳实践

### 版本号规范
- 使用语义化版本：`主版本.次版本.修订版本`
- 示例：`1.0.0` → `1.0.1` → `1.1.0` → `2.0.0`

### 提交信息规范
自动发布会检测以下关键词：
- `bump version to X.X.X`
- `release vX.X.X`
- `version X.X.X`
- 包含 "release" 或 "version" 的提交

### 更新说明编写
```json
{
  "version": "1.0.2",
  "updates": {
    "en": [
      "Added new recording format support",
      "Fixed memory leak issue",
      "Improved UI responsiveness"
    ],
    "zh_CN": [
      "添加新的录制格式支持",
      "修复内存泄漏问题", 
      "提升界面响应速度"
    ]
  }
}
```

## 🎯 发布类型

### 正式发布
```bash
git commit -m "release v1.0.2: stable release"
```

### 预发布版本
1. 使用 GitHub Actions 界面
2. 勾选 **Mark as pre-release**
3. 版本号可以使用：`v1.0.2-beta.1`

### 草稿发布
1. 使用 GitHub Actions 界面
2. 勾选 **Create as draft release**
3. 发布后需要手动发布

## 📦 构建产物

### Windows
- **StreamCap-{version}-Setup.exe** - NSIS 安装程序
- **StreamCap-Windows-{version}.zip** - 便携版

### macOS
- **StreamCap-{version}.dmg** - DMG 安装程序
- **StreamCap-macOS-{version}.zip** - 便携版

## 🔍 监控和调试

### 查看构建状态
1. 进入 **Actions** 标签页
2. 查看最新的工作流运行状态
3. 点击具体运行查看详细日志

### 常见问题

#### 构建失败
- 检查 Python/Node.js 版本兼容性
- 验证依赖文件是否完整
- 查看构建日志中的具体错误

#### 自动发布未触发
- 确认提交信息包含版本关键词
- 检查版本号是否已存在对应标签
- 验证构建工作流是否成功完成

#### 发布失败
- 确认版本格式正确（vX.X.X）
- 检查 config/version.json 中是否有对应版本的更新说明
- 验证 GitHub token 权限

## 📊 工作流状态

### 构建工作流
- ✅ 智能变更检测
- ✅ 跨平台构建
- ✅ 依赖缓存
- ✅ 构建验证

### 发布工作流
- ✅ 版本验证
- ✅ 专业安装程序
- ✅ 多语言发布说明
- ✅ 自动变更日志

### 自动发布工作流
- ✅ 构建状态监控
- ✅ 版本更新检测
- ✅ 重复发布防护
- ✅ 智能提交分析

## 🎉 发布后操作

1. **验证发布**
   - 检查 GitHub Releases 页面
   - 下载并测试安装包
   - 验证发布说明内容

2. **通知用户**
   - 更新项目 README
   - 发布更新公告
   - 通知社区用户

3. **监控反馈**
   - 关注 Issues 中的用户反馈
   - 监控下载统计
   - 收集使用体验

## 🔗 相关链接

- [GitHub Actions 文档](https://docs.github.com/en/actions)
- [工作流详细说明](.github/workflows/README.md)
- [项目主页](https://github.com/ihmily/StreamCap)
- [问题反馈](https://github.com/ihmily/StreamCap/issues)

---

如有疑问，请在项目中创建 Issue 或查看工作流文档。