from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config.settings import Settings
from app.rag.retriever import LocalRAGRetriever
from app.retrieval.query_rewrite import RuleBasedQueryRewriteService
from app.scripts import ensure_rag_ready


class RetrievalService:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()
        backend_root = Path(__file__).resolve().parents[2]
        ensure_rag_ready(backend_root=backend_root, settings=self._settings)
        if self._settings.rag_index_path:
            index_path = Path(self._settings.rag_index_path)
        else:
            index_path = backend_root / "data" / "rag" / "index" / "rag_index.json"
        embedding_index_path = Path(self._settings.embedding_index_path) if self._settings.embedding_index_path else None
        self._retriever = LocalRAGRetriever(
            index_path=index_path,
            settings=self._settings,
            embedding_index_path=embedding_index_path,
        )
        self._query_rewrite_service = RuleBasedQueryRewriteService()

    def retrieve(
        self,
        *,
        destination: str,
        preferences: list[str],
        days: int | None,
        budget: int,
        pace: str = "balanced",
        user_input: str = "",
    ) -> dict[str, object]:
        resolved_days = days or 3
        query_rewrite = self._query_rewrite_service.rewrite(
            destination=destination,
            preferences=preferences,
            days=days,
            budget=budget,
            pace=pace,
            user_input=user_input,
        )
        top_k = self._resolve_top_k(days=resolved_days, preferences=preferences)
        ranked = self._retriever.search(
            destination=destination,
            query=str(query_rewrite["query"]),
            query_terms=[str(item) for item in query_rewrite["query_terms"]],
            preferences=preferences,
            days=days,
            top_k=top_k,
        )
        injected_knowledge = [item["content"] for item in ranked]
        return {
            "query": query_rewrite["query"],
            "query_rewrite": query_rewrite,
            "retrieval_steps": [
                *query_rewrite["steps"],
                "在本地 RAG 文档库中按城市过滤 chunk",
                "使用 BM25 进行初次召回评分",
                "如可用则追加向量相似度召回，并与 BM25 做混合融合",
                "叠加偏好匹配、天数匹配和同城强化做业务重排",
                "按 topic 去重后注入高相关知识片段",
            ],
            "ranking_signals": [
                "bm25_score",
                "vector_score",
                "hybrid_score",
                "lexical_overlap",
                "preference_bonus",
                "exact_city_bonus",
                "day_bonus",
                "topic_base_bonus",
                "topic_diversity",
            ],
            "retrieved_documents": ranked,
            "injected_knowledge": injected_knowledge,
        }

    def _resolve_top_k(self, *, days: int, preferences: list[str]) -> int:
        top_k = 3
        if days >= 4:
            top_k += 1
        if len(preferences) >= 3:
            top_k += 1
        return min(6, top_k)
