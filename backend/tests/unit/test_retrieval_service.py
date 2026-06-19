from app.knowledge.retrieval.retrieval_service import RetrievalService


def test_retrieval_returns_city_documents() -> None:
    service = RetrievalService()

    result = service.retrieve(destination="杭州", preferences=["food"], days=3, budget=3000)

    assert result["retrieved_documents"]
    assert any("杭州" in item["content"] for item in result["retrieved_documents"])
    assert result["retrieval_steps"]
    assert "lexical_overlap" in result["ranking_signals"]
    assert result["query_rewrite"]["source"] == "rule-based"
    assert result["query_rewrite"]["query_terms"][0] == "杭州"


def test_retrieval_returns_beijing_documents() -> None:
    service = RetrievalService()

    result = service.retrieve(destination="北京", preferences=["culture"], days=3, budget=4000)

    assert result["retrieved_documents"]
    assert any("北京" in item["content"] for item in result["retrieved_documents"])


def test_retrieval_returns_new_city_documents() -> None:
    service = RetrievalService()

    result = service.retrieve(destination="西安", preferences=["museum", "culture"], days=3, budget=3500)

    assert result["retrieved_documents"]
    assert any("西安" in item["content"] for item in result["retrieved_documents"])
    assert any(item["topic"] == "trip_route" for item in result["retrieved_documents"])


def test_retrieval_returns_xiamen_documents_with_citywalk_bias() -> None:
    service = RetrievalService()

    result = service.retrieve(destination="厦门", preferences=["citywalk", "nature"], days=3, budget=5000)

    assert result["retrieved_documents"]
    assert any("厦门" in item["content"] for item in result["retrieved_documents"])
    assert any(item["topic"] in {"trip_route", "citywalk"} for item in result["retrieved_documents"])


def test_retrieval_returns_shenzhen_documents_with_diverse_topics() -> None:
    service = RetrievalService()

    result = service.retrieve(destination="深圳", preferences=["citywalk", "nature", "comfortable_hotel"], days=4, budget=6000)

    assert result["retrieved_documents"]
    assert any("深圳" in item["content"] for item in result["retrieved_documents"])
    assert len(result["retrieved_documents"]) >= 4
    topics = {item["topic"] for item in result["retrieved_documents"]}
    assert "trip_route" in topics
    assert "citywalk" in topics or "hotel_area" in topics


def test_retrieval_returns_family_documents_for_sanya() -> None:
    service = RetrievalService()

    result = service.retrieve(destination="三亚", preferences=["family", "quiet_hotel"], days=4, budget=9000)

    assert result["retrieved_documents"]
    assert any("三亚" in item["content"] for item in result["retrieved_documents"])
    topics = {item["topic"] for item in result["retrieved_documents"]}
    assert "family" in topics
    assert "hotel_area" in topics or "trip_route" in topics


def test_retrieval_returns_rainy_day_and_family_documents_for_shanghai() -> None:
    service = RetrievalService()

    result = service.retrieve(destination="上海", preferences=["family", "rainy_day"], days=1, budget=0)

    assert result["retrieved_documents"]
    topics = {item["topic"] for item in result["retrieved_documents"]}
    assert "rainy_day" in topics
    assert "family" in topics


def test_retrieval_query_rewrite_can_extract_extra_keywords_from_user_input() -> None:
    service = RetrievalService()

    result = service.retrieve(
        destination="深圳",
        preferences=["citywalk", "nature"],
        days=2,
        budget=0,
        pace="balanced",
        user_input="深圳周末两天想去海边看夜景，顺便拍照",
    )

    assert "focus_keywords" in result["query_rewrite"]
    assert "海边" in result["query_rewrite"]["focus_keywords"]
    assert "夜景" in result["query_rewrite"]["focus_keywords"]
