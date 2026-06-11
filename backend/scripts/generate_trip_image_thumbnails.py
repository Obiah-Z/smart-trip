from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config.settings import load_settings
from app.image_generation.asset_utils import normalize_manifest_record
from app.image_generation.thumbnails import (
    DEFAULT_THUMBNAIL_WIDTHS,
    generate_thumbnails_for_image,
    record_with_thumbnail_fields,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate 320/640 thumbnail files for trip visual assets.")
    parser.add_argument(
        "--asset-root",
        default="",
        help="Root directory for generated images. Defaults to IMAGE_OUTPUT_DIR from settings.",
    )
    parser.add_argument(
        "--manifest-file",
        default="",
        help="Manifest JSON path. Defaults to ASSET_ROOT/meta/manifest.json.",
    )
    parser.add_argument(
        "--width",
        action="append",
        type=int,
        help="Thumbnail width. Can be passed multiple times. Defaults to 320 and 640.",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=78,
        help="JPEG/WebP thumbnail quality. Defaults to 78.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate thumbnails even when target files already exist.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Only process the first N manifest records. 0 means no limit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be processed without writing files or manifest.",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Only print the summary to stdout.",
    )
    return parser.parse_args()


def load_manifest(path: Path, *, asset_root: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"manifest file not found: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"manifest must be a JSON list: {path}")
    return [
        normalize_manifest_record(dict(item), asset_root=asset_root)
        for item in raw
        if isinstance(item, dict)
    ]


def select_records(records: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    selected = []
    for item in records:
        relative_path = str(item.get("relative_path") or "").strip()
        if not relative_path or relative_path.startswith("__thumbs__/"):
            continue
        selected.append(item)
        if limit > 0 and len(selected) >= limit:
            break
    return selected


def build_widths(values: list[int] | None) -> tuple[int, ...]:
    widths = tuple(sorted({int(item) for item in values or DEFAULT_THUMBNAIL_WIDTHS if int(item) > 0}))
    return widths or DEFAULT_THUMBNAIL_WIDTHS


def main() -> int:
    args = parse_args()
    settings = load_settings()

    asset_root = Path(args.asset_root or settings.image_output_dir).expanduser().resolve()
    manifest_path = (
        Path(args.manifest_file).expanduser().resolve()
        if args.manifest_file
        else asset_root / "meta" / "manifest.json"
    )
    widths = build_widths(args.width)
    quality = max(1, min(args.quality, 95))
    records = load_manifest(manifest_path, asset_root=asset_root)
    selected = select_records(records, limit=max(0, args.limit))

    processed: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    updated_records_by_path: dict[str, dict[str, Any]] = {}

    for item in selected:
        relative_path = str(item.get("relative_path") or "").strip()
        source_path = Path(str(item.get("local_path") or "")) if item.get("local_path") else asset_root / relative_path
        if args.dry_run:
            processed.append(
                {
                    "relative_path": relative_path,
                    "source_path": str(source_path),
                    "thumbnail_widths": list(widths),
                    "dry_run": True,
                }
            )
            continue

        try:
            thumbnails = generate_thumbnails_for_image(
                source_path=source_path,
                asset_root=asset_root,
                relative_path=relative_path,
                widths=widths,
                quality=quality,
                force=bool(args.force),
            )
            updated_record = record_with_thumbnail_fields(item, asset_root=asset_root, widths=widths)
            updated_records_by_path[relative_path] = updated_record
            processed.append(
                {
                    "relative_path": relative_path,
                    "thumbnail_count": len(thumbnails),
                    "thumbnail_paths": [thumb.relative_path for thumb in thumbnails],
                }
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(
                {
                    "relative_path": relative_path,
                    "source_path": str(source_path),
                    "message": str(exc),
                }
            )

    if not args.dry_run and updated_records_by_path:
        output_records = [
            updated_records_by_path.get(str(item.get("relative_path") or "").strip(), item)
            for item in records
        ]
        manifest_path.write_text(
            json.dumps(output_records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    summary = {
        "asset_root": str(asset_root),
        "manifest_file": str(manifest_path),
        "manifest_records": len(records),
        "selected_records": len(selected),
        "processed": len(processed),
        "errors": len(errors),
        "widths": list(widths),
        "quality": quality,
        "force": bool(args.force),
        "dry_run": bool(args.dry_run),
        "manifest_written": bool(not args.dry_run and updated_records_by_path),
    }
    report = {"summary": summary, "processed": processed, "errors": errors}
    if args.summary_only:
        print(json.dumps({"summary": summary}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
