from app.orchestration.memory.memory_injection_service import MemoryInjectionService
from app.orchestration.memory.preference_profile import update_profile_value, signal_definition


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


def test_memory_injection_does_not_fallback_to_unrelated_memory() -> None:
    service = MemoryInjectionService()

    result = service.select(
        long_term_memory=[
            {"key": "preference_family", "value": "family", "updated_at": "2026-01-01T00:00:00+00:00"},
            {"key": "preference_food", "value": "food", "updated_at": "2026-01-02T00:00:00+00:00"},
        ],
        structured_constraints={
            "destination": "杭州",
            "days": None,
            "budget": 0,
            "pace": "balanced",
            "preferences": [],
        },
        user_input="杭州今天会下雨吗",
    )

    assert result["relevant_long_term_memory"] == []
    assert result["selection_reasons"] == []


def test_memory_injection_suppresses_conflicting_profile_memory() -> None:
    service = MemoryInjectionService()
    profile_value = update_profile_value(
        existing_value=None,
        dimension="accommodation",
        signal_definitions=[signal_definition("quiet_hotel")],
        source_text="酒店尽量安静",
        session_id="session-1",
        updated_at="2026-01-01T00:00:00+00:00",
    )

    result = service.select(
        long_term_memory=[
            {"key": "profile:accommodation", "value": profile_value, "scope": "user_profile"},
        ],
        structured_constraints={
            "destination": "杭州",
            "days": 3,
            "budget": 3000,
            "pace": "balanced",
            "preferences": ["lively_hotel"],
        },
        user_input="帮我规划杭州三日游，酒店热闹一点",
    )

    assert result["relevant_long_term_memory"] == []
    assert result["suppressed_memory"]
    assert "冲突" in result["suppressed_memory"][0]["reason"]
