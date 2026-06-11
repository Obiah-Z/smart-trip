from __future__ import annotations

from typing import Any

from app.skills.skill_registry import SkillDefinition, SkillRegistry
from app.skills.skill_script_runner import SkillScriptRunner


class ToolService:
    def __init__(self, skill_registry: SkillRegistry, script_runner: SkillScriptRunner) -> None:
        self._skill_registry = skill_registry
        self._script_runner = script_runner

    def list_skill_definitions(self) -> list[SkillDefinition]:
        return self._skill_registry.all()

    def list_skills(self) -> list[dict[str, Any]]:
        return self._skill_registry.list_skills()

    def run_skill(self, *, skill_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        definition = self._skill_registry.get(skill_id)
        execution = self._script_runner.run(definition=definition, payload=payload)
        return {
            "tool_name": skill_id,
            "display_name": definition.display_name,
            "provider": definition.provider,
            "input": payload,
            "output": execution["output"],
            "sandbox": execution["sandbox"],
        }

    def build_payload(
        self,
        *,
        skill_id: str,
        structured_constraints: dict[str, Any],
        tool_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        definition = self._skill_registry.get(skill_id)
        payload: dict[str, Any] = {}

        for field_name in definition.input_schema:
            if field_name == "days":
                payload[field_name] = structured_constraints.get("days") or 3
                continue
            if field_name == "excluded_attractions":
                payload[field_name] = (
                    structured_constraints.get("expanded_excluded_attractions")
                    or structured_constraints.get("excluded_attractions", [])
                )
                continue
            if field_name in structured_constraints:
                payload[field_name] = structured_constraints[field_name]
                continue
            if field_name == "pace":
                payload[field_name] = structured_constraints.get("pace", "balanced")
                continue
            if field_name == "attraction_names":
                attraction_result = self._find_tool_result(tool_results=tool_results, tool_name="attraction.search")
                attraction_names = []
                if attraction_result is not None:
                    attraction_names = [
                        item["name"] for item in attraction_result["output"].get("attractions", []) if "name" in item
                    ]
                payload[field_name] = attraction_names or [f"{structured_constraints['destination']} 城市漫步"]
                continue
            if field_name == "attraction_items":
                attraction_result = self._find_tool_result(tool_results=tool_results, tool_name="attraction.search")
                payload[field_name] = attraction_result["output"].get("attractions", []) if attraction_result is not None else []

        if "destination" in definition.input_schema and "destination" not in payload:
            payload["destination"] = structured_constraints["destination"]
        return payload

    def weather_lookup(self, *, destination: str) -> dict[str, object]:
        return self.run_skill(skill_id="weather.lookup", payload={"destination": destination})

    def attraction_search(
        self,
        *,
        destination: str,
        preferences: list[str],
        days: int = 3,
        pace: str = "balanced",
        excluded_attractions: list[str] | None = None,
    ) -> dict[str, object]:
        return self.run_skill(
            skill_id="attraction.search",
            payload={
                "destination": destination,
                "preferences": preferences,
                "days": days,
                "pace": pace,
                "excluded_attractions": excluded_attractions or [],
            },
        )

    def hotel_search(self, *, destination: str, budget: int, preferences: list[str]) -> dict[str, object]:
        return self.run_skill(
            skill_id="hotel.search",
            payload={"destination": destination, "budget": budget, "preferences": preferences},
        )

    def route_planner(
        self,
        *,
        destination: str,
        days: int,
        pace: str,
        attraction_names: list[str],
        attraction_items: list[dict[str, Any]] | None = None,
        excluded_attractions: list[str] | None = None,
    ) -> dict[str, object]:
        safe_attraction_names = attraction_names or [f"{destination} 城市漫步"]
        return self.run_skill(
            skill_id="route.plan",
            payload={
                "destination": destination,
                "days": days,
                "pace": pace,
                "attraction_names": safe_attraction_names,
                "attraction_items": attraction_items or [],
                "excluded_attractions": excluded_attractions or [],
            },
        )

    def knowledge_snapshot(self, *, destination: str) -> dict[str, object]:
        return self.run_skill(skill_id="knowledge.snapshot", payload={"destination": destination})

    def _find_tool_result(self, *, tool_results: list[dict[str, Any]], tool_name: str) -> dict[str, Any] | None:
        return next((item for item in tool_results if item["tool_name"] == tool_name), None)
