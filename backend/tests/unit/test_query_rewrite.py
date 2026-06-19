from app.knowledge.retrieval.query_rewrite import RuleBasedQueryRewriteService


def test_query_rewrite_keeps_destination_and_trip_terms() -> None:
    service = RuleBasedQueryRewriteService()

    result = service.rewrite(
        destination="杭州",
        preferences=["local_food", "quiet_hotel"],
        days=3,
        budget=3000,
        pace="relaxed",
        user_input="帮我规划一个杭州三日游，预算3000，节奏轻松一点，酒店尽量安静，想吃本地特色",
    )

    assert result["source"] == "rule-based"
    assert result["query_terms"][0] == "杭州"
    assert "3日游" in result["query_terms"]
    assert "本地特色" in result["query_terms"]
    assert "安静酒店" in result["query_terms"]
    assert "轻松" in result["query_terms"]
    assert "性价比" in result["query_terms"]


def test_query_rewrite_extracts_note_keywords_by_destination() -> None:
    service = RuleBasedQueryRewriteService()

    result = service.rewrite(
        destination="深圳",
        preferences=["citywalk", "nature"],
        days=2,
        budget=0,
        pace="balanced",
        user_input="深圳周末两天想去海边看夜景，顺便拍照",
    )

    assert "海边" in result["focus_keywords"]
    assert "夜景" in result["focus_keywords"]
    assert "拍照" in result["focus_keywords"]
    assert "深圳" in result["query"]
