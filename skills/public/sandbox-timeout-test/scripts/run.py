"""Sandbox timeout 测试 Skill。

该脚本故意 sleep，用于验证 sandbox_policy.timeout_seconds 是否会中断子进程。
它不参与正常旅行规划，只服务沙箱机制回归测试。
"""

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
    # 故意超过测试 Skill 配置的超时时间，验证 SkillSandboxRunner 的 timeout 分支。
    time.sleep(2)
    # 如果沙箱没有按预期超时，才会走到这里输出 JSON。
    print(json.dumps({"ok": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
