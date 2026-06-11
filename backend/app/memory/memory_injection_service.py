from __future__ import annotations

from typing import Any


class MemoryInjectionService:
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

    def select(
        self,
        *,
        long_term_memory: list[dict[str, str]],
        structured_constraints: dict[str, Any],
        user_input: str,
    ) -> dict[str, Any]:
        relevant: list[dict[str, str]] = []
        dropped: list[dict[str, str]] = []
        reasons: list[str] = []

        for item in long_term_memory:
            key = item.get("key", "")
            reason = self._match_reason(
                key=key,
                user_input=user_input,
                structured_constraints=structured_constraints,
            )
            if reason:
                relevant.append(item)
                reasons.append(reason)
            else:
                dropped.append(item)

        if not relevant and long_term_memory:
            relevant = long_term_memory[:3]
            reasons.append("未命中显式相关规则，回退注入最近的长期偏好。")

        return {
            "relevant_long_term_memory": relevant,
            "dropped_memory_count": len(dropped),
            "selection_reasons": list(dict.fromkeys(reasons)),
        }

    def _match_reason(
        self,
        *,
        key: str,
        user_input: str,
        structured_constraints: dict[str, Any],
    ) -> str | None:
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

        keywords = self.RELEVANT_KEYWORDS.get(key, ())
        if any(keyword in user_input for keyword in keywords):
            return f"{key} 与本轮问题中的约束或偏好直接相关。"
        return None
