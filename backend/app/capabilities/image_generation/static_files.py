from __future__ import annotations

from fastapi.staticfiles import StaticFiles
from starlette.responses import Response


class CachedStaticFiles(StaticFiles):
    """Static file server with cache headers for generated image assets."""

    def __init__(
        self,
        *args,
        cache_control: str = "public, max-age=604800, stale-while-revalidate=86400",
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._cache_control = cache_control

    async def get_response(self, path: str, scope) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers.setdefault("Cache-Control", self._cache_control)
        return response
