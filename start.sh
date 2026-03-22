#!/bin/bash
set -e

echo ">>> 检查环境依赖..."
command -v docker >/dev/null 2>&1 || { echo "需要安装 Docker"; exit 1; }
command -v docker-compose >/dev/null 2>&1 || command -v docker >/dev/null 2>&1 || { echo "需要安装 docker compose"; exit 1; }

echo ">>> 加载环境变量..."
[ -f .env ] || cp .env.example .env

echo ">>> 启动服务..."
if command -v docker-compose >/dev/null 2>&1; then
  docker-compose up -d --build
else
  docker compose up -d --build
fi

echo ">>> 等待服务就绪..."
for i in $(seq 1 12); do
  sleep 5
  curl -sf http://localhost:8000/health && break || echo "等待后端启动... ($i/12)"
done

echo ""
echo "============================================"
echo "  系统已启动"
echo "  Web 界面:  http://localhost:3000"
echo "  API 文档:  http://localhost:8000/docs"
echo "  Flower:    http://localhost:5555"
echo "============================================"
