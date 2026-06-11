from __future__ import annotations

import argparse
import json
import time


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload-json", required=True)
    args = parser.parse_args()
    json.loads(args.payload_json)
    time.sleep(2)
    print(json.dumps({"ok": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
