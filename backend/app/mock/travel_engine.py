from __future__ import annotations

import json
from pathlib import Path
from typing import Any

TRAVEL_DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "mock" / "travel_data.json"
PREFERRED_TYPES = {"food", "nature", "culture", "citywalk", "museum", "relaxed"}
PREFERENCE_TAG_MAP = {
    "food": {"food", "night_market", "snack", "local_food"},
    "local_food": {"food", "local_food", "snack"},
    "family": {"family", "park", "zoo", "science", "aquarium", "indoor"},
    "rainy_day": {"indoor", "museum", "art", "science", "aquarium"},
    "nature": {"nature", "lakeview", "wetland", "park", "mountain"},
    "culture": {"culture", "history", "temple", "tea", "heritage"},
    "citywalk": {"citywalk", "night_walk", "street", "canal"},
    "museum": {"museum", "indoor", "history", "art"},
    "relaxed": {"relaxed", "slow_travel", "tea"},
    "quiet_hotel": {"quiet_hotel"},
    "lively_hotel": {"lively_hotel"},
    "comfortable_hotel": {"comfortable_hotel", "lakeview", "design_hotel", "resort"},
}
PACE_COMPATIBILITY = {
    "relaxed": {"relaxed", "balanced"},
    "balanced": {"balanced", "relaxed", "intensive"},
    "intensive": {"intensive", "balanced"},
}
THEME_BY_TYPE = {
    "nature": "自然风景线",
    "culture": "人文体验日",
    "museum": "博物馆轻游",
    "citywalk": "街区漫步",
    "food": "本地风味探索",
    "relaxed": "慢游休闲日",
}
ATTRACTION_EXCLUSION_ALIASES = {
    "西湖": {"西湖", "白堤孤山", "苏堤", "断桥", "花港观鱼", "西湖核心区", "西湖西线", "西湖东线", "西湖沿岸"},
    "故宫": {"故宫", "故宫博物院", "景山公园", "东城中轴"},
}


def load_travel_data() -> dict[str, Any]:
    return json.loads(TRAVEL_DATA_PATH.read_text(encoding="utf-8"))


def weather_lookup(*, data: dict[str, Any], destination: str) -> dict[str, Any]:
    return data["weather"].get(destination, {"summary": "暂无天气数据", "advice": "建议灵活安排行程"})


def select_hotels(
    *,
    data: dict[str, Any],
    destination: str,
    budget: int,
    preferences: list[str],
) -> dict[str, Any]:
    hotels = data["hotels"].get(destination, [])
    nightly_budget = max(220, budget // 3 // 2)
    quiet_required = "quiet_hotel" in preferences
    lively_preferred = "lively_hotel" in preferences
    comfort_required = "comfortable_hotel" in preferences
    family_preferred = "family" in preferences

    filtered = [
        hotel
        for hotel in hotels
        if hotel["pricePerNight"] <= nightly_budget + (250 if comfort_required else 180)
        and (not quiet_required or hotel["quiet"])
        and (not lively_preferred or not hotel["quiet"])
    ]
    if not filtered:
        filtered = hotels[:]

    ranked = sorted(
        filtered,
        key=lambda item: _hotel_score(
            hotel=item,
            nightly_budget=nightly_budget,
            quiet_required=quiet_required,
            lively_preferred=lively_preferred,
            comfort_required=comfort_required,
            family_preferred=family_preferred,
        ),
        reverse=True,
    )
    return {"hotels": ranked[:2], "nightly_budget": nightly_budget}


def select_attractions(
    *,
    data: dict[str, Any],
    destination: str,
    preferences: list[str],
    days: int = 3,
    pace: str = "balanced",
    excluded_attractions: list[str] | None = None,
) -> dict[str, Any]:
    attractions = data["attractions"].get(destination, [])
    if not attractions:
        return {"attractions": []}

    avoid_food = "avoid_food" in preferences or "avoid_local_food" in preferences
    excluded_names = _expand_excluded_terms(excluded_attractions)
    preferred_types = {preference for preference in preferences if preference in PREFERRED_TYPES}
    preferred_tags: set[str] = set()
    for preference in preferences:
        preferred_tags.update(PREFERENCE_TAG_MAP.get(preference, set()))
    preferred_tags.update(PREFERENCE_TAG_MAP.get(pace, set()))

    candidates = []
    for index, attraction in enumerate(attractions):
        attraction_name = str(attraction.get("name", "")).strip()
        attraction_area = str(attraction.get("area", "")).strip()
        if _matches_excluded_attraction(name=attraction_name, area=attraction_area, excluded_terms=excluded_names):
            continue
        if avoid_food and attraction.get("type") == "food":
            continue
        score = _attraction_score(
            attraction=attraction,
            preferred_types=preferred_types,
            preferred_tags=preferred_tags,
            pace=pace,
            preferences=preferences,
        )
        candidates.append({**attraction, "_score": score, "_index": index})

    if not candidates:
        return {"attractions": []}

    ranked = sorted(candidates, key=lambda item: (-item["_score"], item["_index"]))
    target_count = min(len(ranked), _target_attraction_count(days=days, pace=pace))
    selected = _diversify_attractions(ranked=ranked, target_count=target_count)
    return {"attractions": [_strip_internal_fields(item) for item in selected]}


def plan_route(
    *,
    destination: str,
    days: int,
    pace: str = "balanced",
    attraction_items: list[dict[str, Any]] | None = None,
    attraction_names: list[str] | None = None,
    excluded_attractions: list[str] | None = None,
) -> dict[str, Any]:
    excluded_names = _expand_excluded_terms(excluded_attractions)
    items = _prepare_route_items(
        destination=destination,
        attraction_items=attraction_items or [],
        attraction_names=attraction_names or [],
    )
    if excluded_names:
        items = [
            item for item in items
            if not _matches_excluded_attraction(
                name=str(item.get("name", "")).strip(),
                area=str(item.get("area", "")).strip(),
                excluded_terms=excluded_names,
            )
        ]
    if not items:
        items = [
            {
                "name": f"{destination} 城市漫步",
                "type": "citywalk",
                "area": destination,
                "pace": pace,
                "tags": ["citywalk"],
            }
        ]

    day_capacities = _build_day_capacities(days=days, pace=pace, item_count=len(items))
    groups = _group_items_by_area(items)
    plan_days = [{"day": index + 1, "activities": [], "_items": []} for index in range(days)]

    for day_index, capacity in enumerate(day_capacities):
        anchor_area = _next_area_with_items(groups)
        if anchor_area is None:
            break
        plan_days[day_index]["_items"].append(groups[anchor_area].pop(0))
        while len(plan_days[day_index]["_items"]) < capacity and groups[anchor_area]:
            plan_days[day_index]["_items"].append(groups[anchor_area].pop(0))

    leftovers = [item for area_items in groups.values() for item in area_items]
    for item in leftovers:
        target_day = min(
            range(days),
            key=lambda index: (
                len(plan_days[index]["_items"]) >= day_capacities[index],
                len(plan_days[index]["_items"]),
                index,
            ),
        )
        plan_days[target_day]["_items"].append(item)

    finalized_days = []
    for index, day in enumerate(plan_days):
        if not day["_items"]:
            day["_items"].append(
                {
                    "name": f"{destination} 自由活动",
                    "type": "relaxed",
                    "area": destination,
                    "pace": "relaxed",
                    "tags": ["slow_travel"],
                }
            )
        activities = [item["name"] for item in day["_items"]]
        finalized_days.append(
            {
                "day": index + 1,
                "theme": _build_day_theme(destination=destination, day_index=index + 1, items=day["_items"]),
                "activities": activities,
                "route": activities,
                "area": _dominant_value(day["_items"], "area", default=destination),
            }
        )
    return {"days": finalized_days}


def _hotel_score(
    *,
    hotel: dict[str, Any],
    nightly_budget: int,
    quiet_required: bool,
    lively_preferred: bool,
    comfort_required: bool,
    family_preferred: bool,
) -> float:
    score = float(hotel.get("rating", 0)) * 10
    score += float(hotel.get("comfortScore", 0))
    price_distance = abs(hotel.get("pricePerNight", nightly_budget) - nightly_budget)
    score -= price_distance / 35
    if quiet_required and hotel.get("quiet"):
        score += 8
    if lively_preferred and not hotel.get("quiet"):
        score += 6
    if comfort_required and "comfortable_hotel" in hotel.get("tags", []):
        score += 10
    if family_preferred and "family_friendly" in hotel.get("tags", []):
        score += 7
    return score


def _attraction_score(
    *,
    attraction: dict[str, Any],
    preferred_types: set[str],
    preferred_tags: set[str],
    pace: str,
    preferences: list[str],
) -> int:
    attraction_tags = set(attraction.get("tags", []))
    attraction_type = str(attraction.get("type", ""))
    score = 1

    if preferred_types:
        if attraction_type in preferred_types:
            score += 6
        elif attraction_type == "food" and "local_food" in preferences:
            score += 5
        elif attraction_type == "relaxed" and pace == "relaxed":
            score += 4
    if preferred_tags:
        score += len(attraction_tags.intersection(preferred_tags)) * 2
    if "classic" in attraction_tags:
        score += 3

    attraction_pace = str(attraction.get("pace", "balanced"))
    if attraction_pace in PACE_COMPATIBILITY.get(pace, {pace}):
        score += 2
    if pace == "relaxed" and attraction.get("durationHours", 0) <= 2.5:
        score += 1
    if pace == "intensive" and attraction.get("durationHours", 0) >= 2:
        score += 1
    if attraction.get("indoor") and "museum" in preferred_types:
        score += 1
    if "rainy_day" in preferences:
        if attraction.get("indoor"):
            score += 4
        elif attraction_type in {"nature", "citywalk"} and attraction.get("durationHours", 0) >= 2:
            score -= 1
    return score


def _target_attraction_count(*, days: int, pace: str) -> int:
    if pace == "intensive":
        return max(4, min(12, days * 2))
    if pace == "relaxed":
        return max(4, min(10, days + 2))
    return max(4, min(11, days * 2 - 1))


def _diversify_attractions(*, ranked: list[dict[str, Any]], target_count: int) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in ranked:
        groups.setdefault(str(item.get("area", "核心城区")), []).append(item)

    selected: list[dict[str, Any]] = []
    areas = list(groups.keys())
    while len(selected) < target_count:
        made_progress = False
        for area in areas:
            bucket = groups.get(area, [])
            if not bucket:
                continue
            selected.append(bucket.pop(0))
            made_progress = True
            if len(selected) >= target_count:
                break
        if not made_progress:
            break
    return selected


def _strip_internal_fields(item: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in item.items() if not key.startswith("_")}


def _expand_excluded_terms(excluded_attractions: list[str] | None) -> set[str]:
    normalized_inputs = {
        str(item).strip().lower()
        for item in (excluded_attractions or [])
        if str(item).strip()
    }
    expanded = set(normalized_inputs)
    for raw_item in excluded_attractions or []:
        normalized = str(raw_item).strip()
        if not normalized:
            continue
        for alias in ATTRACTION_EXCLUSION_ALIASES.get(normalized, set()):
            expanded.add(alias.strip().lower())
    return expanded


def _matches_excluded_attraction(*, name: str, area: str, excluded_terms: set[str]) -> bool:
    normalized_name = name.strip().lower()
    normalized_area = area.strip().lower()
    if normalized_name in excluded_terms or normalized_area in excluded_terms:
        return True
    return any(term and (term in normalized_name or term in normalized_area) for term in excluded_terms)


def _prepare_route_items(
    *,
    destination: str,
    attraction_items: list[dict[str, Any]],
    attraction_names: list[str],
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    prepared: list[dict[str, Any]] = []

    for item in attraction_items:
        name = str(item.get("name", "")).strip()
        if not name or name in seen:
            continue
        prepared.append(
            {
                "name": name,
                "type": item.get("type", "citywalk"),
                "area": item.get("area", destination),
                "pace": item.get("pace", "balanced"),
                "tags": item.get("tags", []),
            }
        )
        seen.add(name)

    for name in attraction_names:
        normalized = str(name).strip()
        if not normalized or normalized in seen:
            continue
        prepared.append(
            {
                "name": normalized,
                "type": "citywalk",
                "area": destination,
                "pace": "balanced",
                "tags": ["citywalk"],
            }
        )
        seen.add(normalized)
    return prepared


def _build_day_capacities(*, days: int, pace: str, item_count: int) -> list[int]:
    if days <= 0:
        return []
    base = 2 if pace != "relaxed" else 1
    capacities = [base for _ in range(days)]
    remaining = max(0, item_count - sum(capacities))
    index = 0
    while remaining > 0:
        if pace == "relaxed" and capacities[index] >= 2:
            index = (index + 1) % days
            continue
        if pace == "balanced" and capacities[index] >= 2:
            index = (index + 1) % days
            continue
        if pace == "intensive" and capacities[index] >= 3:
            index = (index + 1) % days
            continue
        capacities[index] += 1
        remaining -= 1
        index = (index + 1) % days
    return capacities


def _group_items_by_area(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        groups.setdefault(str(item.get("area", "核心城区")), []).append(item)
    return groups


def _next_area_with_items(groups: dict[str, list[dict[str, Any]]]) -> str | None:
    available = [(area, items) for area, items in groups.items() if items]
    if not available:
        return None
    return max(available, key=lambda entry: len(entry[1]))[0]


def _dominant_value(items: list[dict[str, Any]], field_name: str, *, default: str) -> str:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(field_name, default))
        counts[value] = counts.get(value, 0) + 1
    return max(counts.items(), key=lambda entry: entry[1])[0] if counts else default


def _build_day_theme(*, destination: str, day_index: int, items: list[dict[str, Any]]) -> str:
    area = _dominant_value(items, "area", default=destination)
    attraction_type = _dominant_value(items, "type", default="citywalk")
    theme_suffix = THEME_BY_TYPE.get(attraction_type, "轻松探索")
    return f"{destination} 第{day_index}天，{area}{theme_suffix}"
