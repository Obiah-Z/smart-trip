from __future__ import annotations

from contextlib import contextmanager
import math
import os
import time
from typing import Any

import httpx

from app.config.settings import Settings


class OpenAIEmbeddingClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def enabled(self) -> bool:
        return self._settings.embedding_mode == "openai" and bool(self._settings.embedding_api_key)

    @property
    def model_name(self) -> str:
        return self._settings.embedding_model

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
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
        norm = math.sqrt(sum(value * value for value in vector))
        if norm <= 0:
            return vector
        return [value / norm for value in vector]
