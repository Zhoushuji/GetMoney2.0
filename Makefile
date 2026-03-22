.PHONY: up up-fast down reset logs logs-backend logs-worker shell-backend shell-db migrate migrate-new test build status ps help

up: ## 启动系统（安装依赖 + 构建 + 运行）
	bash start.sh

up-fast: ## 快速启动（跳过镜像重建）
	bash start.sh --no-build

down: ## 停止所有服务
	bash start.sh --stop

reset: ## 重置所有数据
	bash start.sh --reset

logs: ## 实时查看所有日志
	docker compose logs -f

logs-backend: ## 查看后端日志
	docker compose logs -f backend

logs-worker: ## 查看 Worker 日志
	docker compose logs -f worker

shell-backend: ## 进入后端容器 Shell
	docker compose exec backend bash

shell-db: ## 进入 PostgreSQL 交互终端
	docker compose exec postgres psql -U postgres -d leadgen

migrate: ## 手动执行数据库迁移
	docker compose exec backend alembic upgrade head

migrate-new: ## 生成新迁移文件（需提供 MSG 变量）
	docker compose exec backend alembic revision --autogenerate -m "$(MSG)"

test: ## 运行后端测试
	docker compose exec backend pytest tests/ -v --tb=short

build: ## 仅重新构建镜像（不启动）
	docker compose build --no-cache

status: ## 查看各服务状态
	docker compose ps

ps: status

help: ## 显示帮助
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
