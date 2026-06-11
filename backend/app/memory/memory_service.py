from __future__ import annotations

from dataclasses import dataclass

from app.db.repositories import MemoryRepository


@dataclass(frozen=True)
class MemoryContext:
    long_term_memory: list[dict[str, str]]
    short_term_state: dict[str, str | int | list[str]]


class MemoryService:
    def __init__(self, repository: MemoryRepository) -> None:
        self._repository = repository

    def load_context(self, *, user_id: str, short_term_state: dict[str, str | int | list[str]]) -> MemoryContext:
        return MemoryContext(
            long_term_memory=self._repository.list_memories(user_id=user_id),
            short_term_state=short_term_state,
        )

    def persist_preferences(self, *, user_id: str, preferences: list[str], pace: str) -> list[dict[str, str]]:
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
