"""Route Plan Skill 沙箱执行脚本。

该文件是 route.plan 的跨进程执行入口，不是主服务直接调用的函数模块：
- 输入：SkillSandboxRunner 通过 --payload-json 注入目的地、天数、候选景点等参数。
- 输出：脚本将结果 JSON 打印到 stdout，沙箱解析后包装为 tool_result["output"]。
- 安全：网络、子进程、写入目录和资源限制由 sandbox_policy 控制。
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from app.capabilities.mock.travel_engine import plan_route


VALID_PACES = {"relaxed", "balanced", "intensive"}


def build_route_response(*, payload: dict[str, Any]) -> dict[str, Any]:
    """把候选景点整理成按天路线。

    route.plan 通常依赖 attraction.search 的结果；当没有候选点位时会退到城市漫步占位，
    保证链路不中断，同时通过 warnings 告知上层结果质量。
    """
    destination = str(payload.get("destination", "")).strip()
    days, day_warning = _coerce_days(payload.get("days", 3))
    pace, pace_warning = _coerce_pace(payload.get("pace", "balanced"))
    attraction_items = payload.get("attraction_items", []) or []
    attraction_names = _as_string_list(payload.get("attraction_names", []))
    excluded_attractions = _as_string_list(payload.get("excluded_attractions", []) or [])
    warnings = [item for item in (day_warning, pace_warning) if item]

    if not destination:
        warnings.append("missing_destination")
    if not isinstance(attraction_items, list):
        attraction_items = []
        warnings.append("invalid_attraction_items_ignored")
    if not attraction_items and not attraction_names:
        warnings.append("missing_attraction_candidates_used_citywalk_fallback")

    result = plan_route(
        destination=destination or "未知目的地",
        days=days,
        pace=pace,
        attraction_items=attraction_items,
        attraction_names=attraction_names or ([f"{destination} 城市漫步"] if destination else []),
        excluded_attractions=excluded_attractions,
    )
    if not result.get("days"):
        warnings.append("empty_route_result")

    return {
        "destination": destination,
        "days_count": days,
        "pace": pace,
        "excluded_attractions": excluded_attractions,
        "route_strategy": {
            "area_grouping": True,
            "pace_capacity": True,
            "exclusion_applied": bool(excluded_attractions),
        },
        **result,
        "warnings": warnings,
    }


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))


def _coerce_days(value: Any) -> tuple[int, str | None]:
    """限制行程天数，防止异常输入生成过长路线。"""
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
    """校验节奏参数，非法值回退到 balanced。"""
    pace = str(value or "balanced").strip()
    if pace not in VALID_PACES:
        return "balanced", "invalid_pace_defaulted_to_balanced"
    return pace, None


def main() -> None:
    """Skill 子进程入口：读取 payload 并输出按天路线 JSON。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload-json", required=True)
    args = parser.parse_args()

    payload = json.loads(args.payload_json)
    result = build_route_response(payload=payload)
    # stdout 是沙箱协议的唯一成功返回通道，不能混入额外说明文本。
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
