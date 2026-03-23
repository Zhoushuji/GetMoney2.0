.PHONY: up down status migrate shell-db logs restart test build-frontend install-backend help

up: ## 执行原生部署脚本
	bash start.sh

down: ## 停止 leadgen 应用服务
	bash start.sh --stop

status: ## 查看 leadgen 服务状态
	bash start.sh --status

migrate: ## 执行数据库迁移
	cd backend && . .venv/bin/activate && alembic upgrade head

shell-db: ## 进入 PostgreSQL
	sudo -u postgres psql -d $$(grep '^POSTGRES_DB=' .env | cut -d= -f2)

logs: ## 查看应用日志
	tail -f logs/api.log logs/worker.log logs/beat.log logs/flower.log

restart: ## 重启应用服务
	sudo systemctl restart leadgen-api leadgen-worker leadgen-beat leadgen-flower

test: ## 运行后端测试
	cd backend && . .venv/bin/activate && pytest tests/ -v --tb=short

build-frontend: ## 构建前端静态资源
	cd frontend && npm install && npm run build

install-backend: ## 安装后端依赖到虚拟环境
	cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

help: ## 显示帮助
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
