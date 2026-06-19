from __future__ import annotations

import re


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]{1,4}")


def tokenize(text: str) -> list[str]:
    if not text:
        return []
    tokens = TOKEN_PATTERN.findall(text.lower())
    normalized: list[str] = []
    for token in tokens:
        stripped = token.strip()
        if stripped:
            normalized.append(stripped)
    return normalized
