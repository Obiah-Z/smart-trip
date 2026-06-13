from __future__ import annotations

import json
import math
from pathlib import Path

from app.rag.corpus_loader import RAGCorpusLoader
from app.rag.tokenizer import tokenize


class RAGIndexBuilder:
    """从清洗后的 RAG corpus 构建 BM25 检索索引。"""

    def __init__(self, *, corpus_dir: Path, index_dir: Path) -> None:
        self._corpus_dir = corpus_dir
        self._index_dir = index_dir

    def build(self) -> dict[str, object]:
        """生成 rag_index.json，包含 chunk、词频、文档频率和 BM25 参数。"""
        loader = RAGCorpusLoader(corpus_dir=self._corpus_dir)
        chunks = loader.load()
        documents = []
        document_frequencies: dict[str, int] = {}

        for chunk in chunks:
            terms = tokenize(" ".join([chunk.title, chunk.content, *chunk.keywords]))
            unique_terms = set(terms)
            for term in unique_terms:
                document_frequencies[term] = document_frequencies.get(term, 0) + 1
            documents.append(
                {
                    "id": chunk.id,
                    "city": chunk.city,
                    "topic": chunk.topic,
                    "title": chunk.title,
                    "content": chunk.content,
                    "keywords": chunk.keywords,
                    "source": chunk.source,
                    "chunk_index": chunk.chunk_index,
                    "token_count": chunk.token_count,
                    "metadata": chunk.metadata,
                    "terms": terms,
                    "term_freqs": self._count_terms(terms),
                    "length": len(terms),
                }
            )

        avg_doc_length = sum(item["length"] for item in documents) / max(1, len(documents))
        index_payload = {
            "documents": documents,
            "document_frequencies": document_frequencies,
            "document_count": len(documents),
            "avg_doc_length": avg_doc_length,
            "bm25": {"k1": 1.2, "b": 0.75},
        }

        self._index_dir.mkdir(parents=True, exist_ok=True)
        output_path = self._index_dir / "rag_index.json"
        output_path.write_text(json.dumps(index_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"output_path": str(output_path), "documents": len(documents), "avg_doc_length": round(avg_doc_length, 2)}

    def _count_terms(self, terms: list[str]) -> dict[str, int]:
        frequencies: dict[str, int] = {}
        for term in terms:
            frequencies[term] = frequencies.get(term, 0) + 1
        return frequencies

    @staticmethod
    def idf(*, document_count: int, document_frequency: int) -> float:
        return math.log((document_count - document_frequency + 0.5) / (document_frequency + 0.5) + 1.0)
