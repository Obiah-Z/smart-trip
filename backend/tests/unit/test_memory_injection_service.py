from app.memory.memory_injection_service import MemoryInjectionService


def test_memory_injection_selects_relevant_hotel_and_food_preferences() -> None:
    service = MemoryInjectionService()

    result = service.select(
        long_term_memory=[
            {"key": "hotel_style", "value": "prefer_lively_location"},
            {"key": "preference_local_food", "value": "avoid_local_food"},
            {"key": "preference_nature", "value": "nature"},
        ],
        structured_constraints={
            "destination": "杭州",
            "days": 3,
            "budget": 3000,
            "pace": "intensive",
            "preferences": ["lively_hotel", "avoid_local_food"],
        },
        user_input="帮我规划一个杭州三日游，酒店尽量嘈杂，不想吃本地特色",
    )

    selected_keys = {item["key"] for item in result["relevant_long_term_memory"]}

    assert "hotel_style" in selected_keys
    assert "preference_local_food" in selected_keys
    assert result["selection_reasons"]


def test_memory_injection_selects_family_preference_for_family_query() -> None:
    service = MemoryInjectionService()

    result = service.select(
        long_term_memory=[
            {"key": "preference_family", "value": "family"},
            {"key": "hotel_style", "value": "prefer_quiet_location"},
            {"key": "preference_food", "value": "food"},
        ],
        structured_constraints={
            "destination": "三亚",
            "days": 4,
            "budget": 9000,
            "pace": "relaxed",
            "preferences": ["family", "quiet_hotel"],
        },
        user_input="帮我规划一个三亚四日游，适合亲子，酒店尽量安静",
    )

    selected_keys = {item["key"] for item in result["relevant_long_term_memory"]}

    assert "preference_family" in selected_keys
    assert any("亲子或家庭出游偏好" in item for item in result["selection_reasons"])
