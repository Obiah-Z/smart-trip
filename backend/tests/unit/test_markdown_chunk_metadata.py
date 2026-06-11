from pathlib import Path

from app.rag.corpus_builder import build_manifest
from scripts.build_rag_markdown_corpus import build_markdown_corpus


def test_markdown_chunks_preserve_frontmatter_and_section_metadata() -> None:
    build_markdown_corpus()
    backend_root = Path(__file__).resolve().parents[2]
    manifest = build_manifest(markdown_dir=backend_root / "data" / "rag" / "raw_markdown")

    hangzhou_chunks = [chunk for chunk in manifest["chunks"] if chunk["city"] == "杭州"]
    assert hangzhou_chunks

    first_chunk = hangzhou_chunks[0]
    metadata = first_chunk["metadata"]
    assert metadata["kind"] == "markdown_section"
    assert metadata["city_slug"] == "hangzhou"
    assert "section_title" in metadata
    assert "generated_at" in metadata
    assert "source_files" in metadata
    assert first_chunk["source"].endswith("raw_markdown/hangzhou.md")
