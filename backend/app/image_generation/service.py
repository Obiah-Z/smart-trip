from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import threading
from typing import Any

from app.config.settings import Settings
from app.image_generation.asset_utils import (
    ImageAssetMeta,
    build_asset_meta,
    lookup_key,
    normalize_manifest_record,
    subject_name_from_record,
)
from app.image_generation.client import GPTImageClient, ImageGenerationRequest
from app.image_generation.prompt_builder import (
    ASSET_GROUP_LABELS,
    AssetGroup,
    TripImagePromptBuilder,
    TripImagePromptInput,
)
from app.image_generation.thumbnails import (
    DEFAULT_THUMBNAIL_WIDTHS,
    generate_thumbnails_for_image,
    record_with_thumbnail_fields,
)


IMAGE_LABEL = "AI示意图"
DEFAULT_ASSET_GROUP: AssetGroup = "attractions"


class ImageGenerationService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = GPTImageClient(settings)
        self._prompt_builder = TripImagePromptBuilder(settings)
        self._output_dir = Path(settings.image_output_dir)
        self._meta_dir = self._output_dir / "meta"
        self._manifest_path = self._meta_dir / "manifest.json"
        self._manifest_lock = threading.Lock()

    def enabled(self) -> bool:
        return self._client.enabled()

    def generate_asset(
        self,
        *,
        asset_group: str,
        destination: str,
        subject_name: str,
        subject_type: str | None = None,
        area: str | None = None,
        style: str | None = None,
        aspect: str | None = None,
        time_of_day: str | None = None,
        weather_hint: str | None = None,
        user_preferences: list[str] | None = None,
        size: str | None = None,
        quality: str | None = None,
        output_format: str | None = None,
        tags: list[str] | None = None,
        content_hint: str | None = None,
        extra_context: dict[str, Any] | None = None,
        force_regenerate: bool = False,
    ) -> dict[str, Any]:
        normalized_group = self._normalize_asset_group(asset_group)
        self._ensure_storage()

        built_prompt = self._prompt_builder.build(
            TripImagePromptInput(
                asset_group=normalized_group,
                destination=destination,
                subject_name=subject_name,
                subject_type=subject_type,
                area=area,
                style=style,
                aspect=aspect,
                time_of_day=time_of_day,
                weather_hint=weather_hint,
                user_preferences=user_preferences or [],
                size=size,
                tags=tags or [],
                content_hint=content_hint,
                extra_context=extra_context or {},
            )
        )
        effective_quality = quality or self._settings.image_default_quality
        effective_format = output_format or self._settings.image_default_format
        asset_meta = self._build_asset_meta(
            destination=destination,
            asset_group=normalized_group,
            subject_name=subject_name,
            subject_type=subject_type,
            style=built_prompt.style,
            aspect=built_prompt.aspect,
            time_of_day=time_of_day,
            weather_hint=weather_hint,
            output_format=effective_format,
        )
        cache_key = self._build_cache_key(
            prompt=built_prompt.prompt,
            size=built_prompt.size,
            quality=effective_quality,
            output_format=effective_format,
        )

        if self._settings.image_enable_cache and not force_regenerate:
            cached = self._find_cached_record(cache_key)
            if cached is not None:
                return self._build_response_payload(
                    record=cached,
                    asset_meta=asset_meta,
                    cache_hit=True,
                    fallback_label=f"{IMAGE_LABEL} · {ASSET_GROUP_LABELS[normalized_group]}",
                )

        response = self._client.generate_image(
            ImageGenerationRequest(
                prompt=built_prompt.prompt,
                size=built_prompt.size,
                quality=effective_quality,
                output_format=effective_format,
            )
        )

        image_base64 = (response.get("data") or [{}])[0].get("b64_json")
        if not image_base64:
            raise RuntimeError("Image API returned an empty b64_json payload")

        image_bytes = base64.b64decode(image_base64)
        extension = "jpg" if effective_format == "jpeg" else effective_format
        file_name = asset_meta.file_name
        if not file_name.endswith(f".{extension}"):
            file_name = f"{asset_meta.file_stem}.{extension}"
        relative_path = asset_meta.relative_path.with_suffix(f".{extension}")
        file_path = self._output_dir / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(image_bytes)
        thumbnail_fields = self._generate_thumbnail_fields(
            file_path=file_path,
            relative_path=relative_path.as_posix(),
        )

        created_at = datetime.now(timezone.utc).isoformat()
        task_id = f"asset_{hashlib.md5(asset_meta.asset_key.encode('utf-8')).hexdigest()[:12]}"
        record = {
            "task_id": task_id,
            "cache_key": cache_key,
            "image_url": f"/media/generated/{relative_path.as_posix()}",
            "local_path": str(file_path),
            "relative_path": relative_path.as_posix(),
            "file_name": file_name,
            "asset_group": asset_meta.asset_group,
            "destination_folder": asset_meta.destination_folder,
            "asset_key": asset_meta.asset_key,
            "prompt": built_prompt.prompt,
            "destination": destination,
            "subject_name": subject_name,
            "subject_type": subject_type,
            "area": area,
            "style": built_prompt.style,
            "aspect": built_prompt.aspect,
            "size": built_prompt.size,
            "quality": effective_quality,
            "output_format": effective_format,
            "label": f"{IMAGE_LABEL} · {built_prompt.label}",
            "request_id": response.get("_request_id"),
            "usage": response.get("usage") or {},
            "created_at": created_at,
            "tags": tags or [],
            "content_hint": content_hint,
            **thumbnail_fields,
        }
        if normalized_group == "attractions":
            record["attraction_name"] = subject_name
        self._save_record(record)
        return self._build_response_payload(
            record=record,
            asset_meta=asset_meta,
            cache_hit=False,
            fallback_label=f"{IMAGE_LABEL} · {built_prompt.label}",
        )

    def generate_attraction_image(
        self,
        *,
        destination: str,
        attraction_name: str,
        attraction_type: str | None = None,
        area: str | None = None,
        style: str = "travel_editorial",
        aspect: str = "landscape",
        time_of_day: str | None = None,
        weather_hint: str | None = None,
        user_preferences: list[str] | None = None,
        size: str | None = None,
        quality: str | None = None,
        output_format: str | None = None,
        force_regenerate: bool = False,
    ) -> dict[str, Any]:
        # Keep backward compatibility with the old API route.
        return self.generate_asset(
            asset_group="attractions",
            destination=destination,
            subject_name=attraction_name,
            subject_type=attraction_type,
            area=area,
            style=style,
            aspect=aspect,
            time_of_day=time_of_day,
            weather_hint=weather_hint,
            user_preferences=user_preferences,
            size=size,
            quality=quality,
            output_format=output_format,
            force_regenerate=force_regenerate,
        )

    def list_records(self) -> list[dict[str, Any]]:
        return self._load_records()

    def build_visual_assets(self, *, final_plan: dict[str, Any]) -> dict[str, Any]:
        summary = final_plan.get("summary") or {}
        destination = summary.get("destinationCity")
        if not destination:
            return {}

        records = self._load_records()
        index = self._build_lookup_index(records)
        hero_record = self._find_asset_record(
            index=index,
            destination=destination,
            asset_group="hero",
            subject_name=destination,
        )
        visual_assets: dict[str, Any] = {
            "hero": self._to_hero_payload(hero_record) if hero_record is not None else None,
            "attractions": self._map_named_assets(
                index=index,
                destination=destination,
                asset_group="attractions",
                items=final_plan.get("attractionRecommendations") or [],
            ),
            "hotels": self._map_named_assets(
                index=index,
                destination=destination,
                asset_group="hotels",
                items=final_plan.get("hotelOptions") or final_plan.get("hotelRecommendation") or [],
            ),
            "foods": self._map_named_assets(
                index=index,
                destination=destination,
                asset_group="foods",
                items=final_plan.get("foodRecommendations") or [],
            ),
        }
        return visual_assets

    def enrich_plan_visual_assets(self, *, final_plan: dict[str, Any]) -> dict[str, Any]:
        return {
            **final_plan,
            "visualAssets": self.build_visual_assets(final_plan=final_plan),
        }

    def _build_lookup_index(self, records: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
        index: dict[tuple[str, str, str], dict[str, Any]] = {}
        for item in records:
            if not self._record_exists(item):
                continue
            destination_key = lookup_key(item.get("destination") or item.get("destination_folder"))
            asset_group = lookup_key(item.get("asset_group"))
            subject_name = lookup_key(subject_name_from_record(item))
            if not destination_key or not asset_group or not subject_name:
                continue
            index[(destination_key, asset_group, subject_name)] = item
        return index

    def _find_asset_record(
        self,
        *,
        index: dict[tuple[str, str, str], dict[str, Any]],
        destination: str,
        asset_group: str,
        subject_name: str,
    ) -> dict[str, Any] | None:
        return index.get(
            (
                lookup_key(destination),
                lookup_key(asset_group),
                lookup_key(subject_name),
            )
        )

    def _map_named_assets(
        self,
        *,
        index: dict[tuple[str, str, str], dict[str, Any]],
        destination: str,
        asset_group: str,
        items: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        mapped: dict[str, dict[str, Any]] = {}
        for item in items:
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            record = self._find_asset_record(
                index=index,
                destination=destination,
                asset_group=asset_group,
                subject_name=name,
            )
            if record is None:
                continue
            mapped[name] = self._to_card_payload(record)
        return mapped

    def _to_hero_payload(self, record: dict[str, Any]) -> dict[str, Any]:
        url = record.get("image_url")
        thumbnails = self._thumbnail_payload(record)
        return {
            "name": record.get("subject_name") or record.get("destination"),
            "imageUrl": url,
            "url": url,
            **thumbnails,
            "label": record.get("label") or f"{IMAGE_LABEL} · {ASSET_GROUP_LABELS['hero']}",
            "relativePath": record.get("relative_path"),
        }

    def _to_card_payload(self, record: dict[str, Any]) -> dict[str, Any]:
        thumbnails = self._thumbnail_payload(record)
        return {
            "url": record.get("image_url"),
            "imageUrl": record.get("image_url"),
            **thumbnails,
            "label": record.get("label") or IMAGE_LABEL,
            "relativePath": record.get("relative_path"),
        }

    def _build_response_payload(
        self,
        *,
        record: dict[str, Any],
        asset_meta: ImageAssetMeta,
        cache_hit: bool,
        fallback_label: str,
    ) -> dict[str, Any]:
        return {
            "task_id": record["task_id"],
            "status": "ready",
            "image_url": record["image_url"],
            "local_path": record["local_path"],
            "relative_path": record.get("relative_path") or asset_meta.relative_path.as_posix(),
            "file_name": record.get("file_name") or asset_meta.file_name,
            "asset_group": record.get("asset_group") or asset_meta.asset_group,
            "destination_folder": record.get("destination_folder") or asset_meta.destination_folder,
            "asset_key": record.get("asset_key") or asset_meta.asset_key,
            "cache_hit": cache_hit,
            "label": record.get("label") or fallback_label,
            "prompt": record["prompt"],
            "size": record["size"],
            "quality": record["quality"],
            "output_format": record["output_format"],
            "request_id": record.get("request_id"),
            "usage": record.get("usage", {}),
            "created_at": record["created_at"],
            **self._thumbnail_payload(record),
        }

    def _build_cache_key(self, *, prompt: str, size: str, quality: str, output_format: str) -> str:
        payload = {
            "model": self._settings.image_model,
            "prompt": prompt,
            "size": size,
            "quality": quality,
            "output_format": output_format,
            "moderation": self._settings.image_moderation,
        }
        normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _build_asset_meta(
        self,
        *,
        destination: str,
        asset_group: AssetGroup,
        subject_name: str,
        subject_type: str | None,
        style: str,
        aspect: str,
        time_of_day: str | None,
        weather_hint: str | None,
        output_format: str,
    ) -> ImageAssetMeta:
        return build_asset_meta(
            destination=destination,
            asset_group=asset_group,
            subject_name=subject_name,
            subject_type=subject_type,
            style=style,
            aspect=aspect,
            time_of_day=time_of_day,
            weather_hint=weather_hint,
            output_format=output_format,
        )

    def _ensure_storage(self) -> None:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._meta_dir.mkdir(parents=True, exist_ok=True)
        if not self._manifest_path.exists():
            self._manifest_path.write_text("[]", encoding="utf-8")

    def _load_records(self) -> list[dict[str, Any]]:
        self._ensure_storage()
        with self._manifest_lock:
            return self._load_records_unlocked()

    def _save_record(self, record: dict[str, Any]) -> None:
        self._ensure_storage()
        with self._manifest_lock:
            records = self._load_records_unlocked()
            records = [
                item
                for item in records
                if item.get("cache_key") != record["cache_key"]
                and item.get("asset_key") != record["asset_key"]
            ]
            records.append(record)
            self._manifest_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    def _find_cached_record(self, cache_key: str) -> dict[str, Any] | None:
        self._ensure_storage()
        with self._manifest_lock:
            records = self._load_records_unlocked()
            for item in reversed(records):
                if item.get("cache_key") != cache_key:
                    continue
                if self._record_exists(item):
                    return item
        return None

    def _load_records_unlocked(self) -> list[dict[str, Any]]:
        raw_records = json.loads(self._manifest_path.read_text(encoding="utf-8"))
        normalized_records = [
            normalize_manifest_record(item, asset_root=self._output_dir)
            for item in raw_records
        ]
        if normalized_records != raw_records:
            self._manifest_path.write_text(
                json.dumps(normalized_records, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return normalized_records

    def _record_exists(self, record: dict[str, Any]) -> bool:
        local_path = record.get("local_path")
        return bool(local_path) and Path(local_path).exists()

    def _generate_thumbnail_fields(self, *, file_path: Path, relative_path: str) -> dict[str, Any]:
        try:
            generate_thumbnails_for_image(
                source_path=file_path,
                asset_root=self._output_dir,
                relative_path=relative_path,
                widths=DEFAULT_THUMBNAIL_WIDTHS,
                quality=max(1, min(int(self._settings.image_default_compression), 95)),
            )
        except Exception:
            return {}
        return record_with_thumbnail_fields(
            {"relative_path": relative_path},
            asset_root=self._output_dir,
            widths=DEFAULT_THUMBNAIL_WIDTHS,
        )

    def _thumbnail_payload(self, record: dict[str, Any]) -> dict[str, Any]:
        enriched = record_with_thumbnail_fields(
            record,
            asset_root=self._output_dir,
            widths=DEFAULT_THUMBNAIL_WIDTHS,
        )
        thumbnail_urls = enriched.get("thumbnail_urls") or {}
        thumbnail_url = enriched.get("thumbnail_url") or ""
        srcset = ", ".join(
            f"{url} {width}w"
            for width, url in sorted(
                ((int(width), url) for width, url in thumbnail_urls.items() if str(url).strip()),
                key=lambda item: item[0],
            )
        )
        return {
            "thumbnailUrl": thumbnail_url,
            "thumbnailUrls": thumbnail_urls,
            "thumbnailSrcSet": srcset,
        }

    def _normalize_asset_group(self, value: str) -> AssetGroup:
        normalized = str(value or DEFAULT_ASSET_GROUP).strip().lower()
        if normalized not in {"hero", "attractions", "hotels", "foods"}:
            raise ValueError(f"unsupported asset_group: {value}")
        return normalized  # type: ignore[return-value]
