---
name: itinerary-audit
skill_id: itinerary.audit
display_name: 行程审计
provider: local_script
priority: 60
depends_on: ["route.plan", "budget.optimize"]
trigger_keywords: ["校验", "检查", "审计", "一致性", "冲突", "是否合理", "重新规划", "不想去", "不要去", "预算", "天数", "最终方案"]
input_schema: {"destination": "string", "days": "number", "budget": "number", "pace": "string", "preferences": "string[]", "excluded_attractions": "string[]", "route_days": "object[]", "hotel_options": "object[]", "weather": "object", "budget_optimization": "object"}
example_payload: {"destination": "杭州", "days": 3, "budget": 3000, "pace": "relaxed", "preferences": ["quiet_hotel"], "excluded_attractions": ["西湖"], "route_days": [{"day": 1, "activities": ["西溪湿地"]}], "hotel_options": [{"name": "武林静居酒店", "quiet": true}], "weather": {"summary": "多云"}, "budget_optimization": {"total_estimated": 2800, "budget_breakdown": {"transport": 500}}}
sandbox_policy: {"timeout_seconds": 5, "memory_mb": 128, "cpu_seconds": 2, "max_open_files": 32, "allow_network": false, "allow_subprocess": false, "writable_roots": []}
description: Use this skill when a generated itinerary or follow-up replan needs consistency auditing for day count, excluded attractions, budget limit, hotel preference alignment, route density, weather context, or final plan safety before presenting the result to the user.
---

# Itinerary Audit Skill

## Business Role

Use this Skill as the final consistency checker for generated travel plans. It verifies whether route days, excluded attractions, budget, hotel options, pace, and weather context align with the current user constraints.

This Skill should run after `route.plan` and `budget.optimize`. It does not generate a new itinerary; it returns structured findings that the Reviewer Agent can use.

Implementation files:
- `skills/public/itinerary-audit/SKILL.md`
- `skills/public/itinerary-audit/scripts/run.py`

Runtime entry:
- API: `POST /api/skills/itinerary.audit/invoke`
- Script: `python skills/public/itinerary-audit/scripts/run.py --payload-json '<json>'`

## When to Use

- 复杂多日行程生成后，需要最终校验
- 用户追问“不想去西湖 / 不想故宫”，需要确认最终路线没有回流排除景点
- 用户修改预算后，需要确认预算结果没有超限
- 用户要求轻松/紧凑节奏，需要检查路线密度
- 开发调试时需要解释为什么方案被判定为 approved 或 needs_review

## Do Not Use

- 不要用于简单天气问答
- 不要用于发现新景点，景点发现应使用 `attraction.search`
- 不要用于生成预算，预算生成应使用 `budget.optimize`
- 不要把 audit 的 warning 当成用户不可见错误；warning 是提示 Reviewer 做更保守表述

## Input Contract

```json
{
  "destination": "杭州",
  "days": 3,
  "budget": 3000,
  "pace": "relaxed",
  "preferences": ["quiet_hotel"],
  "excluded_attractions": ["西湖"],
  "route_days": [
    {"day": 1, "activities": ["西溪湿地"]}
  ],
  "hotel_options": [
    {"name": "武林静居酒店", "quiet": true}
  ],
  "weather": {"summary": "多云"},
  "budget_optimization": {
    "total_estimated": 2800,
    "budget_breakdown": {"transport": 500, "accommodation": 1200}
  }
}
```

## Output Contract

```json
{
  "audit_status": "approved",
  "summary": "方案通过核心一致性校验。",
  "passed_checks": [
    {"name": "day_count_match", "passed": true}
  ],
  "issues": [],
  "warnings": [],
  "recommendations": [
    "最终回答可以正常展示。"
  ],
  "safe_to_present": true
}
```

Status values:

| Status | Meaning |
|---|---|
| `approved` | 核心检查通过。 |
| `approved_with_warnings` | 可以展示，但需要提示不确定性。 |
| `needs_review` | 存在硬冲突，Reviewer 应修正或要求补充信息。 |

## Audit Checks

1. `day_count_match`: route day count must equal requested days.
2. `excluded_attractions_absent`: route must not include excluded attractions or obvious aliases.
3. `hotel_available`: multi-day itinerary should include hotel candidates.
4. `budget_within_limit`: estimated total should not exceed user budget.
5. `pace_density_aligned`: relaxed route should not be overloaded; intensive route should not be too empty.
6. `weather_context_available`: weather is useful for planning but missing weather is a warning, not a hard error.

## Composition Patterns

### Final Planning Chain

Recommended chain:

1. `weather.lookup`
2. `attraction.search`
3. `hotel.search`
4. `route.plan`
5. `budget.optimize`
6. `itinerary.audit`

### Exclusion Follow-Up

When the user says “不要西湖，重新规划”, audit should receive `excluded_attractions` and route days. If route activities still include 西湖, audit must return `needs_review`.

## Failure Handling

- Missing route days: return `needs_review`.
- Budget output missing: warn, but do not fail if no budget was specified.
- Hotel missing for multi-day route: warn or issue depending on days and task type.
- Weather missing: warn only.

## Example

```bash
curl -X POST http://127.0.0.1:8001/api/skills/itinerary.audit/invoke \
  -H 'Content-Type: application/json' \
  -d '{"payload":{"destination":"杭州","days":3,"budget":3000,"pace":"relaxed","preferences":["quiet_hotel"],"excluded_attractions":["西湖"],"route_days":[{"day":1,"activities":["西溪湿地"]},{"day":2,"activities":["小河直街"]},{"day":3,"activities":["良渚博物院"]}],"hotel_options":[{"name":"武林静居酒店","quiet":true}],"weather":{"summary":"多云"},"budget_optimization":{"total_estimated":2800}}}'
```
