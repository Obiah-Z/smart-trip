# Smart Trip Demo

一个可运行的最小演示项目，用于复刻简历中的“智能旅行规划与决策系统”核心闭环。

## 技术栈
- Backend: FastAPI + SQLite
- Frontend: Vue 3 + Vite
- Mode: Offline demo / mock-first

## 能力
- 自然语言旅行需求输入
- 结构化槽位提取
- Context Assembly
- Memory 读取与回写
- 本地 RAG 检索
- Skill Registry + MCP Mock Gateway
- 串行多 Agent 协作
- 单页可视化控制台

## Skills 在哪里
这个项目现在按 skill 目录组织，说明文件和脚本放在一起：

```bash
skills/public/
```

当前已实现的 skills 目录：
- [skills/public/weather-lookup](/home/obiah/Desktop/smart-trip/skills/public/weather-lookup)
- [skills/public/attraction-search](/home/obiah/Desktop/smart-trip/skills/public/attraction-search)
- [skills/public/hotel-search](/home/obiah/Desktop/smart-trip/skills/public/hotel-search)
- [skills/public/route-plan](/home/obiah/Desktop/smart-trip/skills/public/route-plan)
- [skills/public/knowledge-snapshot](/home/obiah/Desktop/smart-trip/skills/public/knowledge-snapshot)

每个目录里都包含：
- `SKILL.md`
- `scripts/run.py`

对应的 `SKILL.md`：
- [skills/public/weather-lookup/SKILL.md](/home/obiah/Desktop/smart-trip/skills/public/weather-lookup/SKILL.md)
- [skills/public/attraction-search/SKILL.md](/home/obiah/Desktop/smart-trip/skills/public/attraction-search/SKILL.md)
- [skills/public/hotel-search/SKILL.md](/home/obiah/Desktop/smart-trip/skills/public/hotel-search/SKILL.md)
- [skills/public/route-plan/SKILL.md](/home/obiah/Desktop/smart-trip/skills/public/route-plan/SKILL.md)
- [skills/public/knowledge-snapshot/SKILL.md](/home/obiah/Desktop/smart-trip/skills/public/knowledge-snapshot/SKILL.md)

这些 skills 通过下面两层接入主流程：
- Skill 注册表：[backend/app/core/skill_registry.py](/home/obiah/Desktop/smart-trip/backend/app/core/skill_registry.py)
- 脚本执行器：[backend/app/core/skill_script_runner.py](/home/obiah/Desktop/smart-trip/backend/app/core/skill_script_runner.py)

旧的 `backend/app/skills` 目录已经退出运行链路，实际执行统一走 `skills/public/*/scripts/run.py`。

当前主流程已经支持三件事：
- 自动扫描 `skills/public/*/SKILL.md` 注册技能
- 基于 `SKILL.md` 元数据和说明动态选择技能
- 按依赖顺序执行技能，并把选择原因返回前端

## 怎么单独调用 Skills
列出全部 skills：

```bash
curl http://127.0.0.1:8002/api/skills
```

直接调用天气 skill：

```bash
curl -X POST http://127.0.0.1:8002/api/skills/weather.lookup/invoke \
  -H 'Content-Type: application/json' \
  -d '{"payload":{"destination":"北京"}}'
```

直接调用路线规划 skill：

```bash
curl -X POST http://127.0.0.1:8002/api/skills/route.plan/invoke \
  -H 'Content-Type: application/json' \
  -d '{"payload":{"destination":"北京","days":3,"attraction_names":["故宫","颐和园","簋街"]}}'
```

## 启动方式
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
