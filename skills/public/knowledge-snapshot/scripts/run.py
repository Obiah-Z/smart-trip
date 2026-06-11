from __future__ import annotations

import argparse
import json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload-json", required=True)
    args = parser.parse_args()

    json.loads(args.payload_json)
    print(
        json.dumps(
            {
                "source": "mock_mcp",
                "status": "ok",
                "capability": "travel_knowledge_bridge",
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
