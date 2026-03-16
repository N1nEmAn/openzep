#!/usr/bin/env bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[ OK ]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERR ]${NC} $*"; exit 1; }

prompt_value() {
    local var_name="$1"
    local prompt_text="$2"
    local default_value="${3:-}"
    local secret="${4:-0}"
    local required="${5:-1}"
    local current_value="${!var_name:-}"

    if [ -n "$current_value" ]; then
        printf -v "$var_name" '%s' "$current_value"
        return 0
    fi

    if [ ! -t 0 ]; then
        if [ "$required" = "1" ] && [ -z "$default_value" ]; then
            error "${var_name} 未提供，且当前为非交互模式"
        fi
        printf -v "$var_name" '%s' "$default_value"
        return 0
    fi

    if [ -n "$default_value" ]; then
        printf "%b" "${BOLD}${prompt_text} [默认: ${default_value}]: ${NC}"
    else
        printf "%b" "${BOLD}${prompt_text}: ${NC}"
    fi

    if [ "$secret" = "1" ]; then
        read -rs current_value
        echo
    else
        read -r current_value
    fi

    if [ -z "$current_value" ]; then
        current_value="$default_value"
    fi

    if [ "$required" = "1" ] && [ -z "$current_value" ]; then
        error "${var_name} 不能为空"
    fi

    printf -v "$var_name" '%s' "$current_value"
}

echo -e ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║        OpenZep 安装向导              ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════╝${NC}"
echo -e ""

# ── 前置依赖检查 ─────────────────────────────
info "检查前置依赖..."
command -v docker >/dev/null 2>&1 || error "未找到 docker，请先安装 Docker"
command -v python3 >/dev/null 2>&1 || error "未找到 python3，请先安装 Python 3.10+"
PY_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')
[ "$PY_MINOR" -ge 10 ] || error "需要 Python 3.10+，当前版本过低"
success "前置依赖检查通过"
echo

# ── .env 配置向导 ─────────────────────────────
if [ -f .env ]; then
    warn ".env 已存在，跳过配置（如需重新配置请删除 .env 后重新运行）"
else
    echo -e "${BOLD}── 第 1 步：LLM 配置 ────────────────────────${NC}"
    echo "支持任意 OpenAI 兼容接口（OpenAI、SiliconFlow、本地 Ollama 等）"
    echo

    prompt_value "LLM_BASE_URL" "LLM Base URL（如 https://api.openai.com/v1）"
    prompt_value "LLM_API_KEY" "LLM API Key" "" 1
    prompt_value "LLM_MODEL" "LLM 模型名称（如 gpt-4o、anthropic/claude-sonnet-4.6）"

    echo
    echo -e "${BOLD}── 第 2 步：Embedding 配置 ──────────────────${NC}"
    echo "如果 LLM 端点不支持 embedding（如 Anthropic 官方 API），需单独配置 Embedder。"
    prompt_value "SEPARATE_EMBEDDER" "是否单独配置 Embedder？[y/N]" "N" 0 0

    if [[ "$SEPARATE_EMBEDDER" =~ ^[Yy]$ ]]; then
        prompt_value "EMBEDDER_BASE_URL" "Embedder Base URL（如 https://api.siliconflow.cn/v1）"
        prompt_value "EMBEDDER_API_KEY" "Embedder API Key" "" 1
        prompt_value "EMBEDDER_MODEL" "Embedder 模型名称" "BAAI/bge-m3" 0 0
    else
        EMBEDDER_BASE_URL=""
        EMBEDDER_API_KEY=""
        prompt_value "EMBEDDER_MODEL" "Embedder 模型名称" "text-embedding-3-small" 0 0
    fi

    echo
    echo -e "${BOLD}── 第 3 步：OpenZep API Key ──────────────────${NC}"
    prompt_value "API_KEY" "设置服务 API Key（留空自动生成）" "" 1 0
    if [ -z "$API_KEY" ]; then
        API_KEY="openzep-$(cat /dev/urandom | tr -dc 'a-z0-9' | head -c 12)"
        info "已生成随机 API Key: ${BOLD}${API_KEY}${NC}"
    fi

    echo
    echo -e "${BOLD}── 第 4 步：Neo4j 密码 ───────────────────────${NC}"
    prompt_value "NEO4J_PASSWORD" "Neo4j 密码" "password123" 1 0

    cat > .env << EOF
# LLM
LLM_API_KEY=${LLM_API_KEY}
LLM_BASE_URL=${LLM_BASE_URL}
LLM_MODEL=${LLM_MODEL}
LLM_SMALL_MODEL=${LLM_MODEL}

# Embedder
EMBEDDER_API_KEY=${EMBEDDER_API_KEY}
EMBEDDER_BASE_URL=${EMBEDDER_BASE_URL}
EMBEDDER_MODEL=${EMBEDDER_MODEL}

GRAPH_DB=neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=${NEO4J_PASSWORD}

SQLITE_PATH=openzep.db

# OpenZep API Key
API_KEY=${API_KEY}
EOF
    success ".env 已生成"
    echo
fi

# ── 读取 .env 变量 ────────────────────────────
NEO4J_PASSWORD=$(grep '^NEO4J_PASSWORD=' .env | cut -d= -f2)
API_KEY=$(grep '^API_KEY=' .env | cut -d= -f2)

# ── 启动 Neo4j ────────────────────────────────
echo -e "${BOLD}── 启动 Neo4j ───────────────────────────────${NC}"
if docker ps --filter name=neo4j --format '{{.Names}}' | grep -q '^neo4j$'; then
    success "Neo4j 已在运行"
elif docker ps -a --filter name=neo4j --format '{{.Names}}' | grep -q '^neo4j$'; then
    info "启动已有 Neo4j 容器..."
    docker start neo4j > /dev/null
    success "Neo4j 已启动"
else
    info "创建并启动 Neo4j 容器..."
    docker run -d --name neo4j --restart unless-stopped \
        -p 7687:7687 -p 7474:7474 \
        -e "NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}" \
        neo4j:5 > /dev/null
    success "Neo4j 容器已创建"
fi

info "等待 Neo4j 就绪..."
for i in $(seq 1 20); do
    if docker exec neo4j cypher-shell -u neo4j -p "${NEO4J_PASSWORD}" "RETURN 1" >/dev/null 2>&1; then
        success "Neo4j 已就绪"
        break
    fi
    sleep 2
    [ "$i" -eq 20 ] && warn "Neo4j 启动超时，继续安装（稍后服务自动重连）"
done
echo

# ── 安装 Python 依赖 ──────────────────────────
echo -e "${BOLD}── 安装 Python 依赖 ─────────────────────────${NC}"
if [ ! -d .venv ]; then
    info "创建虚拟环境..."
    python3 -m venv .venv
fi
info "安装依赖包（首次可能需要几分钟）..."
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
success "Python 依赖安装完成"
echo

# ── 启动 OpenZep ──────────────────────────────
echo -e "${BOLD}── 启动 OpenZep 服务 ────────────────────────${NC}"
if lsof -ti:8000 >/dev/null 2>&1; then
    warn "端口 8000 已被占用，跳过启动（服务可能已在运行）"
else
    nohup .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 > openzep.log 2>&1 &
    OPENZEP_PID=$!
    info "等待服务启动（PID: ${OPENZEP_PID}）..."
    for i in $(seq 1 15); do
        if curl -sf http://localhost:8000/healthz >/dev/null 2>&1; then
            success "OpenZep 服务已启动"
            break
        fi
        sleep 2
        [ "$i" -eq 15 ] && warn "服务启动超时，请检查日志: tail -50 openzep.log"
    done
fi
echo

# ── 完成提示 ──────────────────────────────────
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${BOLD}${GREEN}║        安装完成！                    ║${NC}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════╝${NC}"
echo
echo -e "  服务地址:  ${BOLD}http://localhost:8000${NC}"
echo -e "  API Key:   ${BOLD}${API_KEY}${NC}"
echo -e "  API 文档:  ${BOLD}http://localhost:8000/docs${NC}"
echo -e "  日志:      ${BOLD}tail -f openzep.log${NC}"
echo
echo -e "  接入示例（Python）:"
echo -e "  ${CYAN}from zep_python import ZepClient${NC}"
echo -e "  ${CYAN}client = ZepClient(api_key=\"${API_KEY}\", base_url=\"http://localhost:8000\")${NC}"
echo
