from __future__ import annotations

from pathlib import Path

from app.core.config.settings import load_settings
from app.knowledge.rag.embedding_client import OpenAIEmbeddingClient
from app.knowledge.rag.vector_index import VectorIndexBuilder


BACKEND_ROOT = Path(__file__).resolve().parents[1]
RAG_CORPUS_DIR = BACKEND_ROOT / "data" / "rag" / "corpus"


def main() -> None:
    settings = load_settings()
    embedding_client = OpenAIEmbeddingClient(settings)
    if not embedding_client.enabled():
        raise SystemExit("embedding client is disabled; set EMBEDDING_MODE=openai and EMBEDDING_API_KEY first")

    result = VectorIndexBuilder(
        corpus_dir=RAG_CORPUS_DIR,
        output_path=Path(settings.embedding_index_path),
        embedding_client=embedding_client,
    ).build()
    print("rag vector index built")
    print(f"- output_path: {result['output_path']}")
    print(f"- documents: {result['documents']}")
    print(f"- model: {result['model']}")
    print(f"- dimensions: {result['dimensions']}")


if __name__ == "__main__":
    main()
