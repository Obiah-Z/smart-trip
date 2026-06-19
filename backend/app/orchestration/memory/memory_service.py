from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.db.repositories import MemoryRepository
from app.orchestration.memory.preference_profile import (
    PROFILE_SCOPE,
    group_signals_by_dimension,
    memory_item_dimension,
    memory_item_signal_names,
    parse_profile_value,
    profile_key,
    signal_definition,
    update_profile_value,
)


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

    def persist_preferences(
        self,
        *,
        user_id: str,
        preferences: list[str],
        pace: str,
        pace_explicit: bool | None = None,
        source_text: str | None = None,
        session_id: str | None = None,
        followup_replan: bool = False,
    ) -> list[dict[str, str]]:
        """把明确偏好写成稳定字段。

        写回只处理用户可复用的旅行偏好，例如酒店环境、餐饮偏好、出行节奏；不会写入
        “某次行程生成的中间结果”，减少长期 Memory 污染。
        """
        resolved_pace_explicit = pace_explicit if pace_explicit is not None else pace != "balanced"
        normalized = self._writable_preference_signals(preferences=preferences)
        if resolved_pace_explicit and pace != "balanced":
            normalized.append(pace)
        normalized = list(dict.fromkeys(normalized))
        updates: list[dict[str, str]] = []
        if not normalized:
            return updates

        def persist(key: str, value: str, scope: str = "travel_preference") -> None:
            self._repository.upsert_memory(user_id=user_id, key=key, value=value, scope=scope)
            updates.append({"key": key, "value": value, "scope": scope})

        existing_profiles = {
            item["key"]: item
            for item in self._repository.list_memories(user_id=user_id)
            if isinstance(item.get("key"), str) and item["key"].startswith("profile:")
        }
        now = datetime.now(timezone.utc).isoformat()
        for dimension, definitions in group_signals_by_dimension(normalized).items():
            key = profile_key(dimension)
            existing_value = existing_profiles.get(key, {}).get("value")
            value = update_profile_value(
                existing_value=existing_value,
                dimension=dimension,
                signal_definitions=definitions,
                source_text=source_text,
                session_id=session_id,
                updated_at=now,
            )
            persist(key, value, PROFILE_SCOPE)

        # 兼容旧前端和已有调试视图：保留少量 legacy key，但不再把新能力扩展成无限 key。
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

        if resolved_pace_explicit and pace != "balanced":
            persist("travel_pace", pace)
        return updates

    def persist_extracted_signals(
        self,
        *,
        user_id: str,
        signal_names: list[str],
        pace: str,
        pace_explicit: bool,
        source_text: str,
        session_id: str | None,
        followup_replan: bool = False,
    ) -> list[dict[str, str]]:
        """写入 MemoryExtractor 已归一化后的 signal。"""
        preference_signals = [signal for signal in signal_names if signal not in {"relaxed", "intensive", "balanced"}]
        return self.persist_preferences(
            user_id=user_id,
            preferences=preference_signals,
            pace=pace,
            pace_explicit=pace_explicit,
            source_text=source_text,
            session_id=session_id,
            followup_replan=followup_replan,
        )

    def audit(self, *, user_id: str) -> dict:
        """返回长期 Memory 的结构化审计视图。"""
        records = self.list_memories(user_id=user_id)
        profiles: dict[str, dict] = {}
        legacy_records: list[dict] = []
        unknown_records: list[dict] = []

        for record in records:
            key = str(record.get("key") or "")
            value = str(record.get("value") or "")
            if key.startswith("profile:"):
                parsed = parse_profile_value(value)
                if parsed:
                    dimension = parsed.get("dimension") or key.removeprefix("profile:")
                    profiles[str(dimension)] = {
                        "key": key,
                        "active_values": parsed.get("active_values", []),
                        "signals": parsed.get("signals", []),
                        "last_updated_at": parsed.get("last_updated_at"),
                        "updated_at": record.get("updated_at"),
                    }
                    continue
            signal_names = memory_item_signal_names(record)
            if signal_names:
                legacy_records.append(
                    {
                        "key": key,
                        "value": value,
                        "scope": record.get("scope"),
                        "updated_at": record.get("updated_at"),
                        "dimension": memory_item_dimension(record),
                        "signals": signal_names,
                    }
                )
            else:
                unknown_records.append(record)

        profile_dimensions = set(profiles)
        shadowed_legacy_records = [
            {
                **record,
                "reason": "同维度 profile 已存在，该 legacy 记录只用于兼容展示，不建议注入模型。",
            }
            for record in legacy_records
            if record.get("dimension") in profile_dimensions
        ]
        return {
            "user_id": user_id,
            "total_records": len(records),
            "profile_count": len(profiles),
            "legacy_count": len(legacy_records),
            "unknown_count": len(unknown_records),
            "profiles": profiles,
            "legacy_records": legacy_records,
            "shadowed_legacy_records": shadowed_legacy_records,
            "unknown_records": unknown_records,
            "conflict_families": self._build_conflict_family_index(profiles=profiles, legacy_records=legacy_records),
            "recommendations": self._build_audit_recommendations(
                profiles=profiles,
                legacy_records=legacy_records,
                shadowed_legacy_records=shadowed_legacy_records,
                unknown_records=unknown_records,
            ),
        }

    def _writable_preference_signals(self, *, preferences: list[str]) -> list[str]:
        """只允许明确、可复用的用户偏好进入长期 Memory。

        继承自 session 的结构化约束由 PlannerService 控制是否传入；这里再过滤明显偏运行态、
        偏一次性场景的 token，降低长期画像污染。
        """
        blocked = {"rainy_day"}
        return [
            preference
            for preference in list(dict.fromkeys(preferences))
            if preference and preference not in blocked
        ]

    def upsert_memory(self, *, user_id: str, key: str, value: str, scope: str) -> None:
        self._repository.upsert_memory(user_id=user_id, key=key, value=value, scope=scope)

    def list_memories(self, *, user_id: str) -> list[dict[str, str]]:
        return self._repository.list_memories(user_id=user_id)

    def _build_conflict_family_index(self, *, profiles: dict[str, dict], legacy_records: list[dict]) -> dict[str, list[dict]]:
        families: dict[str, list[dict]] = {}
        for dimension, profile in profiles.items():
            for signal in profile.get("signals", []):
                if not isinstance(signal, dict) or not signal.get("name"):
                    continue
                family = str(signal.get("family") or signal_definition(str(signal["name"])).family)
                families.setdefault(f"{dimension}:{family}", []).append(
                    {
                        "name": signal.get("name"),
                        "polarity": signal.get("polarity"),
                        "source": profile.get("key"),
                        "updated_at": signal.get("updated_at"),
                    }
                )
        for record in legacy_records:
            for signal_name in record.get("signals", []):
                definition = signal_definition(str(signal_name))
                families.setdefault(f"{definition.dimension}:{definition.family}", []).append(
                    {
                        "name": definition.name,
                        "polarity": definition.polarity,
                        "source": record.get("key"),
                        "updated_at": record.get("updated_at"),
                    }
                )
        return families

    def _build_audit_recommendations(
        self,
        *,
        profiles: dict[str, dict],
        legacy_records: list[dict],
        shadowed_legacy_records: list[dict],
        unknown_records: list[dict],
    ) -> list[str]:
        recommendations: list[str] = []
        if shadowed_legacy_records:
            recommendations.append("已有 profile 覆盖同维度 legacy 记忆，注入时应优先使用 profile。")
        if legacy_records and not profiles:
            recommendations.append("当前仍以 legacy 记忆为主，建议通过下一轮规划逐步生成 profile。")
        if unknown_records:
            recommendations.append("存在无法归类的 Memory 记录，建议人工清理或补充 signal 映射。")
        if not profiles and not legacy_records:
            recommendations.append("当前用户暂无长期偏好画像，系统会仅依赖本轮输入和会话状态。")
        return recommendations
