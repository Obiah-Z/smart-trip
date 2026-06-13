from __future__ import annotations

from typing import Any


class PlanReviewer:
    """Deterministic final-plan checks and local repair helpers."""

    def build_review(
        self,
        *,
        final_plan: dict[str, Any],
        structured_constraints: dict[str, Any],
    ) -> dict[str, Any]:
        issues = [
            *self._review_excluded_attractions(final_plan=final_plan, structured_constraints=structured_constraints),
            *self._review_hotel_availability(final_plan=final_plan, structured_constraints=structured_constraints),
            *self._review_budget(final_plan=final_plan, structured_constraints=structured_constraints),
            *self._review_day_count(final_plan=final_plan, structured_constraints=structured_constraints),
        ]
        hard_issues = [item for item in issues if item["severity"] == "error"]
        repairable_issues = [item for item in issues if item.get("repairable")]
        needs_repair = bool(repairable_issues)
        needs_attention = bool(issues)
        if not issues:
            summary = "LangGraph Reviewer 未发现结构性冲突。"
        else:
            summary = (
                f"LangGraph Reviewer 发现 {len(issues)} 个待处理问题，"
                f"其中 {len(hard_issues)} 个硬冲突、{len(repairable_issues)} 个可自动修复。"
            )
        return {
            "needs_repair": needs_repair,
            "needs_attention": needs_attention,
            "summary": summary,
            "issues": issues,
        }

    def apply_repairs(
        self,
        *,
        final_plan: dict[str, Any],
        structured_constraints: dict[str, Any],
        review: dict[str, Any],
    ) -> dict[str, Any]:
        repaired = dict(final_plan)
        issue_names = {item["name"] for item in review.get("issues", [])}
        if "excluded_attractions_present" in issue_names:
            repaired = self._repair_excluded_attractions(
                final_plan=repaired,
                structured_constraints=structured_constraints,
            )
        if "hotel_missing" in issue_names:
            repaired = self._repair_missing_hotel(
                final_plan=repaired,
                structured_constraints=structured_constraints,
            )
        if "budget_over_limit" in issue_names:
            repaired = self._repair_budget_over_limit(
                final_plan=repaired,
                structured_constraints=structured_constraints,
            )
        return repaired

    def build_repair_notes(
        self,
        *,
        original_review: dict[str, Any],
        repaired_review: dict[str, Any],
    ) -> list[str]:
        notes = []
        original_issue_names = {item["name"] for item in original_review.get("issues", [])}
        remaining_issue_names = {item["name"] for item in repaired_review.get("issues", [])}
        fixed_issue_names = original_issue_names - remaining_issue_names
        if "excluded_attractions_present" in fixed_issue_names:
            notes.append("已移除最终展示结构中的排除景点相关内容。")
        if "hotel_missing" in fixed_issue_names:
            notes.append("已补充住宿待确认占位信息，避免多日行程住宿为空。")
        if "budget_over_limit" in fixed_issue_names:
            notes.append("已按预算上限压缩预算展示。")
        if remaining_issue_names:
            notes.append(f"仍需关注：{', '.join(sorted(remaining_issue_names))}。")
        return notes or ["已执行局部修复。"]

    def _review_excluded_attractions(
        self,
        *,
        final_plan: dict[str, Any],
        structured_constraints: dict[str, Any],
    ) -> list[dict[str, Any]]:
        excluded = self._resolve_excluded_terms(structured_constraints=structured_constraints)
        if not excluded:
            return []
        plan_text_items = self._collect_plan_text_items(final_plan=final_plan)
        matched = [
            term
            for term in excluded
            if any(term.lower() in item.lower() for item in plan_text_items)
        ]
        if not matched:
            return []
        return [
            {
                "name": "excluded_attractions_present",
                "severity": "error",
                "repairable": True,
                "matched_terms": matched,
                "message": "最终方案中仍出现用户明确排除的景点或区域。",
            }
        ]

    def _review_hotel_availability(
        self,
        *,
        final_plan: dict[str, Any],
        structured_constraints: dict[str, Any],
    ) -> list[dict[str, Any]]:
        days = int(structured_constraints.get("days") or 0)
        if days <= 1:
            return []
        hotels = list(final_plan.get("hotelOptions") or final_plan.get("hotelRecommendation") or [])
        if hotels:
            return []
        return [
            {
                "name": "hotel_missing",
                "severity": "warning",
                "repairable": True,
                "message": "多日行程缺少住宿推荐。",
            }
        ]

    def _review_budget(
        self,
        *,
        final_plan: dict[str, Any],
        structured_constraints: dict[str, Any],
    ) -> list[dict[str, Any]]:
        budget_limit = int(structured_constraints.get("budget") or 0)
        if budget_limit <= 0:
            return []
        total_budget = int((final_plan.get("summary") or {}).get("totalBudget") or 0)
        if total_budget <= budget_limit + 600:
            return []
        return [
            {
                "name": "budget_over_limit",
                "severity": "error",
                "repairable": True,
                "budget_limit": budget_limit,
                "total_budget": total_budget,
                "message": "最终方案预算明显超过用户预算上限。",
            }
        ]

    def _review_day_count(
        self,
        *,
        final_plan: dict[str, Any],
        structured_constraints: dict[str, Any],
    ) -> list[dict[str, Any]]:
        requested_days = structured_constraints.get("days")
        if not isinstance(requested_days, int) or requested_days <= 0:
            return []
        route_days = list(final_plan.get("days") or [])
        if len(route_days) == requested_days:
            return []
        return [
            {
                "name": "day_count_mismatch",
                "severity": "error",
                "repairable": False,
                "requested_days": requested_days,
                "actual_days": len(route_days),
                "message": "最终方案天数和用户已确认天数不一致。",
            }
        ]

    def _collect_plan_text_items(self, *, final_plan: dict[str, Any]) -> list[str]:
        items: list[str] = []
        for day in final_plan.get("days") or []:
            if not isinstance(day, dict):
                continue
            items.extend(str(item) for item in day.get("activities", []) or [])
            items.extend(str(item) for item in day.get("route", []) or [])
            if day.get("theme"):
                items.append(str(day["theme"]))
            if day.get("area"):
                items.append(str(day["area"]))
        for key in ("dailyGuide", "attractionRecommendations", "foodRecommendations", "planHighlights", "tripTips"):
            self._collect_nested_text(value=final_plan.get(key), items=items)
        return [item for item in items if item.strip()]

    def _collect_nested_text(self, *, value: Any, items: list[str]) -> None:
        if isinstance(value, str):
            items.append(value)
            return
        if isinstance(value, list):
            for item in value:
                self._collect_nested_text(value=item, items=items)
            return
        if isinstance(value, dict):
            for item in value.values():
                self._collect_nested_text(value=item, items=items)

    def _repair_excluded_attractions(
        self,
        *,
        final_plan: dict[str, Any],
        structured_constraints: dict[str, Any],
    ) -> dict[str, Any]:
        excluded = self._resolve_excluded_terms(structured_constraints=structured_constraints)
        if not excluded:
            return final_plan

        def allowed_text(value: Any) -> bool:
            text = str(value)
            return not any(term.lower() in text.lower() for term in excluded)

        repaired_days = []
        for day in final_plan.get("days") or []:
            if not isinstance(day, dict):
                continue
            repaired_day = dict(day)
            repaired_day["activities"] = [
                item for item in day.get("activities", []) or []
                if allowed_text(item)
            ]
            if "route" in repaired_day:
                repaired_day["route"] = [
                    item for item in day.get("route", []) or []
                    if allowed_text(item)
                ]
            repaired_days.append(repaired_day)

        repaired = {
            **final_plan,
            "days": repaired_days,
            "dailyGuide": self._filter_dict_list_by_exclusions(
                items=final_plan.get("dailyGuide") or [],
                excluded=excluded,
            ),
            "attractionRecommendations": self._filter_dict_list_by_exclusions(
                items=final_plan.get("attractionRecommendations") or [],
                excluded=excluded,
            ),
            "foodRecommendations": self._filter_dict_list_by_exclusions(
                items=final_plan.get("foodRecommendations") or [],
                excluded=excluded,
            ),
            "planHighlights": [
                item for item in final_plan.get("planHighlights") or []
                if allowed_text(item)
            ],
            "tripTips": [
                item for item in final_plan.get("tripTips") or []
                if allowed_text(item)
            ],
        }
        repaired.setdefault("itineraryAudit", {})
        repaired["itineraryAudit"] = {
            **(repaired.get("itineraryAudit") or {}),
            "workflow_exclusion_repair": {
                "removed_terms": excluded,
                "message": "LangGraph Reviewer 已从最终方案展示结构中移除排除景点相关内容。",
            },
        }
        return repaired

    def _filter_dict_list_by_exclusions(
        self,
        *,
        items: list[Any],
        excluded: list[str],
    ) -> list[Any]:
        filtered: list[Any] = []
        for item in items:
            serialized = str(item)
            if any(term.lower() in serialized.lower() for term in excluded):
                continue
            filtered.append(item)
        return filtered

    def _repair_missing_hotel(
        self,
        *,
        final_plan: dict[str, Any],
        structured_constraints: dict[str, Any],
    ) -> dict[str, Any]:
        destination = structured_constraints.get("destination") or "目的地"
        fallback_hotel = {
            "name": f"{destination}舒适住宿待确认",
            "area": "核心交通便利区域",
            "pricePerNight": 0,
            "rating": None,
            "quiet": "quiet_hotel" in (structured_constraints.get("preferences") or []),
            "tags": ["fallback_hotel", *(
                ["quiet_hotel"] if "quiet_hotel" in (structured_constraints.get("preferences") or []) else []
            )],
            "reason": "当前工具未返回可用酒店候选，先提示住宿需要继续确认，避免空白推荐。",
        }
        return {
            **final_plan,
            "hotelRecommendation": [fallback_hotel],
            "hotelOptions": [fallback_hotel],
            "stayAdvice": {
                "recommendedArea": fallback_hotel["area"],
                "nightlyBudget": 0,
                "stayNights": max(1, int(structured_constraints.get("days") or 1) - 1),
                "recommendedHotel": fallback_hotel["name"],
                "backupHotel": None,
                "reason": fallback_hotel["reason"],
            },
        }

    def _repair_budget_over_limit(
        self,
        *,
        final_plan: dict[str, Any],
        structured_constraints: dict[str, Any],
    ) -> dict[str, Any]:
        budget_limit = int(structured_constraints.get("budget") or 0)
        if budget_limit <= 0:
            return final_plan
        budget = dict(final_plan.get("budget") or {})
        total = sum(int(value or 0) for value in budget.values() if isinstance(value, (int, float)))
        if total <= 0:
            return final_plan
        scale = min(1.0, budget_limit / total)
        adjusted_budget = {
            key: int(value * scale) if isinstance(value, (int, float)) else value
            for key, value in budget.items()
        }
        adjusted_total = sum(int(value or 0) for value in adjusted_budget.values() if isinstance(value, (int, float)))
        summary = dict(final_plan.get("summary") or {})
        summary["totalBudget"] = adjusted_total
        budget_insights = list(final_plan.get("budgetInsights") or [])
        budget_insights.insert(
            0,
            {
                "label": "预算修复",
                "value": f"控制到约 ¥{adjusted_total}",
                "detail": "LangGraph Reviewer 检测到预算超限，已按预算上限做保守压缩展示。",
            },
        )
        return {
            **final_plan,
            "summary": summary,
            "budget": adjusted_budget,
            "budgetInsights": budget_insights,
        }

    def _resolve_excluded_terms(self, *, structured_constraints: dict[str, Any]) -> list[str]:
        return [
            str(item).strip()
            for item in (
                structured_constraints.get("expanded_excluded_attractions")
                or structured_constraints.get("excluded_attractions")
                or []
            )
            if str(item).strip()
        ]
