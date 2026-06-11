---
name: weather-lookup
skill_id: weather.lookup
display_name: 天气查询
provider: local_script
priority: 10
depends_on: []
trigger_keywords: ["天气", "气温", "下雨", "外套", "步行", "适合旅游", "防晒"]
input_schema: {"destination": "string"}
example_payload: {"destination": "北京"}
sandbox_policy: {"timeout_seconds": 5, "memory_mb": 128, "cpu_seconds": 2, "max_open_files": 32, "allow_network": false, "allow_subprocess": false, "writable_roots": []}
description: Use this skill when the user asks for destination weather, travel-day weather suitability, packing suggestions, or wants to validate whether a city is suitable for walking and outdoor activities before planning an itinerary.
---

# Weather Lookup Skill

## What This Skill Does

This skill returns weather summary and travel advice for a destination.

Implementation files:
- [SKILL.md](/home/obiah/Desktop/smart-trip/skills/public/weather-lookup/SKILL.md)
- [scripts/run.py](/home/obiah/Desktop/smart-trip/skills/public/weather-lookup/scripts/run.py)

Execution entry:
- `POST /api/skills/weather.lookup/invoke`

## When to Use

Use this skill when the user asks:
- “北京这几天适合旅游吗”
- “杭州天气怎么样，适合步行吗”
- “去成都要不要带外套”

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
curl -X POST http://127.0.0.1:8002/api/skills/weather.lookup/invoke \
  -H 'Content-Type: application/json' \
  -d '{"payload":{"destination":"北京"}}'
```
