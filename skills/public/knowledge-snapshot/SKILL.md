---
name: knowledge-snapshot
skill_id: knowledge.snapshot
display_name: 知识快照
provider: local_script
priority: 90
depends_on: []
trigger_keywords: ["MCP", "skill", "skills", "工具能力", "知识桥接", "系统状态", "外部知识", "调试", "能力列表", "可用能力"]
input_schema: {"destination": "string"}
example_payload: {"destination": "北京"}
sandbox_policy: {"timeout_seconds": 5, "memory_mb": 128, "cpu_seconds": 2, "max_open_files": 32, "allow_network": false, "allow_subprocess": false, "writable_roots": []}
description: Use this skill when the user or developer asks to inspect external travel knowledge capability status, MCP bridge availability, skill/tool integration state, or to demonstrate controlled external-tool-backed execution in the debug pipeline.
---

# Knowledge Snapshot Skill

## Business Role

Use this Skill as a controlled system-introspection capability. It returns a compact status payload describing the local knowledge bridge and external-tool integration surface.

This Skill is primarily for developer/debug scenarios. It should not appear in the user-facing travel recommendation unless the user explicitly asks about system capabilities.

Implementation files:
- `skills/public/knowledge-snapshot/SKILL.md`
- `skills/public/knowledge-snapshot/scripts/run.py`

Runtime entry:
- API: `POST /api/skills/knowledge.snapshot/invoke`
- Script: `python skills/public/knowledge-snapshot/scripts/run.py --payload-json '<json>'`

## When to Use

- 用户问“系统现在有哪些外部知识能力”
- 用户问“MCP 接入有没有生效”
- 用户问“当前有哪些工具或 Skills”
- 开发调试页需要展示受控工具桥接状态
- 需要证明 Skill 可在 Sandbox 内被调度执行

## Do Not Use

- 不要在普通旅行规划中自动调用
- 不要把它作为 RAG 检索替代品，旅行知识检索应走 retrieval/RAG 管线
- 不要向普通用户展示内部路径、密钥、环境变量或实现细节
- 不要把此 Skill 的 `status=ok` 解释为所有外部服务实时可用

## Input Contract

```json
{
  "destination": "北京"
}
```

Field rules:

| Field | Type | Required | Notes |
|---|---:|---:|---|
| `destination` | string | no | 可选的目的地上下文，仅用于说明本次检查与哪个旅行场景相关。 |

## Output Contract

```json
{
  "source": "mock_mcp",
  "status": "ok",
  "capability": "travel_knowledge_bridge",
  "destination": "北京",
  "adapters": ["local_skill_registry", "sandbox_runner"],
  "safe_for_user_view": false
}
```

Output semantics:

| Field | Meaning |
|---|---|
| `source` | 当前桥接来源。当前为本地模拟适配层。 |
| `status` | 桥接检查状态。 |
| `capability` | 能力名称。 |
| `destination` | 当前检查上下文。 |
| `adapters` | 被检查的能力面。 |
| `safe_for_user_view` | 是否适合直接展示到用户视图。 |

## Composition Patterns

### Developer Debug

Use with Stage Trace and Runtime Snapshot to verify:

- Skill registry loaded correctly
- Sandbox execution can return JSON
- Tool result can be injected into Context
- Selected Skill reasoning is visible

### User-Facing System Question

If the user asks “你现在能调用哪些能力”, call this Skill and summarize in plain language. Do not reveal internal filesystem paths or sandbox policy internals unless the user is explicitly debugging.

## Failure Handling

- If this Skill fails, the system can still complete ordinary travel planning.
- If `status` is not `ok`, show it only in developer/debug view unless the user asked directly.
- Keep the output compact; this is a status snapshot, not a full diagnostic report.

## Example

```bash
curl -X POST http://127.0.0.1:8001/api/skills/knowledge.snapshot/invoke \
  -H 'Content-Type: application/json' \
  -d '{"payload":{"destination":"北京"}}'
```
