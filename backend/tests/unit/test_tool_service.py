import pytest

from app.skills.skill_registry import SkillRegistry
from app.skills.skill_script_runner import SkillScriptRunner
from app.skills.tool_service import ToolService


def test_tool_service_returns_weather_and_hotels() -> None:
    service = ToolService(skill_registry=SkillRegistry(), script_runner=SkillScriptRunner())

    weather = service.weather_lookup(destination="杭州")
    hotels = service.hotel_search(destination="杭州", budget=3000, preferences=["quiet_hotel"])

    assert weather["output"]["summary"]
    assert hotels["output"]["hotels"]
    assert weather["sandbox"]["mode"] == "process_sandbox"


def test_tool_service_supports_new_mock_city_and_preference_filter() -> None:
    service = ToolService(skill_registry=SkillRegistry(), script_runner=SkillScriptRunner())

    weather = service.weather_lookup(destination="重庆")
    attractions = service.attraction_search(destination="西安", preferences=["museum", "culture"])
    hotels = service.hotel_search(destination="广州", budget=6000, preferences=["comfortable_hotel"])

    assert "湿度" in weather["output"]["advice"] or "带伞" in weather["output"]["advice"]
    assert attractions["output"]["attractions"]
    assert any(item["type"] in {"museum", "culture"} for item in attractions["output"]["attractions"])
    assert hotels["output"]["hotels"]
    assert hotels["output"]["hotels"][0]["rating"] >= 4.6


def test_tool_service_supports_xiamen_and_nanjing_mock_data() -> None:
    service = ToolService(skill_registry=SkillRegistry(), script_runner=SkillScriptRunner())

    xiamen_weather = service.weather_lookup(destination="厦门")
    xiamen_attractions = service.attraction_search(destination="厦门", preferences=["citywalk", "nature"])
    nanjing_hotels = service.hotel_search(destination="南京", budget=5000, preferences=["museum", "quiet_hotel"])

    assert "海边" in xiamen_weather["output"]["advice"] or "海风" in xiamen_weather["output"]["summary"]
    assert any(item["type"] in {"citywalk", "nature"} for item in xiamen_attractions["output"]["attractions"])
    assert nanjing_hotels["output"]["hotels"]
    assert all(item["quiet"] is True for item in nanjing_hotels["output"]["hotels"])


def test_tool_service_supports_shenzhen_expanded_mock_data() -> None:
    service = ToolService(skill_registry=SkillRegistry(), script_runner=SkillScriptRunner())

    shenzhen_weather = service.weather_lookup(destination="深圳")
    shenzhen_attractions = service.attraction_search(
        destination="深圳",
        preferences=["citywalk", "nature", "comfortable_hotel"],
        days=4,
        pace="relaxed",
    )
    shenzhen_hotels = service.hotel_search(destination="深圳", budget=6000, preferences=["quiet_hotel", "comfortable_hotel"])

    assert "海边" in shenzhen_weather["output"]["advice"] or "海风" in shenzhen_weather["output"]["summary"]
    assert shenzhen_attractions["output"]["attractions"]
    assert any(item["type"] in {"citywalk", "nature"} for item in shenzhen_attractions["output"]["attractions"])
    assert shenzhen_hotels["output"]["hotels"]
    assert shenzhen_hotels["output"]["hotels"][0]["comfortScore"] >= 86


def test_tool_service_builds_varied_hangzhou_five_day_route_from_richer_mock_data() -> None:
    service = ToolService(skill_registry=SkillRegistry(), script_runner=SkillScriptRunner())

    attractions = service.attraction_search(
        destination="杭州",
        preferences=["local_food", "quiet_hotel"],
        days=5,
        pace="relaxed",
    )
    selected_items = attractions["output"]["attractions"]
    route = service.route_planner(
        destination="杭州",
        days=5,
        pace="relaxed",
        attraction_names=[item["name"] for item in selected_items],
        attraction_items=selected_items,
    )

    planned_days = route["output"]["days"]
    all_activities = [activity for day in planned_days for activity in day.get("activities", [])]

    assert len(planned_days) == 5
    assert len(set(all_activities)) >= 5
    assert any(name in all_activities for name in {"九溪烟树", "西溪湿地", "小河直街", "良渚博物院"})


def test_tool_service_prioritizes_family_hotels_for_sanya() -> None:
    service = ToolService(skill_registry=SkillRegistry(), script_runner=SkillScriptRunner())

    hotels = service.hotel_search(destination="三亚", budget=9000, preferences=["family", "quiet_hotel", "comfortable_hotel"])

    assert hotels["output"]["hotels"]
    assert "family_friendly" in hotels["output"]["hotels"][0]["tags"]
    assert hotels["output"]["hotels"][0]["quiet"] is True


def test_tool_service_prioritizes_indoor_attractions_for_rainy_day_queries() -> None:
    service = ToolService(skill_registry=SkillRegistry(), script_runner=SkillScriptRunner())

    attractions = service.attraction_search(
        destination="杭州",
        preferences=["rainy_day", "family"],
        days=2,
        pace="relaxed",
    )

    selected_names = [item["name"] for item in attractions["output"]["attractions"]]

    assert selected_names
    assert any(name in selected_names for name in {"中国茶叶博物馆", "良渚博物院"})
    assert attractions["output"]["attractions"][0].get("indoor") is True


def test_tool_service_exposes_skill_metadata() -> None:
    service = ToolService(skill_registry=SkillRegistry(), script_runner=SkillScriptRunner())

    skills = service.list_skills()

    assert skills
    assert any(item["skill_id"] == "knowledge.snapshot" for item in skills)


@pytest.mark.slow
def test_tool_service_sandbox_blocks_timeout_skill() -> None:
    service = ToolService(skill_registry=SkillRegistry(), script_runner=SkillScriptRunner())

    try:
        service.run_skill(skill_id="sandbox.timeout_test", payload={})
    except RuntimeError as exc:
        assert "timed out" in str(exc)
    else:
        raise AssertionError("expected sandbox timeout to raise")


def test_tool_service_sandbox_blocks_write_outside_allowed_roots() -> None:
    service = ToolService(skill_registry=SkillRegistry(), script_runner=SkillScriptRunner())

    try:
        service.run_skill(skill_id="sandbox.write_test", payload={})
    except RuntimeError as exc:
        assert "blocks writing outside allowed roots" in str(exc)
    else:
        raise AssertionError("expected sandbox write restriction to raise")
