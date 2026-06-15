"""Budget Optimize Skill 沙箱执行脚本。

该文件遵循统一 Skill 脚本协议，由 SkillSandboxRunner 以独立子进程运行：
- 输入：--payload-json 传入结构化 payload。
- 输出：stdout 打印 JSON，主进程通过 json.loads(stdout) 取回 output。
- 约束：不要在这里直接读写业务状态，跨模块状态由上游 payload 显式传入。
"""

from __future__ import annotations

import argparse
import json
from typing import Any


def build_budget_response(*, payload: dict[str, Any]) -> dict[str, Any]:
    """生成预算拆分和住宿升级建议。

    该 Skill 依赖 hotel.search、route.plan、attraction.search 的结果。它不会重新生成路线，
    只根据已有候选计算交通、住宿、餐饮、门票、体验和 buffer 的预算分配。
    """
    destination = str(payload.get("destination", "")).strip()
    days = _coerce_int(payload.get("days"), default=1, minimum=1, maximum=30)
    budget = _coerce_int(payload.get("budget"), default=0, minimum=0, maximum=500000)
    target_budget = _coerce_int(payload.get("target_budget"), default=budget, minimum=0, maximum=500000)
    budget_policy = str(payload.get("budget_policy") or "").strip()
    pace = str(payload.get("pace") or "balanced").strip()
    preferences = _as_string_list(payload.get("preferences", []))
    hotel_options = _as_dict_list(payload.get("hotel_options", []))
    route_days = _as_dict_list(payload.get("route_days", []))
    attraction_items = _as_dict_list(payload.get("attraction_items", []))
    warnings: list[str] = []

    if not destination:
        warnings.append("missing_destination")
    if budget <= 0 and target_budget <= 0:
        warnings.append("missing_budget")
    if not hotel_options and days >= 2:
        warnings.append("missing_hotel_options")
    if not route_days:
        warnings.append("missing_route_days")

    resolved_target = target_budget or budget
    nights = max(1, days - 1) if days >= 2 else 0
    tickets = sum(max(0, _coerce_int(item.get("cost"), default=0, minimum=0, maximum=5000)) for item in attraction_items)
    transport = _estimate_transport(days=days, target_budget=resolved_target, pace=pace)
    food = _estimate_food(days=days, target_budget=resolved_target, preferences=preferences)
    selected_hotel = _select_hotel(
        hotel_options=hotel_options,
        nights=nights,
        target_budget=resolved_target,
        fixed_cost=transport + food + tickets,
        preferences=preferences,
        budget_policy=budget_policy,
    )
    accommodation = int(selected_hotel.get("pricePerNight", 0)) * nights if selected_hotel else 0

    breakdown = {
        "transport": transport,
        "accommodation": accommodation,
        "food": food,
        "tickets": tickets,
        "experience": 0,
        "buffer": 0,
    }
    subtotal = sum(breakdown.values())
    remaining = max(0, resolved_target - subtotal) if resolved_target else 0

    if budget_policy == "target_near" and resolved_target > 0 and remaining > 0:
        food_boost = min(remaining, max(120, days * 90))
        breakdown["food"] += food_boost
        remaining -= food_boost
        if remaining > 0:
            breakdown["experience"] = remaining
            remaining = 0
    else:
        breakdown["buffer"] = remaining
        remaining = 0

    total_estimated = sum(breakdown.values())
    budget_status = _budget_status(total=total_estimated, target_budget=resolved_target)
    if budget_status == "over_budget":
        warnings.append("budget_overrun")

    upgrade_focus = _upgrade_focus(preferences=preferences, budget_policy=budget_policy)
    recommendations = _build_recommendations(
        budget_status=budget_status,
        selected_hotel=selected_hotel,
        upgrade_focus=upgrade_focus,
        breakdown=breakdown,
        target_budget=resolved_target,
    )

    return {
        "destination": destination,
        "days": days,
        "budget_status": budget_status,
        "target_budget": resolved_target,
        "total_estimated": total_estimated,
        "remaining_budget": max(0, resolved_target - total_estimated) if resolved_target else 0,
        "budget_breakdown": breakdown,
        "selected_hotel": selected_hotel,
        "optimization_strategy": {
            "policy": budget_policy or "standard",
            "upgrade_focus": upgrade_focus,
            "nights": nights,
            "pace": pace,
        },
        "recommendations": recommendations,
        "warnings": list(dict.fromkeys(warnings)),
    }


def _coerce_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))


def _as_dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _estimate_transport(*, days: int, target_budget: int, pace: str) -> int:
    """估算市内交通/往返弹性成本；紧凑节奏默认增加交通余量。"""
    if target_budget <= 0:
        return max(300, days * 120)
    base = max(300, target_budget // 6)
    if pace == "intensive":
        base += days * 40
    return base


def _estimate_food(*, days: int, target_budget: int, preferences: list[str]) -> int:
    """按餐饮偏好估算每日餐饮预算。"""
    daily = 120
    if "local_food" in preferences or "food" in preferences:
        daily = 160
    if "avoid_local_food" in preferences or "avoid_food" in preferences:
        daily = 100
    if target_budget >= 8000:
        daily += 60
    return max(200, days * daily)


def _select_hotel(
    *,
    hotel_options: list[dict[str, Any]],
    nights: int,
    target_budget: int,
    fixed_cost: int,
    preferences: list[str],
    budget_policy: str,
) -> dict[str, Any] | None:
    """选择用于预算拆分的主酒店。

    comfortable_hotel 优先看舒适度；target_near 会在目标预算内尽量选择更高品质住宿。
    """
    if not hotel_options or nights <= 0:
        return None
    if "comfortable_hotel" in preferences:
        return max(
            hotel_options,
            key=lambda item: (
                float(item.get("comfortScore", 0) or 0),
                float(item.get("rating", 0) or 0),
                int(item.get("pricePerNight", 0) or 0),
            ),
        )
    if budget_policy == "target_near":
        hotel_cap = max(0, target_budget - fixed_cost) if target_budget else 0
        affordable = [
            item
            for item in hotel_options
            if target_budget <= 0 or int(item.get("pricePerNight", 0) or 0) * nights <= hotel_cap
        ]
        candidates = affordable or hotel_options
        return max(
            candidates,
            key=lambda item: (
                float(item.get("comfortScore", 0) or 0),
                float(item.get("rating", 0) or 0),
                int(item.get("pricePerNight", 0) or 0),
            ),
        )
    return hotel_options[0]


def _budget_status(*, total: int, target_budget: int) -> str:
    """把估算总额转成预算状态标签。"""
    if target_budget <= 0:
        return "no_budget"
    if total > target_budget + 600:
        return "over_budget"
    if total > target_budget:
        return "within_tolerance"
    if total >= int(target_budget * 0.85):
        return "near_target"
    return "within_budget"


def _upgrade_focus(*, preferences: list[str], budget_policy: str) -> str:
    """判断预算增量应该优先投入住宿、餐饮、体验还是均衡分配。"""
    if "comfortable_hotel" in preferences:
        return "accommodation"
    if budget_policy == "target_near":
        return "experience"
    if "local_food" in preferences or "food" in preferences:
        return "food"
    return "balanced"


def _build_recommendations(
    *,
    budget_status: str,
    selected_hotel: dict[str, Any] | None,
    upgrade_focus: str,
    breakdown: dict[str, int],
    target_budget: int,
) -> list[str]:
    """生成面向最终回答的预算优化建议。"""
    recommendations: list[str] = []
    if selected_hotel:
        recommendations.append(f"推荐住宿优先选择 {selected_hotel.get('name')}，预算中已计入住宿费用。")
    if upgrade_focus == "accommodation":
        recommendations.append("已优先把预算增量用于住宿舒适度提升。")
    elif upgrade_focus == "food":
        recommendations.append("餐饮预算已按本地特色体验适度上调。")
    elif breakdown.get("experience", 0) > 0:
        recommendations.append("剩余预算可用于体验项目、打车舒适度或临时加餐。")
    if budget_status == "over_budget":
        recommendations.append("当前估算超过预算，建议降低住宿单价或减少付费景点。")
    elif target_budget > 0:
        recommendations.append("当前预算拆分已保留交通、餐饮、住宿和门票的基础弹性。")
    return recommendations


def main() -> None:
    """Skill 子进程入口：读取 payload 并输出预算优化 JSON。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload-json", required=True)
    args = parser.parse_args()

    payload = json.loads(args.payload_json)
    result = build_budget_response(payload=payload)
    # stdout 是 Skill 与主服务之间的返回通道，必须保持为可解析 JSON。
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
