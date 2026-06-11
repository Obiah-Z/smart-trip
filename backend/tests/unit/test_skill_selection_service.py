from app.config.settings import Settings
from app.llm.openai_client import OpenAIPlannerClient
from app.skills.skill_registry import SkillRegistry
from app.skills.skill_selection_service import SkillSelectionService


def test_skill_selection_service_uses_heuristics_for_itinerary_request() -> None:
    service = SkillSelectionService(
        openai_client=OpenAIPlannerClient(
            Settings(
                openai_mode="mock",
                openai_base_url="https://example.com/v1",
                openai_api_key="",
                openai_model="gpt-5.4",
            )
        )
    )
    registry = SkillRegistry()

    selected = service.select(
        user_input="帮我规划北京三日游，预算4000，想看文化景点，也想吃美食，酒店安静一点",
        structured_constraints={
            "destination": "北京",
            "days": 3,
            "budget": 4000,
            "pace": "relaxed",
            "preferences": ["culture", "food", "quiet_hotel"],
        },
        available_skills=registry.all(),
    )

    selected_ids = [item.skill_id for item in selected]
    assert "route.plan" in selected_ids
    assert "attraction.search" in selected_ids
    assert "hotel.search" in selected_ids
    assert "knowledge.snapshot" not in selected_ids


def test_skill_selection_service_adds_hotel_search_for_multi_day_itinerary_without_explicit_hotel_or_budget() -> None:
    service = SkillSelectionService(
        openai_client=OpenAIPlannerClient(
            Settings(
                openai_mode="mock",
                openai_base_url="https://example.com/v1",
                openai_api_key="",
                openai_model="gpt-5.4",
            )
        )
    )
    registry = SkillRegistry()

    selected = service.select(
        user_input="帮我规划一个杭州三日游，想吃本地特色",
        structured_constraints={
            "destination": "杭州",
            "days": 3,
            "budget": 0,
            "pace": "balanced",
            "preferences": ["local_food"],
        },
        available_skills=registry.all(),
    )

    selected_ids = [item.skill_id for item in selected]
    assert "route.plan" in selected_ids
    assert "attraction.search" in selected_ids
    assert "hotel.search" in selected_ids


def test_skill_selection_service_selects_knowledge_snapshot_for_system_query() -> None:
    service = SkillSelectionService(
        openai_client=OpenAIPlannerClient(
            Settings(
                openai_mode="mock",
                openai_base_url="https://example.com/v1",
                openai_api_key="",
                openai_model="gpt-5.4",
            )
        )
    )
    registry = SkillRegistry()

    selected = service.select(
        user_input="看看当前系统的 MCP 能力和知识桥接状态",
        structured_constraints={
            "destination": "北京",
            "days": 1,
            "budget": 3000,
            "pace": "balanced",
            "preferences": ["food"],
        },
        available_skills=registry.all(),
    )

    selected_ids = [item.skill_id for item in selected]
    assert "knowledge.snapshot" in selected_ids


def test_skill_selection_service_does_not_select_route_plan_for_simple_attraction_query() -> None:
    service = SkillSelectionService(
        openai_client=OpenAIPlannerClient(
            Settings(
                openai_mode="mock",
                openai_base_url="https://example.com/v1",
                openai_api_key="",
                openai_model="gpt-5.4",
            )
        )
    )
    registry = SkillRegistry()

    selected = service.select(
        user_input="杭州有哪些推荐的景点",
        structured_constraints={
            "destination": "杭州",
            "days": 1,
            "budget": 0,
            "pace": "balanced",
            "preferences": [],
        },
        available_skills=registry.all(),
    )

    selected_ids = [item.skill_id for item in selected]
    assert "attraction.search" in selected_ids
    assert "route.plan" not in selected_ids
    assert "weather.lookup" not in selected_ids


def test_skill_selection_service_selects_only_weather_for_simple_weather_query() -> None:
    service = SkillSelectionService(
        openai_client=OpenAIPlannerClient(
            Settings(
                openai_mode="mock",
                openai_base_url="https://example.com/v1",
                openai_api_key="",
                openai_model="gpt-5.4",
            )
        )
    )
    registry = SkillRegistry()

    selected = service.select(
        user_input="杭州今天天气如何",
        structured_constraints={
            "destination": "杭州",
            "days": 1,
            "budget": 0,
            "pace": "balanced",
            "preferences": [],
        },
        available_skills=registry.all(),
    )

    selected_ids = [item.skill_id for item in selected]
    assert selected_ids == ["weather.lookup"]


def test_skill_selection_service_keeps_full_planning_chain_for_followup_replan() -> None:
    service = SkillSelectionService(
        openai_client=OpenAIPlannerClient(
            Settings(
                openai_mode="mock",
                openai_base_url="https://example.com/v1",
                openai_api_key="",
                openai_model="gpt-5.4",
            )
        )
    )
    registry = SkillRegistry()

    selected = service.select(
        user_input="帮我把预算提升到10000，主要是提升住宿舒适度",
        structured_constraints={
            "destination": "杭州",
            "days": 3,
            "budget": 10000,
            "pace": "relaxed",
            "preferences": ["quiet_hotel", "local_food", "comfortable_hotel"],
            "_followup_replan": True,
        },
        available_skills=registry.all(),
    )

    selected_ids = [item.skill_id for item in selected]
    assert "route.plan" in selected_ids
    assert "attraction.search" in selected_ids
    assert "hotel.search" in selected_ids
    assert "weather.lookup" in selected_ids


def test_skill_selection_service_treats_family_consulting_query_as_lightweight() -> None:
    service = SkillSelectionService(
        openai_client=OpenAIPlannerClient(
            Settings(
                openai_mode="mock",
                openai_base_url="https://example.com/v1",
                openai_api_key="",
                openai_model="gpt-5.4",
            )
        )
    )
    registry = SkillRegistry()

    selected = service.select(
        user_input="三亚有哪些适合亲子出游的景点",
        structured_constraints={
            "destination": "三亚",
            "days": 1,
            "budget": 0,
            "pace": "balanced",
            "preferences": ["family"],
        },
        available_skills=registry.all(),
    )

    selected_ids = [item.skill_id for item in selected]
    assert "attraction.search" in selected_ids
    assert "route.plan" not in selected_ids
    assert "weather.lookup" not in selected_ids


def test_skill_selection_service_uses_attraction_query_for_rainy_day_family_consulting() -> None:
    service = SkillSelectionService(
        openai_client=OpenAIPlannerClient(
            Settings(
                openai_mode="mock",
                openai_base_url="https://example.com/v1",
                openai_api_key="",
                openai_model="gpt-5.4",
            )
        )
    )
    registry = SkillRegistry()

    selected = service.select(
        user_input="上海下雨天适合带娃去哪玩",
        structured_constraints={
            "destination": "上海",
            "days": 1,
            "budget": 0,
            "pace": "balanced",
            "preferences": ["family", "rainy_day"],
        },
        available_skills=registry.all(),
    )

    selected_ids = [item.skill_id for item in selected]
    assert selected_ids == ["attraction.search"]
