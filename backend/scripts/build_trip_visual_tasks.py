from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.capabilities.image_generation.task_builder import TripVisualTaskBuilder


DEFAULT_OUTPUT_PATH = BACKEND_ROOT / "data" / "generated_images" / "tasks" / "full_trip_visual_tasks.json"
DEFAULT_SUMMARY_PATH = BACKEND_ROOT / "data" / "generated_images" / "tasks" / "full_trip_visual_tasks.summary.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build offline trip visual generation tasks.")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="Output task JSON path.",
    )
    parser.add_argument(
        "--summary-output",
        default=str(DEFAULT_SUMMARY_PATH),
        help="Output summary JSON path.",
    )
    parser.add_argument(
        "--asset-group",
        action="append",
        choices=["hero", "attractions", "hotels", "foods"],
        help="Only include one or more asset groups.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = Path(args.output).expanduser().resolve()
    summary_path = Path(args.summary_output).expanduser().resolve()

    builder = TripVisualTaskBuilder()
    asset_groups = set(args.asset_group or []) or None
    tasks = builder.build_tasks(asset_groups=asset_groups)
    summary = builder.build_summary(tasks)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "output": str(output_path),
                "summary_output": str(summary_path),
                "summary": summary,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
