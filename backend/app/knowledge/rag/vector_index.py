from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.knowledge.rag.corpus_loader import RAGCorpusLoader
from app.knowledge.rag.embedding_client import OpenAIEmbeddingClient
from app.knowledge.rag.types import KnowledgeChunk


class LocalVectorIndex:
    """只读本地向量索引。"""

    def __init__(self, *, index_path: Path) -> None:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
        self._model = str(payload.get("model", ""))
        self._dimensions = int(payload.get("dimensions", 0))
        self._vectors: dict[str, list[float]] = {}
        for item in payload.get("documents", []):
            if not isinstance(item, dict):
                continue
            chunk_id = str(item.get("id", "")).strip()
            raw_vector = item.get("vector", [])
            if not chunk_id or not isinstance(raw_vector, list):
                continue
            self._vectors[chunk_id] = [float(value) for value in raw_vector]

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def get(self, chunk_id: str) -> list[float] | None:
        return self._vectors.get(chunk_id)

    def has_vectors(self) -> bool:
        return bool(self._vectors)


class VectorIndexBuilder:
    """为 RAG chunk 构建可选 embedding 索引。

    该索引不是主流程的硬依赖；构建或调用 embedding 失败时，检索链路仍能通过 BM25 工作。
    """

    def __init__(
        self,
        *,
        corpus_dir: Path,
        output_path: Path,
        embedding_client: OpenAIEmbeddingClient,
        batch_size: int = 16,
    ) -> None:
        self._corpus_dir = corpus_dir
        self._output_path = output_path
        self._embedding_client = embedding_client
        configured_batch_size = getattr(embedding_client, "_settings", None)
        config_value = getattr(configured_batch_size, "embedding_batch_size", batch_size)
        self._batch_size = max(1, min(batch_size, int(config_value)))

    def build(self) -> dict[str, object]:
        """批量调用 embedding 服务并写入本地向量索引文件。"""
        if not self._embedding_client.enabled():
            raise RuntimeError("Embedding client is disabled")

        loader = RAGCorpusLoader(corpus_dir=self._corpus_dir)
        chunks = loader.load()
        documents: list[dict[str, object]] = []

        for chunk_batch in self._batch_chunks(chunks):
            inputs = [self._chunk_to_embedding_text(chunk) for chunk in chunk_batch]
            vectors = self._embedding_client.embed_texts(inputs)
            for chunk, vector in zip(chunk_batch, vectors, strict=True):
                documents.append(
                    {
                        "id": chunk.id,
                        "city": chunk.city,
                        "topic": chunk.topic,
                        "title": chunk.title,
                        "vector": vector,
                    }
                )

        dimensions = len(documents[0]["vector"]) if documents else 0
        payload = {
            "model": self._embedding_client.model_name,
            "dimensions": dimensions,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "document_count": len(documents),
            "documents": documents,
        }

        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        self._output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "output_path": str(self._output_path),
            "documents": len(documents),
            "dimensions": dimensions,
            "model": self._embedding_client.model_name,
        }

    def _batch_chunks(self, chunks: list[KnowledgeChunk]) -> list[list[KnowledgeChunk]]:
        return [chunks[index : index + self._batch_size] for index in range(0, len(chunks), self._batch_size)]

    def _chunk_to_embedding_text(self, chunk: KnowledgeChunk) -> str:
        """将结构化 chunk 渲染成 embedding 输入文本。"""
        keywords = "、".join(chunk.keywords[:10])
        return (
            f"城市：{chunk.city}\n"
            f"主题：{chunk.topic}\n"
            f"标题：{chunk.title}\n"
            f"关键词：{keywords}\n"
            f"内容：{chunk.content}"
        ).strip()
