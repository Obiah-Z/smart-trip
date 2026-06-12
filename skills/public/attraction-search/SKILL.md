---
name: attraction-search
skill_id: attraction.search
display_name: 景点搜索
provider: local_script
priority: 20
depends_on: []
trigger_keywords: ["景点", "地标", "美食", "本地特色", "小吃", "文化", "自然", "推荐", "citywalk", "打卡", "博物馆", "亲子", "带娃", "雨天", "室内", "避开", "不想去", "不要去"]
input_schema: {"destination": "string", "preferences": "string[]", "days": "number", "pace": "string", "excluded_attractions": "string[]"}
example_payload: {"destination": "北京", "preferences": ["culture", "food"], "days": 3, "pace": "balanced", "excluded_attractions": ["故宫"]}
sandbox_policy: {"timeout_seconds": 5, "memory_mb": 128, "cpu_seconds": 2, "max_open_files": 32, "allow_network": false, "allow_subprocess": false, "writable_roots": []}
description: Use this skill when the user asks for attractions, landmarks, food streets, local food, museums, culture, nature, citywalk, family/rainy-day places, or when itinerary planning needs destination-specific POI candidates filtered by preferences, pace, day count, and excluded attractions.
---

# Attraction Search Skill

## Business Role

Use this Skill as the destination POI candidate generator. It selects attractions, food areas, museums, cultural sites, nature spots, citywalk streets, family-friendly places, and rainy-day alternatives according to user constraints.

This Skill should run before `route.plan` whenever the system needs a day-by-day itinerary. `route.plan` sequences places; `attraction.search` decides which places are allowed and relevant.

Implementation files:
- `skills/public/attraction-search/SKILL.md`
- `skills/public/attraction-search/scripts/run.py`

Runtime entry:
- API: `POST /api/skills/attraction.search/invoke`
- Script: `python skills/public/attraction-search/scripts/run.py --payload-json '<json>'`

## When to Use

- 用户问“北京有哪些文化景点”
- 用户问“杭州有哪些推荐的景点”
- 用户问“上海适合 citywalk 的地方”
- 用户问“下雨天适合带娃去哪玩”
- 用户问“成都有什么本地特色美食”
- 用户规划多日游，需要先生成候选景点
- 用户追问“不想去故宫 / 不想西湖 / 避开人多的经典景点”，需要重新筛选候选点

## Do Not Use

- 不要用于天气查询，天气应使用 `weather.lookup`
- 不要用于住宿筛选，酒店应使用 `hotel.search`
- 不要直接承担按天路线排序，按天安排应交给 `route.plan`
- 不要在缺少目的地时默认使用杭州，应让上游澄清目的地

## Input Contract

```json
{
  "destination": "北京",
  "preferences": ["culture", "food", "quiet_hotel"],
  "days": 3,
  "pace": "balanced",
  "excluded_attractions": ["故宫"]
}
```

Field rules:

| Field | Type | Required | Notes |
|---|---:|---:|---|
| `destination` | string | yes | 明确目的地。不要使用默认城市兜底。 |
| `preferences` | string[] | no | 旅行偏好标签。常见值：`culture`、`food`、`local_food`、`avoid_local_food`、`nature`、`citywalk`、`museum`、`family`、`rainy_day`、`relaxed`。 |
| `days` | number | no | 行程天数，用于控制候选数量。简单问答可传 1。 |
| `pace` | string | no | `relaxed` / `balanced` / `intensive`。影响候选数量和景点时长偏好。 |
| `excluded_attractions` | string[] | no | 用户明确不想去的景点或区域。应包含图谱扩展后的别名。 |

## Output Contract

```json
{
  "destination": "北京",
  "matched": true,
  "preferences": ["culture", "food"],
  "days": 3,
  "pace": "balanced",
  "excluded_attractions": ["故宫"],
  "selection_strategy": {
    "preference_filtering": true,
    "pace_aware": true,
    "exclusion_applied": true,
    "diversified_by_area": true
  },
  "attractions": [
    {
      "name": "颐和园",
      "type": "nature",
      "area": "海淀西线",
      "cost": 30,
      "durationHours": 3,
      "tags": ["classic", "nature"]
    }
  ],
  "warnings": []
}
```

Existing consumers rely on `attractions`. Other fields support debugging and complex planning.

## Selection Logic

The script applies these business rules:

1. Match destination in local travel data.
2. Expand preference tags into attraction-type and tag signals.
3. Remove excluded attractions by name, alias, or area.
4. Remove local-food POIs if preferences include `avoid_food` or `avoid_local_food`.
5. Score candidates by type match, tag match, classic status, pace compatibility, indoor/rainy-day fit, and duration.
6. Diversify across areas to avoid putting all candidates in one district.
7. Limit candidate count based on `days` and `pace`.

## Composition Patterns

### Lightweight Attraction Q&A

Use only `attraction.search` when the user asks for recommended places but not a day-by-day plan.

Example:

```json
{
  "destination": "杭州",
  "preferences": ["culture"],
  "days": 1,
  "pace": "balanced",
  "excluded_attractions": []
}
```

### Full Itinerary Planning

Use this Skill before `route.plan`. Pass both `attraction_names` and `attraction_items` from its output into `route.plan`.

Recommended chain:

1. `weather.lookup`
2. `attraction.search`
3. `hotel.search`
4. `route.plan`

### Follow-Up Replanning With Exclusions

If the user says “不想去西湖，重新规划”, inherit destination/days/budget from session context and pass:

```json
{
  "destination": "杭州",
  "preferences": ["local_food", "quiet_hotel"],
  "days": 3,
  "pace": "relaxed",
  "excluded_attractions": ["西湖", "白堤孤山", "苏堤", "断桥"]
}
```

The final plan must not include any excluded item or obvious alias.

## Failure Handling

- Unknown destination: return `matched=false`, empty `attractions`, and a warning.
- All candidates excluded: return empty `attractions`; downstream `route.plan` may create a generic citywalk fallback, but the final answer should state that more POI data is needed.
- Conflicting preferences such as `local_food` and `avoid_local_food`: exclusion preference wins for food POIs.
- Missing days: use 1 only for lightweight consulting; full planning should ask for clarification before using this Skill.

## Example

```bash
curl -X POST http://127.0.0.1:8001/api/skills/attraction.search/invoke \
  -H 'Content-Type: application/json' \
  -d '{"payload":{"destination":"北京","preferences":["culture","food"],"days":3,"pace":"balanced","excluded_attractions":["故宫"]}}'
```
