# B2B 智能客户开发系统

面向 B2B 外贸业务员的全栈 SaaS 脚手架，覆盖：

- 潜在客户发现（Lead Discovery）
- 核心联系人挖掘（Contact Intelligence）
- 客户触达与商业拓展（Outreach & BD，预留架构）

## 技术栈

- 后端：FastAPI、Celery、Redis、PostgreSQL、SQLAlchemy 2.x、Alembic
- 前端：React 18、TypeScript、Vite、Zustand、TanStack Query
- 部署：systemd、Nginx、本机 PostgreSQL / Redis、`backend/.venv`

## 快速开始

```bash
cp .env.example .env
bash start.sh
```

## 原生部署目录

- `deploy/systemd/`：4 个 systemd unit 模板，由 `start.sh` 渲染到 `/etc/systemd/system/`
- `deploy/nginx/leadgen.conf`：Nginx server 块模板，渲染后写入站点配置
- `deploy/postgres/init.sql`：初始化 `uuid-ossp` / `pg_trgm` 扩展
- `backend/.venv/`：后端虚拟环境（运行时创建，不提交）
- `frontend/dist/`：前端静态构建产物（构建中间产物，不直接由 Nginx 指向）
- `/var/www/leadgen/current`：前端静态站点发布目录，`start.sh` 会将 `frontend/dist/` 同步到这里供 Nginx 服务
- `logs/`：API / worker / beat / flower / nginx 日志目录

## 关键能力

- lead 搜索、任务状态轮询、联系人 enrichment 与导出接口
- 代理池、robots 合规、限速器、熔断器等基础设施骨架
- 三模块前端导航与 Lead Discovery 工作台
- systemd + Nginx + PostgreSQL + Redis 的原生部署脚本与模板
