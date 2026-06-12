---
name: weather-lookup
skill_id: weather.lookup
display_name: 天气查询
provider: local_script
priority: 10
depends_on: []
trigger_keywords: ["天气", "气温", "下雨", "有雨", "外套", "穿什么", "步行", "适合旅游", "防晒", "户外", "雨天", "温度"]
input_schema: {"destination": "string"}
example_payload: {"destination": "北京"}
sandbox_policy: {"timeout_seconds": 5, "memory_mb": 128, "cpu_seconds": 2, "max_open_files": 32, "allow_network": false, "allow_subprocess": false, "writable_roots": []}
description: Use this skill when the user asks about destination weather, temperature, rain, clothing, walking suitability, outdoor feasibility, rainy-day travel risk, or when an itinerary needs weather context before selecting attractions and route intensity.
---

# Weather Lookup Skill

## Business Role

Use this skill as the system's lightweight weather and travel-suitability capability. It turns a destination into a structured weather summary that downstream planning can use to adjust route density, indoor/outdoor attraction mix, packing advice, and risk reminders.

This is a local-script Skill. The current implementation reads curated local travel weather data, not a live weather API. Treat the result as a deterministic travel-context signal unless the project later swaps the script internals for a real-time provider.

Implementation files:
- `skills/public/weather-lookup/SKILL.md`
- `skills/public/weather-lookup/scripts/run.py`

Runtime entry:
- API: `POST /api/skills/weather.lookup/invoke`
- Script: `python skills/public/weather-lookup/scripts/run.py --payload-json '<json>'`

## When to Use

- 用户问“北京今天天气怎么样”
- 用户问“杭州适合步行吗”
- 用户问“去成都要不要带外套”
- 用户问“上海下雨天适合去哪玩”
- 用户正在做多日路线规划，需要判断户外景点是否适合安排
- 用户追问“天气不好能不能换室内一点”

## Do Not Use

- 不要把它用于景点搜索，景点候选应使用 `attraction.search`
- 不要把它用于酒店筛选，住宿应使用 `hotel.search`
- 不要为了简单景点问答强行调用天气，除非用户明确问到天气、雨天、穿衣、户外适宜性
- 不要把本地天气快照当成实时气象预警，如需实时预警应接入外部天气服务后再升级脚本

## Input Contract

```json
{
  "destination": "北京"
}
```

Field rules:

| Field | Type | Required | Notes |
|---|---:|---:|---|
| `destination` | string | yes | 城市名或目的地名。应由上游 slot/context 明确解析，缺失时不要默认兜底到杭州。 |

## Output Contract

The script returns a JSON object. Existing consumers rely on at least `summary` and `advice`.

```json
{
  "destination": "北京",
  "matched": true,
  "summary": "晴到多云，18-28℃，适合步行和户外游览",
  "advice": "建议准备防晒用品，午后户外行程注意补水。",
  "travel_suitability": "good",
  "risk_flags": ["sun_exposure"],
  "data_source": "local_mock_travel_data"
}
```

Output semantics:

| Field | Meaning |
|---|---|
| `destination` | 本次查询目的地 |
| `matched` | 本地数据是否命中该目的地 |
| `summary` | 面向用户的天气概览 |
| `advice` | 可直接进入最终回答的旅行建议 |
| `travel_suitability` | `good` / `moderate` / `limited` / `unknown` |
| `risk_flags` | 可供路线规划参考的风险标签，如 `rain`、`heat`、`cold`、`sun_exposure`、`unknown_weather` |
| `data_source` | 当前数据来源说明 |

## Workflow

1. Confirm `destination` from current user input or session context.
2. Call `weather.lookup` only if weather context is directly useful for the current task.
3. Inject `summary` and `advice` into the final answer for weather Q&A.
4. For route planning, pass weather into the Executor/Reviewer stage so outdoor intensity and rainy-day alternatives can be evaluated.
5. If `matched=false`, tell the user that weather data is unavailable and give conservative planning advice instead of fabricating exact temperature.

## Composition Patterns

### Simple Weather Q&A

Use only this Skill. Do not trigger route planning.

Example:

```json
{
  "destination": "杭州"
}
```

Expected answer shape:
- 当前天气概览
- 是否适合步行/户外
- 穿衣和携带物建议

### Rainy-Day Attraction Consultation

Use `weather.lookup` only when the user explicitly asks about rain/weather. If the user asks “下雨天适合带娃去哪玩”, combine:

1. `weather.lookup`
2. `attraction.search` with preferences such as `rainy_day`, `family`, `indoor`

### Multi-Day Itinerary

For multi-day planning, this Skill should usually be part of the tool chain:

1. `weather.lookup`
2. `attraction.search`
3. `hotel.search`
4. `route.plan`

The weather result should not dominate the itinerary, but should affect route risk notes and alternative suggestions.

## Failure Handling

- Missing `destination`: return a structured error or let the planner ask a clarification question.
- Unknown destination: return `matched=false`, `travel_suitability=unknown`, and conservative advice.
- Script timeout or sandbox failure: continue route planning without weather, but mark `weather_context_available=false` in Reviewer output.

## Example

```bash
curl -X POST http://127.0.0.1:8001/api/skills/weather.lookup/invoke \
  -H 'Content-Type: application/json' \
  -d '{"payload":{"destination":"北京"}}'
```
