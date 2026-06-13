from __future__ import annotations

from contextlib import contextmanager
import math
import os
import time
from typing import Any

import httpx

from app.config.settings import Settings


class OpenAIEmbeddingClient:
    """OpenAI-compatible embedding 客户端。

    主生成模型和 embedding 模型解耦：生成侧可以使用其他厂商，RAG 向量索引仍可使用
    OpenAI-compatible embedding 接口。调用失败会由检索层捕获并降级到 BM25。
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def enabled(self) -> bool:
        """只有显式开启 openai embedding 且配置 API key 时才启用向量检索。"""
        return self._settings.embedding_mode == "openai" and bool(self._settings.embedding_api_key)

    @property
    def model_name(self) -> str:
        return self._settings.embedding_model

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """批量生成归一化向量，并带有限重试。"""
        if not texts:
            return []
        if not self.enabled():
            raise RuntimeError("Embedding client is disabled")

        payload: dict[str, Any] = {
            "model": self._settings.embedding_model,
            "input": [self._normalize_text(text) for text in texts],
            "encoding_format": "float",
        }
        if self._settings.embedding_dimensions > 0:
            payload["dimensions"] = self._settings.embedding_dimensions

        response = None
        last_error: Exception | None = None
        for attempt in range(self._settings.embedding_max_retries + 1):
            try:
                response = self._post_embeddings(payload=payload)
                response.raise_for_status()
                break
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if attempt >= self._settings.embedding_max_retries:
                    raise
                time.sleep(min(2.0 * (attempt + 1), 5.0))

        if response is None:
            raise last_error or RuntimeError("Embedding request failed without response")
        data = response.json()
        return self._parse_embeddings_response(data=data, expected_count=len(texts))

    def _post_embeddings(self, *, payload: dict[str, Any]) -> httpx.Response:
        """发送 embedding 请求，并兼容用户环境里的代理配置异常。"""
        timeout = float(max(10, self._settings.embedding_timeout_seconds))
        if self._settings.embedding_trust_env:
            try:
                with self._temporary_proxy_cleanup():
                    with httpx.Client(timeout=timeout, trust_env=True) as client:
                        return client.post(
                            f"{self._settings.embedding_base_url.rstrip('/')}/embeddings",
                            headers={
                                "Authorization": f"Bearer {self._settings.embedding_api_key}",
                                "Accept": "application/json",
                                "Content-Type": "application/json",
                            },
                            json=payload,
                        )
            except ValueError:
                pass

        with httpx.Client(timeout=timeout, trust_env=False) as client:
            return client.post(
                f"{self._settings.embedding_base_url.rstrip('/')}/embeddings",
                headers={
                    "Authorization": f"Bearer {self._settings.embedding_api_key}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

    @contextmanager
    def _temporary_proxy_cleanup(self):
        """临时移除 ALL_PROXY，规避部分 httpx/代理组合的 URL 解析问题。"""
        keys = ("ALL_PROXY", "all_proxy")
        original_values = {key: os.environ.get(key) for key in keys}
        try:
            for key in keys:
                os.environ.pop(key, None)
            yield
        finally:
            for key, value in original_values.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def _parse_embeddings_response(self, *, data: dict[str, Any], expected_count: int) -> list[list[float]]:
        """校验并按 index 顺序解析 embedding 响应。"""
        raw_items = data.get("data", [])
        if not isinstance(raw_items, list) or not raw_items:
            raise ValueError("Embedding response does not contain any vectors")

        ordered_items = sorted(raw_items, key=lambda item: int(item.get("index", 0)))
        vectors: list[list[float]] = []
        for item in ordered_items:
            raw_vector = item.get("embedding", [])
            if not isinstance(raw_vector, list) or not raw_vector:
                raise ValueError("Embedding item is missing vector data")
            vectors.append(self._normalize_vector([float(value) for value in raw_vector]))

        if len(vectors) != expected_count:
            raise ValueError("Embedding response count does not match request count")
        return vectors

    def _normalize_text(self, text: str) -> str:
        return " ".join(text.replace("\n", " ").split())

    def _normalize_vector(self, vector: list[float]) -> list[float]:
        """把向量归一化，后续余弦相似度可直接使用点积近似。"""
        norm = math.sqrt(sum(value * value for value in vector))
        if norm <= 0:
            return vector
        return [value / norm for value in vector]
