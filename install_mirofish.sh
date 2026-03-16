#!/usr/bin/env bash
# install_mirofish.sh — OpenZep + MiroFish 一体化安装入口
# 用法: bash install_mirofish.sh [MIROFISH_PATH]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo
echo "==> [1/2] 安装并启动 OpenZep"
(cd "$SCRIPT_DIR" && bash setup.sh)

echo
echo "==> [2/2] 接入 MiroFish"
if [[ $# -ge 1 ]]; then
    (cd "$SCRIPT_DIR" && bash setup_mirofish.sh "$1")
else
    (cd "$SCRIPT_DIR" && bash setup_mirofish.sh)
fi
