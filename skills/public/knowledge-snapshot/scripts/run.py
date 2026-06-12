from __future__ import annotations

import argparse
import json
from typing import Any


def build_snapshot_response(*, payload: dict[str, Any]) -> dict[str, Any]:
    destination = str(payload.get("destination", "")).strip()
    return {
        "source": "mock_mcp",
        "status": "ok",
        "capability": "travel_knowledge_bridge",
        "destination": destination,
        "adapters": ["local_skill_registry", "sandbox_runner", "mcp_gateway_placeholder"],
        "safe_for_user_view": False,
        "notes": [
            "当前返回的是受控本地知识桥接状态，不包含密钥、环境变量或外部服务细节。",
            "普通旅行规划不应自动展示该结果。",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload-json", required=True)
    args = parser.parse_args()

    payload = json.loads(args.payload_json)
    result = build_snapshot_response(payload=payload)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
