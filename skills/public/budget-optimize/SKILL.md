---
name: budget-optimize
skill_id: budget.optimize
display_name: 预算优化
provider: local_script
priority: 50
depends_on: ["hotel.search", "route.plan"]
trigger_keywords: ["预算", "花费", "费用", "总预算", "总花费", "省钱", "提升预算", "提高预算", "住宿舒适度", "升级住宿", "预算分配", "控制成本"]
input_schema: {"destination": "string", "days": "number", "budget": "number", "target_budget": "number", "budget_policy": "string", "pace": "string", "preferences": "string[]", "hotel_options": "object[]", "route_days": "object[]", "attraction_items": "object[]"}
example_payload: {"destination": "杭州", "days": 3, "budget": 10000, "target_budget": 10000, "budget_policy": "target_near", "pace": "relaxed", "preferences": ["quiet_hotel", "comfortable_hotel"], "hotel_options": [{"name": "西湖静奢酒店", "pricePerNight": 1280, "comfortScore": 95}], "route_days": [{"day": 1, "activities": ["西溪湿地"]}], "attraction_items": [{"name": "西溪湿地", "cost": 80}]}
sandbox_policy: {"timeout_seconds": 5, "memory_mb": 128, "cpu_seconds": 2, "max_open_files": 32, "allow_network": false, "allow_subprocess": false, "writable_roots": []}
description: Use this skill when the user mentions budget, total cost, spending allocation, cost control, budget upgrade, hotel comfort upgrade, or when a multi-day itinerary needs an explicit budget breakdown and optimization plan based on selected hotels, route days, and attraction ticket costs.
---

# Budget Optimize Skill

## Business Role

Use this Skill as the travel budget allocation and upgrade strategy unit. It converts route days, hotel candidates, attraction costs, user budget, and preference signals into a structured budget plan.

This Skill should run after `hotel.search` and `route.plan`, because it needs lodging candidates and planned route days. It does not search hotels or attractions by itself.

Implementation files:
- `skills/public/budget-optimize/SKILL.md`
- `skills/public/budget-optimize/scripts/run.py`

Runtime entry:
- API: `POST /api/skills/budget.optimize/invoke`
- Script: `python skills/public/budget-optimize/scripts/run.py --payload-json '<json>'`

## When to Use

- 用户说“预算 3000，帮我规划三日游”
- 用户说“帮我把预算提升到 10000”
- 用户说“主要提升住宿舒适度”
- 用户问“这个方案大概要花多少钱”
- 用户问“预算怎么分配更合理”
- 多日行程已经生成酒店和路线，需要给出预算拆分

## Do Not Use

- 不要用于简单天气问答
- 不要在没有路线和酒店候选时给出精确预算
- 不要为了凑满预算硬编消费项目，应把剩余预算标记为 `experience` 或 `buffer`
- 不要覆盖用户明确的预算约束，除非用户表达“提高预算”或“升级”

## Input Contract

```json
{
  "destination": "杭州",
  "days": 3,
  "budget": 10000,
  "target_budget": 10000,
  "budget_policy": "target_near",
  "pace": "relaxed",
  "preferences": ["quiet_hotel", "comfortable_hotel"],
  "hotel_options": [
    {"name": "西湖静奢酒店", "pricePerNight": 1280, "comfortScore": 95}
  ],
  "route_days": [
    {"day": 1, "activities": ["西溪湿地"]}
  ],
  "attraction_items": [
    {"name": "西溪湿地", "cost": 80}
  ]
}
```

Field rules:

| Field | Type | Required | Notes |
|---|---:|---:|---|
| `destination` | string | yes | 当前规划目的地。 |
| `days` | number | yes | 行程天数，用于住宿晚数、餐饮和交通估算。 |
| `budget` | number | no | 当前总预算。没有预算时给出保守估算并标记 warning。 |
| `target_budget` | number | no | 用户明确希望提升或贴近的新预算。 |
| `budget_policy` | string | no | `target_near` 表示尽量贴近预算，常用于预算升级场景。 |
| `pace` | string | no | 节奏会影响餐饮、体验和交通冗余。 |
| `preferences` | string[] | no | 影响酒店升级、本地美食、家庭出行等预算分配。 |
| `hotel_options` | object[] | preferred | 来自 `hotel.search`。 |
| `route_days` | object[] | preferred | 来自 `route.plan`。 |
| `attraction_items` | object[] | preferred | 来自 `attraction.search`，用于门票估算。 |

## Output Contract

```json
{
  "destination": "杭州",
  "budget_status": "within_budget",
  "target_budget": 10000,
  "total_estimated": 10000,
  "remaining_budget": 0,
  "budget_breakdown": {
    "transport": 1666,
    "accommodation": 2560,
    "food": 680,
    "tickets": 160,
    "experience": 4934,
    "buffer": 0
  },
  "selected_hotel": {
    "name": "西湖静奢酒店",
    "pricePerNight": 1280
  },
  "optimization_strategy": {
    "policy": "target_near",
    "upgrade_focus": "accommodation",
    "nights": 2
  },
  "recommendations": [
    "已优先把预算增量用于住宿舒适度提升。"
  ],
  "warnings": []
}
```

Existing consumers should use:
- `budget_breakdown`
- `total_estimated`
- `selected_hotel`
- `recommendations`
- `warnings`

## Optimization Logic

1. Resolve target budget: prefer `target_budget`, then `budget`.
2. Estimate nights as `max(days - 1, 1)` for multi-day trips.
3. Estimate fixed costs:
   - transport from destination/day/budget scale
   - food from days and food preferences
   - tickets from attraction candidates
4. Select hotel:
   - comfort upgrade prefers highest `comfortScore` and affordable price
   - normal mode prefers the first ranked hotel candidate
5. If `budget_policy=target_near`, allocate remaining budget to food upgrade and experience budget instead of leaving a misleading gap.
6. Return warnings for missing budget, missing hotels, missing route, or budget overrun.

## Composition Patterns

### New Budgeted Itinerary

Recommended chain:

1. `weather.lookup`
2. `attraction.search`
3. `hotel.search`
4. `route.plan`
5. `budget.optimize`
6. `itinerary.audit`

### Budget Upgrade Follow-Up

If the user says “预算提升到 10000，主要提升住宿舒适度”, use prior session destination/days/pace, add `comfortable_hotel`, then run this Skill with:

```json
{
  "budget": 10000,
  "target_budget": 10000,
  "budget_policy": "target_near",
  "preferences": ["quiet_hotel", "comfortable_hotel"]
}
```

The final answer should explicitly say what changed in the budget allocation.

## Failure Handling

- Missing budget: return `budget_status=no_budget` and conservative estimates.
- No hotel candidates: set `selected_hotel=null`, keep accommodation estimate conservative, and warn.
- Budget overrun: set `budget_status=over_budget` and include downgrade recommendations.
- Missing route days: still estimate budget from `days`, but warn that route-derived precision is limited.

## Example

```bash
curl -X POST http://127.0.0.1:8001/api/skills/budget.optimize/invoke \
  -H 'Content-Type: application/json' \
  -d '{"payload":{"destination":"杭州","days":3,"budget":10000,"target_budget":10000,"budget_policy":"target_near","pace":"relaxed","preferences":["quiet_hotel","comfortable_hotel"],"hotel_options":[{"name":"西湖静奢酒店","pricePerNight":1280,"comfortScore":95}],"route_days":[{"day":1,"activities":["西溪湿地"]}],"attraction_items":[{"name":"西溪湿地","cost":80}]}}'
```
