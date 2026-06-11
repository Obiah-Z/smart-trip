from __future__ import annotations

import json
from pathlib import Path

from app.rag.types import KnowledgeChunk


class RAGCorpusLoader:
    def __init__(self, *, corpus_dir: Path) -> None:
        self._corpus_dir = corpus_dir

    def load(self) -> list[KnowledgeChunk]:
        manifest_path = self._corpus_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        chunks: list[KnowledgeChunk] = []
        for item in manifest.get("chunks", []):
            chunks.append(
                KnowledgeChunk(
                    id=str(item["id"]),
                    city=str(item["city"]),
                    topic=str(item["topic"]),
                    title=str(item["title"]),
                    content=str(item["content"]),
                    keywords=[str(keyword) for keyword in item.get("keywords", [])],
                    source=str(item.get("source", "generated_corpus")),
                    chunk_index=int(item.get("chunk_index", 0)),
                    token_count=int(item.get("token_count", 0)),
                    metadata=dict(item.get("metadata", {})),
                )
            )
        return chunks
