from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from app.llm.openai_client import OpenAIPlannerClient
from app.skills.skill_registry import SkillDefinition


@dataclass(frozen=True)
class SkillSelectionItem:
    """一次 Skill 选择结果，包含选择原因和来源。"""

    skill_id: str
    reason: str
    source: str


class SkillSelectionService:
    """根据用户输入和结构化约束选择本轮需要执行的 Skills。

    选择优先级：简单咨询 fast path -> LLM 选择（可用时）-> 规则启发式兜底 ->
    规划必需 Skill 补齐 -> 依赖展开。这样可以兼顾响应速度、可解释性和复杂规划完整性。
    """

    ITINERARY_KEYWORDS = ("行程", "路线", "规划", "安排", "攻略", "几日游", "旅行方案", "旅游方案")
    ATTRACTION_KEYWORDS = (
        "景点",
        "去哪玩",
        "去哪里玩",
        "打卡",
        "文化",
        "自然",
        "美食",
        "citywalk",
        "博物馆",
        "推荐",
        "亲子",
        "带娃",
        "遛娃",
        "小朋友",
        "雨天",
        "室内",
    )
    HOTEL_KEYWORDS = ("酒店", "住宿", "民宿", "住哪里", "安静", "舒适", "舒服", "舒适度")
    WEATHER_KEYWORDS = ("天气", "气温", "外套", "穿什么", "步行", "适合旅游")
    BUDGET_KEYWORDS = ("预算", "花费", "费用", "总预算", "总花费", "提升预算", "提高预算", "省钱", "成本")
    SYSTEM_KEYWORDS = ("mcp", "skill", "skills", "工具", "能力", "知识桥接", "系统", "外部知识")

    def __init__(self, openai_client: OpenAIPlannerClient) -> None:
        self._openai_client = openai_client

    def select(
        self,
        *,
        user_input: str,
        structured_constraints: dict[str, Any],
        available_skills: list[SkillDefinition],
    ) -> list[SkillSelectionItem]:
        """选择并排序本轮可执行 Skill。"""
        resolved_days = structured_constraints.get("days") or 0
        followup_replan = structured_constraints.get("_followup_replan") is True
        consulting_fast_path = (
            not followup_replan
            and
            not self._contains_any(user_input, self.ITINERARY_KEYWORDS)
            and resolved_days <= 1
            and structured_constraints.get("budget", 0) == 0
        )
        if consulting_fast_path:
            # 天气/景点等轻咨询不走 LLM 选择，减少耗时并避免误补路线规划能力。
            heuristic = self._select_with_heuristics(
                user_input=user_input,
                structured_constraints=structured_constraints,
                available_skills=available_skills,
            )
            enriched = self._ensure_required_planning_skills(
                user_input=user_input,
                structured_constraints=structured_constraints,
                items=heuristic,
                available_skills=available_skills,
            )
            return self._expand_dependencies(items=enriched, available_skills=available_skills)

        if self._openai_client.enabled() and not followup_replan:
            try:
                candidates = self._openai_client.select_skills(
                    user_input=user_input,
                    structured_constraints=structured_constraints,
                    available_skills=available_skills,
                )
                normalized = self._normalize(candidates=candidates, available_skills=available_skills, source="llm")
                if normalized:
                    enriched = self._ensure_required_planning_skills(
                        user_input=user_input,
                        structured_constraints=structured_constraints,
                        items=normalized,
                        available_skills=available_skills,
                    )
                    return self._expand_dependencies(items=enriched, available_skills=available_skills)
            except (ValueError, KeyError, TypeError):
                pass

        heuristic = self._select_with_heuristics(
            user_input=user_input,
            structured_constraints=structured_constraints,
            available_skills=available_skills,
        )
        enriched = self._ensure_required_planning_skills(
            user_input=user_input,
            structured_constraints=structured_constraints,
            items=heuristic,
            available_skills=available_skills,
        )
        return self._expand_dependencies(items=enriched, available_skills=available_skills)

    def _ensure_required_planning_skills(
        self,
        *,
        user_input: str,
        structured_constraints: dict[str, Any],
        items: list[SkillSelectionItem],
        available_skills: list[SkillDefinition],
    ) -> list[SkillSelectionItem]:
        """为完整规划补齐关键 Skill。

        即使 LLM 或关键词只选中了 route.plan，多日旅行仍需要住宿、预算和审计等能力来保证
        输出可用性和约束一致性。
        """
        skills_by_id = {skill.skill_id: skill for skill in available_skills}
        item_map = {item.skill_id: item for item in items}
        resolved_days = structured_constraints.get("days") or 0
        followup_planning = structured_constraints.get("_followup_replan") is True
        itinerary_intent = followup_planning or self._contains_any(user_input, self.ITINERARY_KEYWORDS)

        should_add_hotel = (
            itinerary_intent
            and resolved_days >= 2
            and structured_constraints.get("destination")
            and "hotel.search" in skills_by_id
            and "hotel.search" not in item_map
        )
        if should_add_hotel:
            item_map["hotel.search"] = SkillSelectionItem(
                skill_id="hotel.search",
                reason="多日旅行规划默认补充住宿推荐，避免结果缺少落脚点。",
                source="policy",
            )

        should_add_budget_optimizer = (
            itinerary_intent
            and structured_constraints.get("destination")
            and "budget.optimize" in skills_by_id
            and "budget.optimize" not in item_map
            and (
                (structured_constraints.get("budget") or 0) > 0
                or (structured_constraints.get("target_budget") or 0) > 0
                or bool(structured_constraints.get("budget_policy"))
                or "comfortable_hotel" in (structured_constraints.get("preferences") or [])
                or self._contains_any(user_input, self.BUDGET_KEYWORDS)
            )
        )
        if should_add_budget_optimizer:
            item_map["budget.optimize"] = SkillSelectionItem(
                skill_id="budget.optimize",
                reason="当前规划包含预算、费用或住宿升级约束，需要生成预算拆分与优化建议。",
                source="policy",
            )

        should_add_itinerary_audit = (
            itinerary_intent
            and structured_constraints.get("destination")
            and resolved_days >= 1
            and "route.plan" in item_map
            and "itinerary.audit" in skills_by_id
            and "itinerary.audit" not in item_map
        )
        if should_add_itinerary_audit:
            item_map["itinerary.audit"] = SkillSelectionItem(
                skill_id="itinerary.audit",
                reason="按天路线生成后需要做天数、预算、住宿和排除景点一致性校验。",
                source="policy",
            )

        return sorted(item_map.values(), key=lambda item: skills_by_id[item.skill_id].priority)

    def _normalize(
        self,
        *,
        candidates: list[dict[str, Any]],
        available_skills: list[SkillDefinition],
        source: str,
    ) -> list[SkillSelectionItem]:
        """清洗 LLM 返回的候选 Skill，只保留注册表中存在且未重复的项。"""
        skills_by_id = {skill.skill_id: skill for skill in available_skills}
        items: list[SkillSelectionItem] = []
        seen: set[str] = set()
        for candidate in candidates:
            skill_id = str(candidate.get("skill_id", "")).strip()
            if skill_id not in skills_by_id or skill_id in seen:
                continue
            reason = str(candidate.get("reason") or f"选择 {skills_by_id[skill_id].display_name} 来补全当前问题。").strip()
            items.append(SkillSelectionItem(skill_id=skill_id, reason=reason, source=source))
            seen.add(skill_id)
        return items

    def _select_with_heuristics(
        self,
        *,
        user_input: str,
        structured_constraints: dict[str, Any],
        available_skills: list[SkillDefinition],
    ) -> list[SkillSelectionItem]:
        """规则型 Skill 选择兜底。

        这里显式区分天气咨询、景点推荐、多日规划、住宿、预算和系统能力查询，保证在模型
        不可用或不稳定时主链路仍能跑通。
        """
        text = user_input.lower()
        preferences = structured_constraints.get("preferences", [])
        itinerary_intent = self._contains_any(user_input, self.ITINERARY_KEYWORDS)
        followup_planning = structured_constraints.get("_followup_replan") is True
        attraction_intent = self._contains_any(user_input, self.ATTRACTION_KEYWORDS) or itinerary_intent
        hotel_intent = (
            self._contains_any(user_input, self.HOTEL_KEYWORDS)
            or "quiet_hotel" in preferences
            or "lively_hotel" in preferences
            or "comfortable_hotel" in preferences
        )
        weather_intent = self._contains_any(user_input, self.WEATHER_KEYWORDS) or self._matches_weather_question(user_input)
        explicit_budget = bool(re.search(r"预算\s*\d+|(\d{3,5})\s*元", user_input))
        budget_intent = (
            self._contains_any(user_input, self.BUDGET_KEYWORDS)
            or explicit_budget
            or bool(structured_constraints.get("budget_policy"))
            or (structured_constraints.get("target_budget") or 0) > 0
            or "comfortable_hotel" in preferences
        )
        system_intent = self._contains_any(text, self.SYSTEM_KEYWORDS)

        selected: list[SkillSelectionItem] = []
        for skill in available_skills:
            matched_keywords = [keyword for keyword in skill.trigger_keywords if keyword.lower() in text]
            include = False
            reason = ""

            if skill.skill_id == "knowledge.snapshot":
                include = system_intent
                reason = "用户在询问系统能力、MCP 或外部知识桥接状态。"
            elif skill.skill_id == "route.plan":
                include = itinerary_intent or followup_planning
                reason = "用户在请求按天行程规划，或在上一轮方案基础上继续调整。"
            elif skill.skill_id == "attraction.search":
                include = attraction_intent or followup_planning
                reason = "用户需要目的地景点、美食或兴趣点筛选结果。"
            elif skill.skill_id == "hotel.search":
                include = hotel_intent or followup_planning or (itinerary_intent and explicit_budget)
                reason = "用户提到了住宿偏好，或者预算信息需要纳入住宿决策。"
            elif skill.skill_id == "weather.lookup":
                include = weather_intent or itinerary_intent or followup_planning
                reason = "用户在规划旅行时需要天气适宜性作为补充判断。"
            elif skill.skill_id == "budget.optimize":
                include = budget_intent and (itinerary_intent or followup_planning)
                reason = "用户提供了预算、费用或住宿升级约束，需要进行预算优化。"
            elif skill.skill_id == "itinerary.audit":
                include = (itinerary_intent or followup_planning) and structured_constraints.get("destination")
                reason = "复杂路线生成后需要做最终一致性审计。"

            if not include and matched_keywords:
                if skill.skill_id == "weather.lookup" and not weather_intent:
                    continue
                if skill.skill_id == "budget.optimize" and not (budget_intent and (itinerary_intent or followup_planning)):
                    continue
                if skill.skill_id == "itinerary.audit" and not (itinerary_intent or followup_planning):
                    continue
                include = True
                reason = f"用户输入命中了该 skill 的触发词：{', '.join(matched_keywords[:3])}。"

            if include:
                selected.append(SkillSelectionItem(skill_id=skill.skill_id, reason=reason, source="heuristic"))

        if not selected and available_skills:
            fallback = next((skill for skill in available_skills if skill.skill_id == "attraction.search"), available_skills[0])
            selected.append(
                SkillSelectionItem(
                    skill_id=fallback.skill_id,
                    reason="未识别出明确的工具意图，先选择最通用的目的地推荐能力。",
                    source="heuristic",
                )
            )

        return selected

    def _expand_dependencies(
        self,
        *,
        items: list[SkillSelectionItem],
        available_skills: list[SkillDefinition],
    ) -> list[SkillSelectionItem]:
        """按 Skill 定义中的 depends_on 递归补齐依赖，并按 priority 排序。"""
        skills_by_id = {skill.skill_id: skill for skill in available_skills}
        explicit = {item.skill_id: item for item in items}
        ordered_items = sorted(items, key=lambda item: skills_by_id[item.skill_id].priority)
        resolved: list[SkillSelectionItem] = []
        visited: set[str] = set()

        def visit(skill_id: str) -> None:
            if skill_id in visited or skill_id not in skills_by_id:
                return
            definition = skills_by_id[skill_id]
            for dependency_id in definition.depends_on:
                visit(dependency_id)
            item = explicit.get(skill_id)
            if item is None:
                item = SkillSelectionItem(
                    skill_id=skill_id,
                    reason=f"{definition.display_name} 是后续技能执行所需的依赖步骤。",
                    source="dependency",
                )
            resolved.append(item)
            visited.add(skill_id)

        for item in ordered_items:
            visit(item.skill_id)
        return resolved

    def _contains_any(self, text: str, keywords: tuple[str, ...]) -> bool:
        normalized = text.lower()
        return any(keyword.lower() in normalized for keyword in keywords)

    def _matches_weather_question(self, text: str) -> bool:
        """匹配常见中文天气问法。"""
        return bool(re.search(r"(会)?下雨吗|有雨吗|天气如何|天气怎么样|气温多少|几度|多少度", text))
