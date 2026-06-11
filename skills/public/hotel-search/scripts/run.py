from __future__ import annotations

import argparse
import json

from app.mock.travel_engine import load_travel_data, select_hotels


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload-json", required=True)
    args = parser.parse_args()

    payload = json.loads(args.payload_json)
    destination = payload.get("destination", "")
    budget = int(payload.get("budget", 3000))
    preferences = payload.get("preferences", [])

    data = load_travel_data()
    result = select_hotels(
        data=data,
        destination=destination,
        budget=budget,
        preferences=preferences,
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
