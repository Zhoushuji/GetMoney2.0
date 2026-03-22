# B2B 智能客户开发系统

基于 FastAPI + Celery + PostgreSQL + React + Vite 的全栈 SaaS 脚手架，覆盖：

- 潜在客户发现（Lead Discovery）
- 核心联系人挖掘（Contact Intelligence）
- 客户触达与商业拓展（Outreach & BD，预留）

## 快速开始

```bash
cp .env.example .env
./start.sh
```

## 目录结构

- `backend/`：FastAPI、Celery、SQLAlchemy、Alembic、服务层
- `frontend/`：React 18 + TypeScript + Vite + Zustand + TanStack Query
- `nginx/`：生产反向代理配置
- `docker-compose.yml`：本地开发编排
- `docker-compose.prod.yml`：生产部署编排示例

## 主要能力

- 异步 lead 搜索任务创建、轮询、结果读取与导出
- 联系人 enrichment 任务 API 与表格扩展列
- 代理池、robots 合规、限速器、熔断器基础实现
- stabila 风格的工业化前端首页与三模块布局
