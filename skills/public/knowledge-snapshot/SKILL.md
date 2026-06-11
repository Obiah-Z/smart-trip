---
name: knowledge-snapshot
skill_id: knowledge.snapshot
display_name: 知识快照
provider: local_script
priority: 90
depends_on: []
trigger_keywords: ["MCP", "skill", "skills", "工具能力", "知识桥接", "系统状态", "外部知识"]
input_schema: {"destination": "string"}
example_payload: {"destination": "北京"}
sandbox_policy: {"timeout_seconds": 5, "memory_mb": 128, "cpu_seconds": 2, "max_open_files": 32, "allow_network": false, "allow_subprocess": false, "writable_roots": []}
description: Use this skill when the user wants to inspect external travel knowledge capability status, verify MCP bridge availability, or demonstrate how the system can expose external-tool-backed skill execution in a controlled way.
---

# Knowledge Snapshot Skill

## What This Skill Does

This skill returns a lightweight knowledge bridge status payload through the MCP adapter layer.

Implementation files:
- [SKILL.md](/home/obiah/Desktop/smart-trip/skills/public/knowledge-snapshot/SKILL.md)
- [scripts/run.py](/home/obiah/Desktop/smart-trip/skills/public/knowledge-snapshot/scripts/run.py)

Execution entry:
- `POST /api/skills/knowledge.snapshot/invoke`

## When to Use

Use this skill when the user asks:
- “系统现在有哪些外部知识能力”
- “MCP 接入有没有生效”
- “给我看一下当前知识桥接状态”

## Input

```json
{
  "payload": {
    "destination": "北京"
  }
}
```

## Example

```bash
curl -X POST http://127.0.0.1:8002/api/skills/knowledge.snapshot/invoke \
  -H 'Content-Type: application/json' \
  -d '{"payload":{"destination":"北京"}}'
```
