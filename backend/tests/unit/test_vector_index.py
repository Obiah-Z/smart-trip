import json
from pathlib import Path

from app.config.settings import Settings
from app.rag.corpus_builder import build_manifest, write_corpus_and_index
from app.rag.embedding_client import OpenAIEmbeddingClient
from app.rag.vector_index import LocalVectorIndex, VectorIndexBuilder
from scripts.build_rag_markdown_corpus import build_markdown_corpus


class FakeEmbeddingClient(OpenAIEmbeddingClient):
    def __init__(self) -> None:
        super().__init__(
            Settings(
                embedding_mode="openai",
                embedding_api_key="test-key",
                embedding_model="text-embedding-3-small",
            )
        )

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, float(index + 1)] for index, _ in enumerate(texts)]


def test_vector_index_builder_writes_embedding_index(tmp_path: Path) -> None:
    build_markdown_corpus()
    backend_root = Path(__file__).resolve().parents[2]
    manifest = build_manifest(markdown_dir=backend_root / "data" / "rag" / "raw_markdown")
    write_corpus_and_index(
        manifest=manifest,
        corpus_dir=tmp_path / "corpus",
        index_dir=tmp_path / "index",
    )

    output_path = tmp_path / "index" / "embedding_index.json"
    result = VectorIndexBuilder(
        corpus_dir=tmp_path / "corpus",
        output_path=output_path,
        embedding_client=FakeEmbeddingClient(),
        batch_size=8,
    ).build()

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result["documents"] == len(manifest["chunks"])
    assert result["dimensions"] == 3
    assert payload["model"] == "text-embedding-3-small"
    assert payload["document_count"] == len(manifest["chunks"])
    assert payload["documents"][0]["vector"]


def test_local_vector_index_loads_saved_vectors(tmp_path: Path) -> None:
    output_path = tmp_path / "embedding_index.json"
    output_path.write_text(
        json.dumps(
            {
                "model": "text-embedding-3-small",
                "dimensions": 2,
                "documents": [
                    {"id": "chunk-a", "vector": [0.6, 0.8]},
                    {"id": "chunk-b", "vector": [0.1, 0.9]},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    index = LocalVectorIndex(index_path=output_path)

    assert index.model == "text-embedding-3-small"
    assert index.dimensions == 2
    assert index.get("chunk-a") == [0.6, 0.8]
    assert index.has_vectors() is True
