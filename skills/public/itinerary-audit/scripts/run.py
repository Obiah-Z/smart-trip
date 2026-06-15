"""Itinerary Audit Skill 沙箱执行脚本。

该脚本用于在受限子进程中执行确定性行程审计：
- 输入：--payload-json 传入路线、预算、住宿、天气等上游结果。
- 输出：stdout 打印审计 JSON，供 ToolService 和 Agent 链路继续消费。
- 注意：stdout 不应混入调试文本，否则主进程 json.loads 会失败。
"""

from __future__ import annotations

import argparse
import json
from typing import Any


def build_audit_response(*, payload: dict[str, Any]) -> dict[str, Any]:
    """对工具链生成的行程做确定性审计。

    该 Skill 主要服务复杂规划：检查天数、排除景点、住宿、预算、节奏密度和天气上下文。
    它输出 issues/warnings，后续 AgentService 和 LangGraph Reviewer 会继续整合这些结果。
    """
    destination = str(payload.get("destination", "")).strip()
    requested_days = _coerce_int(payload.get("days"), default=0, minimum=0, maximum=30)
    budget = _coerce_int(payload.get("budget"), default=0, minimum=0, maximum=500000)
    pace = str(payload.get("pace") or "balanced").strip()
    preferences = _as_string_list(payload.get("preferences", []))
    excluded_attractions = _as_string_list(payload.get("excluded_attractions", []))
    route_days = _as_dict_list(payload.get("route_days", []))
    hotel_options = _as_dict_list(payload.get("hotel_options", []))
    weather = payload.get("weather") if isinstance(payload.get("weather"), dict) else {}
    budget_optimization = (
        payload.get("budget_optimization") if isinstance(payload.get("budget_optimization"), dict) else {}
    )

    checks = [
        _check_day_count(requested_days=requested_days, route_days=route_days),
        _check_exclusions(route_days=route_days, excluded_attractions=excluded_attractions),
        _check_hotel(days=requested_days, preferences=preferences, hotel_options=hotel_options),
        _check_budget(budget=budget, budget_optimization=budget_optimization),
        _check_pace_density(pace=pace, route_days=route_days),
        _check_weather(weather=weather),
    ]
    issues = [check for check in checks if not check["passed"] and check["severity"] == "error"]
    warnings = [check for check in checks if not check["passed"] and check["severity"] == "warning"]
    audit_status = "approved"
    if issues:
        audit_status = "needs_review"
    elif warnings:
        audit_status = "approved_with_warnings"

    return {
        "destination": destination,
        "audit_status": audit_status,
        "summary": _build_summary(audit_status=audit_status, issues=issues, warnings=warnings),
        "passed_checks": [
            {"name": check["name"], "passed": check["passed"]}
            for check in checks
        ],
        "issues": issues,
        "warnings": warnings,
        "recommendations": _build_recommendations(audit_status=audit_status, issues=issues, warnings=warnings),
        "safe_to_present": audit_status != "needs_review",
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


def _check_day_count(*, requested_days: int, route_days: list[dict[str, Any]]) -> dict[str, Any]:
    """检查路线天数是否匹配用户已确认天数。"""
    actual_days = len(route_days)
    passed = requested_days > 0 and actual_days == requested_days
    return {
        "name": "day_count_match",
        "passed": passed,
        "severity": "error",
        "message": f"请求 {requested_days} 天，当前路线为 {actual_days} 天。",
        "expected": requested_days,
        "actual": actual_days,
    }


def _check_exclusions(*, route_days: list[dict[str, Any]], excluded_attractions: list[str]) -> dict[str, Any]:
    """检查路线中是否仍出现用户明确排除的景点或区域。"""
    if not excluded_attractions:
        return {
            "name": "excluded_attractions_absent",
            "passed": True,
            "severity": "error",
            "message": "没有排除景点约束。",
            "matched_terms": [],
        }
    activities = []
    for day in route_days:
        for item in day.get("activities", []) or []:
            activities.append(str(item))
        for item in day.get("route", []) or []:
            activities.append(str(item))
        if day.get("area"):
            activities.append(str(day["area"]))
    matched_terms = [
        term
        for term in excluded_attractions
        if any(term and term.lower() in activity.lower() for activity in activities)
    ]
    return {
        "name": "excluded_attractions_absent",
        "passed": not matched_terms,
        "severity": "error",
        "message": "路线中不应出现用户明确排除的景点或区域。",
        "matched_terms": matched_terms,
    }


def _check_hotel(*, days: int, preferences: list[str], hotel_options: list[dict[str, Any]]) -> dict[str, Any]:
    """检查多日行程是否有住宿候选，并校验安静住宿偏好。"""
    if days <= 1:
        return {
            "name": "hotel_available",
            "passed": True,
            "severity": "warning",
            "message": "单日咨询不要求住宿。",
        }
    if not hotel_options:
        return {
            "name": "hotel_available",
            "passed": False,
            "severity": "warning",
            "message": "多日行程缺少住宿候选。",
        }
    if "quiet_hotel" in preferences and not any(bool(item.get("quiet")) for item in hotel_options):
        return {
            "name": "hotel_available",
            "passed": False,
            "severity": "warning",
            "message": "用户偏好安静住宿，但候选酒店未体现安静属性。",
        }
    return {
        "name": "hotel_available",
        "passed": True,
        "severity": "warning",
        "message": "住宿候选可用。",
    }


def _check_budget(*, budget: int, budget_optimization: dict[str, Any]) -> dict[str, Any]:
    """检查预算优化结果是否在用户预算范围内。"""
    if budget <= 0:
        return {
            "name": "budget_within_limit",
            "passed": True,
            "severity": "warning",
            "message": "用户未指定预算，不做超限判断。",
        }
    total_estimated = _coerce_int(budget_optimization.get("total_estimated"), default=0, minimum=0, maximum=500000)
    if total_estimated <= 0:
        return {
            "name": "budget_within_limit",
            "passed": False,
            "severity": "warning",
            "message": "缺少预算优化结果，无法确认是否超预算。",
        }
    return {
        "name": "budget_within_limit",
        "passed": total_estimated <= budget + 600,
        "severity": "error",
        "message": f"预算 {budget} 元，估算花费 {total_estimated} 元，系统允许 600 元以内的舒适度升级弹性。",
        "budget": budget,
        "total_estimated": total_estimated,
    }


def _check_pace_density(*, pace: str, route_days: list[dict[str, Any]]) -> dict[str, Any]:
    """根据每日活动数量粗略判断节奏密度是否匹配。"""
    if not route_days:
        return {
            "name": "pace_density_aligned",
            "passed": False,
            "severity": "warning",
            "message": "缺少路线，无法判断节奏密度。",
        }
    counts = [len(day.get("activities", []) or []) for day in route_days]
    average_count = sum(counts) / len(counts)
    if pace == "relaxed":
        passed = average_count <= 2.5
    elif pace == "intensive":
        passed = average_count >= 1.5
    else:
        passed = average_count <= 3.5
    return {
        "name": "pace_density_aligned",
        "passed": passed,
        "severity": "warning",
        "message": f"当前平均每天 {average_count:.1f} 个点位，节奏为 {pace}。",
        "average_activities_per_day": round(average_count, 2),
    }


def _check_weather(*, weather: dict[str, Any]) -> dict[str, Any]:
    """确认天气上下文是否可用。"""
    summary = str(weather.get("summary", "")).strip()
    return {
        "name": "weather_context_available",
        "passed": bool(summary),
        "severity": "warning",
        "message": "天气上下文可用。" if summary else "缺少天气上下文，最终回答应避免过度承诺户外适宜性。",
    }


def _build_summary(*, audit_status: str, issues: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> str:
    """把审计状态转换成一句摘要。"""
    if audit_status == "approved":
        return "方案通过核心一致性校验。"
    if audit_status == "approved_with_warnings":
        return f"方案可展示，但存在 {len(warnings)} 条需要提示的不确定性。"
    return f"方案存在 {len(issues)} 条硬冲突，需要修正后再展示。"


def _build_recommendations(
    *,
    audit_status: str,
    issues: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> list[str]:
    """根据失败检查生成修复建议。"""
    if audit_status == "approved":
        return ["最终回答可以正常展示。"]

    recommendations = []
    for item in [*issues, *warnings]:
        if item["name"] == "excluded_attractions_absent":
            recommendations.append("重新运行景点筛选和路线规划，确保排除景点不再进入路线。")
        elif item["name"] == "day_count_match":
            recommendations.append("按用户已确认天数重新生成 route_days。")
        elif item["name"] == "budget_within_limit":
            recommendations.append("下调住宿或体验预算，确保总估算不超过用户预算。")
        elif item["name"] == "hotel_available":
            recommendations.append("补充住宿候选，或在最终回答中明确住宿待确认。")
        elif item["name"] == "weather_context_available":
            recommendations.append("最终回答中避免给出过强天气确定性。")
    return list(dict.fromkeys(recommendations)) or ["保守展示结果，并提示用户可继续调整。"]


def main() -> None:
    """Skill 子进程入口：读取 payload 并输出审计 JSON。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload-json", required=True)
    args = parser.parse_args()

    payload = json.loads(args.payload_json)
    result = build_audit_response(payload=payload)
    # 沙箱只把 stdout 当作结构化结果读取，因此这里必须输出单个 JSON 对象。
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
