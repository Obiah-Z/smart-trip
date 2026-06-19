from __future__ import annotations

import json
from typing import Any

from app.core.db.sqlite import DATA_DIR, get_connection, sqlite_available


class GraphStore:
    _memory_nodes: list[dict[str, Any]] = []
    _memory_edges: list[dict[str, str]] = []

    def __init__(self) -> None:
        self._snapshot_path = DATA_DIR / "knowledge_graph" / "graph_snapshot.json"

    def ensure_schema(self) -> None:
        if not sqlite_available():
            self._snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            return
        with get_connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS graph_nodes (
                    node_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    node_type TEXT NOT NULL,
                    city TEXT NOT NULL,
                    aliases_json TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS graph_edges (
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    edge_type TEXT NOT NULL,
                    PRIMARY KEY (source_id, target_id, edge_type)
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_graph_edges_source ON graph_edges(source_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_graph_edges_target ON graph_edges(target_id)")
            connection.commit()

    def replace_all(self, *, nodes: list[dict[str, Any]], edges: list[dict[str, str]]) -> None:
        self._memory_nodes = [dict(item) for item in nodes]
        self._memory_edges = [dict(item) for item in edges]
        GraphStore._memory_nodes = [dict(item) for item in nodes]
        GraphStore._memory_edges = [dict(item) for item in edges]
        self._write_snapshot(nodes=nodes, edges=edges)

        if not sqlite_available():
            return

        self.ensure_schema()
        with get_connection() as connection:
            connection.execute("DELETE FROM graph_edges")
            connection.execute("DELETE FROM graph_nodes")
            connection.executemany(
                """
                INSERT INTO graph_nodes (node_id, title, node_type, city, aliases_json, tags_json, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item["node_id"],
                        item["title"],
                        item["node_type"],
                        item["city"],
                        json.dumps(item.get("aliases", []), ensure_ascii=False),
                        json.dumps(item.get("tags", []), ensure_ascii=False),
                        json.dumps(item.get("metadata", {}), ensure_ascii=False),
                    )
                    for item in nodes
                ],
            )
            connection.executemany(
                """
                INSERT INTO graph_edges (source_id, target_id, edge_type)
                VALUES (?, ?, ?)
                """,
                [(item["source_id"], item["target_id"], item["edge_type"]) for item in edges],
            )
            connection.commit()

    def expand_entity(self, *, entity: str) -> list[str]:
        normalized = str(entity).strip()
        if not normalized:
            return []

        if not sqlite_available():
            return self._expand_entity_from_records(
                entity=normalized,
                nodes=self._load_snapshot_nodes(),
                edges=self._load_snapshot_edges(),
            )

        self.ensure_schema()
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT node_id, title, aliases_json
                FROM graph_nodes
                """
            ).fetchall()
            if not rows:
                return self._expand_entity_from_records(
                    entity=normalized,
                    nodes=self._load_snapshot_nodes(),
                    edges=self._load_snapshot_edges(),
                )
            matched_node_id = None
            for row in rows:
                aliases = json.loads(row["aliases_json"])
                candidates = {
                    str(row["node_id"]).strip(),
                    str(row["title"]).strip(),
                    *[str(item).strip() for item in aliases],
                }
                if normalized in candidates:
                    matched_node_id = str(row["node_id"])
                    break
            if matched_node_id is None:
                return [normalized]

            expanded: list[str] = [normalized]
            edge_rows = connection.execute(
                """
                SELECT target_id, edge_type
                FROM graph_edges
                WHERE source_id = ?
                """,
                (matched_node_id,),
            ).fetchall()
            for row in edge_rows:
                edge_type = str(row["edge_type"])
                if edge_type not in {"alias", "cluster_member"}:
                    continue
                target = str(row["target_id"]).strip()
                if target:
                    expanded.append(target)
            return list(dict.fromkeys(expanded))

    def _expand_entity_from_records(
        self,
        *,
        entity: str,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, str]],
    ) -> list[str]:
        matched_node_id = None
        for row in nodes:
            aliases = row.get("aliases", [])
            candidates = {
                str(row.get("node_id", "")).strip(),
                str(row.get("title", "")).strip(),
                *[str(item).strip() for item in aliases],
            }
            if entity in candidates:
                matched_node_id = str(row.get("node_id", "")).strip()
                break

        if matched_node_id is None:
            return [entity]

        expanded: list[str] = [entity]
        for row in edges:
            if str(row.get("source_id", "")).strip() != matched_node_id:
                continue
            edge_type = str(row.get("edge_type", "")).strip()
            if edge_type not in {"alias", "cluster_member"}:
                continue
            target = str(row.get("target_id", "")).strip()
            if target:
                expanded.append(target)
        return list(dict.fromkeys(expanded))

    def _write_snapshot(self, *, nodes: list[dict[str, Any]], edges: list[dict[str, str]]) -> None:
        self._snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        self._snapshot_path.write_text(
            json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_snapshot_nodes(self) -> list[dict[str, Any]]:
        if self._memory_nodes:
            return self._memory_nodes
        if GraphStore._memory_nodes:
            return GraphStore._memory_nodes
        payload = self._load_snapshot_payload()
        nodes = payload.get("nodes", [])
        return nodes if isinstance(nodes, list) else []

    def _load_snapshot_edges(self) -> list[dict[str, str]]:
        if self._memory_edges:
            return self._memory_edges
        if GraphStore._memory_edges:
            return GraphStore._memory_edges
        payload = self._load_snapshot_payload()
        edges = payload.get("edges", [])
        return edges if isinstance(edges, list) else []

    def _load_snapshot_payload(self) -> dict[str, Any]:
        if not self._snapshot_path.exists():
            return {}
        try:
            payload = json.loads(self._snapshot_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}
