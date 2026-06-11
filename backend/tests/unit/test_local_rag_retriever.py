import json
from pathlib import Path

from app.config.settings import Settings
from app.rag.corpus_builder import build_manifest, write_corpus_and_index
from app.rag.embedding_client import OpenAIEmbeddingClient
from app.rag.retriever import LocalRAGRetriever
from scripts.build_rag_markdown_corpus import build_markdown_corpus


def test_local_rag_retriever_returns_ranked_city_chunks(tmp_path: Path) -> None:
    build_markdown_corpus()
    backend_root = Path(__file__).resolve().parents[2]
    manifest = build_manifest(markdown_dir=backend_root / "data" / "rag" / "raw_markdown")
    result = write_corpus_and_index(
        manifest=manifest,
        corpus_dir=tmp_path / "corpus",
        index_dir=tmp_path / "index",
    )

    retriever = LocalRAGRetriever(index_path=Path(result["output_path"]))
    ranked = retriever.search(
        destination="深圳",
        query="深圳 4日游 海边 citywalk 安静酒店 攻略 推荐",
        query_terms=["深圳", "4日游", "海边", "citywalk", "安静酒店", "攻略", "推荐"],
        preferences=["citywalk", "nature", "quiet_hotel"],
        days=4,
        top_k=5,
    )

    assert ranked
    assert all(item["content"] for item in ranked)
    assert any("深圳" in item["content"] or "深圳" in item["title"] for item in ranked)
    assert "bm25_score" in ranked[0]


class StubEmbeddingClient(OpenAIEmbeddingClient):
    def __init__(self) -> None:
        super().__init__(
            Settings(
                embedding_mode="openai",
                embedding_api_key="test-key",
                embedding_model="text-embedding-3-small",
            )
        )

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0]


def test_local_rag_retriever_can_merge_vector_scores(tmp_path: Path) -> None:
    build_markdown_corpus()
    backend_root = Path(__file__).resolve().parents[2]
    manifest = build_manifest(markdown_dir=backend_root / "data" / "rag" / "raw_markdown")
    result = write_corpus_and_index(
        manifest=manifest,
        corpus_dir=tmp_path / "corpus",
        index_dir=tmp_path / "index",
    )

    first_chunk_id = str(manifest["chunks"][0]["id"])
    second_chunk_id = str(manifest["chunks"][1]["id"])
    embedding_index_path = tmp_path / "index" / "embedding_index.json"
    embedding_index_path.write_text(
        json.dumps(
            {
                "model": "text-embedding-3-small",
                "dimensions": 2,
                "documents": [
                    {"id": first_chunk_id, "vector": [1.0, 0.0]},
                    {"id": second_chunk_id, "vector": [0.0, 1.0]},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    retriever = LocalRAGRetriever(
        index_path=Path(result["output_path"]),
        settings=Settings(
            embedding_mode="openai",
            embedding_api_key="test-key",
            embedding_model="text-embedding-3-small",
        ),
        embedding_index_path=embedding_index_path,
        embedding_client=StubEmbeddingClient(),
    )
    ranked = retriever.search(
        destination=str(manifest["chunks"][0]["city"]),
        query="测试 query",
        query_terms=["测试"],
        preferences=[],
        days=None,
        top_k=3,
    )

    assert ranked
    assert ranked[0]["retrieval_mode"] == "hybrid"
    assert "vector_score" in ranked[0]
    assert "hybrid_score" in ranked[0]
