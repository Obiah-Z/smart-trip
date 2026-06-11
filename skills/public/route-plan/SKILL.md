---
name: route-plan
skill_id: route.plan
display_name: 路线规划
provider: local_script
priority: 40
depends_on: ["attraction.search"]
trigger_keywords: ["行程", "路线", "规划", "安排", "攻略", "几日游", "按天"]
input_schema: {"destination": "string", "days": "number", "pace": "string", "attraction_names": "string[]", "attraction_items": "object[]", "excluded_attractions": "string[]"}
example_payload: {"destination": "北京", "days": 3, "pace": "balanced", "attraction_names": ["故宫", "颐和园", "簋街"], "attraction_items": [{"name": "故宫", "type": "culture", "area": "东城中轴"}], "excluded_attractions": ["故宫"]}
sandbox_policy: {"timeout_seconds": 5, "memory_mb": 128, "cpu_seconds": 2, "max_open_files": 32, "allow_network": false, "allow_subprocess": false, "writable_roots": []}
description: Use this skill when the user asks for a multi-day route, daily arrangement, itinerary sequencing, attraction ordering, or wants to convert a list of places into a day-by-day travel plan.
---

# Route Plan Skill

## What This Skill Does

This skill converts a destination, day count, travel pace, and attraction candidates into a day-by-day route.

Implementation files:
- [SKILL.md](/home/obiah/Desktop/smart-trip/skills/public/route-plan/SKILL.md)
- [scripts/run.py](/home/obiah/Desktop/smart-trip/skills/public/route-plan/scripts/run.py)

Execution entry:
- `POST /api/skills/route.plan/invoke`

## When to Use

Use this skill when the user asks:
- “帮我排一个北京三日行程”
- “把故宫、颐和园、簋街分成三天”
- “给我一个按天路线”

## Input

```json
{
  "payload": {
    "destination": "北京",
    "days": 3,
    "pace": "balanced",
    "attraction_names": ["故宫", "颐和园", "簋街"],
    "excluded_attractions": ["故宫"],
    "attraction_items": [
      {"name": "故宫", "type": "culture", "area": "东城中轴"},
      {"name": "颐和园", "type": "nature", "area": "海淀西线"}
    ]
  }
}
```

## Example

```bash
curl -X POST http://127.0.0.1:8002/api/skills/route.plan/invoke \
  -H 'Content-Type: application/json' \
  -d '{"payload":{"destination":"北京","days":3,"pace":"balanced","attraction_names":["故宫","颐和园","簋街"],"excluded_attractions":["故宫"],"attraction_items":[{"name":"故宫","type":"culture","area":"东城中轴"},{"name":"颐和园","type":"nature","area":"海淀西线"}]}}'
```
