# Smart Trip

Smart Trip 是一个面向旅行咨询、行程规划与出行决策的智能交互系统。系统支持自然语言需求理解、多轮追问、旅行知识检索、实时工具调用、路线规划、偏好记忆和结果可视化展示，帮助用户更高效地获得可执行的旅行建议。

## 核心能力

- 旅行咨询与行程规划：支持天气、景点、住宿、路线、预算、节奏和餐饮偏好等常见旅行问题。
- 多轮上下文理解：能够在已有方案基础上继续调整预算、住宿、景点排除项和出行偏好。
- Memory 机制：区分短期任务状态和长期用户偏好，支持跨轮次复用有效信息。
- RAG 检索增强：基于本地旅行知识库、BM25 索引和可选向量索引召回相关知识。
- Skill 调用：封装天气查询、景点搜索、酒店推荐、路线规划等可复用业务能力。
- Sandbox 执行：对 Skill 脚本执行做超时、资源和权限限制，降低工具调用风险。
- 多 Agent 协作：复杂任务可拆分为需求拆解、信息整理、方案生成和结果校验等阶段。
- 双视图前端：用户视图聚焦旅行结果，开发调试视图展示链路状态、RAG、Memory、Tool 和 Agent 信息。

## 技术栈

- Backend: Python, FastAPI, SQLite
- Frontend: Vue 3, Vite
- AI / Workflow: OpenAI-compatible API, LangChain / LangGraph-style workflow, RAG, ReAct, Tool Calling, MCP-style skill integration
- Retrieval: Markdown corpus, BM25, optional embedding index

## 目录结构

```text
backend/        后端服务、规划链路、RAG、Memory、Skill、Agent 和 API
frontend/       Vue 前端页面
skills/         可被系统调度的业务 Skill，每个 Skill 包含说明文件和执行脚本
md/             系统设计、流程总结和迭代文档
deploy/         Docker、Nginx 和部署相关配置
```

## Skills

业务 Skill 统一放在：

```text
skills/public/
```

每个 Skill 目录包含：

```text
SKILL.md
scripts/run.py
```

当前主要 Skill 包括：

- `weather.lookup`：天气查询与出行建议
- `attraction.search`：景点与玩法搜索
- `hotel.search`：住宿推荐
- `route.plan`：按天路线规划
- `knowledge.snapshot`：知识与工具能力快照

系统启动后会读取 Skill 元数据，根据用户需求选择合适的 Skill，并通过受限执行环境运行对应脚本。

## 本地启动

后端：

```bash
cd backend
python -m uvicorn app.main:app --reload --port 8001
```

前端：

```bash
cd frontend
npm install
npm run dev
```

生产构建：

```bash
cd frontend
npm run build
```

## 配置

本地环境变量不要提交到仓库。可以参考以下示例文件创建自己的配置：

```text
.env.production.example
backend/.env.example
```

常用配置项包括模型服务地址、API Key、RAG 模式、Embedding 配置、图片生成配置和地图服务配置。
