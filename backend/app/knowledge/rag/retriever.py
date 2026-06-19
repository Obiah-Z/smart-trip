from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import httpx

from app.core.config.settings import Settings
from app.knowledge.rag.embedding_client import OpenAIEmbeddingClient
from app.knowledge.rag.tokenizer import tokenize
from app.knowledge.rag.vector_index import LocalVectorIndex


class LocalRAGRetriever:
    """本地 RAG 检索器。

    检索过程先按城市过滤，避免跨城市知识污染；再计算 BM25 和可选向量相似度；最后叠加
    业务信号并做 topic 去重，让注入的知识既相关又覆盖路线、住宿、餐饮等不同维度。
    """

    TOPIC_PREFERENCE_MAP = {
        "food": {"food", "local_food", "avoid_food", "avoid_local_food"},
        "trip_route": {"culture", "nature", "museum", "citywalk", "metro", "high_speed_rail", "family"},
        "hotel_area": {"quiet_hotel", "lively_hotel", "comfortable_hotel", "family"},
        "culture": {"culture", "museum", "family"},
        "citywalk": {"citywalk"},
        "family": {"family"},
        "seasonal": {"nature", "family", "citywalk"},
        "rainy_day": {"museum", "family", "culture", "rainy_day"},
    }
    TOPIC_BASE_BONUS = {
        "trip_route": 2,
        "hotel_area": 1,
        "citywalk": 1,
        "family": 1,
        "rainy_day": 1,
        "city_overview": -1,
    }

    def __init__(
        self,
        *,
        index_path: Path,
        settings: Settings | None = None,
        embedding_index_path: Path | None = None,
        embedding_client: OpenAIEmbeddingClient | None = None,
    ) -> None:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
        self._documents = payload["documents"]
        self._document_frequencies = payload["document_frequencies"]
        self._document_count = int(payload["document_count"])
        self._avg_doc_length = float(payload["avg_doc_length"])
        bm25 = payload.get("bm25", {})
        self._k1 = float(bm25.get("k1", 1.2))
        self._b = float(bm25.get("b", 0.75))
        self._settings = settings or Settings()
        self._embedding_client = embedding_client or OpenAIEmbeddingClient(self._settings)
        self._vector_index = self._load_vector_index(embedding_index_path=embedding_index_path)

    def search(
        self,
        *,
        destination: str,
        query: str,
        query_terms: list[str],
        preferences: list[str],
        days: int | None,
        top_k: int,
    ) -> list[dict[str, Any]]:
        """在指定城市内检索并返回已重排、已去重的 chunk。"""
        normalized_query_terms = list(dict.fromkeys(tokenize(query) + [term.lower() for term in query_terms]))
        candidates = [document for document in self._documents if document["city"] == destination]
        vector_scores = self._vector_scores(query=query, candidates=candidates)
        scored: list[dict[str, Any]] = []

        for document in candidates:
            lexical_overlap = len(set(normalized_query_terms).intersection(set(document["terms"])))
            bm25_score = self._bm25_score(query_terms=normalized_query_terms, document=document)
            vector_score = vector_scores.get(str(document["id"]), 0.0)
            hybrid_score = self._hybrid_score(bm25_score=bm25_score, vector_score=vector_score)
            preference_bonus = self._preference_bonus(topic=str(document.get("topic", "")), preferences=preferences)
            exact_city_bonus = 2 if destination in document.get("keywords", []) else 0
            day_bonus = self._day_bonus(days=days, document=document)
            topic_base_bonus = self._topic_base_bonus(topic=str(document.get("topic", "")))
            total_score = hybrid_score + lexical_overlap + preference_bonus + exact_city_bonus + day_bonus + topic_base_bonus
            scored.append(
                {
                    "id": document["id"],
                    "topic": document["topic"],
                    "title": document["title"],
                    "content": document["content"],
                    "keywords": document["keywords"],
                    "source": document["source"],
                    "chunk_index": document["chunk_index"],
                    "token_count": document["token_count"],
                    "metadata": document["metadata"],
                    "score": round(total_score, 4),
                    "bm25_score": round(bm25_score, 4),
                    "vector_score": round(vector_score, 4),
                    "hybrid_score": round(hybrid_score, 4),
                    "lexical_overlap": lexical_overlap,
                    "preference_bonus": preference_bonus,
                    "exact_city_bonus": exact_city_bonus,
                    "day_bonus": day_bonus,
                    "topic_base_bonus": topic_base_bonus,
                    "retrieval_mode": self._resolve_retrieval_mode(),
                }
            )

        ranked_candidates = sorted(scored, key=lambda item: item["score"], reverse=True)
        return self._select_diverse_documents(ranked_candidates=ranked_candidates, top_k=top_k)

    def _bm25_score(self, *, query_terms: list[str], document: dict[str, Any]) -> float:
        """计算单个 chunk 的 BM25 分数。"""
        score = 0.0
        length = max(1, int(document["length"]))
        term_freqs: dict[str, int] = document["term_freqs"]
        for term in query_terms:
            tf = term_freqs.get(term, 0)
            if tf <= 0:
                continue
            df = int(self._document_frequencies.get(term, 0))
            idf = math.log((self._document_count - df + 0.5) / (df + 0.5) + 1.0)
            numerator = tf * (self._k1 + 1)
            denominator = tf + self._k1 * (1 - self._b + self._b * length / max(1.0, self._avg_doc_length))
            score += idf * numerator / denominator
        return score

    def _preference_bonus(self, *, topic: str, preferences: list[str]) -> int:
        """根据结构化偏好给对应 topic 加权；避免类偏好会压低 food topic。"""
        matched = self.TOPIC_PREFERENCE_MAP.get(topic, set()).intersection(preferences)
        if not matched:
            return 0
        if "avoid_food" in matched or "avoid_local_food" in matched:
            return 1 if topic != "food" else -1
        return len(matched)

    def _day_bonus(self, *, days: int | None, document: dict[str, Any]) -> int:
        if days is None:
            return 0
        content = str(document.get("content", ""))
        keywords = {str(item) for item in document.get("keywords", [])}
        day_keywords = {f"{days}日游", f"{days}天", f"{days}日"}
        if day_keywords.intersection(keywords):
            return 2
        if any(token in content for token in day_keywords):
            return 1
        return 0

    def _topic_base_bonus(self, *, topic: str) -> int:
        return self.TOPIC_BASE_BONUS.get(topic, 0)

    def _select_diverse_documents(
        self,
        *,
        ranked_candidates: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        """优先保证 topic 多样性，避免 Top K 全部来自同一主题。"""
        selected: list[dict[str, Any]] = []
        seen_topics: set[str] = set()

        for item in ranked_candidates:
            topic = str(item.get("topic", ""))
            if topic in seen_topics:
                continue
            selected.append(item)
            seen_topics.add(topic)
            if len(selected) >= top_k:
                return selected

        for item in ranked_candidates:
            if item in selected:
                continue
            selected.append(item)
            if len(selected) >= top_k:
                break
        return selected

    def _load_vector_index(self, *, embedding_index_path: Path | None) -> LocalVectorIndex | None:
        """加载可选向量索引；失败时返回 None，主流程自动退回 BM25。"""
        if embedding_index_path is None or not embedding_index_path.exists():
            return None
        try:
            return LocalVectorIndex(index_path=embedding_index_path)
        except (OSError, ValueError, json.JSONDecodeError):
            return None

    def _vector_scores(self, *, query: str, candidates: list[dict[str, Any]]) -> dict[str, float]:
        """计算 query 与候选 chunk 的向量相似度；任何网络/格式异常都降级为空分数。"""
        if not candidates or self._vector_index is None or not self._vector_index.has_vectors():
            return {}
        if not self._embedding_client.enabled():
            return {}
        try:
            query_vector = self._embedding_client.embed_query(query)
        except (RuntimeError, ValueError, httpx.HTTPError):
            return {}

        scores: dict[str, float] = {}
        for document in candidates:
            vector = self._vector_index.get(str(document["id"]))
            if vector is None:
                continue
            scores[str(document["id"])] = self._cosine_similarity(query_vector, vector)
        return scores

    def _hybrid_score(self, *, bm25_score: float, vector_score: float) -> float:
        """融合词法分数和向量分数；无向量分数时保持纯 BM25。"""
        if vector_score <= 0:
            return bm25_score
        return bm25_score * 0.65 + vector_score * 6.0

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        size = min(len(left), len(right))
        if size <= 0:
            return 0.0
        return sum(left[index] * right[index] for index in range(size))

    def _resolve_retrieval_mode(self) -> str:
        if self._vector_index is not None and self._vector_index.has_vectors() and self._embedding_client.enabled():
            return "hybrid"
        return "bm25"
