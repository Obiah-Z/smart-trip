from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config.settings import load_settings
from app.capabilities.image_generation.audit import (
    audit_trip_visual_assets,
    default_quarantine_dir,
    load_manifest,
    load_tasks,
    move_relative_files,
    prune_unexpected_manifest_records,
    write_json,
)


DEFAULT_TASKS_FILE = BACKEND_ROOT / "data" / "generated_images" / "tasks" / "full_trip_visual_tasks.json"
DEFAULT_OUTPUT_FILE = BACKEND_ROOT / "data" / "generated_images" / "tasks" / "trip_visual_audit_report.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit and optionally normalize local trip visual assets.")
    parser.add_argument(
        "--tasks-file",
        default=str(DEFAULT_TASKS_FILE),
        help="Path to the canonical task JSON file.",
    )
    parser.add_argument(
        "--manifest-file",
        default="",
        help="Path to the image manifest JSON file. Defaults to IMAGE_OUTPUT_DIR/meta/manifest.json.",
    )
    parser.add_argument(
        "--asset-root",
        default="",
        help="Root directory for generated images. Defaults to IMAGE_OUTPUT_DIR from settings.",
    )
    parser.add_argument(
        "--output-file",
        default=str(DEFAULT_OUTPUT_FILE),
        help="Optional path to write the audit report JSON.",
    )
    parser.add_argument(
        "--write-manifest",
        action="store_true",
        help="Write normalized or pruned manifest content back to disk.",
    )
    parser.add_argument(
        "--prune-unexpected-manifest",
        action="store_true",
        help="Remove manifest entries that are not part of the canonical task list.",
    )
    parser.add_argument(
        "--quarantine-stale-files",
        action="store_true",
        help="Move filesystem files not referenced by the manifest into a quarantine directory.",
    )
    parser.add_argument(
        "--quarantine-unexpected-files",
        action="store_true",
        help="Move files referenced by unexpected manifest entries into a quarantine directory.",
    )
    parser.add_argument(
        "--quarantine-dir",
        default="",
        help="Override quarantine directory. Defaults to backend/data/generated_images/quarantine/<timestamp>/.",
    )
    parser.add_argument(
        "--fail-on-drift",
        action="store_true",
        help="Return non-zero if the audit finds any drift.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = load_settings()

    asset_root = Path(args.asset_root or settings.image_output_dir).expanduser().resolve()
    manifest_path = Path(args.manifest_file).expanduser().resolve() if args.manifest_file else asset_root / "meta" / "manifest.json"
    tasks_path = Path(args.tasks_file).expanduser().resolve()

    tasks = load_tasks(tasks_path)
    manifest_records = load_manifest(manifest_path, asset_root=asset_root)
    report = audit_trip_visual_assets(
        tasks=tasks,
        manifest_records=manifest_records,
        asset_root=asset_root,
    )

    manifest_to_write = report["normalized_manifest"]
    quarantine_dir = (
        Path(args.quarantine_dir).expanduser().resolve()
        if args.quarantine_dir
        else default_quarantine_dir(asset_root)
    )
    moved_files: list[dict[str, str]] = []

    if args.quarantine_unexpected_files:
        moved_files.extend(
            move_relative_files(
                asset_root=asset_root,
                relative_paths=[
                    str(item.get("relative_path") or "")
                    for item in report["unexpected_manifest_entries"]
                ],
                quarantine_dir=quarantine_dir / "unexpected_manifest_files",
            )
        )

    if args.prune_unexpected_manifest:
        manifest_to_write = prune_unexpected_manifest_records(
            manifest_to_write,
            report["unexpected_manifest_entries"],
        )

    if args.quarantine_stale_files:
        moved_files.extend(
            move_relative_files(
                asset_root=asset_root,
                relative_paths=[
                    str(item.get("relative_path") or "")
                    for item in report["stale_files"]
                ],
                quarantine_dir=quarantine_dir / "stale_files",
            )
        )

    should_write_manifest = bool(
        args.write_manifest
        or args.prune_unexpected_manifest
    )

    report["actions"] = {
        "manifest_written": False,
        "manifest_pruned": bool(args.prune_unexpected_manifest),
        "quarantine_dir": str(quarantine_dir) if moved_files else "",
        "moved_files": moved_files,
    }

    if should_write_manifest:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest_to_write, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        report["actions"]["manifest_written"] = True

    if moved_files or should_write_manifest:
        refreshed_manifest = load_manifest(manifest_path, asset_root=asset_root) if manifest_path.exists() else manifest_to_write
        report = audit_trip_visual_assets(
            tasks=tasks,
            manifest_records=refreshed_manifest,
            asset_root=asset_root,
        )
        report["actions"] = {
            "manifest_written": should_write_manifest,
            "manifest_pruned": bool(args.prune_unexpected_manifest),
            "quarantine_dir": str(quarantine_dir) if moved_files else "",
            "moved_files": moved_files,
        }

    if args.output_file:
        output_path = Path(args.output_file).expanduser().resolve()
        write_json(output_path, report)
        report["actions"]["output_file"] = str(output_path)

    print(json.dumps(report, ensure_ascii=False, indent=2))

    summary = report["summary"]
    has_drift = any(
        summary[key] > 0
        for key in (
            "normalization_changes",
            "missing_manifest_entries",
            "unexpected_manifest_entries",
            "duplicate_manifest_keys",
            "missing_files_for_manifest",
            "stale_files",
            "expected_file_gaps",
        )
    )
    if args.fail_on_drift and has_drift:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
