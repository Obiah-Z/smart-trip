from pathlib import Path

from app.knowledge.rag.corpus_builder import build_manifest, write_corpus_and_index
from scripts.build_rag_markdown_corpus import build_markdown_corpus


def test_build_manifest_generates_chunks_from_knowledge_and_structured_data(tmp_path: Path) -> None:
    build_markdown_corpus()
    backend_root = Path(__file__).resolve().parents[2]
    manifest = build_manifest(markdown_dir=backend_root / "data" / "rag" / "raw_markdown")

    chunks = manifest["chunks"]
    assert chunks
    assert any(chunk["city"] == "杭州" for chunk in chunks)
    assert any(chunk["topic"] == "hotel_area" for chunk in chunks)
    assert any("raw_markdown/hangzhou.md" in chunk["source"] for chunk in chunks)
    assert any(chunk["metadata"]["kind"] == "markdown_section" for chunk in chunks)

    result = write_corpus_and_index(
        manifest=manifest,
        corpus_dir=tmp_path / "corpus",
        index_dir=tmp_path / "index",
    )

    assert Path(result["manifest_path"]).exists()
    assert Path(result["output_path"]).exists()
    assert result["documents"] > 0
