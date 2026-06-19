from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


DEFAULT_THUMBNAIL_WIDTHS = (320, 640)
THUMBNAIL_ROOT = "__thumbs__"


@dataclass(frozen=True)
class ThumbnailResult:
    width: int
    relative_path: str
    url: str
    local_path: str


def thumbnail_relative_path(relative_path: str | Path, *, width: int) -> Path:
    source = Path(str(relative_path))
    return Path(THUMBNAIL_ROOT) / str(width) / source


def thumbnail_url(relative_path: str | Path, *, width: int) -> str:
    return f"/media/generated/{thumbnail_relative_path(relative_path, width=width).as_posix()}"


def build_thumbnail_fields(
    *,
    relative_path: str,
    asset_root: Path,
    widths: tuple[int, ...] = DEFAULT_THUMBNAIL_WIDTHS,
) -> dict[str, Any]:
    thumbnail_urls: dict[str, str] = {}
    thumbnail_paths: dict[str, str] = {}
    for width in widths:
        thumb_relative = thumbnail_relative_path(relative_path, width=width).as_posix()
        if (asset_root / thumb_relative).exists():
            key = str(width)
            thumbnail_paths[key] = thumb_relative
            thumbnail_urls[key] = f"/media/generated/{thumb_relative}"
    if not thumbnail_urls:
        return {}
    largest_width = max(int(key) for key in thumbnail_urls)
    return {
        "thumbnail_url": thumbnail_urls[str(largest_width)],
        "thumbnail_urls": thumbnail_urls,
        "thumbnail_paths": thumbnail_paths,
    }


def record_with_thumbnail_fields(
    record: Mapping[str, Any],
    *,
    asset_root: Path,
    widths: tuple[int, ...] = DEFAULT_THUMBNAIL_WIDTHS,
) -> dict[str, Any]:
    normalized = dict(record)
    relative_path = str(normalized.get("relative_path") or "").strip()
    if not relative_path:
        return normalized
    normalized.update(
        build_thumbnail_fields(
            relative_path=relative_path,
            asset_root=asset_root,
            widths=widths,
        )
    )
    return normalized


def generate_thumbnails_for_image(
    *,
    source_path: Path,
    asset_root: Path,
    relative_path: str,
    widths: tuple[int, ...] = DEFAULT_THUMBNAIL_WIDTHS,
    quality: int = 78,
    force: bool = False,
) -> list[ThumbnailResult]:
    from PIL import Image

    if not source_path.exists():
        raise FileNotFoundError(f"image source not found: {source_path}")

    results: list[ThumbnailResult] = []
    with Image.open(source_path) as image:
        image.load()
        source_width, source_height = image.size
        for width in widths:
            if width <= 0:
                continue
            thumb_relative = thumbnail_relative_path(relative_path, width=width)
            thumb_path = asset_root / thumb_relative
            if thumb_path.exists() and not force:
                results.append(
                    ThumbnailResult(
                        width=width,
                        relative_path=thumb_relative.as_posix(),
                        url=f"/media/generated/{thumb_relative.as_posix()}",
                        local_path=str(thumb_path),
                    )
                )
                continue

            target_width = min(width, source_width)
            target_height = max(1, round(source_height * (target_width / source_width)))
            thumbnail = image.copy()
            thumbnail.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)
            if thumbnail.mode not in {"RGB", "L"}:
                thumbnail = thumbnail.convert("RGB")

            thumb_path.parent.mkdir(parents=True, exist_ok=True)
            save_kwargs: dict[str, Any] = {"optimize": True}
            if thumb_path.suffix.lower() in {".jpg", ".jpeg"}:
                save_kwargs.update({"quality": quality, "progressive": True})
            elif thumb_path.suffix.lower() == ".webp":
                save_kwargs.update({"quality": quality, "method": 6})
            thumbnail.save(thumb_path, **save_kwargs)
            results.append(
                ThumbnailResult(
                    width=width,
                    relative_path=thumb_relative.as_posix(),
                    url=f"/media/generated/{thumb_relative.as_posix()}",
                    local_path=str(thumb_path),
                )
            )
    return results
