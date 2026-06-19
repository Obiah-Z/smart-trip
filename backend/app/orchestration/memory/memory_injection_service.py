from __future__ import annotations

from typing import Any

from app.orchestration.memory.preference_profile import (
    dimension_from_profile_key,
    legacy_key_replaced_by_profile,
    memory_item_dimension,
    memory_item_signal_names,
    parse_profile_value,
    signal_definition,
    signals_conflict,
)


class MemoryInjectionService:
    """决定哪些长期 Memory 应该进入本轮 Context。

    长期记忆可能很多，但每轮请求只需要一小部分。这里用结构化偏好和用户原话中的关键词
    做轻量相关性筛选，避免旧偏好对当前任务造成干扰。
    """

    RELEVANT_KEYWORDS = {
        "hotel_style": ("酒店", "住宿", "住哪里", "安静", "热闹", "嘈杂"),
        "preference_quiet_hotel": ("酒店", "住宿", "安静", "热闹", "嘈杂"),
        "preference_local_food": ("吃", "美食", "本地特色", "餐饮"),
        "preference_food": ("吃", "美食", "餐饮"),
        "preference_culture": ("文化", "博物馆", "景点"),
        "preference_nature": ("自然", "徒步", "风景", "景点"),
        "preference_museum": ("博物馆", "展览", "历史"),
        "preference_family": ("亲子", "带娃", "遛娃", "小朋友", "家庭"),
        "preference_citywalk": ("citywalk", "散步", "夜景", "步行"),
        "preference_metro": ("交通", "地铁", "通勤"),
        "preference_high_speed_rail": ("高铁", "交通"),
        "travel_pace": ("节奏", "紧张", "轻松", "紧凑", "休闲"),
    }
    DIMENSION_KEYWORDS = {
        "accommodation": ("酒店", "住宿", "民宿", "住哪里", "安静", "热闹", "嘈杂", "舒适"),
        "food": ("吃", "美食", "本地特色", "餐饮", "小吃", "口味"),
        "pace": ("节奏", "紧张", "轻松", "紧凑", "休闲", "慢一点"),
        "interests": ("景点", "文化", "自然", "博物馆", "citywalk", "夜景", "海边"),
        "transport": ("交通", "地铁", "高铁", "打车", "步行"),
        "traveler": ("亲子", "带娃", "遛娃", "小朋友", "家庭", "老人", "情侣"),
    }
    PLANNING_KEYWORDS = ("规划", "行程", "路线", "安排", "几日游", "旅行方案", "旅游方案", "攻略")
    MAX_INJECTED_MEMORY = 8

    def select(
        self,
        *,
        long_term_memory: list[dict[str, str]],
        structured_constraints: dict[str, Any],
        user_input: str,
    ) -> dict[str, Any]:
        """返回本轮注入的长期记忆、筛选原因和丢弃数量。"""
        relevant: list[dict[str, str]] = []
        dropped: list[dict[str, str]] = []
        suppressed: list[dict[str, Any]] = []
        reasons: list[str] = []
        profile_dimensions = {
            dimension
            for item in long_term_memory
            if (dimension := dimension_from_profile_key(str(item.get("key") or "")))
        }
        active_current_signals = self._active_current_signals(structured_constraints=structured_constraints)

        for item in long_term_memory:
            if legacy_key_replaced_by_profile(item, profile_dimensions):
                suppressed.append(
                    {
                        "key": item.get("key", ""),
                        "value": item.get("value", ""),
                        "reason": "同维度 profile 记忆已存在，旧版 legacy key 不再注入。",
                    }
                )
                continue
            conflict_reason = self._conflict_reason(item=item, active_current_signals=active_current_signals)
            if conflict_reason:
                suppressed.append(
                    {
                        "key": item.get("key", ""),
                        "value": item.get("value", ""),
                        "reason": conflict_reason,
                    }
                )
                continue
            key = item.get("key", "")
            reason = self._match_reason(
                item=item,
                key=key,
                user_input=user_input,
                structured_constraints=structured_constraints,
            )
            if reason:
                relevant.append(item)
                reasons.append(reason)
            else:
                dropped.append(item)

        relevant = relevant[: self.MAX_INJECTED_MEMORY]
        return {
            "relevant_long_term_memory": relevant,
            "dropped_memory_count": len(dropped) + len(suppressed),
            "selection_reasons": list(dict.fromkeys(reasons)),
            "suppressed_memory": suppressed,
            "memory_profile": self._build_memory_profile(relevant),
        }

    def _match_reason(
        self,
        *,
        item: dict[str, Any],
        key: str,
        user_input: str,
        structured_constraints: dict[str, Any],
    ) -> str | None:
        """给单条 Memory 生成注入原因；返回 None 表示本轮不注入。"""
        preferences = structured_constraints.get("preferences", [])
        if key == "preference_family" and "family" in preferences:
            return "当前问题包含亲子或家庭出游偏好。"
        if key == "travel_pace" and structured_constraints.get("pace") != "balanced":
            return "当前问题显式包含行程节奏要求。"
        if key == "preference_local_food" and any(item in preferences for item in ("local_food", "avoid_local_food")):
            return "当前问题包含餐饮偏好约束。"
        if key in {"hotel_style", "preference_quiet_hotel"} and any(
            item in preferences for item in ("quiet_hotel", "lively_hotel")
        ):
            return "当前问题包含住宿环境偏好。"

        dimension = memory_item_dimension(item)
        if dimension and self._dimension_is_relevant(
            dimension=dimension,
            user_input=user_input,
            structured_constraints=structured_constraints,
        ):
            return f"{key} 属于 {dimension} 维度，与当前旅行决策相关。"

        keywords = self.RELEVANT_KEYWORDS.get(key, ())
        if any(keyword in user_input for keyword in keywords):
            return f"{key} 与本轮问题中的约束或偏好直接相关。"
        return None

    def _active_current_signals(self, *, structured_constraints: dict[str, Any]) -> list[str]:
        preferences = list(structured_constraints.get("preferences") or [])
        pace = structured_constraints.get("pace")
        if pace and pace != "balanced":
            preferences.append(str(pace))
        return list(dict.fromkeys(preferences))

    def _conflict_reason(self, *, item: dict[str, Any], active_current_signals: list[str]) -> str | None:
        if not active_current_signals:
            return None
        for memory_signal in memory_item_signal_names(item):
            for current_signal in active_current_signals:
                if signals_conflict(memory_signal, current_signal):
                    return f"当前任务的 {current_signal} 与历史记忆 {memory_signal} 冲突，已按当前请求优先。"
        return None

    def _dimension_is_relevant(
        self,
        *,
        dimension: str,
        user_input: str,
        structured_constraints: dict[str, Any],
    ) -> bool:
        preferences = structured_constraints.get("preferences") or []
        if any(signal_definition(preference).dimension == dimension for preference in preferences):
            return True
        pace = structured_constraints.get("pace")
        if pace != "balanced" and dimension == "pace":
            return True
        if any(keyword in user_input for keyword in self.DIMENSION_KEYWORDS.get(dimension, ())):
            return True
        is_planning = bool(structured_constraints.get("days")) or any(
            keyword in user_input for keyword in self.PLANNING_KEYWORDS
        )
        return is_planning and dimension in {"accommodation", "food", "interests", "transport", "traveler", "pace"}

    def _build_memory_profile(self, memories: list[dict[str, Any]]) -> dict[str, Any]:
        profile: dict[str, Any] = {}
        for item in memories:
            key = str(item.get("key") or "")
            dimension = memory_item_dimension(item)
            if not dimension:
                continue
            parsed_profile = parse_profile_value(str(item.get("value") or ""))
            if parsed_profile:
                profile[dimension] = {
                    "source_key": key,
                    "active_values": parsed_profile.get("active_values", []),
                    "signals": parsed_profile.get("signals", []),
                    "last_updated_at": parsed_profile.get("last_updated_at"),
                }
                continue
            signals = memory_item_signal_names(item)
            if not signals:
                continue
            dimension_profile = profile.setdefault(
                dimension,
                {"source_key": key, "active_values": [], "signals": []},
            )
            for signal_name in signals:
                definition = signal_definition(signal_name)
                if signal_name not in dimension_profile["active_values"]:
                    dimension_profile["active_values"].append(signal_name)
                dimension_profile["signals"].append(
                    {
                        "name": signal_name,
                        "label": definition.label,
                        "family": definition.family,
                        "polarity": definition.polarity,
                    }
                )
        return profile
