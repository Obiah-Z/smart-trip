from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.memory.preference_profile import signal_definition
from app.planning.slot_extractor import SlotExtractionResult, SlotExtractor


@dataclass(frozen=True)
class ExtractedMemorySignal:
    """从用户自然语言中抽取出的长期偏好候选。"""

    name: str
    dimension: str
    family: str
    polarity: str
    label: str
    confidence: float
    evidence: str
    source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "dimension": self.dimension,
            "family": self.family,
            "polarity": self.polarity,
            "label": self.label,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "source": self.source,
        }


@dataclass(frozen=True)
class MemoryExtractionResult:
    """长期 Memory 写回前的抽取结果。"""

    signals: list[ExtractedMemorySignal]
    pace: str
    pace_explicit: bool
    source_text: str
    extraction_steps: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "signals": [signal.to_dict() for signal in self.signals],
            "preferences": [signal.name for signal in self.signals if signal.name not in {"relaxed", "intensive"}],
            "pace": self.pace,
            "pace_explicit": self.pace_explicit,
            "source_text": self.source_text,
            "extraction_steps": self.extraction_steps,
        }


class MemoryExtractor:
    """把自然语言请求规整成长期 Memory signal。

    目前使用规则抽取，接口刻意做成独立服务，后续可以在这里增加 LLM 抽取、向量匹配或
    用户确认机制，而不需要改 MemoryService 的存储结构。
    """

    BLOCKED_SHORT_LIVED_SIGNALS = {"rainy_day"}

    def __init__(self, slot_extractor: SlotExtractor | None = None) -> None:
        self._slot_extractor = slot_extractor or SlotExtractor()

    def extract(
        self,
        *,
        message: str,
        slots: SlotExtractionResult | None = None,
        session_context: dict[str, Any] | None = None,
    ) -> MemoryExtractionResult:
        active_slots = slots or self._slot_extractor.extract(message)
        source_text = message
        steps = ["使用槽位抽取结果作为长期偏好候选来源。"]
        preferences = list(active_slots.preferences)
        pace = active_slots.pace
        pace_explicit = active_slots.pace_explicit

        if self._looks_like_clarification_recovery(active_slots=active_slots, session_context=session_context):
            initial_request_text = (session_context or {}).get("initial_request_text")
            if isinstance(initial_request_text, str) and initial_request_text.strip():
                initial_slots = self._slot_extractor.extract(initial_request_text)
                preferences = list(dict.fromkeys([*initial_slots.preferences, *preferences]))
                if not pace_explicit and initial_slots.pace_explicit:
                    pace = initial_slots.pace
                    pace_explicit = True
                source_text = f"{initial_request_text} / {message}"
                steps.append("当前输入是澄清恢复，合并上一轮原始请求中的明确偏好。")

        signals = self._signals_from_preferences(preferences=preferences, source_text=source_text)
        if pace_explicit and pace != "balanced":
            signals.append(self._signal_from_name(name=pace, source_text=source_text, evidence="用户明确表达了行程节奏。"))
            steps.append("识别到显式行程节奏，允许写入长期节奏画像。")
        elif pace == "balanced":
            steps.append("balanced 是默认节奏，不写入长期 Memory。")

        deduped = self._dedupe_signals(signals)
        if len(deduped) != len(signals):
            steps.append("对重复偏好 signal 做去重。")
        return MemoryExtractionResult(
            signals=deduped,
            pace=pace,
            pace_explicit=pace_explicit,
            source_text=source_text,
            extraction_steps=steps,
        )

    def _signals_from_preferences(self, *, preferences: list[str], source_text: str) -> list[ExtractedMemorySignal]:
        signals: list[ExtractedMemorySignal] = []
        for preference in preferences:
            if preference in self.BLOCKED_SHORT_LIVED_SIGNALS:
                continue
            signals.append(
                self._signal_from_name(
                    name=preference,
                    source_text=source_text,
                    evidence=f"用户表达中识别到 {preference} 偏好。",
                )
            )
        return signals

    def _signal_from_name(self, *, name: str, source_text: str, evidence: str) -> ExtractedMemorySignal:
        definition = signal_definition(name)
        return ExtractedMemorySignal(
            name=definition.name,
            dimension=definition.dimension,
            family=definition.family,
            polarity=definition.polarity,
            label=definition.label,
            confidence=0.95,
            evidence=evidence,
            source="rule_slot_extractor",
        )

    def _dedupe_signals(self, signals: list[ExtractedMemorySignal]) -> list[ExtractedMemorySignal]:
        deduped: dict[str, ExtractedMemorySignal] = {}
        for signal in signals:
            deduped[signal.name] = signal
        return list(deduped.values())

    def _looks_like_clarification_recovery(
        self,
        *,
        active_slots: SlotExtractionResult,
        session_context: dict[str, Any] | None,
    ) -> bool:
        if not session_context or not session_context.get("session_found"):
            return False
        final_plan = session_context.get("latest_final_plan") or {}
        missing_fields = final_plan.get("missingFields") or []
        if "destination" in missing_fields and active_slots.destination_explicit:
            return True
        return "days" in missing_fields and active_slots.days is not None
