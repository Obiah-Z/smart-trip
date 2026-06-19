from __future__ import annotations

from pathlib import Path

import httpx

from app.core.config.settings import Settings
from app.knowledge.rag.corpus_builder import build_manifest, write_corpus_and_index
from app.knowledge.rag.embedding_client import OpenAIEmbeddingClient
from app.knowledge.rag.vector_index import VectorIndexBuilder


def ensure_rag_ready(*, backend_root: Path, settings: Settings | None = None) -> None:
    raw_markdown_dir = backend_root / "data" / "rag" / "raw_markdown"
    corpus_dir = backend_root / "data" / "rag" / "corpus"
    index_dir = backend_root / "data" / "rag" / "index"
    index_path = index_dir / "rag_index.json"

    if not raw_markdown_dir.exists():
        from scripts.build_rag_markdown_corpus import build_markdown_corpus

        build_markdown_corpus()

    if not index_path.exists():
        manifest = build_manifest(markdown_dir=raw_markdown_dir)
        write_corpus_and_index(
            manifest=manifest,
            corpus_dir=corpus_dir,
            index_dir=index_dir,
        )

    if settings is None:
        return

    embedding_client = OpenAIEmbeddingClient(settings)
    if not embedding_client.enabled():
        return

    embedding_index_path = Path(settings.embedding_index_path)
    if embedding_index_path.exists():
        return

    builder = VectorIndexBuilder(
        corpus_dir=corpus_dir,
        output_path=embedding_index_path,
        embedding_client=embedding_client,
    )
    try:
        builder.build()
    except (RuntimeError, ValueError, OSError, httpx.HTTPError):
        return
