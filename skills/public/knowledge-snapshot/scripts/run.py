from __future__ import annotations

import argparse
import json
from typing import Any


def build_snapshot_response(*, payload: dict[str, Any]) -> dict[str, Any]:
    """返回系统知识桥接能力快照。

    这是开发调试类 Skill，不应出现在普通用户旅行建议中，因此 safe_for_user_view=False。
    """
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
    """Skill 子进程入口：读取 payload 并输出能力快照 JSON。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload-json", required=True)
    args = parser.parse_args()

    payload = json.loads(args.payload_json)
    result = build_snapshot_response(payload=payload)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
