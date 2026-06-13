from __future__ import annotations

from dataclasses import dataclass


def _append_unique(parts: list[str], value: str) -> None:
    """保持检索词顺序并去重。"""
    normalized = value.strip()
    if not normalized:
        return
    if normalized not in parts:
        parts.append(normalized)


@dataclass(frozen=True)
class NoteKeywordRule:
    """从用户原话中抽取补充检索词的规则。"""

    triggers: tuple[str, ...]
    outputs: tuple[str, ...]
    destinations: tuple[str, ...] = ()


class RuleBasedQueryRewriteService:
    """把结构化旅行约束改写成更适合本地 RAG 的检索 query。

    当前实现是规则型，优点是稳定、可解释；后续如果接入 LLM query rewrite，可以保留
    这里的输出格式，减少 RetrievalService 和前端调试面板的改动。
    """

    PREFERENCE_TERM_MAP = {
        "family": ("亲子", "家庭友好", "室内"),
        "rainy_day": ("雨天", "室内", "替代路线"),
        "museum": ("博物馆", "展览", "室内"),
        "culture": ("文化", "历史", "人文"),
        "nature": ("自然", "风景", "公园"),
        "citywalk": ("citywalk", "步行", "街区"),
        "food": ("美食", "小吃", "餐饮"),
        "local_food": ("本地特色", "特色美食", "小吃"),
        "avoid_food": ("少餐饮", "非美食导向"),
        "avoid_local_food": ("不吃本地特色", "非本地美食"),
        "quiet_hotel": ("安静酒店", "住宿区域"),
        "lively_hotel": ("热闹酒店", "商圈住宿"),
        "comfortable_hotel": ("舒适住宿", "品质酒店"),
        "metro": ("地铁", "交通便利"),
        "high_speed_rail": ("高铁", "站点交通"),
    }
    PACE_TERM_MAP = {
        "relaxed": ("轻松", "慢节奏"),
        "balanced": ("均衡",),
        "intensive": ("紧凑", "高效"),
    }
    STABLE_TERMS = ("景点", "行程", "攻略", "推荐")
    NOTE_RULES = (
        NoteKeywordRule(triggers=("夜景", "晚上"), outputs=("夜景", "傍晚")),
        NoteKeywordRule(triggers=("拍照", "出片", "摄影"), outputs=("拍照", "摄影", "出片")),
        NoteKeywordRule(triggers=("雨天", "下雨"), outputs=("雨天", "室内")),
        NoteKeywordRule(triggers=("周末",), outputs=("周末", "短途")),
        NoteKeywordRule(triggers=("第一次去", "初次去"), outputs=("经典路线", "首次到访")),
        NoteKeywordRule(triggers=("亲子", "带娃", "遛娃", "小朋友"), outputs=("亲子", "家庭友好")),
        NoteKeywordRule(triggers=("日落", "傍晚"), outputs=("日落", "傍晚"), destinations=("三亚", "厦门", "青岛", "深圳")),
        NoteKeywordRule(triggers=("海边", "海景"), outputs=("海边", "滨海"), destinations=("厦门", "青岛", "三亚", "深圳")),
        NoteKeywordRule(triggers=("古镇",), outputs=("古镇", "历史街区"), destinations=("苏州", "杭州", "成都", "桂林")),
    )

    def rewrite(
        self,
        *,
        destination: str,
        preferences: list[str],
        days: int | None,
        budget: int,
        pace: str,
        user_input: str = "",
    ) -> dict[str, object]:
        """把目的地、天数、偏好、节奏、预算和原话关键词合并为检索词。"""
        query_terms: list[str] = [destination]
        steps = [f"锁定目的地为 {destination}，避免跨城市知识污染。"]

        if days:
            _append_unique(query_terms, f"{days}日游")
            steps.append(f"补入行程时长信号：{days} 日。")

        normalized_preferences: list[str] = []
        for preference in preferences:
            mapped_terms = self.PREFERENCE_TERM_MAP.get(preference, ())
            if not mapped_terms:
                continue
            normalized_preferences.extend(mapped_terms)
            for term in mapped_terms:
                _append_unique(query_terms, term)
        if normalized_preferences:
            steps.append(f"把结构化偏好改写为检索词：{' / '.join(dict.fromkeys(normalized_preferences))}。")

        pace_terms = self.PACE_TERM_MAP.get(pace, ())
        for term in pace_terms:
            _append_unique(query_terms, term)
        if pace_terms:
            steps.append(f"补入节奏信号：{' / '.join(pace_terms)}。")

        note_keywords = self._extract_note_keywords(user_input=user_input, destination=destination)
        for keyword in note_keywords:
            _append_unique(query_terms, keyword)
        if note_keywords:
            steps.append(f"从用户原话中提炼补充关键词：{' / '.join(note_keywords)}。")

        budget_terms = self._budget_terms(budget)
        for term in budget_terms:
            _append_unique(query_terms, term)
        if budget_terms:
            steps.append(f"加入预算侧重：{' / '.join(budget_terms)}。")

        for term in self.STABLE_TERMS:
            _append_unique(query_terms, term)
        steps.append("追加稳定检索词，保证景点、路线与攻略类文档都能被召回。")

        return {
            "source": "rule-based",
            "query": " ".join(query_terms),
            "query_terms": query_terms,
            "focus_keywords": note_keywords,
            "steps": steps,
        }

    def _extract_note_keywords(self, *, user_input: str, destination: str) -> list[str]:
        """从用户补充描述中提取“雨天/夜景/亲子”等场景词。"""
        if not user_input.strip():
            return []

        keywords: list[str] = []
        for rule in self.NOTE_RULES:
            if rule.destinations and destination not in rule.destinations:
                continue
            if any(trigger in user_input for trigger in rule.triggers):
                for output in rule.outputs:
                    _append_unique(keywords, output)
        return keywords

    def _budget_terms(self, budget: int) -> tuple[str, ...]:
        """将预算转成检索侧的体验倾向。"""
        if budget <= 0:
            return ()
        if budget <= 3000:
            return (f"预算{budget}", "性价比")
        if budget >= 8000:
            return (f"预算{budget}", "品质体验")
        return (f"预算{budget}",)
