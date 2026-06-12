---
name: hotel-search
skill_id: hotel.search
display_name: 酒店搜索
provider: local_script
priority: 30
depends_on: []
trigger_keywords: ["酒店", "住宿", "民宿", "住哪里", "安静", "热闹", "舒适", "舒服", "舒适度", "升级住宿", "预算", "商圈", "位置"]
input_schema: {"destination": "string", "budget": "number", "preferences": "string[]"}
example_payload: {"destination": "北京", "budget": 4000, "preferences": ["quiet_hotel"]}
sandbox_policy: {"timeout_seconds": 5, "memory_mb": 128, "cpu_seconds": 2, "max_open_files": 32, "allow_network": false, "allow_subprocess": false, "writable_roots": []}
description: Use this skill when the user asks for hotels, accommodation, stay areas, quiet/lively lodging, comfort upgrades, budget-sensitive hotel choices, or when multi-day itinerary planning needs a concrete accommodation recommendation aligned with budget and preferences.
---

# Hotel Search Skill

## Business Role

Use this Skill as the lodging recommendation capability. It maps destination, budget, and preference signals into hotel candidates with nightly budget guidance.

The Skill is intentionally business-level. The planner should not expose raw hotel data directly without explaining why a hotel matches the user's budget, quiet/lively preference, comfort requirement, and route convenience.

Implementation files:
- `skills/public/hotel-search/SKILL.md`
- `skills/public/hotel-search/scripts/run.py`

Runtime entry:
- API: `POST /api/skills/hotel.search/invoke`
- Script: `python skills/public/hotel-search/scripts/run.py --payload-json '<json>'`

## When to Use

- 用户问“北京有没有安静一点的酒店”
- 用户问“杭州住哪里比较方便”
- 用户问“预算 4000 住三晚推荐什么酒店”
- 用户追问“酒店住得更舒适一点”
- 用户追问“把预算提升到 10000，主要提升住宿舒适度”
- 多日旅行规划中需要给出推荐住宿，而不是只给路线

## Do Not Use

- 不要用于景点候选生成，景点应使用 `attraction.search`
- 不要用于路线排序，按天路线应使用 `route.plan`
- 不要在用户只问天气或单个景点时强行调用酒店
- 不要忽略用户“嘈杂/热闹”和“安静”的互斥偏好，最新明确表达应优先

## Input Contract

```json
{
  "destination": "北京",
  "budget": 4000,
  "preferences": ["quiet_hotel", "comfortable_hotel"]
}
```

Field rules:

| Field | Type | Required | Notes |
|---|---:|---:|---|
| `destination` | string | yes | 城市名或目的地名。 |
| `budget` | number | no | 总预算。脚本会估算每晚预算，但上游应尽量传入当前轮解析/继承后的预算。 |
| `preferences` | string[] | no | 支持 `quiet_hotel`、`lively_hotel`、`comfortable_hotel`、`family` 等。 |

## Output Contract

```json
{
  "destination": "北京",
  "matched": true,
  "budget": 4000,
  "nightly_budget": 666,
  "preferences": ["quiet_hotel"],
  "selection_strategy": {
    "budget_aware": true,
    "quiet_required": true,
    "lively_preferred": false,
    "comfort_required": false
  },
  "hotels": [
    {
      "name": "中轴静舍酒店",
      "area": "东城中轴",
      "pricePerNight": 520,
      "quiet": true,
      "rating": 4.7,
      "comfortScore": 86,
      "tags": ["quiet_hotel"]
    }
  ],
  "warnings": []
}
```

Existing consumers rely on `hotels` and `nightly_budget`.

## Selection Logic

1. Resolve destination hotel pool.
2. Estimate nightly budget from total budget.
3. Apply hard preference filters:
   - `quiet_hotel`: keep quiet hotels when possible.
   - `lively_hotel`: prefer lively/non-quiet hotels when possible.
   - `comfortable_hotel`: allow higher nightly cost and boost comfort score.
4. Rank by rating, comfort score, distance from nightly budget, and preference fit.
5. Return the top candidates with warnings if fallback was needed.

## Composition Patterns

### Multi-Day Planning

Use `hotel.search` for any itinerary with `days >= 2`, even if the user does not explicitly mention hotel. A multi-day user-facing travel plan should normally include where to stay.

### Budget Upgrade Follow-Up

If the user says “预算提升到 10000，主要提升住宿舒适度”, inherit the original destination/days/pace, add `comfortable_hotel`, and pass the updated budget:

```json
{
  "destination": "杭州",
  "budget": 10000,
  "preferences": ["quiet_hotel", "local_food", "comfortable_hotel"]
}
```

The final answer should explain what changed: hotel class, nightly budget, comfort score, and remaining budget allocation.

### Conflicting Hotel Preferences

If the latest user request says “酒店尽量嘈杂/热闹”, prefer `lively_hotel` and remove stale `quiet_hotel` from active preferences before calling this Skill. If both are present due to memory conflict, the planner should resolve conflict before invocation.

## Failure Handling

- Unknown destination: return `matched=false`, empty `hotels`, and a warning.
- No hotel fits budget/preference: return fallback candidates and include a warning.
- Budget missing or 0: use a conservative default but mark it in warnings so final answer does not overstate precision.
- User asks only weather/simple attraction: do not call this Skill.

## Example

```bash
curl -X POST http://127.0.0.1:8001/api/skills/hotel.search/invoke \
  -H 'Content-Type: application/json' \
  -d '{"payload":{"destination":"北京","budget":4000,"preferences":["quiet_hotel","comfortable_hotel"]}}'
```
