from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any


@dataclass(frozen=True)
class RevisionIntent:
    is_revision: bool
    revision_type: str
    confidence: float
    normalized_message: str
    budget_policy: str | None
    target_budget: int | None
    affected_fields: list[str]
    evidence: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RevisionIntentResolver:
    REPLAN_KEYWORDS = ("重新规划", "重做", "重排", "再规划", "再安排", "调整方案", "更新方案", "改一下")
    DESTINATION_TERMS = ("目的地", "城市", "地方", "行程地", "旅行地")
    DESTINATION_UPDATE_TERMS = ("换到", "换成", "换为", "改到", "改成", "改为", "调整到", "调整成", "变成", "改去", "换去")
    BUDGET_TERMS = ("预算", "总预算", "总体预算", "总花费", "总费用", "总价", "花费", "费用", "钱")
    HOTEL_TERMS = ("酒店", "住宿", "民宿", "住得", "住的", "舒适", "舒服", "安静", "热闹")
    PACE_TERMS = ("节奏", "轻松", "紧凑", "紧张", "特种兵", "慢一点")
    FOOD_TERMS = ("美食", "本地特色", "餐饮", "吃")

    def analyze(self, *, message: str, slots, session_context: dict[str, Any]) -> RevisionIntent:
        normalized_message = self.normalize_message(message)
        affected_fields = self._affected_fields(message=normalized_message, slots=slots)
        evidence = self._build_evidence(message=normalized_message, slots=slots, affected_fields=affected_fields)
        latest_constraints = session_context.get("latest_structured_constraints") or {}
        baseline_constraints = session_context.get("session_baseline_constraints") or {}
        budget_policy = getattr(slots, "budget_policy", None) or self._budget_policy_from_text(normalized_message)
        target_budget = (
            getattr(slots, "target_budget", None)
            or getattr(slots, "budget", None)
            or self._extract_budget_amount(normalized_message)
        )

        if budget_policy == "target_near" and target_budget is None:
            inherited_budget = latest_constraints.get("budget") or baseline_constraints.get("budget")
            target_budget = inherited_budget if isinstance(inherited_budget, int) and inherited_budget > 0 else None

        session_supports_revision = self._session_supports_revision(session_context=session_context)
        potential_revision = bool(affected_fields) and not self.looks_like_consulting_query(message=normalized_message, slots=slots)
        is_revision = session_supports_revision and potential_revision

        confidence = 0.0
        if is_revision:
            confidence = min(0.95, 0.55 + 0.1 * len(affected_fields) + 0.1 * len(evidence))
        elif potential_revision:
            confidence = 0.45

        revision_type = self._revision_type(affected_fields=affected_fields, budget_policy=budget_policy)
        return RevisionIntent(
            is_revision=is_revision,
            revision_type=revision_type,
            confidence=round(confidence, 2),
            normalized_message=normalized_message,
            budget_policy=budget_policy,
            target_budget=target_budget,
            affected_fields=affected_fields,
            evidence=evidence,
        )

    def has_revision_signal(self, *, message: str, slots) -> bool:
        normalized_message = self.normalize_message(message)
        if self.looks_like_consulting_query(message=normalized_message, slots=slots):
            return False
        return bool(self._affected_fields(message=normalized_message, slots=slots))

    def has_destination_update_signal(self, *, message: str, slots) -> bool:
        normalized_message = self.normalize_message(message)
        return self._has_destination_update_signal(message=normalized_message, slots=slots)

    def normalize_message(self, message: str) -> str:
        return (
            message.replace("不想要去逛", "不想去")
            .replace("不想再去", "不去")
            .replace("不要去逛", "不要去")
            .replace("不想逛", "不去")
            .replace("不去逛", "不去")
            .replace("别去逛", "别去")
        )

    def looks_like_consulting_query(self, *, message: str, slots) -> bool:
        if self._has_hard_revision_signal(message=message, slots=slots):
            return False
        weather_hit = any(token in message for token in ("天气", "气温", "几度", "下雨", "穿什么", "适合旅游"))
        factual_question_hit = bool(re.search(r"(有哪些|有什么|有啥|如何|怎么样|吗|几度|多少度|门票|开放时间)", message))
        return weather_hit or factual_question_hit

    def _session_supports_revision(self, *, session_context: dict[str, Any]) -> bool:
        if not session_context.get("session_found"):
            return False
        latest_constraints = session_context.get("latest_structured_constraints")
        latest_task_profile = session_context.get("latest_task_profile") or {}
        return bool(latest_constraints) and latest_task_profile.get("task_type") == "travel_planning"

    def _affected_fields(self, *, message: str, slots) -> list[str]:
        fields: list[str] = []
        if self._has_destination_update_signal(message=message, slots=slots):
            fields.append("destination")
        if self._has_budget_signal(message=message, slots=slots):
            fields.append("budget")
        if getattr(slots, "days", None) is not None:
            fields.append("days")
        if getattr(slots, "pace_explicit", False) or any(token in message for token in self.PACE_TERMS):
            fields.append("pace")
        if getattr(slots, "excluded_attractions", []):
            fields.append("excluded_attractions")
        if self._has_hotel_signal(message=message, slots=slots):
            fields.append("accommodation")
        if self._has_food_signal(message=message, slots=slots):
            fields.append("food")
        if self._has_preference_signal(message=message, slots=slots):
            fields.append("preferences")
        if any(token in message for token in self.REPLAN_KEYWORDS):
            fields.append("plan")
        return list(dict.fromkeys(fields))

    def _has_hard_revision_signal(self, *, message: str, slots) -> bool:
        return bool(
            self._has_budget_signal(message=message, slots=slots)
            or self._has_destination_update_signal(message=message, slots=slots)
            or getattr(slots, "days", None) is not None
            or getattr(slots, "pace_explicit", False)
            or getattr(slots, "excluded_attractions", [])
            or any(token in message for token in self.REPLAN_KEYWORDS)
        )

    def _has_destination_update_signal(self, *, message: str, slots) -> bool:
        destination = getattr(slots, "destination", None)
        if not getattr(slots, "destination_explicit", False) or not destination:
            return False

        escaped_destination = re.escape(str(destination))
        direct_update = any(token in message for token in self.DESTINATION_UPDATE_TERMS)
        destination_context = any(token in message for token in self.DESTINATION_TERMS)
        update_terms_pattern = "|".join(map(re.escape, self.DESTINATION_UPDATE_TERMS))
        if direct_update and (destination_context or re.search(rf"(?:{update_terms_pattern}).{{0,8}}{escaped_destination}", message)):
            return True

        destination_patterns = [
            rf"(?:目的地|城市|地方|行程地|旅行地).{{0,8}}(?:换|改|调整|变).{{0,8}}{escaped_destination}",
            rf"(?:换|改|调整).{{0,4}}(?:去|到|成|为).{{0,4}}{escaped_destination}",
            rf"(?:改去|换去|改到|换到|改成|换成|改为|换为|调整到|调整成|变成).{{0,4}}{escaped_destination}",
        ]
        return any(re.search(pattern, message) for pattern in destination_patterns)

    def _has_budget_signal(self, *, message: str, slots) -> bool:
        if getattr(slots, "budget", None) is not None or getattr(slots, "budget_policy", None):
            return True
        return bool(
            any(token in message for token in self.BUDGET_TERMS)
            and re.search(r"\d{3,6}|贴近|接近|靠近|用满|花满|不超过|控制|压到|便宜|省钱|少花", message)
        )

    def _has_hotel_signal(self, *, message: str, slots) -> bool:
        preferences = set(getattr(slots, "preferences", []) or [])
        hotel_preferences = {"quiet_hotel", "lively_hotel", "comfortable_hotel"}
        return bool(preferences.intersection(hotel_preferences) or any(token in message for token in self.HOTEL_TERMS))

    def _has_food_signal(self, *, message: str, slots) -> bool:
        preferences = set(getattr(slots, "preferences", []) or [])
        food_preferences = {"food", "local_food", "avoid_food", "avoid_local_food"}
        return bool(preferences.intersection(food_preferences) or any(token in message for token in self.FOOD_TERMS))

    def _has_preference_signal(self, *, message: str, slots) -> bool:
        if not getattr(slots, "preferences", []):
            return False
        return any(token in message for token in ("想", "多", "少", "优先", "主要", "尽量", "换成", "改", "不要", "不想"))

    def _budget_policy_from_text(self, message: str) -> str | None:
        if re.search(r"(?:尽可能|尽量|最好)?(?:贴近|接近|靠近)|(?:尽量|尽可能)?(?:用满|花满)", message):
            return "target_near"
        if re.search(r"不超过|别超过|不要超过|以内|以下|控制在|控制到|压到|最多", message):
            return "cap"
        if re.search(r"提升到|提高到|增加到|升级到", message):
            return "increase_to"
        if re.search(r"便宜|省钱|降低|减少|压缩|再低一点|少花", message):
            return "minimize"
        return None

    def _extract_budget_amount(self, message: str) -> int | None:
        match = re.search(r"(\d{3,6})\s*(?:元|左右|上下|以内|以下|内)?", message)
        return int(match.group(1)) if match else None

    def _build_evidence(self, *, message: str, slots, affected_fields: list[str]) -> list[str]:
        evidence: list[str] = []
        if "budget" in affected_fields:
            evidence.append("识别到预算或总花费调整表达")
        if "destination" in affected_fields:
            evidence.append("识别到目的地变更表达")
        if "excluded_attractions" in affected_fields:
            evidence.append("识别到排除景点表达")
        if "accommodation" in affected_fields:
            evidence.append("识别到住宿相关调整表达")
        if "pace" in affected_fields:
            evidence.append("识别到节奏调整表达")
        if "food" in affected_fields:
            evidence.append("识别到餐饮偏好调整表达")
        if any(token in message for token in self.REPLAN_KEYWORDS):
            evidence.append("识别到重新规划表达")
        return evidence

    def _revision_type(self, *, affected_fields: list[str], budget_policy: str | None) -> str:
        if "destination" in affected_fields:
            return "destination_update"
        if "budget" in affected_fields:
            return "budget_optimization" if budget_policy == "target_near" else "budget_update"
        if "excluded_attractions" in affected_fields:
            return "attraction_exclusion"
        if "accommodation" in affected_fields:
            return "accommodation_update"
        if "pace" in affected_fields:
            return "pace_update"
        if "food" in affected_fields:
            return "food_preference_update"
        if "plan" in affected_fields:
            return "general_replan"
        return "none"
