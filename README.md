<!-- Banner -->
<div align="center">

![OpenZep Banner](./docs/banner.png)

# OpenZep

**Self-hosted Zep API-compatible memory service powered by Graphiti knowledge graph.**

[![License](https://img.shields.io/badge/license-OpenZep%20Proprietary-red?style=flat-square)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.12+-blue?style=flat-square&logo=python)](https://python.org)
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

### 一键启动

```bash
# 1. 克隆项目
git clone https://github.com/N1nEmAn/openzep.git
cd openzep

# 2. 配置
cp .env.example .env
vim .env  # 填入 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL

# 3. 启动
docker compose up -d

# 4. 验证
curl http://localhost:8000/healthz
# {"status": "ok"}
```

### 最简配置（仅三行）

```env
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://api.siliconflow.cn/v1
LLM_MODEL=Qwen/Qwen2.5-72B-Instruct
```

> **注意**：如果你的 LLM 端点不支持 embedding（如 Anthropic 官方 API），需额外配置 `EMBEDDER_*` 指向支持 embedding 的服务（SiliconFlow、OpenAI 均支持）。

### 接入现有 Zep 应用

```python
from zep_python import ZepClient

client = ZepClient(
    api_key="your-api-key",   # .env 中的 API_KEY，留空则不填
    base_url="http://localhost:8000"
)
```

---

## Architecture

<div align="center">

![Architecture](./docs/architecture.png)

</div>
---

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
| `POST` | `/api/v2/graph/search` | 知识图谱语义搜索 |

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

---

## 本地开发

```bash
# 启动 Neo4j
docker run -d --name neo4j -p 7687:7687 -p 7474:7474 \
  -e NEO4J_AUTH=neo4j/password123 neo4j:5

# 安装依赖
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 启动开发服务器
uvicorn main:app --reload
```

---

## Star History

<div align="center">

[![Star History Chart](https://api.star-history.com/svg?repos=N1nEmAn/openzep&type=Date)](https://star-history.com/#N1nEmAn/openzep&Date)

</div>

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
