---
name: route-plan
skill_id: route.plan
display_name: 路线规划
provider: local_script
priority: 40
depends_on: ["attraction.search"]
trigger_keywords: ["行程", "路线", "规划", "安排", "攻略", "几日游", "日游", "按天", "重新规划", "调整路线", "换路线", "避开", "不想去", "不要去"]
input_schema: {"destination": "string", "days": "number", "pace": "string", "attraction_names": "string[]", "attraction_items": "object[]", "excluded_attractions": "string[]"}
example_payload: {"destination": "北京", "days": 3, "pace": "balanced", "attraction_names": ["故宫", "颐和园", "簋街"], "attraction_items": [{"name": "故宫", "type": "culture", "area": "东城中轴"}], "excluded_attractions": ["故宫"]}
sandbox_policy: {"timeout_seconds": 5, "memory_mb": 128, "cpu_seconds": 2, "max_open_files": 32, "allow_network": false, "allow_subprocess": false, "writable_roots": []}
description: Use this skill when the user asks for a multi-day itinerary, day-by-day route, route sequencing, replanning, attraction exclusion replanning, or when selected destination POIs need to be converted into a coherent daily travel plan.
---

# Route Plan Skill

## Business Role

Use this Skill as the route sequencing and day allocation capability. It converts attraction candidates into a day-by-day itinerary while respecting destination, day count, travel pace, attraction area, and excluded attractions.

This Skill is not responsible for discovering POIs. It depends on `attraction.search` and should receive both attraction names and structured attraction items from that Skill whenever available.

Implementation files:
- `skills/public/route-plan/SKILL.md`
- `skills/public/route-plan/scripts/run.py`

Runtime entry:
- API: `POST /api/skills/route.plan/invoke`
- Script: `python skills/public/route-plan/scripts/run.py --payload-json '<json>'`

## When to Use

- 用户问“帮我规划北京三日游”
- 用户问“把故宫、颐和园、簋街分成三天”
- 用户问“给我一个按天路线”
- 用户追问“不想去故宫，重新规划一下”
- 用户追问“不要西湖，换一版杭州三天行程”
- 用户修改预算、节奏、住宿或排除景点后，需要基于上一轮方案重排路线

## Do Not Use

- 不要用于简单天气问答
- 不要用于“有哪些景点”这类轻咨询，除非用户明确要按天安排
- 不要在缺少天数的全新规划请求中默认三天，应由上游澄清
- 不要把已排除景点重新放回路线，即使它们来自旧会话或候选列表

## Input Contract

```json
{
  "destination": "北京",
  "days": 3,
  "pace": "balanced",
  "attraction_names": ["颐和园", "天坛", "簋街"],
  "attraction_items": [
    {"name": "颐和园", "type": "nature", "area": "海淀西线"},
    {"name": "天坛", "type": "culture", "area": "南城中轴"}
  ],
  "excluded_attractions": ["故宫"]
}
```

Field rules:

| Field | Type | Required | Notes |
|---|---:|---:|---|
| `destination` | string | yes | 当前规划目的地。 |
| `days` | number | yes | 行程天数。追问重排应从会话上下文继承，不应重复向用户索要。 |
| `pace` | string | no | `relaxed` / `balanced` / `intensive`。控制每天容量。 |
| `attraction_names` | string[] | no | 候选景点名称。缺少 `attraction_items` 时作为 fallback。 |
| `attraction_items` | object[] | preferred | 推荐由 `attraction.search` 输出，包含 `name`、`type`、`area`、`tags` 等。 |
| `excluded_attractions` | string[] | no | 用户明确排除的景点、区域或别名。 |

## Output Contract

```json
{
  "destination": "北京",
  "days_count": 3,
  "pace": "balanced",
  "excluded_attractions": ["故宫"],
  "route_strategy": {
    "area_grouping": true,
    "pace_capacity": true,
    "exclusion_applied": true
  },
  "days": [
    {
      "day": 1,
      "theme": "北京 第1天，人文体验日",
      "activities": ["天坛", "前门大街"],
      "route": ["天坛", "前门大街"],
      "area": "南城中轴"
    }
  ],
  "warnings": []
}
```

Existing consumers rely on `days`.

## Planning Logic

1. Prefer structured `attraction_items`; use `attraction_names` only as fallback.
2. Remove excluded attractions by name, alias, or area.
3. Group remaining POIs by area to reduce cross-city hopping.
4. Determine daily capacity from `pace`:
   - `relaxed`: fewer stops, more free time.
   - `balanced`: moderate density.
   - `intensive`: more stops and tighter sequencing.
5. Assign area-coherent POIs to days.
6. Fill empty days with conservative free-activity placeholders only when candidates are insufficient.

## Composition Patterns

### Full New Itinerary

Recommended chain:

1. `weather.lookup`
2. `attraction.search`
3. `hotel.search`
4. `route.plan`

### Follow-Up Replanning

When user says “不想西湖，请重新规划”, the system should:

1. Treat it as a follow-up replan, not a new request.
2. Restore destination/days/budget/pace from session context.
3. Add `西湖` and expanded aliases into `excluded_attractions`.
4. Re-run `attraction.search`.
5. Re-run `route.plan` with updated candidates and exclusions.
6. Ensure final route does not contain excluded items.

### Budget or Hotel-Only Follow-Up

If the user only upgrades hotel comfort and does not change route preference, the planner may still keep route days stable. `route.plan` is useful when final plan must be regenerated consistently, but the answer should clearly say the main change is accommodation.

## Failure Handling

- Missing `days` in a new planning request: do not call this Skill; ask a clarification question.
- Missing `days` in a follow-up request: inherit from latest planning session.
- No attraction candidates after exclusion: return generic citywalk/free-activity placeholders and warning; final answer should ask whether the user wants more candidate types.
- Unknown destination: return a route fallback only if user explicitly wants a placeholder; otherwise let the planner clarify.

## Example

```bash
curl -X POST http://127.0.0.1:8001/api/skills/route.plan/invoke \
  -H 'Content-Type: application/json' \
  -d '{"payload":{"destination":"北京","days":3,"pace":"balanced","attraction_names":["颐和园","天坛","簋街"],"excluded_attractions":["故宫"],"attraction_items":[{"name":"颐和园","type":"nature","area":"海淀西线"},{"name":"天坛","type":"culture","area":"南城中轴"}]}}'
```
