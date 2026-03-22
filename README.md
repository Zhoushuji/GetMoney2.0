# B2B 智能客户开发系统

面向 B2B 外贸业务员的全栈 SaaS 脚手架，覆盖：

- 潜在客户发现（Lead Discovery）
- 核心联系人挖掘（Contact Intelligence）
- 客户触达与商业拓展（Outreach & BD，预留架构）

## 技术栈

- 后端：FastAPI、Celery、Redis、PostgreSQL、SQLAlchemy 2.x、Alembic
- 前端：React 18、TypeScript、Vite、Zustand、TanStack Query
- 基础设施：Docker Compose、Nginx、start.sh、Makefile

## 快速开始

```bash
cp .env.example .env
bash start.sh
```

## 目录说明

- `backend/`：FastAPI 应用、模型、服务层、Celery、Alembic
- `frontend/`：React UI、页面、组件、样式与静态数据
- `nginx/`：`http` 层与 `server` 层拆分配置
- `scripts/init.sql`：PostgreSQL 初始化脚本
- `.data/`：PostgreSQL / Redis 宿主持久化目录
- `logs/`：运行日志目录

## 关键能力

- 统一的 lead 搜索、任务状态轮询、联系人 enrichment 与导出接口
- 代理池、robots 合规、限速器、熔断器等基础设施骨架
- 三模块前端导航、工业化 UI 风格与 Lead Discovery 搜索工作台
- 一键启动脚本、开发/生产 compose、Nginx 反向代理与 Alembic 迁移
