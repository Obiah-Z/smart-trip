from pathlib import Path

from scripts.build_rag_markdown_corpus import build_markdown_corpus


def test_build_rag_markdown_corpus_writes_city_markdown_files() -> None:
    written_files = build_markdown_corpus()

    assert written_files
    assert any(path.name == "hangzhou.md" for path in written_files)
    assert any(path.name == "README.md" for path in written_files)

    hangzhou_path = Path(__file__).resolve().parents[2] / "data" / "rag" / "raw_markdown" / "hangzhou.md"
    content = hangzhou_path.read_text(encoding="utf-8")
    assert content.startswith("---\n")
    assert 'doc_type: "travel_city_knowledge"' in content
    assert 'city: "杭州"' in content
    assert 'city_slug: "hangzhou"' in content
    assert "section_counts:" in content
    assert "generated_at:" in content
    assert "# 杭州旅行知识库" in content
    assert "## 景点与玩法清单" in content
    assert "## 住宿建议" in content
