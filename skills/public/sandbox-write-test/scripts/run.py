"""Sandbox write restriction 测试 Skill。

该脚本故意写入工作区外文件，用于验证沙箱写入拦截是否生效。
它不参与正常旅行规划，只作为安全边界测试用例。
"""

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
    # 目标路径不在 sandbox_policy.writable_roots 内，正常情况下应被拦截。
    target = Path(__file__).resolve().parents[4] / "sandbox-write-should-fail.txt"
    target.write_text("blocked", encoding="utf-8")
    # 如果沙箱没有拦截写入，才会走到这里输出 JSON。
    print(json.dumps({"ok": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
