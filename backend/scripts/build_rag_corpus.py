from __future__ import annotations

from pathlib import Path

from app.core.config.settings import load_settings
from app.knowledge.rag.corpus_builder import build_manifest, write_corpus_and_index
from app.knowledge.rag.embedding_client import OpenAIEmbeddingClient
from app.knowledge.rag.vector_index import VectorIndexBuilder


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_ROOT / "data"
RAW_MARKDOWN_DIR = DATA_DIR / "rag" / "raw_markdown"
RAG_CORPUS_DIR = DATA_DIR / "rag" / "corpus"
RAG_INDEX_DIR = DATA_DIR / "rag" / "index"


def main() -> None:
    settings = load_settings()
    manifest = build_manifest(markdown_dir=RAW_MARKDOWN_DIR)
    result = write_corpus_and_index(
        manifest=manifest,
        corpus_dir=RAG_CORPUS_DIR,
        index_dir=RAG_INDEX_DIR,
    )
    print("rag corpus built")
    print(f"- manifest: {result['manifest_path']}")
    print(f"- chunks: {len(manifest['chunks'])}")
    print(f"- index: {result['output_path']}")
    print(f"- avg_doc_length: {result['avg_doc_length']}")

    embedding_client = OpenAIEmbeddingClient(settings)
    if not embedding_client.enabled():
        print("- embedding_index: skipped (EMBEDDING_MODE is not openai or EMBEDDING_API_KEY missing)")
        return

    vector_result = VectorIndexBuilder(
        corpus_dir=RAG_CORPUS_DIR,
        output_path=Path(settings.embedding_index_path),
        embedding_client=embedding_client,
    ).build()
    print(f"- embedding_index: {vector_result['output_path']}")
    print(f"- embedding_model: {vector_result['model']}")
    print(f"- embedding_dimensions: {vector_result['dimensions']}")


if __name__ == "__main__":
    main()
