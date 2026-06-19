from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Mapping
import unicodedata

from app.capabilities.image_generation.thumbnails import record_with_thumbnail_fields


@dataclass(frozen=True)
class ImageAssetMeta:
    asset_group: str
    destination_folder: str
    file_name: str
    file_stem: str
    relative_path: Path
    asset_key: str


def safe_path_part(value: str, *, default: str, max_length: int) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    normalized = normalized.replace("/", "-").replace("\\", "-")
    normalized = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized[:max_length].strip("-") or default


def lookup_key(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    normalized = normalized.replace("/", "").replace("\\", "")
    normalized = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", normalized)
    return normalized


def relative_path_to_asset_key(relative_path: str | Path) -> str:
    return Path(relative_path).with_suffix("").as_posix().lstrip("./")


def subject_name_from_record(record: Mapping[str, Any]) -> str | None:
    for candidate in (
        record.get("subject_name"),
        record.get("attraction_name"),
        record.get("destination"),
    ):
        value = str(candidate or "").strip()
        if value:
            return value
    return None


def build_asset_meta(
    *,
    destination: str,
    asset_group: str,
    subject_name: str,
    subject_type: str | None,
    style: str,
    aspect: str,
    time_of_day: str | None,
    weather_hint: str | None,
    output_format: str,
) -> ImageAssetMeta:
    destination_folder = safe_path_part(destination, default="unknown-city", max_length=32)
    group_folder = safe_path_part(asset_group, default="assets", max_length=24)
    file_parts = [
        safe_path_part(subject_name, default="subject", max_length=40),
    ]
    if asset_group != "hero":
        file_parts.append(safe_path_part(subject_type or asset_group, default="generic", max_length=24))
    else:
        file_parts.append("hero")
    file_parts.append(safe_path_part(style, default="style", max_length=24))
    file_parts.append(safe_path_part(aspect, default="aspect", max_length=16))
    if time_of_day:
        file_parts.append(safe_path_part(time_of_day, default="time", max_length=24))
    if weather_hint:
        file_parts.append(safe_path_part(weather_hint, default="weather", max_length=24))

    file_stem = "-".join(part for part in file_parts if part)
    extension = "jpg" if output_format == "jpeg" else output_format
    file_name = f"{file_stem}.{extension}"
    relative_path = Path(destination_folder) / group_folder / file_name
    asset_key = f"{destination_folder}/{group_folder}/{file_stem}"
    return ImageAssetMeta(
        asset_group=asset_group,
        destination_folder=destination_folder,
        file_name=file_name,
        file_stem=file_stem,
        relative_path=relative_path,
        asset_key=asset_key,
    )


def build_asset_meta_from_task(task: Mapping[str, Any]) -> ImageAssetMeta:
    subject_name = str(
        task.get("subject_name")
        or task.get("attraction_name")
        or task.get("destination")
        or ""
    ).strip()
    return build_asset_meta(
        destination=str(task.get("destination") or ""),
        asset_group=str(task.get("asset_group") or "attractions"),
        subject_name=subject_name,
        subject_type=_optional_text(task.get("subject_type")),
        style=str(task.get("style") or ""),
        aspect=str(task.get("aspect") or ""),
        time_of_day=_optional_text(task.get("time_of_day")),
        weather_hint=_optional_text(task.get("weather_hint")),
        output_format=str(task.get("output_format") or "jpeg"),
    )


def normalize_manifest_record(
    record: Mapping[str, Any],
    *,
    asset_root: Path | None = None,
) -> dict[str, Any]:
    normalized = dict(record)
    subject_name = subject_name_from_record(normalized)
    if subject_name and not str(normalized.get("subject_name") or "").strip():
        normalized["subject_name"] = subject_name
    if (
        normalized.get("asset_group") == "attractions"
        and subject_name
        and not str(normalized.get("attraction_name") or "").strip()
    ):
        normalized["attraction_name"] = subject_name

    relative_path = str(normalized.get("relative_path") or "").strip()
    if not relative_path and asset_root is not None:
        local_path = str(normalized.get("local_path") or "").strip()
        if local_path:
            try:
                relative_path = Path(local_path).resolve().relative_to(asset_root.resolve()).as_posix()
            except ValueError:
                relative_path = ""

    if relative_path:
        normalized["relative_path"] = relative_path
        if not str(normalized.get("file_name") or "").strip():
            normalized["file_name"] = Path(relative_path).name
        if not str(normalized.get("asset_key") or "").strip():
            normalized["asset_key"] = relative_path_to_asset_key(relative_path)
        if not str(normalized.get("image_url") or "").strip():
            normalized["image_url"] = f"/media/generated/{relative_path}"
        if asset_root is not None and not str(normalized.get("local_path") or "").strip():
            normalized["local_path"] = str((asset_root / relative_path).resolve())
        if not str(normalized.get("destination_folder") or "").strip():
            parts = Path(relative_path).parts
            if parts:
                normalized["destination_folder"] = parts[0]
        if not str(normalized.get("destination") or "").strip():
            destination_folder = str(normalized.get("destination_folder") or "").strip()
            if destination_folder:
                normalized["destination"] = destination_folder

    if normalized.get("asset_group") == "hero" and not str(normalized.get("subject_name") or "").strip():
        destination = str(normalized.get("destination") or normalized.get("destination_folder") or "").strip()
        if destination:
            normalized["subject_name"] = destination

    if asset_root is not None:
        normalized = record_with_thumbnail_fields(normalized, asset_root=asset_root)

    return normalized


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None
