---
name: attraction-search
skill_id: attraction.search
display_name: 景点搜索
provider: local_script
priority: 20
depends_on: []
trigger_keywords: ["景点", "地标", "美食", "文化", "自然", "推荐", "citywalk", "打卡", "博物馆"]
input_schema: {"destination": "string", "preferences": "string[]", "days": "number", "pace": "string", "excluded_attractions": "string[]"}
example_payload: {"destination": "北京", "preferences": ["culture", "food"], "days": 3, "pace": "balanced", "excluded_attractions": ["故宫"]}
sandbox_policy: {"timeout_seconds": 5, "memory_mb": 128, "cpu_seconds": 2, "max_open_files": 32, "allow_network": false, "allow_subprocess": false, "writable_roots": []}
description: Use this skill when the user asks for attractions, landmarks, food streets, cultural spots, or destination recommendations filtered by travel preferences such as food, culture, or nature.
---

# Attraction Search Skill

## What This Skill Does

This skill filters attraction candidates by destination, preferences, travel pace, and day count.

Implementation files:
- [SKILL.md](/home/obiah/Desktop/smart-trip/skills/public/attraction-search/SKILL.md)
- [scripts/run.py](/home/obiah/Desktop/smart-trip/skills/public/attraction-search/scripts/run.py)

Execution entry:
- `POST /api/skills/attraction.search/invoke`

## When to Use

Use this skill when the user asks:
- “北京有哪些文化景点”
- “给我推荐杭州美食和自然景点”
- “上海适合 citywalk 的地方有哪些”

## Input

```json
{
  "payload": {
    "destination": "北京",
    "preferences": ["culture", "food"],
    "days": 3,
    "pace": "balanced",
    "excluded_attractions": ["故宫"]
  }
}
```

## Example

```bash
curl -X POST http://127.0.0.1:8002/api/skills/attraction.search/invoke \
  -H 'Content-Type: application/json' \
  -d '{"payload":{"destination":"北京","preferences":["culture","food"],"days":3,"pace":"balanced","excluded_attractions":["故宫"]}}'
```
