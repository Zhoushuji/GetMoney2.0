#!/usr/bin/env bash
# ============================================================
#  B2B 智能客户开发系统 — 一键安装 & 启动脚本
#  支持: Ubuntu 20.04/22.04/24.04, Debian 11/12, macOS 12+
#  用法: bash start.sh [--reset] [--no-build] [--stop]
# ============================================================
set -euo pipefail

RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERR]${NC}   $*" >&2; }
section() { echo -e "\n${BOLD}${CYAN}══ $* ══${NC}"; }

RESET=false; NO_BUILD=false; STOP=false
for arg in "$@"; do
  case "$arg" in
    --reset) RESET=true ;;
    --no-build) NO_BUILD=true ;;
    --stop) STOP=true ;;
    --help|-h)
      echo "用法: bash start.sh [选项]"
      echo "  --reset     清除所有数据并重新初始化"
      echo "  --no-build  跳过镜像构建（使用已有镜像）"
      echo "  --stop      停止所有服务"
      exit 0 ;;
    *)
      error "未知参数: $arg"
      exit 1 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

ensure_compose_command() {
  if docker compose version >/dev/null 2>&1; then
    DC=(docker compose)
  elif command -v docker-compose >/dev/null 2>&1; then
    DC=(docker-compose)
  else
    error "未检测到 Docker Compose，请先安装 Docker / Docker Compose"
    exit 1
  fi
}

if $STOP; then
  ensure_compose_command
  section "停止所有服务"
  "${DC[@]}" down
  success "服务已停止"
  exit 0
fi

if $RESET; then
  ensure_compose_command
  section "重置所有数据"
  warn "非交互环境下将直接执行 reset 流程"
  "${DC[@]}" down -v --remove-orphans 2>/dev/null || true
  rm -rf .data/postgres/* .data/redis/* logs/* 2>/dev/null || true
  mkdir -p .data/postgres .data/redis logs
  success "数据目录已重置"
fi

section "阶段 0 — 检测操作系统"
OS="unknown"
PKG_MGR=""
if [[ "${OSTYPE:-}" == darwin* ]]; then
  OS="macos"
  info "检测到 macOS"
elif [[ -f /etc/os-release ]]; then
  # shellcheck disable=SC1091
  . /etc/os-release
  OS="linux"
  info "检测到 ${PRETTY_NAME:-Linux}"
  if command -v apt-get >/dev/null 2>&1; then
    PKG_MGR="apt"
  elif command -v dnf >/dev/null 2>&1; then
    PKG_MGR="dnf"
  elif command -v yum >/dev/null 2>&1; then
    PKG_MGR="yum"
  fi
else
  warn "未能精确识别操作系统，将以最小化检查继续"
fi

section "阶段 1 — 安装系统级基础依赖"
if command -v curl >/dev/null 2>&1 && command -v git >/dev/null 2>&1; then
  success "基础依赖已满足，跳过安装"
else
  warn "当前环境缺少部分基础依赖；脚本在此环境下不自动安装系统包，请按 README 手动补齐"
fi

section "阶段 2 — 安装 Docker Engine"
if command -v docker >/dev/null 2>&1; then
  success "Docker 已安装：$(docker --version)"
else
  error "未检测到 Docker。请按平台要求安装 Docker Engine / Docker Desktop。"
  exit 1
fi

section "阶段 3 — 安装 Docker Compose Plugin（v2）"
ensure_compose_command
success "Compose 命令可用：${DC[*]}"

section "阶段 4 — 安装 Node.js 20 LTS（前端构建）"
if command -v node >/dev/null 2>&1; then
  NODE_MAJOR=$(node -e "process.stdout.write(process.version.split('.')[0].slice(1))")
  if [[ "$NODE_MAJOR" -ge 20 ]]; then
    success "Node.js 已满足要求：$(node --version)"
  else
    warn "检测到 Node.js $(node --version)，建议升级到 v20 LTS"
  fi
else
  warn "未检测到 Node.js；容器构建可继续，本地前端构建会受影响"
fi

section "阶段 5 — 安装 Python 3.11+（可选，本地调试用）"
if command -v python3 >/dev/null 2>&1; then
  success "Python 可用：$(python3 --version)"
else
  warn "未检测到 Python 3，本地调试将不可用，但容器内运行不受影响"
fi

section "阶段 6 — 初始化环境配置"
if [[ ! -f .env ]]; then
  cp .env.example .env
  success ".env 已从模板创建"
else
  info ".env 已存在，跳过创建"
fi
mkdir -p .data/postgres .data/redis logs

check_env_key() {
  local key="$1"
  local val=""
  if [[ -f .env ]]; then
    val=$(grep -E "^${key}=" .env | head -n1 | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
  fi
  if [[ -z "$val" ]]; then
    warn "环境变量 ${key} 未配置"
    return 1
  fi
  return 0
}

MISSING_KEYS=0
check_env_key SERPER_API_KEY || MISSING_KEYS=$((MISSING_KEYS+1))
check_env_key DATABASE_URL || MISSING_KEYS=$((MISSING_KEYS+1))
check_env_key SECRET_KEY || MISSING_KEYS=$((MISSING_KEYS+1))
if [[ $MISSING_KEYS -gt 0 ]]; then
  warn "存在 ${MISSING_KEYS} 个关键配置项未填写，系统可能降级运行"
fi

section "阶段 7 — 预拉取基础镜像"
"${DC[@]}" pull postgres redis nginx >/dev/null 2>&1 || warn "基础镜像预拉取失败，将在构建时重试"
success "基础镜像预热完成"

section "阶段 8 — 构建并启动所有容器"
BUILD_ARGS=()
if ! $NO_BUILD; then
  BUILD_ARGS+=(--build)
fi
"${DC[@]}" up -d "${BUILD_ARGS[@]}" --remove-orphans
success "容器启动命令已执行"

wait_for_port() {
  local name="$1" host="$2" port="$3" max_wait="${4:-60}"
  info "等待 ${name} (${host}:${port}) 就绪..."
  local elapsed=0
  while ! (echo >/dev/tcp/"$host"/"$port") >/dev/null 2>&1; do
    sleep 2
    elapsed=$((elapsed+2))
    if [[ $elapsed -ge $max_wait ]]; then
      error "${name} 在 ${max_wait}s 内未就绪"
      "${DC[@]}" logs --tail=50 || true
      exit 1
    fi
  done
  success "${name} 就绪（${elapsed}s）"
}

section "阶段 9 — 等待基础服务就绪（PostgreSQL + Redis）"
wait_for_port "PostgreSQL" "127.0.0.1" "5432" 90
wait_for_port "Redis" "127.0.0.1" "6379" 60

section "阶段 10 — 数据库迁移（Alembic）"
if "${DC[@]}" exec -T backend alembic upgrade head; then
  success "数据库迁移完成"
else
  warn "Alembic 迁移执行失败，请检查 backend 日志"
fi

info "安装 Playwright 浏览器（首次运行）..."
"${DC[@]}" exec -T backend playwright install chromium --with-deps >/dev/null 2>&1 || warn "Playwright 浏览器安装失败，动态抓取能力将降级"

wait_for_http() {
  local name="$1" url="$2" max_wait="${3:-120}"
  info "等待 ${name} (${url}) 就绪..."
  local elapsed=0
  while ! curl -sf "$url" -o /dev/null 2>/dev/null; do
    sleep 3
    elapsed=$((elapsed+3))
    if [[ $elapsed -ge $max_wait ]]; then
      error "${name} 在 ${max_wait}s 内未响应"
      "${DC[@]}" logs --tail=50 || true
      exit 1
    fi
  done
  success "${name} 就绪（${elapsed}s）"
}

section "阶段 11 — 等待应用服务就绪"
wait_for_http "后端 API" "http://localhost:8000/health" 120
wait_for_http "前端界面" "http://localhost:3000" 120
wait_for_http "Flower" "http://localhost:5555" 120

section "阶段 12 — 系统就绪"
echo ""
echo -e "${BOLD}${GREEN}"
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║      B2B 智能客户开发系统 — 已成功启动       ║"
echo "  ╠══════════════════════════════════════════════╣"
echo "  ║  🌐 Web 界面:   http://localhost:3000        ║"
echo "  ║  📡 API 文档:   http://localhost:8000/docs   ║"
echo "  ║  🌸 Flower:     http://localhost:5555        ║"
echo "  ╠══════════════════════════════════════════════╣"
echo "  ║  停止服务:  bash start.sh --stop             ║"
echo "  ║  重置数据:  bash start.sh --reset            ║"
echo "  ║  查看日志:  docker compose logs -f           ║"
echo "  ╚══════════════════════════════════════════════╝"
echo -e "${NC}"

info "各容器运行状态："
"${DC[@]}" ps
