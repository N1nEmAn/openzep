# OpenZep 接入 MiroFish 安装说明

## 一体化安装

在 `openzep` 目录执行：

```bash
bash install_mirofish.sh
```

这是推荐入口。脚本默认会：

- 先执行 `setup_docker.sh`
- 在启动 Docker 前写好 `openzep/.env`
- 再执行 `setup_mirofish.sh`
- 自动把 MiroFish 指到 `OpenZep`

如果你不想用 Docker，而是想本机直接跑 `uvicorn`：

```bash
OPENZEP_INSTALL_MODE=local bash install_mirofish.sh
```

本地模式要求 `python3` 为 3.11 或 3.12。先检查：

```bash
python3 --version
which python3
```

注意这里看的是 `python3`，不是 `python`。如果机器上同时装了多个 Python，可以这样指定：

```bash
PYTHON_BIN=python3.12 OPENZEP_INSTALL_MODE=local bash install_mirofish.sh
```

## 交互式安装说明

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
- 在 Docker 模式下，把容器内需要的 `localhost` / `127.0.0.1` 自动改成 `host.docker.internal`
- 在 Docker 模式下，先写入 `NEO4J_PASSWORD`，再启动 `docker compose`
- 更新 MiroFish 根目录 `.env` 中的 `ZEP_API_KEY` 和 `ZEP_BASE_URL`
- 自动替换 MiroFish 后端关键文件中的 Zep 客户端配置
- 验证 `http://localhost:8000/healthz` 是否可访问

不需要手动把 `from zep_python import ZepClient` 粘贴到 MiroFish 的任何源码文件里。

## Docker 部署

如果你使用 Docker 运行 OpenZep，建议直接执行：

```bash
bash setup_docker.sh
```

脚本会自动处理 Docker 场景下的 `.env`：

- `LLM_BASE_URL=http://localhost:...` 会自动改成 `http://host.docker.internal:...`
- `EMBEDDER_BASE_URL=http://127.0.0.1:...` 也会自动改成容器可访问的地址
- 然后再执行 `docker compose up -d --build`

这可以避免容器里访问不到宿主机代理、Ollama、one-api、new-api 等本地服务。

## 脚本说明

`install_mirofish.sh`

- 一体化入口
- 默认会先执行 `setup_docker.sh`
- 再执行 `setup_mirofish.sh`
- 可通过 `OPENZEP_INSTALL_MODE=local` 切换为 `setup.sh`

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
OPENZEP_INSTALL_MODE="docker" \
LLM_BASE_URL="https://your-llm-base-url/v1" \
LLM_API_KEY="your-llm-api-key" \
LLM_MODEL="your-llm-model" \
API_KEY="your-openzep-api-key" \
NEO4J_PASSWORD="your-neo4j-password" \
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
