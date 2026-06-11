from __future__ import annotations

import argparse
import json

from app.mock.travel_engine import plan_route


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload-json", required=True)
    args = parser.parse_args()

    payload = json.loads(args.payload_json)
    destination = payload.get("destination", "")
    days = int(payload.get("days", 3))
    pace = str(payload.get("pace", "balanced"))
    attraction_items = payload.get("attraction_items", []) or []
    attraction_names = payload.get("attraction_names", []) or [f"{destination} 城市漫步"]
    excluded_attractions = payload.get("excluded_attractions", []) or []

    result = plan_route(
        destination=destination,
        days=days,
        pace=pace,
        attraction_items=attraction_items,
        attraction_names=attraction_names,
        excluded_attractions=excluded_attractions,
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
