from __future__ import annotations

import argparse
import json
import time


def main() -> None:
    """沙箱超时测试脚本：故意 sleep，用于验证 timeout_seconds 是否生效。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload-json", required=True)
    args = parser.parse_args()
    json.loads(args.payload_json)
    time.sleep(2)
    print(json.dumps({"ok": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
