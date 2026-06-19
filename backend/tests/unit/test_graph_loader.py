from pathlib import Path

from app.knowledge.graph.loader import ObsidianGraphLoader
from app.knowledge.graph.service import GraphExpansionService


def test_obsidian_graph_loader_parses_frontmatter_and_wikilinks(tmp_path: Path) -> None:
    vault_dir = tmp_path / "vault"
    city_dir = vault_dir / "杭州"
    city_dir.mkdir(parents=True)
    note_path = city_dir / "西湖.md"
    note_path.write_text(
        """---
title: 西湖
type: attraction
city: 杭州
aliases: ["西湖景区"]
cluster_members: ["白堤孤山", "苏堤"]
alternatives: ["西溪湿地"]
tags: ["nature", "classic"]
---

# 西湖

- [[白堤孤山]]
- [[苏堤]]
- [[西溪湿地]]
""",
        encoding="utf-8",
    )

    loader = ObsidianGraphLoader()
    nodes, edges = loader.load_directory(vault_dir=vault_dir)

    assert len(nodes) == 1
    assert nodes[0]["node_id"] == "西湖"
    assert nodes[0]["aliases"] == ["西湖景区"]
    assert nodes[0]["metadata"]["cluster_members"] == ["白堤孤山", "苏堤"]
    assert nodes[0]["metadata"]["alternatives"] == ["西溪湿地"]
    assert any(item["edge_type"] == "cluster_member" and item["target_id"] == "白堤孤山" for item in edges)
    assert any(item["edge_type"] == "wikilink" and item["target_id"] == "西溪湿地" for item in edges)


def test_graph_expansion_service_expands_cluster_members() -> None:
    class StubGraphStore:
        def expand_entity(self, *, entity: str) -> list[str]:
            if entity == "西湖":
                return ["西湖", "白堤孤山", "苏堤"]
            return [entity]

    service = GraphExpansionService(graph_store=StubGraphStore())
    expanded = service.expand_excluded_attractions(attractions=["西湖"])

    assert expanded == ["西湖", "白堤孤山", "苏堤"]
