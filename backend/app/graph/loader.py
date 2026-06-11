from __future__ import annotations

from pathlib import Path
import json
import re
from typing import Any


class ObsidianGraphLoader:
    FRONTMATTER_PATTERN = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)
    WIKILINK_PATTERN = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")

    def load_directory(self, *, vault_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, str]] = []
        for file_path in sorted(vault_dir.rglob("*.md")):
            if not file_path.is_file():
                continue
            node, node_edges = self._load_note(file_path=file_path)
            if node is None:
                continue
            nodes.append(node)
            edges.extend(node_edges)
        return nodes, edges

    def _load_note(self, *, file_path: Path) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
        text = file_path.read_text(encoding="utf-8")
        metadata, body = self._split_frontmatter(text)
        title = str(metadata.get("title") or file_path.stem).strip()
        if not title:
            return None, []

        aliases = self._normalize_list(metadata.get("aliases"))
        cluster_members = self._normalize_list(metadata.get("cluster_members"))
        alternatives = self._normalize_list(metadata.get("alternatives"))
        tags = self._normalize_list(metadata.get("tags"))
        city = str(metadata.get("city") or "").strip()
        node_type = str(metadata.get("type") or "attraction").strip()

        node = {
            "node_id": title,
            "title": title,
            "node_type": node_type,
            "city": city,
            "aliases": aliases,
            "tags": tags,
            "metadata": {
                "cluster_members": cluster_members,
                "alternatives": alternatives,
                "source_path": str(file_path),
            },
        }

        edges: list[dict[str, str]] = []
        for alias in aliases:
            edges.append({"source_id": title, "target_id": alias, "edge_type": "alias"})
        for item in cluster_members:
            edges.append({"source_id": title, "target_id": item, "edge_type": "cluster_member"})
        for item in alternatives:
            edges.append({"source_id": title, "target_id": item, "edge_type": "alternative"})
        for target in self._extract_wikilinks(body):
            edges.append({"source_id": title, "target_id": target, "edge_type": "wikilink"})
        return node, edges

    def _split_frontmatter(self, text: str) -> tuple[dict[str, Any], str]:
        match = self.FRONTMATTER_PATTERN.match(text)
        if not match:
            return {}, text
        block = match.group(1)
        body = text[match.end():]
        metadata: dict[str, Any] = {}
        for raw_line in block.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            key, raw_value = line.split(":", 1)
            metadata[key.strip()] = self._parse_value(raw_value.strip())
        return metadata, body

    def _parse_value(self, raw_value: str) -> Any:
        if not raw_value:
            return ""
        if raw_value[0] in "[{":
            return json.loads(raw_value)
        if len(raw_value) >= 2 and raw_value[0] == raw_value[-1] and raw_value[0] in {"'", '"'}:
            return raw_value[1:-1]
        return raw_value

    def _normalize_list(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    def _extract_wikilinks(self, body: str) -> list[str]:
        links = [match.group(1).strip() for match in self.WIKILINK_PATTERN.finditer(body)]
        return list(dict.fromkeys([item for item in links if item]))
