from app.core.config.settings import Settings
from app.knowledge.rag.embedding_client import OpenAIEmbeddingClient


def test_parse_embeddings_response_sorts_by_index_and_normalizes_vectors() -> None:
    client = OpenAIEmbeddingClient(
        Settings(
            embedding_mode="openai",
            embedding_base_url="https://api.openai.com/v1",
            embedding_api_key="test-key",
            embedding_model="text-embedding-3-small",
        )
    )

    vectors = client._parse_embeddings_response(
        data={
            "data": [
                {"index": 1, "embedding": [0.0, 5.0]},
                {"index": 0, "embedding": [3.0, 4.0]},
            ]
        },
        expected_count=2,
    )

    assert vectors[0] == [0.6, 0.8]
    assert vectors[1] == [0.0, 1.0]


def test_enabled_requires_openai_mode_and_api_key() -> None:
    disabled_client = OpenAIEmbeddingClient(Settings())
    enabled_client = OpenAIEmbeddingClient(
        Settings(
            embedding_mode="openai",
            embedding_api_key="test-key",
            embedding_model="text-embedding-3-small",
        )
    )

    assert disabled_client.enabled() is False
    assert enabled_client.enabled() is True
