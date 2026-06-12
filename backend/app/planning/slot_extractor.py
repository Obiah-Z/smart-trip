from __future__ import annotations

import json
from pathlib import Path
import re
from dataclasses import dataclass

DEFAULT_CITY_NAMES = ("北京", "杭州", "成都", "上海")
CLAUSE_SEPARATORS = "，。！？,.!?；;\n"


def _load_city_names() -> tuple[str, ...]:
    knowledge_path = Path(__file__).resolve().parents[2] / "data" / "knowledge" / "cities.json"
    try:
        payload = json.loads(knowledge_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return DEFAULT_CITY_NAMES

    dynamic_names = [
        str(item.get("city", "")).strip()
        for item in payload.get("cities", [])
        if str(item.get("city", "")).strip()
    ]
    return tuple(dict.fromkeys([*dynamic_names, *DEFAULT_CITY_NAMES]))


def _load_attraction_names() -> tuple[str, ...]:
    mock_path = Path(__file__).resolve().parents[2] / "data" / "mock" / "travel_data.json"
    try:
        payload = json.loads(mock_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return ()

    names: list[str] = []
    for items in (payload.get("attractions") or {}).values():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if name:
                names.append(name)

    unique_names = list(dict.fromkeys(names))
    return tuple(sorted(unique_names, key=len, reverse=True))


CITY_NAMES = _load_city_names()
ATTRACTION_NAMES = _load_attraction_names()
PACE_KEYWORDS = {
    "轻松": "relaxed",
    "慢一点": "relaxed",
    "休闲": "relaxed",
    "紧张": "intensive",
    "紧凑": "intensive",
    "特种兵": "intensive",
}
NEGATIVE_PREFERENCE_PATTERNS = {
    "本地特色": "avoid_local_food",
    "美食": "avoid_food",
    "安静": "lively_hotel",
}
POSITIVE_PREFERENCE_KEYWORDS = {
    "美食": "food",
    "本地特色": "local_food",
    "亲子": "family",
    "带娃": "family",
    "遛娃": "family",
    "小朋友": "family",
    "雨天": "rainy_day",
    "下雨": "rainy_day",
    "室内": "rainy_day",
    "安静": "quiet_hotel",
    "嘈杂": "lively_hotel",
    "热闹": "lively_hotel",
    "舒适度": "comfortable_hotel",
    "舒适一点": "comfortable_hotel",
    "更舒适": "comfortable_hotel",
    "更舒服": "comfortable_hotel",
    "住好一点": "comfortable_hotel",
    "舒服一点": "comfortable_hotel",
    "住得更舒服": "comfortable_hotel",
    "住得更舒适": "comfortable_hotel",
    "升级住宿": "comfortable_hotel",
    "自然": "nature",
    "文化": "culture",
    "博物馆": "museum",
    "citywalk": "citywalk",
    "夜景": "citywalk",
    "海边": "nature",
    "海景": "nature",
    "地铁": "metro",
    "高铁": "high_speed_rail",
}


@dataclass(frozen=True)
class SlotExtractionResult:
    destination: str | None
    destination_explicit: bool
    days: int | None
    budget: int | None
    budget_policy: str | None
    target_budget: int | None
    pace: str
    pace_explicit: bool
    preferences: list[str]
    excluded_attractions: list[str]


class SlotExtractor:
    def extract(self, message: str) -> SlotExtractionResult:
        destination = self._extract_destination(message)
        days = self._extract_days(message)
        budget, budget_policy = self._extract_budget(message)
        pace, pace_explicit = self._extract_pace(message)
        preferences = self._extract_preferences(message)
        return SlotExtractionResult(
            destination=destination,
            destination_explicit=destination is not None,
            days=days,
            budget=budget,
            budget_policy=budget_policy,
            target_budget=budget,
            pace=pace,
            pace_explicit=pace_explicit,
            preferences=preferences,
            excluded_attractions=self._extract_excluded_attractions(message),
        )

    def _extract_destination(self, message: str) -> str | None:
        for city in CITY_NAMES:
            if city in message:
                return city
        return None

    def _extract_days(self, message: str) -> int:
        match = re.search(r"(\d+)\s*(?:天|日游)", message)
        if match:
            return max(1, int(match.group(1)))
        cn_match = re.search(r"([一二三四五六七两])\s*日游|([一二三四五六七两])\s*天", message)
        if not cn_match:
            return None
        value = next(group for group in cn_match.groups() if group)
        mapping = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7}
        return mapping.get(value, 3)

    def _extract_budget(self, message: str) -> tuple[int | None, str | None]:
        policy = self._extract_budget_policy(message)
        match = re.search(
            r"(?:预算|总预算|总体预算|总花费|总费用|总价|花费|费用)"
            r".{0,12}?(?:提升到|提高到|增加到|改到|改成|调整到|压到|控制到|控制在)?\s*(\d{3,6})",
            message,
        )
        if match:
            return int(match.group(1)), policy or self._policy_from_budget_context(message)
        amount_match = re.search(r"(\d{3,5})\s*元", message)
        if amount_match:
            return int(amount_match.group(1)), policy or self._policy_from_budget_context(message)
        around_match = re.search(r"(\d{3,5})\s*(?:左右|上下|以内|以下|内|附近)", message)
        if around_match and self._has_budget_context(message):
            return int(around_match.group(1)), policy or self._policy_from_budget_context(message)
        close_match = re.search(r"(?:贴近|接近|靠近|用满|花满).{0,8}?(\d{3,5})", message)
        if close_match:
            return int(close_match.group(1)), policy or "target_near"
        return None, policy

    def _extract_budget_policy(self, message: str) -> str | None:
        if re.search(r"(?:尽可能|尽量|最好)?(?:贴近|接近|靠近)|(?:尽量|尽可能)?(?:用满|花满)", message):
            return "target_near"
        if re.search(r"不超过|别超过|不要超过|以内|以下|控制在|控制到|压到|最多", message):
            return "cap"
        if re.search(r"提升到|提高到|增加到|升级到", message):
            return "increase_to"
        if re.search(r"便宜|省钱|降低|减少|压缩|再低一点|少花", message):
            return "minimize"
        return None

    def _policy_from_budget_context(self, message: str) -> str:
        if re.search(r"提升|提高|增加|升级", message):
            return "increase_to"
        if re.search(r"不超过|别超过|不要超过|以内|以下|控制|压到|最多", message):
            return "cap"
        if re.search(r"贴近|接近|靠近|左右|上下|用满|花满|尽量|尽可能", message):
            return "target_near"
        return "set_to"

    def _has_budget_context(self, message: str) -> bool:
        return bool(re.search(r"预算|总预算|总体预算|总花费|总费用|总价|花费|费用|控制|贴近|接近|用满", message))

    def _extract_pace(self, message: str) -> tuple[str, bool]:
        for keyword, value in PACE_KEYWORDS.items():
            if keyword in message:
                return value, True
        return "balanced", False

    def _extract_preferences(self, message: str) -> list[str]:
        preferences: list[str] = []
        negative_tokens = self._extract_negative_preferences(message)

        for keyword, value in POSITIVE_PREFERENCE_KEYWORDS.items():
            if keyword not in message:
                continue
            if value == "food" and "avoid_food" in negative_tokens:
                continue
            if value == "local_food" and "avoid_local_food" in negative_tokens:
                continue
            if value == "quiet_hotel" and "lively_hotel" in negative_tokens:
                continue
            preferences.append(value)

        preferences.extend(negative_tokens)
        unique_matches = list(dict.fromkeys(preferences))
        return unique_matches

    def _extract_negative_preferences(self, message: str) -> list[str]:
        matches: list[str] = []
        for keyword, value in NEGATIVE_PREFERENCE_PATTERNS.items():
            escaped_keyword = re.escape(keyword)
            negative_patterns = [
                rf"不想.{{0,3}}{escaped_keyword}",
                rf"不要.{{0,3}}{escaped_keyword}",
                rf"不吃.{{0,3}}{escaped_keyword}",
                rf"别吃.{{0,3}}{escaped_keyword}",
                rf"不住.{{0,3}}{escaped_keyword}",
                rf"不要太{escaped_keyword}",
                rf"不喜欢.{{0,3}}{escaped_keyword}",
                rf"尽量别.{{0,3}}{escaped_keyword}",
            ]
            if any(re.search(pattern, message) for pattern in negative_patterns):
                matches.append(value)
        return list(dict.fromkeys(matches))

    def _extract_excluded_attractions(self, message: str) -> list[str]:
        normalized = (
            message.replace("不想要去逛", "不想去")
            .replace("不想再去", "不去")
            .replace("不要去逛", "不要去")
            .replace("不想逛", "不去")
            .replace("不去逛", "不去")
            .replace("别去逛", "别去")
        )
        patterns = [
            r"(?:不想去|不要去|不去|别去|避开|去掉|删掉|移除)([\u4e00-\u9fffA-Za-z0-9·\-]{2,20})",
            r"(?:不想要|不要)([\u4e00-\u9fffA-Za-z0-9·\-]{2,20})(?:这个景点|这个地方|这个点|了)?",
        ]
        candidates: list[str] = []
        for pattern in patterns:
            for match in re.finditer(pattern, normalized):
                value = str(match.group(1) or "").strip(" ，。,.!！?？、")
                value = re.sub(r"^(?:去|逛|到|游览|参观)", "", value).strip(" ，。,.!！?？、")
                if not value:
                    continue
                if value in {"景点", "地方", "这里", "这个", "那个", "一下", "一下子"}:
                    continue
                candidates.append(value)
        candidates.extend(self._extract_named_excluded_attractions(normalized))
        return list(dict.fromkeys(candidates))

    def _extract_named_excluded_attractions(self, message: str) -> list[str]:
        candidates: list[str] = []
        for attraction_name in ATTRACTION_NAMES:
            escaped_name = re.escape(attraction_name)
            for match in re.finditer(escaped_name, message):
                clause = self._extract_clause(text=message, start=match.start(), end=match.end())
                if self._clause_excludes_attraction(clause=clause, attraction_name=attraction_name):
                    candidates.append(attraction_name)
                    break
        return candidates

    def _extract_clause(self, *, text: str, start: int, end: int) -> str:
        left = max(text.rfind(separator, 0, start) for separator in CLAUSE_SEPARATORS)
        right_candidates = [
            position
            for separator in CLAUSE_SEPARATORS
            if (position := text.find(separator, end)) != -1
        ]
        right = min(right_candidates) if right_candidates else len(text)
        return text[left + 1 : right].strip()

    def _clause_excludes_attraction(self, *, clause: str, attraction_name: str) -> bool:
        escaped_name = re.escape(attraction_name)
        prefix_pattern = (
            r"(?:不想|不想要|不要|不喜欢|不考虑|不打算|不愿意|别|"
            r"避开|去掉|删掉|移除|排除|不安排|别安排|不看|不逛|不去)"
        )
        suffix_pattern = (
            r"(?:不想去|不想逛|不想看|不要去|不要逛|不安排|"
            r"别安排|去掉|删掉|移除|排除|不考虑)"
        )
        gap = r"[\u4e00-\u9fffA-Za-z0-9·\-]{0,8}"
        return bool(
            re.search(rf"{prefix_pattern}{gap}{escaped_name}", clause)
            or re.search(rf"{escaped_name}{gap}{suffix_pattern}", clause)
        )
