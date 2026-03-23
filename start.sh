#!/usr/bin/env bash
# ============================================================
#  B2B 智能客户开发系统 — 原生部署脚本
#  支持: Ubuntu/Debian/CentOS/RHEL/Fedora/macOS（systemd 步骤限 Linux）
#  用法: bash start.sh [--stop] [--status]
# ============================================================
set -euo pipefail

RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERR]${NC}   $*" >&2; }
section() { echo -e "\n${BOLD}${CYAN}══ $* ══${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
VENV_DIR="$BACKEND_DIR/.venv"
LOG_DIR="$SCRIPT_DIR/logs"
ENV_FILE="$SCRIPT_DIR/.env"
DEPLOY_USER="${SUDO_USER:-$USER}"
SERVER_NAME="_"
STOP=false
STATUS=false

for arg in "$@"; do
  case "$arg" in
    --stop) STOP=true ;;
    --status) STATUS=true ;;
    --help|-h)
      echo "用法: bash start.sh [--stop] [--status]"
      exit 0 ;;
    *)
      error "未知参数: $arg"
      exit 1 ;;
  esac
done

service_status() {
  local service="$1"
  if command -v systemctl >/dev/null 2>&1; then
    systemctl is-active "$service" 2>/dev/null || true
  else
    echo "unsupported"
  fi
}

if $STOP; then
  section "停止 leadgen 应用服务"
  if command -v systemctl >/dev/null 2>&1; then
    sudo systemctl stop leadgen-flower leadgen-beat leadgen-worker leadgen-api || true
    success "已停止 leadgen-* 服务（PostgreSQL / Redis / Nginx 保持运行）"
  else
    warn "当前系统不支持 systemctl，无法执行 --stop"
  fi
  exit 0
fi

if $STATUS; then
  section "服务状态"
  for service in postgresql redis nginx leadgen-api leadgen-worker leadgen-beat leadgen-flower; do
    printf '%-18s %s\n' "$service" "$(service_status "$service")"
  done
  exit 0
fi

OS="unknown"
PKG_MGR=""
if [[ "${OSTYPE:-}" == darwin* ]]; then
  OS="macos"
elif [[ -f /etc/os-release ]]; then
  # shellcheck disable=SC1091
  . /etc/os-release
  OS="linux"
  if command -v apt-get >/dev/null 2>&1; then
    PKG_MGR="apt"
  elif command -v dnf >/dev/null 2>&1; then
    PKG_MGR="dnf"
  elif command -v yum >/dev/null 2>&1; then
    PKG_MGR="yum"
  fi
fi

require_sudo() {
  if [[ "$OS" == "linux" ]] && ! sudo -n true 2>/dev/null; then
    warn "后续安装/写入 systemd/Nginx/PostgreSQL 配置需要 sudo 权限"
  fi
}

replace_or_append() {
  local file="$1" pattern="$2" replacement="$3"
  if sudo test -f "$file"; then
    if sudo grep -qE "$pattern" "$file"; then
      sudo sed -i -E "s|$pattern|$replacement|" "$file"
    else
      echo "$replacement" | sudo tee -a "$file" >/dev/null
    fi
  fi
}

render_template() {
  local src="$1" dest="$2"
  sed \
    -e "s|__SCRIPT_DIR__|$SCRIPT_DIR|g" \
    -e "s|__VENV_DIR__|$VENV_DIR|g" \
    -e "s|__DEPLOY_USER__|$DEPLOY_USER|g" \
    -e "s|__LOG_DIR__|$LOG_DIR|g" \
    -e "s|__ENV_FILE__|$ENV_FILE|g" \
    -e "s|__FRONTEND_DIST_DIR__|$FRONTEND_DIR/dist|g" \
    -e "s|__SERVER_NAME__|$SERVER_NAME|g" \
    "$src" | sudo tee "$dest" >/dev/null
}

get_env() {
  local key="$1"
  grep -E "^${key}=" "$ENV_FILE" | head -n1 | cut -d= -f2-
}

postgres_psql() {
  local sql="$1"
  local escaped_sql
  printf -v escaped_sql '%q' "$sql"
  sudo -u postgres bash -lc "cd /tmp && psql -v ON_ERROR_STOP=1 -tc $escaped_sql"
}

postgres_exec() {
  local command="$1"
  sudo -u postgres bash -lc "cd /tmp && $command"
}

require_env_value() {
  local key="$1"
  local value="$2"
  if [[ -z "$value" ]]; then
    error "环境变量 ${key} 未配置，无法继续执行 PostgreSQL 初始化"
    exit 1
  fi
}

require_pg_identifier() {
  local key="$1"
  local value="$2"
  if [[ ! "$value" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
    error "${key}=${value} 不是安全的 PostgreSQL 标识符；仅允许字母、数字和下划线，且不能以数字开头"
    exit 1
  fi
}

escape_pg_literal() {
  local value="$1"
  value=${value//\'/\'\'}
  printf '%s' "$value"
}

postgres_db_psql() {
  local database="$1"
  local sql="$2"
  local escaped_sql
  printf -v escaped_sql '%q' "$sql"
  sudo -u postgres bash -lc "cd /tmp && psql -v ON_ERROR_STOP=1 -d '$database' -tc $escaped_sql"
}

wait_for_port() {
  local name="$1" host="$2" port="$3" max_wait="${4:-60}"
  local elapsed=0
  info "等待 ${name} (${host}:${port}) 就绪..."
  while ! (echo >/dev/tcp/"$host"/"$port") >/dev/null 2>&1; do
    sleep 2
    elapsed=$((elapsed+2))
    if [[ $elapsed -ge $max_wait ]]; then
      error "${name} 在 ${max_wait}s 内未就绪"
      exit 1
    fi
  done
  success "${name} 已就绪"
}

wait_for_http() {
  local name="$1" url="$2" max_wait="${3:-120}"
  local elapsed=0
  info "等待 ${name} (${url}) 响应..."
  while ! curl -sf "$url" >/dev/null 2>&1; do
    sleep 3
    elapsed=$((elapsed+3))
    if [[ $elapsed -ge $max_wait ]]; then
      error "${name} 在 ${max_wait}s 内未响应"
      exit 1
    fi
  done
  success "${name} 已响应"
}

section "阶段 0 — 检测操作系统"
info "OS=${OS} PKG_MGR=${PKG_MGR:-none}"
require_sudo

section "阶段 1 — 安装系统级基础依赖"
if [[ "$OS" == "linux" ]]; then
  case "$PKG_MGR" in
    apt)
      sudo apt-get update -y
      sudo apt-get install -y curl wget git unzip lsof net-tools software-properties-common ca-certificates gnupg build-essential python3-venv python3-pip ;;
    dnf|yum)
      sudo "$PKG_MGR" install -y curl wget git unzip lsof net-tools ca-certificates gcc gcc-c++ make python3 python3-pip ;;
    *) warn "未识别包管理器，请手动安装基础依赖" ;;
  esac
elif [[ "$OS" == "macos" ]]; then
  command -v brew >/dev/null 2>&1 || error "请先安装 Homebrew"
  brew install curl wget git unzip || true
fi
success "基础依赖阶段完成"

section "阶段 2 — 安装 PostgreSQL 15"
if command -v psql >/dev/null 2>&1; then
  success "PostgreSQL 已安装：$(psql --version)"
else
  if [[ "$OS" == "linux" ]]; then
    case "$PKG_MGR" in
      apt)
        sudo install -d /usr/share/postgresql-common/pgdg
        curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo gpg --dearmor -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.gpg
        echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.gpg] http://apt.postgresql.org/pub/repos/apt $(. /etc/os-release && echo $VERSION_CODENAME)-pgdg main" | sudo tee /etc/apt/sources.list.d/pgdg.list >/dev/null
        sudo apt-get update -y && sudo apt-get install -y postgresql-15 postgresql-client-15 postgresql-contrib-15 ;;
      dnf|yum)
        sudo "$PKG_MGR" install -y postgresql15-server postgresql15-contrib postgresql15 ;;
      *) warn "请手动安装 PostgreSQL 15" ;;
    esac
  else
    brew install postgresql@15 || true
  fi
fi
if command -v systemctl >/dev/null 2>&1; then
  sudo systemctl enable --now postgresql || sudo systemctl enable --now postgresql-15 || true
fi

section "阶段 3 — 安装 Redis 7"
if command -v redis-server >/dev/null 2>&1; then
  success "Redis 已安装：$(redis-server --version | head -n1)"
else
  if [[ "$OS" == "linux" ]]; then
    case "$PKG_MGR" in
      apt) sudo apt-get install -y redis-server ;;
      dnf|yum) sudo "$PKG_MGR" install -y redis ;;
      *) warn "请手动安装 Redis 7" ;;
    esac
  else
    brew install redis || true
  fi
fi
if command -v systemctl >/dev/null 2>&1; then
  sudo systemctl enable --now redis || sudo systemctl enable --now redis-server || true
fi

section "阶段 4 — 安装 Nginx"
if command -v nginx >/dev/null 2>&1; then
  success "Nginx 已安装：$(nginx -v 2>&1)"
else
  if [[ "$OS" == "linux" ]]; then
    case "$PKG_MGR" in
      apt) sudo apt-get install -y nginx ;;
      dnf|yum) sudo "$PKG_MGR" install -y nginx ;;
      *) warn "请手动安装 Nginx" ;;
    esac
  else
    brew install nginx || true
  fi
fi
if command -v systemctl >/dev/null 2>&1; then
  sudo systemctl enable --now nginx || true
fi

section "阶段 5 — 安装 Node.js 20 LTS"
if command -v node >/dev/null 2>&1; then
  info "检测到 Node.js $(node --version)"
else
  export NVM_DIR="$HOME/.nvm"
  if [[ ! -d "$NVM_DIR" ]]; then
    curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
  fi
  # shellcheck disable=SC1090
  [[ -s "$NVM_DIR/nvm.sh" ]] && . "$NVM_DIR/nvm.sh"
  nvm install 20 --lts
  nvm use 20
  nvm alias default 20
fi
success "Node.js 阶段完成"

section "阶段 6 — 安装 Python 3.11+"
if command -v python3 >/dev/null 2>&1; then
  info "检测到 $(python3 --version)"
else
  error "未检测到 python3，请手动安装 Python 3.11+"
  exit 1
fi

section "阶段 7 — 初始化环境与日志目录"
cd "$SCRIPT_DIR"
[[ -f "$ENV_FILE" ]] || cp .env.example .env
mkdir -p "$LOG_DIR"
touch "$LOG_DIR"/api.log "$LOG_DIR"/worker.log "$LOG_DIR"/beat.log "$LOG_DIR"/flower.log "$LOG_DIR"/nginx-access.log "$LOG_DIR"/nginx-error.log
success "环境文件与日志目录已就绪"

section "阶段 8 — 初始化 PostgreSQL（角色 / 数据库 / 扩展）"
POSTGRES_USER_VAL="$(get_env POSTGRES_USER)"
POSTGRES_PASSWORD_VAL="$(get_env POSTGRES_PASSWORD)"
POSTGRES_DB_VAL="$(get_env POSTGRES_DB)"
require_env_value "POSTGRES_USER" "$POSTGRES_USER_VAL"
require_env_value "POSTGRES_PASSWORD" "$POSTGRES_PASSWORD_VAL"
require_env_value "POSTGRES_DB" "$POSTGRES_DB_VAL"
require_pg_identifier "POSTGRES_USER" "$POSTGRES_USER_VAL"
require_pg_identifier "POSTGRES_DB" "$POSTGRES_DB_VAL"
POSTGRES_PASSWORD_ESCAPED="$(escape_pg_literal "$POSTGRES_PASSWORD_VAL")"
wait_for_port "PostgreSQL" "127.0.0.1" "5432" 90
POSTGRES_INIT_SQL="$SCRIPT_DIR/deploy/postgres/init.sql"
if postgres_psql "SELECT 1 FROM pg_roles WHERE rolname='${POSTGRES_USER_VAL}'" | grep -q 1; then
  info "PostgreSQL 角色 ${POSTGRES_USER_VAL} 已存在，刷新密码"
  postgres_exec "psql -v ON_ERROR_STOP=1 -c \"ALTER ROLE ${POSTGRES_USER_VAL} WITH LOGIN PASSWORD '${POSTGRES_PASSWORD_ESCAPED}';\""
else
  info "创建 PostgreSQL 角色 ${POSTGRES_USER_VAL}"
  postgres_exec "psql -v ON_ERROR_STOP=1 -c \"CREATE ROLE ${POSTGRES_USER_VAL} WITH LOGIN PASSWORD '${POSTGRES_PASSWORD_ESCAPED}';\""
fi
if postgres_psql "SELECT 1 FROM pg_database WHERE datname='${POSTGRES_DB_VAL}'" | grep -q 1; then
  info "数据库 ${POSTGRES_DB_VAL} 已存在，校正 owner"
  postgres_exec "psql -v ON_ERROR_STOP=1 -c \"ALTER DATABASE ${POSTGRES_DB_VAL} OWNER TO ${POSTGRES_USER_VAL};\""
else
  info "创建数据库 ${POSTGRES_DB_VAL}"
  postgres_exec "createdb -O '${POSTGRES_USER_VAL}' '${POSTGRES_DB_VAL}'"
fi
postgres_exec "psql -v ON_ERROR_STOP=1 -d '${POSTGRES_DB_VAL}' -f '${POSTGRES_INIT_SQL}'"
postgres_db_psql "$POSTGRES_DB_VAL" "ALTER SCHEMA public OWNER TO ${POSTGRES_USER_VAL};"
postgres_db_psql "$POSTGRES_DB_VAL" "GRANT ALL PRIVILEGES ON SCHEMA public TO ${POSTGRES_USER_VAL};"
success "PostgreSQL 初始化完成"

section "阶段 9 — Redis 加固"
if [[ "$OS" == "linux" ]]; then
  REDIS_CONF="/etc/redis/redis.conf"
  if sudo test -f "$REDIS_CONF"; then
    replace_or_append "$REDIS_CONF" '^bind .*' 'bind 127.0.0.1 ::1'
    replace_or_append "$REDIS_CONF" '^maxmemory .*' 'maxmemory 512mb'
    replace_or_append "$REDIS_CONF" '^maxmemory-policy .*' 'maxmemory-policy allkeys-lru'
    replace_or_append "$REDIS_CONF" '^save .*' 'save 60 1'
    sudo systemctl restart redis || sudo systemctl restart redis-server || true
  else
    warn "未找到 redis.conf，跳过自动加固"
  fi
else
  warn "macOS 环境跳过 Redis 自动加固，请手动配置 bind/maxmemory/RDB"
fi
wait_for_port "Redis" "127.0.0.1" "6379" 60

section "阶段 10 — 创建 backend/.venv 并安装 Python 依赖"
cd "$BACKEND_DIR"
python3 -m venv .venv
# shellcheck disable=SC1091
. "$VENV_DIR/bin/activate"
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
success "后端虚拟环境与依赖已安装"

section "阶段 11 — 构建前端静态资源"
cd "$FRONTEND_DIR"
npm install
npm run build
success "前端静态构建完成：$FRONTEND_DIR/dist"

section "阶段 12 — 执行数据库迁移"
cd "$BACKEND_DIR"
# shellcheck disable=SC1091
. "$VENV_DIR/bin/activate"
alembic upgrade head
success "Alembic 迁移完成"

section "阶段 13 — 渲染并启用 Nginx 配置"
if [[ "$OS" == "linux" ]]; then
  sudo mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled
  render_template "$SCRIPT_DIR/deploy/nginx/leadgen.conf" /etc/nginx/sites-available/leadgen.conf
  sudo ln -sf /etc/nginx/sites-available/leadgen.conf /etc/nginx/sites-enabled/leadgen.conf
  sudo nginx -t
  sudo systemctl reload nginx
  success "Nginx 配置已加载"
else
  warn "macOS 环境未自动写入 Nginx 站点配置，请手动使用 deploy/nginx/leadgen.conf"
fi

section "阶段 14 — 渲染并启动 systemd 服务"
if command -v systemctl >/dev/null 2>&1; then
  for unit in leadgen-api.service leadgen-worker.service leadgen-beat.service leadgen-flower.service; do
    render_template "$SCRIPT_DIR/deploy/systemd/$unit" "/etc/systemd/system/$unit"
  done
  sudo systemctl daemon-reload
  sudo systemctl enable --now leadgen-api.service
  sudo systemctl enable --now leadgen-worker.service
  sudo systemctl enable --now leadgen-beat.service
  sudo systemctl enable --now leadgen-flower.service
  success "systemd 服务已启动"
else
  warn "当前系统不支持 systemd，请手动参考 deploy/systemd/ 模板启动服务"
fi

section "阶段 15 — 健康检查"
wait_for_http "后端 API" "http://127.0.0.1:8000/health" 120
wait_for_http "前端页面" "http://127.0.0.1" 120
wait_for_http "Flower" "http://127.0.0.1:5555" 120

section "阶段 16 — 系统就绪"
echo ""
echo -e "${BOLD}${GREEN}"
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║      B2B 智能客户开发系统 — 已原生部署      ║"
echo "  ╠══════════════════════════════════════════════╣"
echo "  ║  🌐 Web:      http://127.0.0.1              ║"
echo "  ║  📡 API Docs: http://127.0.0.1:8000/docs    ║"
echo "  ║  🌸 Flower:   http://127.0.0.1:5555         ║"
echo "  ╠══════════════════════════════════════════════╣"
echo "  ║  停止服务: bash start.sh --stop             ║"
echo "  ║  查看状态: bash start.sh --status           ║"
echo "  ╚══════════════════════════════════════════════╝"
echo -e "${NC}"

if command -v systemctl >/dev/null 2>&1; then
  for service in postgresql redis nginx leadgen-api leadgen-worker leadgen-beat leadgen-flower; do
    printf '%-18s %s\n' "$service" "$(service_status "$service")"
  done
fi
