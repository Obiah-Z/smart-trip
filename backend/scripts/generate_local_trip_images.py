from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import sys
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config.settings import load_settings
from app.capabilities.image_generation.client import ImageGenerationError
from app.capabilities.image_generation.service import ImageGenerationService


DEFAULT_TASKS_FILE = BACKEND_ROOT / "data" / "generated_images" / "tasks" / "full_trip_visual_tasks.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate local trip images into city-based folders.")
    parser.add_argument(
        "--tasks-file",
        default=str(DEFAULT_TASKS_FILE),
        help="Path to a JSON file containing trip image generation tasks.",
    )
    parser.add_argument(
        "--asset-group",
        action="append",
        choices=["hero", "attractions", "hotels", "foods"],
        help="Only generate one or more asset groups.",
    )
    parser.add_argument(
        "--city",
        action="append",
        help="Only generate one or more cities.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Only run the first N filtered tasks. 0 means no limit.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of concurrent workers. Keep low to avoid relay throttling.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore cache and force regeneration.",
    )
    parser.add_argument(
        "--output-file",
        default="",
        help="Optional path to write the full JSON report.",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Only print the summary to stdout. Useful for large batches.",
    )
    return parser.parse_args()


def load_tasks(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def filter_tasks(
    *,
    tasks: list[dict[str, Any]],
    asset_groups: set[str] | None,
    cities: set[str] | None,
    limit: int,
) -> list[dict[str, Any]]:
    filtered = []
    for item in tasks:
        if asset_groups and str(item.get("asset_group")) not in asset_groups:
            continue
        if cities and str(item.get("destination")) not in cities:
            continue
        filtered.append(item)
        if limit > 0 and len(filtered) >= limit:
            break
    return filtered


def serialize_result(item: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    return {
        "destination": item.get("destination"),
        "asset_group": item.get("asset_group"),
        "subject_name": item.get("subject_name") or item.get("attraction_name"),
        "image_url": result.get("image_url"),
        "local_path": result.get("local_path"),
        "relative_path": result.get("relative_path"),
        "file_name": result.get("file_name"),
        "destination_folder": result.get("destination_folder"),
        "asset_key": result.get("asset_key"),
        "request_id": result.get("request_id"),
        "cache_hit": result.get("cache_hit"),
        "size": result.get("size"),
        "quality": result.get("quality"),
        "output_format": result.get("output_format"),
    }


def serialize_error(item: dict[str, Any], exc: Exception) -> dict[str, Any]:
    if isinstance(exc, ImageGenerationError):
        return {
            "destination": item.get("destination"),
            "asset_group": item.get("asset_group"),
            "subject_name": item.get("subject_name") or item.get("attraction_name"),
            "message": str(exc),
            "status_code": exc.status_code,
            "request_id": exc.request_id,
            "error_code": exc.error_code,
            "error_type": exc.error_type,
            "raw_error": exc.raw_error,
        }
    return {
        "destination": item.get("destination"),
        "asset_group": item.get("asset_group"),
        "subject_name": item.get("subject_name") or item.get("attraction_name"),
        "message": str(exc),
    }


def run_single_task(service: ImageGenerationService, item: dict[str, Any], force: bool) -> dict[str, Any]:
    payload = dict(item)
    if force:
        payload["force_regenerate"] = True
    return service.generate_asset(**payload)


def main() -> int:
    args = parse_args()
    tasks_path = Path(args.tasks_file).expanduser().resolve()
    if not tasks_path.exists():
        print(json.dumps({"error": f"tasks file not found: {tasks_path}"}, ensure_ascii=False))
        return 1

    settings = load_settings()
    service = ImageGenerationService(settings)
    if not service.enabled():
        print(json.dumps({"error": "image generation is not enabled in current settings"}, ensure_ascii=False))
        return 1

    tasks = load_tasks(tasks_path)
    filtered = filter_tasks(
        tasks=tasks,
        asset_groups=set(args.asset_group or [] ) or None,
        cities=set(args.city or [] ) or None,
        limit=max(0, args.limit),
    )

    if not filtered:
        print(json.dumps({"results": [], "errors": [], "summary": {"matched_tasks": 0}}, ensure_ascii=False, indent=2))
        return 0

    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    workers = max(1, min(args.workers, 6))

    if workers == 1:
        for item in filtered:
            try:
                result = run_single_task(service, item, args.force)
                results.append(serialize_result(item, result))
            except Exception as exc:  # noqa: BLE001
                errors.append(serialize_error(item, exc))
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_item = {
                executor.submit(run_single_task, service, item, args.force): item
                for item in filtered
            }
            for future in as_completed(future_to_item):
                item = future_to_item[future]
                try:
                    result = future.result()
                    results.append(serialize_result(item, result))
                except Exception as exc:  # noqa: BLE001
                    errors.append(serialize_error(item, exc))

    summary = {
        "matched_tasks": len(filtered),
        "generated": len(results),
        "errors": len(errors),
        "workers": workers,
        "force": bool(args.force),
        "asset_groups": sorted({str(item.get("asset_group")) for item in filtered}),
        "cities": sorted({str(item.get("destination")) for item in filtered}),
    }
    report = {"summary": summary, "results": results, "errors": errors}
    if args.output_file:
        output_path = Path(args.output_file).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        summary["output_file"] = str(output_path)

    if args.summary_only:
        print(json.dumps({"summary": summary}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
