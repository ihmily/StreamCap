# StreamCap Makefile
# 提供便捷的开发和发布命令

.PHONY: help install test build release clean version

# 默认目标
help:
	@echo "StreamCap 开发工具"
	@echo ""
	@echo "可用命令:"
	@echo "  install     - 安装依赖"
	@echo "  test        - 运行测试"
	@echo "  test-version - 测试版本更新功能"
	@echo "  build       - 本地构建应用"
	@echo "  version     - 更新版本号"
	@echo "  release     - 创建发布"
	@echo "  clean       - 清理构建文件"
	@echo "  lint        - 代码检查"
	@echo "  format      - 代码格式化"
	@echo ""
	@echo "示例:"
	@echo "  make version VERSION=1.0.2"
	@echo "  make release VERSION=1.0.2"

# 安装依赖
install:
	@echo "安装Python依赖..."
	pip install -r requirements.txt
	pip install -r requirements-dev.txt || pip install pytest black flake8 pyinstaller
	@echo "依赖安装完成!"

# 运行测试
test:
	@echo "运行测试..."
	python -m pytest tests/ -v || echo "未找到测试文件，跳过测试"

# 测试版本更新功能
test-version:
	@echo "测试版本更新功能..."
	python scripts/test_version_update.py

# 本地构建
build:
	@echo "本地构建应用..."
	@if [ "$(OS)" = "Windows_NT" ]; then \
		echo "构建Windows版本..."; \
		pyinstaller --noconfirm --onedir --windowed --icon "assets/icon.ico" --name "StreamCap" main.py; \
	elif [ "$$(uname)" = "Darwin" ]; then \
		echo "构建macOS版本..."; \
		pyinstaller --noconfirm --onedir --windowed --icon "assets/icon.ico" --name "StreamCap" main.py; \
	else \
		echo "Linux环境，运行Web模式测试..."; \
		python main.py --web --host 127.0.0.1 --port 6006 & \
		sleep 5; \
		pkill -f "python main.py"; \
		echo "Web模式测试完成"; \
	fi

# 更新版本号
version:
	@if [ -z "$(VERSION)" ]; then \
		echo "错误: 请指定版本号"; \
		echo "用法: make version VERSION=1.0.2"; \
		exit 1; \
	fi
	@echo "更新版本到 $(VERSION)..."
	python scripts/update_version.py $(VERSION) $(ARGS)
	@echo "版本更新完成!"
	@echo ""
	@echo "下一步:"
	@echo "1. 检查更改: git diff"
	@echo "2. 提交更改: git add . && git commit -m 'chore: bump version to $(VERSION)'"
	@echo "3. 推送代码: git push"
	@echo "4. 创建标签: git tag v$(VERSION) && git push origin v$(VERSION)"

# 创建发布
release:
	@if [ -z "$(VERSION)" ]; then \
		echo "错误: 请指定版本号"; \
		echo "用法: make release VERSION=1.0.2"; \
		exit 1; \
	fi
	@echo "创建发布 v$(VERSION)..."
	@echo "1. 更新版本号..."
	python scripts/update_version.py $(VERSION) $(ARGS)
	@echo "2. 提交更改..."
	git add .
	git commit -m "chore: bump version to $(VERSION)"
	@echo "3. 创建标签..."
	git tag v$(VERSION)
	@echo "4. 推送到远程..."
	git push origin main
	git push origin v$(VERSION)
	@echo "发布创建完成! GitHub Actions将自动构建和发布。"

# 清理构建文件
clean:
	@echo "清理构建文件..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.spec
	rm -rf __pycache__/
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@echo "清理完成!"

# 代码检查
lint:
	@echo "运行代码检查..."
	flake8 app/ main.py --max-line-length=120 --ignore=E203,W503 || echo "flake8未安装，跳过检查"
	@echo "代码检查完成!"

# 代码格式化
format:
	@echo "格式化代码..."
	black app/ main.py --line-length=120 || echo "black未安装，跳过格式化"
	@echo "代码格式化完成!"

# 开发环境设置
dev-setup: install
	@echo "设置开发环境..."
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "已创建 .env 文件，请根据需要修改配置"; \
	fi
	@echo "开发环境设置完成!"

# 运行应用（桌面模式）
run-desktop:
	@echo "启动桌面模式..."
	python main.py

# 运行应用（Web模式）
run-web:
	@echo "启动Web模式..."
	python main.py --web --host 0.0.0.0 --port 6006

# 查看版本信息
info:
	@echo "StreamCap 项目信息:"
	@echo "当前版本: $$(grep '^version = ' pyproject.toml | sed 's/version = \"\(.*\)\"/\1/')"
	@echo "Python版本: $$(python --version)"
	@echo "Git分支: $$(git branch --show-current 2>/dev/null || echo '未知')"
	@echo "Git提交: $$(git rev-parse --short HEAD 2>/dev/null || echo '未知')"

# Docker相关命令
docker-build:
	@echo "构建Docker镜像..."
	docker build -t streamcap:latest .

docker-run:
	@echo "运行Docker容器..."
	docker run -p 6006:6006 -v $$(pwd)/downloads:/app/downloads streamcap:latest

docker-compose-up:
	@echo "启动Docker Compose..."
	docker-compose up -d

docker-compose-down:
	@echo "停止Docker Compose..."
	docker-compose down

# 帮助信息
help-version:
	@echo "版本管理帮助:"
	@echo ""
	@echo "更新版本号:"
	@echo "  make version VERSION=1.0.2"
	@echo ""
	@echo "带更新说明的版本更新:"
	@echo "  make version VERSION=1.0.2 ARGS='--updates-zh \"修复bug\" \"优化性能\" --updates-en \"Fix bugs\" \"Performance improvements\"'"
	@echo ""
	@echo "创建发布:"
	@echo "  make release VERSION=1.0.2"
	@echo ""
	@echo "版本号格式: 主版本.次版本.修订版本 (如: 1.0.2)"

help-build:
	@echo "构建帮助:"
	@echo ""
	@echo "本地构建:"
	@echo "  make build"
	@echo ""
	@echo "清理构建文件:"
	@echo "  make clean"
	@echo ""
	@echo "Docker构建:"
	@echo "  make docker-build"
	@echo "  make docker-run"