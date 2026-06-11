from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
import shutil
from typing import Any

from app.image_generation.asset_utils import (
    build_asset_meta_from_task,
    normalize_manifest_record,
    subject_name_from_record,
)


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_tasks(path: Path) -> list[dict[str, Any]]:
    data = load_json(path)
    if not isinstance(data, list):
        raise ValueError(f"expected list JSON in tasks file: {path}")
    return [dict(item) for item in data]


def load_manifest(path: Path, *, asset_root: Path) -> list[dict[str, Any]]:
    data = load_json(path)
    if not isinstance(data, list):
        raise ValueError(f"expected list JSON in manifest file: {path}")
    return [
        normalize_manifest_record(dict(item), asset_root=asset_root)
        for item in data
    ]


def expected_assets_from_tasks(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expected_assets: list[dict[str, Any]] = []
    for item in tasks:
        meta = build_asset_meta_from_task(item)
        expected_assets.append(
            {
                "asset_key": meta.asset_key,
                "relative_path": meta.relative_path.as_posix(),
                "file_name": meta.file_name,
                "asset_group": str(item.get("asset_group") or ""),
                "destination": str(item.get("destination") or ""),
                "subject_name": str(
                    item.get("subject_name")
                    or item.get("attraction_name")
                    or item.get("destination")
                    or ""
                ).strip(),
                "subject_type": str(item.get("subject_type") or "").strip(),
            }
        )
    return expected_assets


def collect_image_files(asset_root: Path) -> dict[str, dict[str, Any]]:
    files: dict[str, dict[str, Any]] = {}
    if not asset_root.exists():
        return files
    for path in asset_root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        relative_path = path.relative_to(asset_root).as_posix()
        files[relative_path] = {
            "relative_path": relative_path,
            "absolute_path": str(path),
            "size_bytes": path.stat().st_size,
        }
    return files


def audit_trip_visual_assets(
    *,
    tasks: list[dict[str, Any]],
    manifest_records: list[dict[str, Any]],
    asset_root: Path,
) -> dict[str, Any]:
    expected_assets = expected_assets_from_tasks(tasks)
    expected_by_key = {item["asset_key"]: item for item in expected_assets}

    raw_manifest_records = [dict(item) for item in manifest_records]
    normalized_manifest = [
        normalize_manifest_record(item, asset_root=asset_root)
        for item in raw_manifest_records
    ]
    normalization_changes = sum(
        1
        for before, after in zip(raw_manifest_records, normalized_manifest)
        if before != after
    )

    manifest_by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in normalized_manifest:
        asset_key = str(item.get("asset_key") or "").strip()
        if not asset_key:
            continue
        manifest_by_key[asset_key].append(item)

    duplicate_manifest_entries: list[dict[str, Any]] = []
    for asset_key, records in sorted(manifest_by_key.items()):
        if len(records) <= 1:
            continue
        duplicate_manifest_entries.append(
            {
                "asset_key": asset_key,
                "count": len(records),
                "relative_paths": [str(item.get("relative_path") or "") for item in records],
            }
        )

    expected_keys = set(expected_by_key)
    manifest_keys = set(manifest_by_key)
    missing_manifest_entries = [
        expected_by_key[asset_key]
        for asset_key in sorted(expected_keys - manifest_keys)
    ]
    unexpected_manifest_entries = [
        summarize_manifest_record(item)
        for asset_key in sorted(manifest_keys - expected_keys)
        for item in manifest_by_key[asset_key]
    ]

    filesystem_files = collect_image_files(asset_root)
    manifest_relative_paths = {
        str(item.get("relative_path") or "").strip()
        for item in normalized_manifest
        if str(item.get("relative_path") or "").strip()
    }
    filesystem_relative_paths = set(filesystem_files)

    missing_files_for_manifest = [
        summarize_manifest_record(item)
        for item in normalized_manifest
        if str(item.get("relative_path") or "").strip()
        and str(item.get("relative_path")).strip() not in filesystem_relative_paths
    ]
    stale_files = [
        filesystem_files[relative_path]
        for relative_path in sorted(filesystem_relative_paths - manifest_relative_paths)
    ]

    expected_file_gaps = []
    for asset_key in sorted(expected_keys):
        expected_item = expected_by_key[asset_key]
        relative_path = expected_item["relative_path"]
        if relative_path not in filesystem_relative_paths:
            expected_file_gaps.append(expected_item)

    summary = {
        "expected_tasks": len(tasks),
        "expected_assets": len(expected_assets),
        "manifest_records": len(normalized_manifest),
        "filesystem_files": len(filesystem_files),
        "normalization_changes": normalization_changes,
        "missing_manifest_entries": len(missing_manifest_entries),
        "unexpected_manifest_entries": len(unexpected_manifest_entries),
        "duplicate_manifest_keys": len(duplicate_manifest_entries),
        "missing_files_for_manifest": len(missing_files_for_manifest),
        "stale_files": len(stale_files),
        "expected_file_gaps": len(expected_file_gaps),
    }

    return {
        "summary": summary,
        "expected_assets": expected_assets,
        "normalized_manifest": normalized_manifest,
        "missing_manifest_entries": missing_manifest_entries,
        "unexpected_manifest_entries": unexpected_manifest_entries,
        "duplicate_manifest_entries": duplicate_manifest_entries,
        "missing_files_for_manifest": missing_files_for_manifest,
        "stale_files": stale_files,
        "expected_file_gaps": expected_file_gaps,
    }


def summarize_manifest_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "asset_key": str(record.get("asset_key") or ""),
        "asset_group": str(record.get("asset_group") or ""),
        "destination": str(record.get("destination") or record.get("destination_folder") or ""),
        "subject_name": str(subject_name_from_record(record) or ""),
        "relative_path": str(record.get("relative_path") or ""),
        "file_name": str(record.get("file_name") or ""),
        "created_at": str(record.get("created_at") or ""),
    }


def prune_unexpected_manifest_records(
    manifest_records: list[dict[str, Any]],
    unexpected_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    unexpected_relative_paths = {
        str(item.get("relative_path") or "").strip()
        for item in unexpected_records
        if str(item.get("relative_path") or "").strip()
    }
    return [
        item
        for item in manifest_records
        if str(item.get("relative_path") or "").strip() not in unexpected_relative_paths
    ]


def move_relative_files(
    *,
    asset_root: Path,
    relative_paths: list[str],
    quarantine_dir: Path,
) -> list[dict[str, Any]]:
    moved: list[dict[str, Any]] = []
    for relative_path in sorted(dict.fromkeys(relative_paths)):
        if not relative_path:
            continue
        source = asset_root / relative_path
        if not source.exists():
            continue
        destination = uniquify_path(quarantine_dir / relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        moved.append(
            {
                "from": str(source),
                "to": str(destination),
                "relative_path": relative_path,
            }
        )
    return moved


def default_quarantine_dir(asset_root: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return asset_root.parent / "quarantine" / f"trip_visual_assets_{stamp}"


def uniquify_path(path: Path) -> Path:
    if not path.exists():
        return path
    counter = 2
    while True:
        candidate = path.with_name(f"{path.stem}-{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1
