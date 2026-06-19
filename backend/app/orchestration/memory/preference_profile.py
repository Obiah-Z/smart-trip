from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

PROFILE_PREFIX = "profile:"
PROFILE_SCOPE = "user_profile"
PROFILE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class PreferenceSignalDefinition:
    """稳定偏好信号定义。

    存储层只按 profile 维度扩展，具体偏好作为 signal 存在 value JSON 里，避免不断新增
    preference_xxx 这类顶层 key。
    """

    name: str
    dimension: str
    family: str
    polarity: str
    label: str


SIGNAL_DEFINITIONS: dict[str, PreferenceSignalDefinition] = {
    "quiet_hotel": PreferenceSignalDefinition("quiet_hotel", "accommodation", "hotel_environment", "prefer", "偏安静住宿"),
    "lively_hotel": PreferenceSignalDefinition("lively_hotel", "accommodation", "hotel_environment", "prefer", "偏热闹住宿"),
    "comfortable_hotel": PreferenceSignalDefinition("comfortable_hotel", "accommodation", "hotel_comfort", "prefer", "提升住宿舒适度"),
    "local_food": PreferenceSignalDefinition("local_food", "food", "local_food", "prefer", "想吃本地特色"),
    "avoid_local_food": PreferenceSignalDefinition("avoid_local_food", "food", "local_food", "avoid", "不想吃本地特色"),
    "food": PreferenceSignalDefinition("food", "food", "food_focus", "prefer", "愿意重点安排餐饮"),
    "avoid_food": PreferenceSignalDefinition("avoid_food", "food", "food_focus", "avoid", "不想重点安排餐饮"),
    "rainy_day": PreferenceSignalDefinition("rainy_day", "interests", "weather_scene", "prefer", "关注雨天/室内安排"),
    "culture": PreferenceSignalDefinition("culture", "interests", "attraction_theme", "prefer", "偏文化体验"),
    "nature": PreferenceSignalDefinition("nature", "interests", "attraction_theme", "prefer", "偏自然景点"),
    "museum": PreferenceSignalDefinition("museum", "interests", "attraction_theme", "prefer", "偏博物馆/展览"),
    "citywalk": PreferenceSignalDefinition("citywalk", "interests", "travel_style", "prefer", "偏城市漫步"),
    "family": PreferenceSignalDefinition("family", "traveler", "traveler_group", "prefer", "适合家庭/亲子"),
    "metro": PreferenceSignalDefinition("metro", "transport", "transport_mode", "prefer", "偏地铁出行"),
    "high_speed_rail": PreferenceSignalDefinition("high_speed_rail", "transport", "transport_mode", "prefer", "偏高铁出行"),
    "relaxed": PreferenceSignalDefinition("relaxed", "pace", "pace", "prefer", "偏轻松节奏"),
    "balanced": PreferenceSignalDefinition("balanced", "pace", "pace", "prefer", "偏均衡节奏"),
    "intensive": PreferenceSignalDefinition("intensive", "pace", "pace", "prefer", "偏紧凑节奏"),
}

LEGACY_MEMORY_SIGNAL_MAP = {
    ("hotel_style", "prefer_quiet_location"): "quiet_hotel",
    ("hotel_style", "prefer_lively_location"): "lively_hotel",
    ("preference_quiet_hotel", "quiet_hotel"): "quiet_hotel",
    ("preference_quiet_hotel", "avoid_quiet_hotel"): "lively_hotel",
    ("preference_local_food", "local_food"): "local_food",
    ("preference_local_food", "avoid_local_food"): "avoid_local_food",
    ("preference_food", "food"): "food",
    ("preference_food", "avoid_food"): "avoid_food",
    ("preference_culture", "culture"): "culture",
    ("preference_nature", "nature"): "nature",
    ("preference_museum", "museum"): "museum",
    ("preference_citywalk", "citywalk"): "citywalk",
    ("preference_family", "family"): "family",
    ("preference_metro", "metro"): "metro",
    ("preference_high_speed_rail", "high_speed_rail"): "high_speed_rail",
    ("travel_pace", "relaxed"): "relaxed",
    ("travel_pace", "balanced"): "balanced",
    ("travel_pace", "intensive"): "intensive",
}


def profile_key(dimension: str) -> str:
    return f"{PROFILE_PREFIX}{dimension}"


def dimension_from_profile_key(key: str) -> str | None:
    if not key.startswith(PROFILE_PREFIX):
        return None
    dimension = key.removeprefix(PROFILE_PREFIX).strip()
    return dimension or None


def signal_definition(signal_name: str) -> PreferenceSignalDefinition:
    """返回 signal 定义；未知 signal 会被收敛到 generic 维度。

    这样后续接入 LLM 偏好抽取时，可以先保存新 signal，不需要改 SQLite schema 或新增
    顶层 key。
    """
    if signal_name in SIGNAL_DEFINITIONS:
        return SIGNAL_DEFINITIONS[signal_name]
    if "hotel" in signal_name or "住宿" in signal_name:
        dimension = "accommodation"
    elif "food" in signal_name or "吃" in signal_name or "餐" in signal_name:
        dimension = "food"
    elif "rail" in signal_name or "metro" in signal_name or "交通" in signal_name:
        dimension = "transport"
    else:
        dimension = "interests"
    polarity = "avoid" if signal_name.startswith("avoid_") else "prefer"
    return PreferenceSignalDefinition(
        name=signal_name,
        dimension=dimension,
        family=signal_name,
        polarity=polarity,
        label=signal_name,
    )


def group_signals_by_dimension(signal_names: list[str]) -> dict[str, list[PreferenceSignalDefinition]]:
    grouped: dict[str, list[PreferenceSignalDefinition]] = {}
    for signal_name in list(dict.fromkeys(signal_names)):
        definition = signal_definition(signal_name)
        grouped.setdefault(definition.dimension, []).append(definition)
    return grouped


def parse_profile_value(value: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("schema_version") != PROFILE_SCHEMA_VERSION:
        return None
    if not isinstance(payload.get("signals"), list):
        return None
    return payload


def dump_profile_value(profile: dict[str, Any]) -> str:
    return json.dumps(profile, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def active_signal_names_from_profile(profile: dict[str, Any]) -> list[str]:
    active_values = profile.get("active_values")
    if isinstance(active_values, list):
        return [str(item) for item in active_values if str(item).strip()]
    signals = profile.get("signals") or []
    return [
        str(item.get("name"))
        for item in signals
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]


def memory_item_signal_names(item: dict[str, Any]) -> list[str]:
    key = str(item.get("key") or "")
    value = str(item.get("value") or "")
    if dimension_from_profile_key(key):
        profile = parse_profile_value(value)
        return active_signal_names_from_profile(profile) if profile else []
    legacy_signal = LEGACY_MEMORY_SIGNAL_MAP.get((key, value))
    return [legacy_signal] if legacy_signal else []


def memory_item_dimension(item: dict[str, Any]) -> str | None:
    key = str(item.get("key") or "")
    profile_dimension = dimension_from_profile_key(key)
    if profile_dimension:
        return profile_dimension
    signal_names = memory_item_signal_names(item)
    if not signal_names:
        return None
    return signal_definition(signal_names[0]).dimension


def update_profile_value(
    *,
    existing_value: str | None,
    dimension: str,
    signal_definitions: list[PreferenceSignalDefinition],
    source_text: str | None,
    session_id: str | None,
    updated_at: str,
) -> str:
    profile = parse_profile_value(existing_value or "") or {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "dimension": dimension,
        "signals": [],
        "active_values": [],
    }
    signals = [
        dict(item)
        for item in profile.get("signals", [])
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]

    for definition in signal_definitions:
        signals = [
            item
            for item in signals
            if not _is_conflicting_signal(existing=item, incoming=definition)
            and str(item.get("name")) != definition.name
        ]
        signals.append(
            {
                "name": definition.name,
                "label": definition.label,
                "dimension": definition.dimension,
                "family": definition.family,
                "polarity": definition.polarity,
                "confidence": 0.95,
                "source": "explicit_user_input",
                "source_text": source_text or "",
                "source_session_id": session_id or "",
                "updated_at": updated_at,
            }
        )

    signals.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
    signals = signals[:12]
    profile = {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "dimension": dimension,
        "signals": signals,
        "active_values": [str(item["name"]) for item in signals if item.get("name")],
        "last_updated_at": updated_at,
    }
    return dump_profile_value(profile)


def signals_conflict(first_signal: str, second_signal: str) -> bool:
    first = signal_definition(first_signal)
    second = signal_definition(second_signal)
    return first.dimension == second.dimension and first.family == second.family and first.name != second.name


def legacy_key_replaced_by_profile(item: dict[str, Any], available_profile_dimensions: set[str]) -> bool:
    dimension = memory_item_dimension(item)
    return bool(dimension and not dimension_from_profile_key(str(item.get("key") or "")) and dimension in available_profile_dimensions)


def _is_conflicting_signal(*, existing: dict[str, Any], incoming: PreferenceSignalDefinition) -> bool:
    existing_name = str(existing.get("name") or "")
    if not existing_name:
        return False
    return signals_conflict(existing_name, incoming.name)
