---
name: hotel-search
skill_id: hotel.search
display_name: 酒店搜索
provider: local_script
priority: 30
depends_on: []
trigger_keywords: ["酒店", "住宿", "民宿", "安静", "预算", "住哪里"]
input_schema: {"destination": "string", "budget": "number", "preferences": "string[]"}
example_payload: {"destination": "北京", "budget": 4000, "preferences": ["quiet_hotel"]}
sandbox_policy: {"timeout_seconds": 5, "memory_mb": 128, "cpu_seconds": 2, "max_open_files": 32, "allow_network": false, "allow_subprocess": false, "writable_roots": []}
description: Use this skill when the user asks for hotel recommendations, quiet accommodation, budget-sensitive lodging, or wants a stay area recommendation tied to travel preferences and spend limits.
---

# Hotel Search Skill

## What This Skill Does

This skill returns hotel candidates filtered by destination, budget, and user preferences.

Implementation files:
- [SKILL.md](/home/obiah/Desktop/smart-trip/skills/public/hotel-search/SKILL.md)
- [scripts/run.py](/home/obiah/Desktop/smart-trip/skills/public/hotel-search/scripts/run.py)

Execution entry:
- `POST /api/skills/hotel.search/invoke`

## When to Use

Use this skill when the user asks:
- “北京有没有安静一点的酒店”
- “预算 4000 住三晚推荐什么酒店”
- “杭州适合安静住宿的区域和酒店有哪些”

## Input

```json
{
  "payload": {
    "destination": "北京",
    "budget": 4000,
    "preferences": ["quiet_hotel"]
  }
}
```

## Example

```bash
curl -X POST http://127.0.0.1:8002/api/skills/hotel.search/invoke \
  -H 'Content-Type: application/json' \
  -d '{"payload":{"destination":"北京","budget":4000,"preferences":["quiet_hotel"]}}'
```
