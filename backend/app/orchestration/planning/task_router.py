from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TaskProfile:
    task_type: str
    complexity: str
    needs_rag: bool
    needs_tools: bool
    needs_multi_agent: bool
    intent_summary: str
    evidence: list[str]


class TaskRouter:
    ITINERARY_KEYWORDS = ("规划", "行程", "路线", "攻略", "安排", "几日游", "旅行方案", "旅游方案")
    RAG_KEYWORDS = (
        "攻略",
        "景点",
        "介绍",
        "注意事项",
        "适合",
        "推荐",
        "文化",
        "自然",
        "美食",
        "亲子",
        "带娃",
        "遛娃",
        "小朋友",
        "雨天",
        "室内",
    )
    TOOL_KEYWORDS = ("天气", "酒店", "住宿", "路线", "交通", "住哪里", "去哪玩", "去哪里玩", "室内")
    COMPLEXITY_KEYWORDS = ("预算", "天", "节奏", "偏好", "不想", "尽量", "同时", "并且")

    def analyze(self, message: str, *, days: int | None, preferences: list[str]) -> TaskProfile:
        evidence: list[str] = []
        itinerary_hit = self._contains_any(message, self.ITINERARY_KEYWORDS)
        rag_hit = itinerary_hit or self._contains_any(message, self.RAG_KEYWORDS)
        consultation_tool_hit = self._contains_any(message, self.TOOL_KEYWORDS) or self._contains_any(message, self.RAG_KEYWORDS)
        tool_hit = itinerary_hit or consultation_tool_hit
        hard_constraints = sum(1 for token in self.COMPLEXITY_KEYWORDS if token in message)
        complexity = "complex" if itinerary_hit and (hard_constraints >= 2 or len(preferences) >= 2) else "simple"
        needs_multi_agent = itinerary_hit and (tool_hit or rag_hit)

        if itinerary_hit:
            evidence.append("识别到多日旅行规划意图")
        if rag_hit:
            evidence.append("问题包含景点/攻略/注意事项等知识增强需求")
        if tool_hit:
            evidence.append("问题涉及天气/酒店/路线等外部能力")
        if len(preferences) >= 2:
            evidence.append("检测到多项用户偏好或限制条件")
        if hard_constraints >= 2:
            evidence.append("检测到预算、节奏或限制表达，任务复杂度提高")

        if not evidence:
            evidence.append("识别为单轮旅行咨询或事实问答，不进入路线规划链路")

        return TaskProfile(
            task_type="travel_planning" if itinerary_hit else "travel_consulting",
            complexity=complexity,
            needs_rag=rag_hit,
            needs_tools=tool_hit,
            needs_multi_agent=needs_multi_agent,
            intent_summary="围绕目的地、预算、天数和偏好生成可执行旅行方案" if itinerary_hit else "提供旅行相关咨询答复",
            evidence=evidence,
        )

    def force_planning_profile(self, *, message: str, days: int | None, preferences: list[str]) -> TaskProfile:
        profile = self.analyze(message, days=days, preferences=preferences)
        evidence = [
            "识别为基于上一轮方案的增量调整请求，继续沿用旅行规划链路。",
            *profile.evidence,
        ]
        return TaskProfile(
            task_type="travel_planning",
            complexity="complex" if len(preferences) >= 2 or (days or 0) >= 2 else "simple",
            needs_rag=True,
            needs_tools=True,
            needs_multi_agent=True,
            intent_summary="基于已有会话状态重算旅行方案，并吸收新的预算或偏好修改",
            evidence=list(dict.fromkeys(evidence)),
        )

    def _contains_any(self, text: str, keywords: tuple[str, ...]) -> bool:
        normalized = text.lower()
        return any(keyword.lower() in normalized for keyword in keywords)
