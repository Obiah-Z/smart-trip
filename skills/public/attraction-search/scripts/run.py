from __future__ import annotations

import argparse
import json

from app.mock.travel_engine import load_travel_data, select_attractions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload-json", required=True)
    args = parser.parse_args()

    payload = json.loads(args.payload_json)
    destination = payload.get("destination", "")
    preferences = payload.get("preferences", [])
    days = int(payload.get("days", 3))
    pace = str(payload.get("pace", "balanced"))
    excluded_attractions = payload.get("excluded_attractions", []) or []

    data = load_travel_data()
    result = select_attractions(
        data=data,
        destination=destination,
        preferences=preferences,
        days=days,
        pace=pace,
        excluded_attractions=excluded_attractions,
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
