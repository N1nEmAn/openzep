#!/usr/bin/env bash
# install_mirofish.sh — OpenZep + MiroFish 一体化安装入口
# 用法: bash install_mirofish.sh [MIROFISH_PATH]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

prompt_install_mode() {
    local current_value="${OPENZEP_INSTALL_MODE:-}"

    if [[ -n "$current_value" ]]; then
        printf '%s\n' "$current_value"
        return 0
    fi

    if [[ ! -t 0 ]]; then
        printf '%s\n' "docker"
        return 0
    fi

    printf "OpenZep 安装方式 [默认: docker，可选: docker/local]: "
    read -r current_value
    current_value="${current_value:-docker}"
    printf '%s\n' "$current_value"
}

INSTALL_MODE="$(prompt_install_mode)"
case "$INSTALL_MODE" in
    docker|local)
        ;;
    *)
        echo "无效的 OPENZEP_INSTALL_MODE: $INSTALL_MODE，仅支持 docker 或 local" >&2
        exit 1
        ;;
esac

echo
echo "==> [1/2] 安装并启动 OpenZep (${INSTALL_MODE})"
if [[ "$INSTALL_MODE" == "docker" ]]; then
    (cd "$SCRIPT_DIR" && bash setup_docker.sh)
else
    (cd "$SCRIPT_DIR" && bash setup.sh)
fi

echo
echo "==> [2/2] 接入 MiroFish"
if [[ $# -ge 1 ]]; then
    (cd "$SCRIPT_DIR" && bash setup_mirofish.sh "$1")
else
    (cd "$SCRIPT_DIR" && bash setup_mirofish.sh)
fi
