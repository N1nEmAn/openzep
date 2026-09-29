<!-- Banner -->
<div align="center">

![OpenZep Banner](./docs/banner.png)

# OpenZep

**Self-hosted Zep API-compatible memory service powered by Graphiti knowledge graph.**

[![License](https://img.shields.io/badge/license-OpenZep%20Proprietary-red?style=flat-square)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.11--3.12-blue?style=flat-square&logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![Graphiti](https://img.shields.io/badge/graphiti--core-0.28+-orange?style=flat-square)](https://github.com/getzep/graphiti)
[![Neo4j](https://img.shields.io/badge/Neo4j-5-blue?style=flat-square&logo=neo4j)](https://neo4j.com)

[快速开始](#快速开始) · [API 文档](#api-endpoints) · [配置](#configuration) · [架构](#architecture) · [许可证](#license)

</div>

---

> Zep Cloud 于 2025 年 4 月废弃开源社区版，但大量应用仍依赖 Zep API 格式。
> **OpenZep** 填补这一空白：完全自托管的 Zep API 兼容服务，底层使用 Graphiti 时序知识图谱引擎，支持接入任意 OpenAI 兼容 LLM API。

---

## ✨ 核心特性

- **无缝替换 Zep Cloud** — 已有 Zep 应用零改动迁移，只需修改 endpoint
- **自由选择 LLM** — 支持 Claude、GPT、SiliconFlow、Ollama 等任意 OpenAI 兼容 API
- **完全自托管** — 数据不出本地，无订阅费，无隐私风险
- **真实图谱记忆** — 基于 Graphiti 时序知识图谱，自动提取实体关系，非简单向量检索
- **完整 API 覆盖** — 实现全部 20 个 Zep V2 REST API 端点
- **Docker 一键部署** — 开箱即用

---

## 快速开始

### 前置要求

- Docker & Docker Compose
- 任意 OpenAI 兼容 LLM API Key

如果你要用 `OPENZEP_INSTALL_MODE=local` 本机运行后端，再额外准备：

- Python 3.11 或 3.12
- 建议先执行 `python3 --version`
- 如果系统里同时有多个 Python，可用 `PYTHON_BIN=python3.12 bash setup.sh` 指定解释器

### 一键启动

```bash
# 1. 克隆项目
git clone https://github.com/N1nEmAn/openzep.git
cd openzep

# 2. 运行 Docker 安装脚本
bash setup_docker.sh

# 3. 验证
curl http://localhost:8000/healthz
# {"status": "ok"}
```

这个脚本会自动处理 Docker 场景下的地址问题。
如果你填的是宿主机上的本地网关或代理，例如 `http://localhost:11434/v1` 或 `http://127.0.0.1:8080/v1`，脚本会在写入 `.env` 时自动改成 `http://host.docker.internal:...`，避免容器内无法访问宿主机服务。

> `docker-compose.yml` 也已内置 `host.docker.internal:host-gateway`，用于 Linux 下访问宿主机。

### 最简配置（仅三行）

```env
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://api.siliconflow.cn/v1
LLM_MODEL=Qwen/Qwen2.5-72B-Instruct
```

> **注意**：如果你的 LLM 端点不支持 embedding（如 Anthropic 官方 API），需额外配置 `EMBEDDER_*` 指向支持 embedding 的服务（SiliconFlow、OpenAI 均支持）。

### 接入现有 Zep 应用

如果你接入的是 **MiroFish**，不要把下面这段 `ZepClient(...)` 示例手动加到源码里。

直接运行：

```bash
bash install_mirofish.sh
```

按提示填写 `LLM API`、`OpenZep API Key`、`OpenZep URL` 和 `MiroFish 路径` 即可。

默认会走 `docker` 安装模式，并在启动容器前自动写好 `.env`：

- 自动配置 `LLM_*` / `EMBEDDER_*`
- 自动修正 Docker 内访问宿主机的 `localhost` / `127.0.0.1`
- 自动写入 `NEO4J_PASSWORD`
- 自动更新 MiroFish 的 `ZEP_BASE_URL`、`ZEP_API_KEY` 和关键 Zep 客户端文件
- 如果检测到 MiroFish 使用 Docker Compose，会自动把容器内需要的 `localhost` / `127.0.0.1` 改成 `host.docker.internal`
- 会自动生成 compose override 文件，为 `mirofish` 服务补上 `host.docker.internal:host-gateway`

如果你明确要本机直接跑 `uvicorn`，可以切到本地模式：

```bash
OPENZEP_INSTALL_MODE=local bash install_mirofish.sh
```

详细说明见 [INSTALL.md](./INSTALL.md)。

下面这段 Python 示例，适用于你自己写的独立 Zep 客户端应用：

```python
from zep_python import ZepClient

client = ZepClient(
    api_key="your-api-key",   # .env 中的 API_KEY，留空则不填
    base_url="http://localhost:8000"
)
```

---

## 实测验证：与 MiroFish 完整集成

OpenZep 已通过与 [MiroFish](https://github.com/666ghj/MiroFish)（多智能体舆论模拟系统）的完整集成测试，验证了全链路兼容性。

### 测试环境

- **openzep** v0.2.0（本次修复版本）
- **mirofish** latest，Docker 部署
- **LLM**：Claude Opus 4.6（通过 OpenAI 兼容接口）
- **Embedder**：BAAI/bge-m3（SiliconFlow）

### 测试流程

1. **图谱构建**：上传 48KB 种子文档，自动提取本体（10种实体类型 + 10种关系类型）
2. **Episode 处理**：异步并行处理 68 个 episode，全部完成
3. **图谱结果**：**161 节点，190 条边**，耗时 966 秒
4. **多智能体模拟**：161 个 Agent 并行运行，Twitter + Reddit 双平台，**168 轮模拟**
5. **总计交互**：**7000+ 次 Agent 行动**
6. **报告生成**：基于模拟数据自动生成结构化预测报告

### 截图

**总览**

<div align="center"><img src="./docs/overview.jpg" width="500"></div>

**图谱可视化（161节点，190边）**

<div align="center"><img src="./docs/graph-visual-1.jpg" width="500"></div>

<div align="center"><img src="./docs/graph-visual-2.jpg" width="500"></div>

**Simulation 准备阶段（161个Agent人设生成）**

<div align="center"><img src="./docs/agent-1.jpg" width="500"></div>

<div align="center"><img src="./docs/agent-2.jpg" width="500"></div>

**预测报告总览**

<div align="center"><img src="./docs/report.jpg" width="500"></div>

### 本次修复的关键兼容性问题

| 问题 | 影响 | 修复方案 |
|------|------|----------|
| 仅支持 `Bearer` 鉴权格式 | mirofish 使用 `Api-Key` 格式，鉴权失败 | 同时支持两种格式 |
| episode 同步处理导致超时 | 大批量 episode 处理超时，图谱构建失败 | 改为异步后台 + Semaphore 限流 + 进度轮询 |
| MiroFish 动态 ontology 未生效 | 所有实体都退化成 `ExtractedEntity`，图谱类型单一 | 接入 `/entity-types`，将 ontology 注入 Graphiti 提取流程，仅在无自定义标签时回退 |
| 空图谱查询抛出异常 | 初始化阶段报错 | 捕获异常返回空列表 |
| `EpisodeResponse` 缺少 `processed` 字段 | mirofish 轮询状态卡死 | 添加 `processed: bool = True` |

---

## Architecture

<div align="center">

![Architecture](./docs/architecture.png)

</div>

## API Endpoints

### Sessions

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v2/sessions` | 创建会话 |
| `GET` | `/api/v2/sessions` | 列出所有会话 |
| `POST` | `/api/v2/sessions/search` | 跨会话语义搜索 |
| `GET` | `/api/v2/sessions/{id}` | 获取会话详情 |
| `PATCH` | `/api/v2/sessions/{id}` | 更新会话 metadata |
| `DELETE` | `/api/v2/sessions/{id}` | 删除会话 |

### Memory

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v2/sessions/{id}/memory` | 添加消息，触发知识图谱更新 |
| `GET` | `/api/v2/sessions/{id}/memory` | 获取记忆上下文（图谱 facts） |
| `DELETE` | `/api/v2/sessions/{id}/memory` | 清空会话记忆 |
| `GET` | `/api/v2/sessions/{id}/messages` | 获取消息历史 |
| `GET` | `/api/v2/sessions/{id}/messages/{uuid}` | 获取单条消息 |
| `PATCH` | `/api/v2/sessions/{id}/messages/{uuid}` | 更新消息 metadata |

### Users

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v2/users` | 创建用户 |
| `GET` | `/api/v2/users` | 列出所有用户 |
| `GET` | `/api/v2/users/{id}` | 获取用户详情 |
| `PATCH` | `/api/v2/users/{id}` | 更新用户信息 |
| `DELETE` | `/api/v2/users/{id}` | 删除用户 |
| `GET` | `/api/v2/users/{id}/sessions` | 获取用户的所有会话 |

### Facts & Graph

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v2/facts/{uuid}` | 获取单个知识图谱 fact |
| `DELETE` | `/api/v2/facts/{uuid}` | 删除单个 fact |
| `POST` | `/api/v2/graph` | 添加 episode（单条） |
| `POST` | `/api/v2/graph-batch` | 批量添加 episode |
| `GET` | `/api/v2/graph/episodes/{uuid}` | 获取单个 episode 详情 |
| `DELETE` | `/api/v2/graph/episodes/{uuid}` | 删除单个 episode（级联清理关联边与孤儿节点） |
| `POST` | `/api/v2/graph/search` | 知识图谱语义搜索 |
| `GET` | `/api/v2/graph/node/{uuid}` | 获取单个图节点 |
| `GET` | `/api/v2/graph/node/{uuid}/entity-edges` | 获取节点关联的边 |
| `GET` | `/api/v2/graph/{graph_id}/statistics` | 获取图谱统计信息 |
| `DELETE` | `/api/v2/graph/{graph_id}` | 删除整个图谱 |
| `GET` | `/api/v2/graph/list-all` | 列出所有知识图谱（含节点/边数量） |

### Batch ingestion

兼容 `zep-cloud` SDK 3.25+ 的批量图谱写入流程：先创建 batch，再添加
`graph_episode` items，最后调用 process 并轮询状态。

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v2/batches` | 创建草稿 batch |
| `POST` | `/api/v2/batches/{id}/items` | 添加图谱 episode items |
| `POST` | `/api/v2/batches/{id}/process` | 开始异步处理 |
| `GET` | `/api/v2/batches/{id}` | 查询 batch 状态 |
| `GET` | `/api/v2/batches/{id}/items` | 查询 item 状态 |

交互式 API 文档：`http://localhost:8000/docs`

---

## Configuration

所有配置通过环境变量（`.env` 文件）控制：

```env
# LLM（必填）
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://api.siliconflow.cn/v1
LLM_MODEL=Qwen/Qwen2.5-72B-Instruct
LLM_SMALL_MODEL=Qwen/Qwen2.5-7B-Instruct    # 可选，用于轻量任务

# Embedder（可选，留空则复用 LLM 配置）
# EMBEDDER_API_KEY=
# EMBEDDER_BASE_URL=
EMBEDDER_MODEL=BAAI/bge-m3

# Neo4j
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password

# OpenZep API Key（可选，留空则禁用认证）
API_KEY=your-openzep-api-key
```

### 常见 LLM 提供商配置示例

**SiliconFlow（推荐，支持 embedding）**
```env
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://api.siliconflow.cn/v1
LLM_MODEL=Qwen/Qwen2.5-72B-Instruct
EMBEDDER_MODEL=BAAI/bge-m3
```

**OpenAI**
```env
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o
EMBEDDER_MODEL=text-embedding-3-small
```

**本地 Ollama**
```env
LLM_API_KEY=ollama
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=llama3.1:8b
EMBEDDER_MODEL=nomic-embed-text
```

**Anthropic / 不支持 embedding 的 LLM**

如果你的 LLM 端点不提供 embedding（如 Anthropic 官方 API、部分本地代理），需单独配置 Embedder：

```env
# LLM 用 Anthropic 兼容代理
LLM_API_KEY=your-llm-key
LLM_BASE_URL=http://your-proxy/v1
LLM_MODEL=anthropic/claude-sonnet-4.6

# Embedder 单独指向支持 embedding 的服务（SiliconFlow / OpenAI 均可）
EMBEDDER_API_KEY=sk-xxx
EMBEDDER_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDER_MODEL=BAAI/bge-m3
```

### 常见问题排查

**构建图谱时报 401 unauthorized**

两类根因，逐条排查：

1. 客户端的 `ZEP_API_KEY` 与 `openzep/.env` 里的 `API_KEY` 不完全一致。两边 key 必须逐字符相同（注意前后空格、换行）。最稳的做法是两边都留空（`API_KEY=`），即可关闭鉴权。
2. 客户端连到的不是你的 OpenZep，而是官方 Zep Cloud。症状是 `server: cloudflare`、`status_code: 401`。
   - MiroFish 在 Docker 里跑时，`ZEP_BASE_URL` **不能**写 `http://localhost:8000/api/v2`（容器里的 localhost 指向容器自己），要写成宿主机可达地址，例如 `http://host.docker.internal:8000/api/v2` 或宿主机局域网 IP `http://192.168.x.x:8000/api/v2`。
   - 地址末尾必须带 `/api/v2`。

改完 `.env` 后必须重建容器，否则不会重新加载环境变量：

```bash
docker compose up -d --force-recreate
# MiroFish 侧确认它真正读到的值：
docker exec -it mirofish sh -lc 'env | grep ^ZEP_'
```

直接用 curl 验证 OpenZep 本身是否正常（替换 KEY 和 IP）：

```bash
curl -i -H "Authorization: Bearer YOUR_KEY" -H "Content-Type: application/json" \
  -d '{"graph_id":"test","name":"test"}' http://NAS_IP:8000/api/v2/graph/create
# 200 = OpenZep 正常，问题在客户端配置；401 = 两边 key 不一致；连不上 = 地址或网络问题
```

> 自 v0.x 起，401 错误体已包含上述排查指引，无需翻文档。

**构建图谱时 `批量发送到Zep失败 ... timed out`（issue #4）**

上游 LLM 太慢（大模型、高延迟代理）导致单个 episode 超时。OpenZep 默认 bulk=90s / single=60s，可在 `openzep/.env` 调大：

```env
GRAPH_BULK_TIMEOUT_SECONDS=300
GRAPH_SINGLE_TIMEOUT_SECONDS=120
```

超时只是某条 episode 写入失败，不影响整体流程；调大窗口通常能消除告警。

**图谱为空（Nodes: 0, Edges: 0）**

通常是上游 LLM 解析失败或返回格式不符合 schema。检查 OpenZep 日志 `docker compose logs -f openzep`，确认模型确实有输出。换一个更强的模型或更稳定的端点通常能解决。

---

## 本地开发

```bash
# 1. 启动 Neo4j
docker run -d --name neo4j --restart unless-stopped \
  -p 7687:7687 -p 7474:7474 \
  -e NEO4J_AUTH=neo4j/password123 neo4j:5

# 2. 配置环境变量
cp .env.example .env
vim .env  # 填入 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL

# 3. 安装依赖
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4. 启动开发服务器
uvicorn main:app --reload

# 或后台运行
nohup .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 > openzep.log 2>&1 &
```

> **启动时的索引报错**：首次启动或 Neo4j 容器已存在数据时，日志中会出现 `EquivalentSchemaRuleAlreadyExists` 错误，这是 graphiti-core 在 Neo4j 5 上重复创建索引时的已知行为，**不影响服务正常运行**，可忽略。

> **uvicorn 找不到**：如果直接运行 `uvicorn` 提示 command not found，请确保已激活 venv（`source .venv/bin/activate`），或使用完整路径 `.venv/bin/uvicorn`。

---

## Star History

[![Star History Chart](https://api.star-history.com/image?repos=N1nEmAn/openzep&type=date&legend=top-left)](https://www.star-history.com/?repos=N1nEmAn%2Fopenzep&type=date&legend=top-left)

---

## License

Copyright © 2026 [N1nEmAn](https://github.com/N1nEmAn). All rights reserved.

This software is licensed under the **OpenZep Proprietary License**. See [LICENSE](./LICENSE) for full terms.

**Summary:**
- The original author (N1nEmAn) retains exclusive commercial rights
- You may use this software for personal, non-commercial purposes
- Any redistribution, fork, or derivative work must clearly credit the original author
- Commercial use by third parties requires written permission from the author
- See [LICENSE](./LICENSE) for complete terms

---

<div align="center">

Made with by [N1nEmAn](https://github.com/N1nEmAn)

**OpenZep** — *Memory that thinks, not just remembers.*

</div>
