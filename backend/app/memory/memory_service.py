from __future__ import annotations

from dataclasses import dataclass

from app.db.repositories import MemoryRepository


@dataclass(frozen=True)
class MemoryContext:
    """本轮可用记忆上下文。

    long_term_memory 来自用户级持久记忆；short_term_state 是当前会话/当前任务的结构化状态。
    两者分开保存，避免把一次性任务状态误写成长期偏好。
    """

    long_term_memory: list[dict[str, str]]
    short_term_state: dict[str, str | int | list[str]]


class MemoryService:
    """Memory 的读取和写回入口。"""

    def __init__(self, repository: MemoryRepository) -> None:
        self._repository = repository

    def load_context(self, *, user_id: str, short_term_state: dict[str, str | int | list[str]]) -> MemoryContext:
        """读取用户长期记忆，并携带本轮短期状态返回给 Context 层。"""
        return MemoryContext(
            long_term_memory=self._repository.list_memories(user_id=user_id),
            short_term_state=short_term_state,
        )

    def persist_preferences(self, *, user_id: str, preferences: list[str], pace: str) -> list[dict[str, str]]:
        """把明确偏好写成稳定字段。

        写回只处理用户可复用的旅行偏好，例如酒店环境、餐饮偏好、出行节奏；不会写入
        “某次行程生成的中间结果”，减少长期 Memory 污染。
        """
        normalized = list(dict.fromkeys(preferences))
        updates: list[dict[str, str]] = []

        def persist(key: str, value: str, scope: str = "travel_preference") -> None:
            self._repository.upsert_memory(user_id=user_id, key=key, value=value, scope=scope)
            updates.append({"key": key, "value": value, "scope": scope})

        if "lively_hotel" in normalized:
            persist("hotel_style", "prefer_lively_location")
            persist("preference_quiet_hotel", "avoid_quiet_hotel")
        elif "quiet_hotel" in normalized:
            persist("hotel_style", "prefer_quiet_location")
            persist("preference_quiet_hotel", "quiet_hotel")

        if "avoid_local_food" in normalized:
            persist("preference_local_food", "avoid_local_food")
        elif "local_food" in normalized:
            persist("preference_local_food", "local_food")

        if "avoid_food" in normalized:
            persist("preference_food", "avoid_food")
        elif "food" in normalized:
            persist("preference_food", "food")

        for preference in normalized:
            if preference in {"culture", "nature", "museum", "citywalk", "metro", "high_speed_rail", "family"}:
                persist(f"preference_{preference}", preference)

        persist("travel_pace", pace)
        return updates

    def upsert_memory(self, *, user_id: str, key: str, value: str, scope: str) -> None:
        self._repository.upsert_memory(user_id=user_id, key=key, value=value, scope=scope)

    def list_memories(self, *, user_id: str) -> list[dict[str, str]]:
        return self._repository.list_memories(user_id=user_id)
