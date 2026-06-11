from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class KnowledgeChunk:
    id: str
    city: str
    topic: str
    title: str
    content: str
    keywords: list[str]
    source: str
    chunk_index: int = 0
    token_count: int = 0
    metadata: dict[str, object] = field(default_factory=dict)
