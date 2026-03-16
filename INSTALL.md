# OpenZep 接入 MiroFish 安装说明

## 手动安装

在 `openzep` 目录执行：

```bash
bash install_mirofish.sh
```

脚本会按提示让你填写或确认这些信息：

- `LLM_BASE_URL`
- `LLM_API_KEY`
- `LLM_MODEL`
- `OpenZep API Key`
- `OpenZep 服务地址`
- `MiroFish 项目路径`

安装脚本会自动完成这些事：

- 安装并启动 OpenZep
- 写入或更新 `openzep/.env`
- 更新 MiroFish 根目录 `.env` 中的 `ZEP_API_KEY` 和 `ZEP_BASE_URL`
- 自动替换 MiroFish 后端关键文件中的 Zep 客户端配置
- 验证 `http://localhost:8000/healthz` 是否可访问

不需要手动把 `from zep_python import ZepClient` 粘贴到 MiroFish 的任何源码文件里。

## 脚本说明

`install_mirofish.sh`

- 一体化入口
- 会先执行 `setup.sh`
- 再执行 `setup_mirofish.sh`

`setup.sh`

- 负责安装 OpenZep 本体
- 会提示填写 LLM 与 OpenZep 服务相关配置

`setup_mirofish.sh`

- 负责把 MiroFish 接到 OpenZep
- 会自动更新 `.env` 和关键 Python 文件

## 安装完成后检查

确认 MiroFish 根目录 `.env` 中至少包含：

```env
ZEP_API_KEY=your_openzep_api_key
ZEP_BASE_URL=http://localhost:8000/api/v2
```

然后重启 MiroFish。

## Agent 安装指令

如果是 agent 或 CI 环境，建议直接传环境变量，避免交互输入：

```bash
LLM_BASE_URL="https://your-llm-base-url/v1" \
LLM_API_KEY="your-llm-api-key" \
LLM_MODEL="your-llm-model" \
API_KEY="your-openzep-api-key" \
OPENZEP_URL="http://localhost:8000" \
MIROFISH_PATH="/absolute/path/to/MiroFish" \
bash install_mirofish.sh
```

如果需要单独配置 embedding，再额外传这些变量：

```bash
SEPARATE_EMBEDDER="Y" \
EMBEDDER_BASE_URL="https://your-embedder-base-url/v1" \
EMBEDDER_API_KEY="your-embedder-api-key" \
EMBEDDER_MODEL="BAAI/bge-m3" \
bash install_mirofish.sh
```
