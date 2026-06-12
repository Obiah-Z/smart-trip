from __future__ import annotations

import argparse
import json
from typing import Any

from app.mock.travel_engine import load_travel_data, select_attractions


VALID_PACES = {"relaxed", "balanced", "intensive"}


def build_attraction_response(*, data: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    destination = str(payload.get("destination", "")).strip()
    preferences = _as_string_list(payload.get("preferences", []))
    days, day_warning = _coerce_days(payload.get("days", 3))
    pace, pace_warning = _coerce_pace(payload.get("pace", "balanced"))
    excluded_attractions = _as_string_list(payload.get("excluded_attractions", []) or [])
    warnings = [item for item in (day_warning, pace_warning) if item]

    if not destination:
        return {
            "destination": "",
            "matched": False,
            "preferences": preferences,
            "days": days,
            "pace": pace,
            "excluded_attractions": excluded_attractions,
            "selection_strategy": _selection_strategy(excluded_attractions=excluded_attractions),
            "attractions": [],
            "warnings": ["missing_destination", *warnings],
        }

    matched = destination in data.get("attractions", {})
    result = select_attractions(
        data=data,
        destination=destination,
        preferences=preferences,
        days=days,
        pace=pace,
        excluded_attractions=excluded_attractions,
    )
    if not matched:
        warnings.append("unknown_destination")
    if matched and not result.get("attractions"):
        warnings.append("no_attractions_after_filtering")

    return {
        "destination": destination,
        "matched": matched,
        "preferences": preferences,
        "days": days,
        "pace": pace,
        "excluded_attractions": excluded_attractions,
        "selection_strategy": _selection_strategy(excluded_attractions=excluded_attractions),
        **result,
        "warnings": warnings,
    }


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))


def _coerce_days(value: Any) -> tuple[int, str | None]:
    try:
        days = int(value)
    except (TypeError, ValueError):
        return 3, "invalid_days_defaulted_to_3"
    if days < 1:
        return 1, "days_clamped_to_1"
    if days > 14:
        return 14, "days_clamped_to_14"
    return days, None


def _coerce_pace(value: Any) -> tuple[str, str | None]:
    pace = str(value or "balanced").strip()
    if pace not in VALID_PACES:
        return "balanced", "invalid_pace_defaulted_to_balanced"
    return pace, None


def _selection_strategy(*, excluded_attractions: list[str]) -> dict[str, bool]:
    return {
        "preference_filtering": True,
        "pace_aware": True,
        "exclusion_applied": bool(excluded_attractions),
        "diversified_by_area": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload-json", required=True)
    args = parser.parse_args()

    payload = json.loads(args.payload_json)
    data = load_travel_data()
    result = build_attraction_response(data=data, payload=payload)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
