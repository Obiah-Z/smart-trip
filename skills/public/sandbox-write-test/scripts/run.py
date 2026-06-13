from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    """沙箱写入测试脚本：故意写工作区外文件，用于验证写入限制是否生效。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload-json", required=True)
    args = parser.parse_args()
    json.loads(args.payload_json)
    target = Path(__file__).resolve().parents[4] / "sandbox-write-should-fail.txt"
    target.write_text("blocked", encoding="utf-8")
    print(json.dumps({"ok": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
