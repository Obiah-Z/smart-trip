from app.skills.skill_registry import SkillRegistry


def test_skill_registry_lists_expected_skills() -> None:
    registry = SkillRegistry()

    skills = registry.list_skills()

    assert skills
    assert any(item["skill_id"] == "weather.lookup" for item in skills)
    assert any(item["skill_id"] == "route.plan" for item in skills)
    route_plan = next(item for item in skills if item["skill_id"] == "route.plan")
    assert route_plan["depends_on"] == ["attraction.search"]
    assert route_plan["script_path"].endswith("/skills/public/route-plan/scripts/run.py")
    assert route_plan["sandbox_policy"]["allow_network"] is False
