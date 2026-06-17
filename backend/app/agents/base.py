from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AgentExecutionResult:
    """单个 Agent 阶段的输出。"""

    name: str
    summary: str
    payload: dict[str, Any]


TOOL_NAME_MAP = {
    "route": "route.plan",
    "hotel": "hotel.search",
    "weather": "weather.lookup",
    "attraction": "attraction.search",
    "budget": "budget.optimize",
    "audit": "itinerary.audit",
}

ATTRACTION_TYPE_LABELS = {
    "nature": "自然风景",
    "culture": "人文体验",
    "museum": "博物馆",
    "citywalk": "城市漫步",
    "food": "餐饮小吃",
    "relaxed": "轻松休闲",
}

PACE_LABELS = {
    "relaxed": "轻松",
    "balanced": "均衡",
    "intensive": "紧凑",
}


def tool_result(tool_results: list[dict[str, Any]], tool_name: str) -> dict[str, Any] | None:
    return next((item for item in tool_results if item["tool_name"] == tool_name), None)
