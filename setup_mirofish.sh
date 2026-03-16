#!/usr/bin/env bash
# setup_mirofish.sh — 将 MiroFish 接入 OpenZep 的一键配置脚本
# 用法: bash setup_mirofish.sh [MIROFISH_PATH]
# 示例: bash setup_mirofish.sh /home/N1nE/MiroFish

set -euo pipefail

BOLD="\033[1m"
GREEN="\033[0;32m"
CYAN="\033[0;36m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
NC="\033[0m"

info()    { echo -e "  ${CYAN}[INFO]${NC} $*"; }
success() { echo -e "  ${GREEN}[OK]${NC}   $*"; }
warn()    { echo -e "  ${YELLOW}[WARN]${NC} $*"; }
die()     { echo -e "  ${RED}[ERR]${NC}  $*"; exit 1; }

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
            die "${var_name} 未提供，且当前为非交互模式"
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
        die "${var_name} 不能为空"
    fi

    printf -v "$var_name" '%s' "$current_value"
}

OPENZEP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_MIROFISH="$(cd "$OPENZEP_DIR/.." && pwd)"
ENV_API_KEY="$(grep -E '^API_KEY=' "$OPENZEP_DIR/.env" 2>/dev/null | cut -d= -f2 | tr -d '\r' || true)"

# ── 0. 参数与配置读取 ──────────────────────────────────────────────────────────

if [[ $# -ge 1 && -n "${1:-}" ]]; then
    MIROFISH_PATH="$1"
fi

prompt_value "MIROFISH_PATH" "MiroFish 项目路径" "$DEFAULT_MIROFISH" 0 1
MIROFISH="${MIROFISH_PATH%/}"
[[ -d "$MIROFISH" ]] || die "目录不存在: $MIROFISH"

prompt_value "OPENZEP_URL" "OpenZep 服务地址" "${OPENZEP_URL:-http://localhost:8000}" 0 1
prompt_value "OPENZEP_API_KEY" "OpenZep API Key" "${OPENZEP_API_KEY:-$ENV_API_KEY}" 1 1

echo
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}  OpenZep × MiroFish 一键配置脚本${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  MiroFish 路径: ${CYAN}$MIROFISH${NC}"
echo -e "  OpenZep  地址: ${CYAN}$OPENZEP_URL${NC}"
echo -e "  OpenZep  密钥: ${CYAN}$OPENZEP_API_KEY${NC}"
echo

# ── 1. 同步 OpenZep 配置 ─────────────────────────────────────────────────────

echo -e "${BOLD}[1/4] 同步 OpenZep 配置${NC}"
info "API Key : $OPENZEP_API_KEY"
info "Base URL: $OPENZEP_URL"
info "API URL : $OPENZEP_URL/api/v2"

if [[ -f "$OPENZEP_DIR/.env" ]]; then
    cp "$OPENZEP_DIR/.env" "$OPENZEP_DIR/.env.bak"
else
    touch "$OPENZEP_DIR/.env"
fi

if grep -qE '^API_KEY=' "$OPENZEP_DIR/.env" 2>/dev/null; then
    sed -i "s|^API_KEY=.*|API_KEY=${OPENZEP_API_KEY}|" "$OPENZEP_DIR/.env"
else
    echo "API_KEY=${OPENZEP_API_KEY}" >> "$OPENZEP_DIR/.env"
fi

success "OpenZep .env 已同步"
echo

# ── 2. 修改 MiroFish 的 Zep 客户端文件 ─────────────────────────────────────

echo -e "${BOLD}[2/4] 修改 MiroFish Python 文件${NC}"

TARGET_FILES=(
    "graph_builder.py"
    "zep_tools.py"
    "zep_graph_memory_updater.py"
    "zep_entity_reader.py"
    "oasis_profile_generator.py"
)

PATCHED=0
SKIPPED=0

for fname in "${TARGET_FILES[@]}"; do
    fpath=$(find "$MIROFISH" -name "$fname" -type f 2>/dev/null | head -1)

    if [[ -z "$fpath" ]]; then
        warn "未找到 $fname，跳过"
        ((SKIPPED++)) || true
        continue
    fi

    info "处理: $fpath"
    cp "$fpath" "${fpath}.bak"

    if grep -qE 'base_url=.*ZEP_BASE_URL|base_url=.*localhost:8000' "$fpath" 2>/dev/null; then
        warn "$fname 已含 base_url，跳过修改（保留备份）"
        ((SKIPPED++)) || true
        continue
    fi

    sed -i 's/Zep(api_key=self\.api_key)/Zep(api_key=self.api_key, base_url=Config.ZEP_BASE_URL)/g' "$fpath"
    sed -i 's/Zep(api_key=self\.zep_api_key)/Zep(api_key=self.zep_api_key, base_url=Config.ZEP_BASE_URL)/g' "$fpath"

    success "已修改: $fname"
    ((PATCHED++)) || true
done

echo

# ── 3. 修改 MiroFish .env ────────────────────────────────────────────────────

echo -e "${BOLD}[3/4] 更新 MiroFish .env${NC}"

MIROFISH_ENV="$MIROFISH/.env"

if [[ ! -f "$MIROFISH_ENV" ]]; then
    warn ".env 不存在，将创建: $MIROFISH_ENV"
    touch "$MIROFISH_ENV"
fi

cp "$MIROFISH_ENV" "${MIROFISH_ENV}.bak"

update_env() {
    local key="$1"
    local val="$2"
    if grep -qE "^${key}=" "$MIROFISH_ENV" 2>/dev/null; then
        sed -i "s|^${key}=.*|${key}=${val}|" "$MIROFISH_ENV"
        info "更新: ${key}=${val}"
    else
        echo "${key}=${val}" >> "$MIROFISH_ENV"
        info "追加: ${key}=${val}"
    fi
}

update_env "ZEP_BASE_URL" "${OPENZEP_URL}/api/v2"
update_env "ZEP_API_KEY"  "${OPENZEP_API_KEY}"

success ".env 更新完成"

# 在 config.py 里补充 ZEP_BASE_URL 字段（如果还没有）
CONFIG_PY=$(find "$MIROFISH" -path '*/app/config.py' -type f 2>/dev/null | head -1)
if [[ -n "$CONFIG_PY" ]]; then
    if ! grep -q 'ZEP_BASE_URL' "$CONFIG_PY" 2>/dev/null; then
        sed -i "s|ZEP_API_KEY = os.environ.get('ZEP_API_KEY')|ZEP_API_KEY = os.environ.get('ZEP_API_KEY')\n    ZEP_BASE_URL = os.environ.get('ZEP_BASE_URL', 'http://localhost:8000/api/v2')|" "$CONFIG_PY"
        success "config.py 已添加 ZEP_BASE_URL"
    else
        info "config.py 已含 ZEP_BASE_URL，跳过"
    fi
fi
echo

# ── 4. 验证 OpenZep 服务 ─────────────────────────────────────────────────────

echo -e "${BOLD}[4/4] 验证 OpenZep 服务${NC}"

if curl -sf --max-time 3 "${OPENZEP_URL}/healthz" >/dev/null 2>&1; then
    success "OpenZep 服务在线: $OPENZEP_URL"
else
    warn "OpenZep 未响应（${OPENZEP_URL}/healthz）"
    warn "请先完成 OpenZep 安装并启动服务，再重试接入脚本"
fi

echo

# ── 完成摘要 ─────────────────────────────────────────────────────────────────

echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}  配置完成${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo
echo -e "  已修改文件 : ${GREEN}${PATCHED}${NC} 个（${SKIPPED} 个跳过）"
echo -e "  MiroFish .env 已写入:"
echo -e "    ${CYAN}ZEP_BASE_URL=${OPENZEP_URL}/api/v2${NC}"
echo -e "    ${CYAN}ZEP_API_KEY=${OPENZEP_API_KEY}${NC}"
echo
echo -e "  ${BOLD}下一步:${NC}"
echo -e "  1. 确认 MiroFish Config.py 中有以下内容:"
echo    "       ZEP_BASE_URL = os.getenv('ZEP_BASE_URL', 'http://localhost:8000/api/v2')"
echo -e "  2. 确认 OpenZep 已启动并可访问:"
echo -e "     ${CYAN}${OPENZEP_URL}/healthz${NC}"
echo -e "  3. 重启 MiroFish，内存服务将指向本地 OpenZep"
echo
echo -e "  备份文件均以 ${YELLOW}.bak${NC} 结尾，如需回滚直接还原即可"
echo
