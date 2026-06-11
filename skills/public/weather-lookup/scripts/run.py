from __future__ import annotations

import argparse
import json

from app.mock.travel_engine import load_travel_data, weather_lookup


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload-json", required=True)
    args = parser.parse_args()

    payload = json.loads(args.payload_json)
    destination = payload.get("destination", "")

    data = load_travel_data()
    result = weather_lookup(data=data, destination=destination)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
