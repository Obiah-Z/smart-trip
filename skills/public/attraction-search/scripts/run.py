from __future__ import annotations

import argparse
import json
from typing import Any

from app.mock.travel_engine import load_travel_data, select_attractions


VALID_PACES = {"relaxed", "balanced", "intensive"}


def build_attraction_response(*, data: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """根据目的地、偏好、天数、节奏和排除景点筛选候选点位。

    这个 Skill 输出会被 route.plan、budget.optimize、itinerary.audit 和 AgentService 继续消费，
    因此返回结构中保留了 matched、warnings、selection_strategy 等调试字段。
    """
    destination = str(payload.get("destination", "")).strip()
    preferences = _as_string_list(payload.get("preferences", []))
    days, day_warning = _coerce_days(payload.get("days", 3))
    pace, pace_warning = _coerce_pace(payload.get("pace", "balanced"))
    excluded_attractions = _as_string_list(payload.get("excluded_attractions", []) or [])
    warnings = [item for item in (day_warning, pace_warning) if item]

    if not destination:
        return {
            "destination": "",
            "matched": False,
            "preferences": preferences,
            "days": days,
            "pace": pace,
            "excluded_attractions": excluded_attractions,
            "selection_strategy": _selection_strategy(excluded_attractions=excluded_attractions),
            "attractions": [],
            "warnings": ["missing_destination", *warnings],
        }

    matched = destination in data.get("attractions", {})
    result = select_attractions(
        data=data,
        destination=destination,
        preferences=preferences,
        days=days,
        pace=pace,
        excluded_attractions=excluded_attractions,
    )
    if not matched:
        warnings.append("unknown_destination")
    if matched and not result.get("attractions"):
        warnings.append("no_attractions_after_filtering")

    return {
        "destination": destination,
        "matched": matched,
        "preferences": preferences,
        "days": days,
        "pace": pace,
        "excluded_attractions": excluded_attractions,
        "selection_strategy": _selection_strategy(excluded_attractions=excluded_attractions),
        **result,
        "warnings": warnings,
    }


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))


def _coerce_days(value: Any) -> tuple[int, str | None]:
    """把外部传入天数限制在路线规划可处理的安全范围内。"""
    try:
        days = int(value)
    except (TypeError, ValueError):
        return 3, "invalid_days_defaulted_to_3"
    if days < 1:
        return 1, "days_clamped_to_1"
    if days > 14:
        return 14, "days_clamped_to_14"
    return days, None


def _coerce_pace(value: Any) -> tuple[str, str | None]:
    """只接受系统定义的三种节奏，非法值回退到 balanced。"""
    pace = str(value or "balanced").strip()
    if pace not in VALID_PACES:
        return "balanced", "invalid_pace_defaulted_to_balanced"
    return pace, None


def _selection_strategy(*, excluded_attractions: list[str]) -> dict[str, bool]:
    """描述当前筛选策略，方便开发调试视图解释点位来源。"""
    return {
        "preference_filtering": True,
        "pace_aware": True,
        "exclusion_applied": bool(excluded_attractions),
        "diversified_by_area": True,
    }


def main() -> None:
    """Skill 子进程入口：从 --payload-json 读取输入，并向 stdout 输出 JSON。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload-json", required=True)
    args = parser.parse_args()

    payload = json.loads(args.payload_json)
    data = load_travel_data()
    result = build_attraction_response(data=data, payload=payload)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
