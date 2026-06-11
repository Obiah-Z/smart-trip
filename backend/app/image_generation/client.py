from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.config.settings import Settings


class ImageGenerationError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        request_id: str | None = None,
        error_code: str | None = None,
        error_type: str | None = None,
        raw_error: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.request_id = request_id
        self.error_code = error_code
        self.error_type = error_type
        self.raw_error = raw_error or {}


@dataclass(frozen=True)
class ImageGenerationRequest:
    prompt: str
    size: str | None = None
    quality: str | None = None
    output_format: str | None = None
    output_compression: int | None = None
    moderation: str | None = None
    n: int = 1


class GPTImageClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def enabled(self) -> bool:
        return self._settings.image_mode in {"openai", "openai_compatible"} and bool(self._settings.image_api_key)

    def generate_image(self, request: ImageGenerationRequest) -> dict[str, Any]:
        if not self.enabled():
            raise ImageGenerationError("Image generation client is disabled")

        payload = {
            "model": self._settings.image_model,
            "prompt": request.prompt,
            "n": max(1, request.n),
            "size": request.size or self._settings.image_default_size,
        }

        # Many OpenAI-compatible image relays only accept the minimal core fields.
        # Keep native OpenAI richer, but default relays to a conservative payload.
        if self._supports_advanced_options():
            quality = request.quality or self._settings.image_default_quality
            output_format = request.output_format or self._settings.image_default_format
            moderation = request.moderation or self._settings.image_moderation
            if quality:
                payload["quality"] = quality
            if output_format:
                payload["output_format"] = output_format
            if moderation:
                payload["moderation"] = moderation

            output_compression = (
                request.output_compression
                if request.output_compression is not None
                else self._settings.image_default_compression
            )
            if output_format in {"jpeg", "webp"}:
                payload["output_compression"] = str(max(0, min(100, int(output_compression))))

        with httpx.Client(timeout=float(self._settings.image_timeout_seconds), trust_env=False) as client:
            response = client.post(
                f"{self._settings.image_base_url.rstrip('/')}/images/generations",
                headers={
                    "Authorization": f"Bearer {self._settings.image_api_key}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        if response.is_error:
            self._raise_api_error(response)

        data = response.json()
        data["_request_id"] = (
            response.headers.get("x-oneapi-request-id")
            or response.headers.get("x-request-id")
            or response.headers.get("bdwaf-request-id")
        )
        images = data.get("data") or []
        if not images:
            raise ImageGenerationError(
                "Image API returned no image payload",
                status_code=response.status_code,
                request_id=response.headers.get("x-request-id"),
                raw_error=data,
            )
        return data

    def _supports_advanced_options(self) -> bool:
        base_url = self._settings.image_base_url.rstrip("/").lower()
        if self._settings.image_mode == "openai":
            return True
        return "api.openai.com" in base_url

    def _raise_api_error(self, response: httpx.Response) -> None:
        request_id = (
            response.headers.get("x-oneapi-request-id")
            or response.headers.get("x-request-id")
            or response.headers.get("bdwaf-request-id")
        )
        try:
            payload = response.json()
        except ValueError:
            payload = {"error": {"message": response.text.strip() or "Unknown image API error"}}

        error = payload.get("error") if isinstance(payload, dict) else None
        message = "Image generation request failed"
        error_code = None
        error_type = None
        if isinstance(error, dict):
            message = str(error.get("message") or message)
            error_code = error.get("code")
            error_type = error.get("type")

        raise ImageGenerationError(
            message,
            status_code=response.status_code,
            request_id=request_id,
            error_code=error_code,
            error_type=error_type,
            raw_error=payload if isinstance(payload, dict) else {},
        )
