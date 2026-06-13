from __future__ import annotations

import argparse
import json
from typing import Any

from app.mock.travel_engine import load_travel_data, select_hotels


def build_hotel_response(*, data: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """根据预算和住宿偏好筛选酒店候选。

    输出的 hotels 会被 AgentService 用于住宿推荐、预算估算和 stayAdvice 生成。
    """
    destination = str(payload.get("destination", "")).strip()
    budget, budget_warning = _coerce_budget(payload.get("budget", 3000))
    preferences = _as_string_list(payload.get("preferences", []))
    warnings = [budget_warning] if budget_warning else []

    if not destination:
        return {
            "destination": "",
            "matched": False,
            "budget": budget,
            "preferences": preferences,
            "nightly_budget": max(220, budget // 3 // 2),
            "selection_strategy": _selection_strategy(preferences=preferences),
            "hotels": [],
            "warnings": ["missing_destination", *warnings],
        }

    matched = destination in data.get("hotels", {})
    result = select_hotels(data=data, destination=destination, budget=budget, preferences=preferences)
    if not matched:
        warnings.append("unknown_destination")
    if matched and not result.get("hotels"):
        warnings.append("no_hotels_after_filtering")

    return {
        "destination": destination,
        "matched": matched,
        "budget": budget,
        "preferences": preferences,
        "selection_strategy": _selection_strategy(preferences=preferences),
        **result,
        "warnings": warnings,
    }


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))


def _coerce_budget(value: Any) -> tuple[int, str | None]:
    """规范预算输入，避免异常或极端值传入住宿筛选逻辑。"""
    try:
        budget = int(value)
    except (TypeError, ValueError):
        return 3000, "invalid_budget_defaulted_to_3000"
    if budget <= 0:
        return 3000, "missing_budget_defaulted_to_3000"
    if budget > 200000:
        return 200000, "budget_clamped_to_200000"
    return budget, None


def _selection_strategy(*, preferences: list[str]) -> dict[str, bool]:
    """返回本次住宿筛选使用到的偏好信号。"""
    return {
        "budget_aware": True,
        "quiet_required": "quiet_hotel" in preferences,
        "lively_preferred": "lively_hotel" in preferences,
        "comfort_required": "comfortable_hotel" in preferences,
        "family_preferred": "family" in preferences,
    }


def main() -> None:
    """Skill 子进程入口：读取 payload 并输出酒店候选 JSON。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload-json", required=True)
    args = parser.parse_args()

    payload = json.loads(args.payload_json)
    data = load_travel_data()
    result = build_hotel_response(data=data, payload=payload)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
