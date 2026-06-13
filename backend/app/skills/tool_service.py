from __future__ import annotations

from typing import Any

from app.skills.skill_registry import SkillDefinition, SkillRegistry
from app.skills.skill_script_runner import SkillScriptRunner


class ToolService:
    """把业务侧 Tool Calling 语义映射到本地 Skill 执行。

    Workflow 不直接拼 Skill payload，而是通过这里根据 Skill 的 input_schema 和已有工具结果
    生成输入，保证 route.plan、budget.optimize、itinerary.audit 等链式 Skill 能拿到前序输出。
    """

    def __init__(self, skill_registry: SkillRegistry, script_runner: SkillScriptRunner) -> None:
        self._skill_registry = skill_registry
        self._script_runner = script_runner

    def list_skill_definitions(self) -> list[SkillDefinition]:
        return self._skill_registry.all()

    def list_skills(self) -> list[dict[str, Any]]:
        return self._skill_registry.list_skills()

    def run_skill(self, *, skill_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """执行一个 Skill，并统一封装为 tool_result。"""
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
        """根据 Skill input_schema 从约束和前序 tool_results 中组装 payload。"""
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
                continue
            if field_name == "hotel_options":
                hotel_result = self._find_tool_result(tool_results=tool_results, tool_name="hotel.search")
                payload[field_name] = hotel_result["output"].get("hotels", []) if hotel_result is not None else []
                continue
            if field_name == "route_days":
                route_result = self._find_tool_result(tool_results=tool_results, tool_name="route.plan")
                payload[field_name] = route_result["output"].get("days", []) if route_result is not None else []
                continue
            if field_name == "weather":
                weather_result = self._find_tool_result(tool_results=tool_results, tool_name="weather.lookup")
                payload[field_name] = weather_result["output"] if weather_result is not None else {}
                continue
            if field_name == "budget_optimization":
                budget_result = self._find_tool_result(tool_results=tool_results, tool_name="budget.optimize")
                payload[field_name] = budget_result["output"] if budget_result is not None else {}
                continue

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

    def budget_optimize(
        self,
        *,
        destination: str,
        days: int,
        budget: int,
        target_budget: int | None,
        budget_policy: str | None,
        pace: str,
        preferences: list[str],
        hotel_options: list[dict[str, Any]],
        route_days: list[dict[str, Any]],
        attraction_items: list[dict[str, Any]],
    ) -> dict[str, object]:
        return self.run_skill(
            skill_id="budget.optimize",
            payload={
                "destination": destination,
                "days": days,
                "budget": budget,
                "target_budget": target_budget,
                "budget_policy": budget_policy,
                "pace": pace,
                "preferences": preferences,
                "hotel_options": hotel_options,
                "route_days": route_days,
                "attraction_items": attraction_items,
            },
        )

    def itinerary_audit(
        self,
        *,
        destination: str,
        days: int,
        budget: int,
        pace: str,
        preferences: list[str],
        excluded_attractions: list[str],
        route_days: list[dict[str, Any]],
        hotel_options: list[dict[str, Any]],
        weather: dict[str, Any],
        budget_optimization: dict[str, Any],
    ) -> dict[str, object]:
        return self.run_skill(
            skill_id="itinerary.audit",
            payload={
                "destination": destination,
                "days": days,
                "budget": budget,
                "pace": pace,
                "preferences": preferences,
                "excluded_attractions": excluded_attractions,
                "route_days": route_days,
                "hotel_options": hotel_options,
                "weather": weather,
                "budget_optimization": budget_optimization,
            },
        )

    def _find_tool_result(self, *, tool_results: list[dict[str, Any]], tool_name: str) -> dict[str, Any] | None:
        """查找链式 Skill 所依赖的前序工具结果。"""
        return next((item for item in tool_results if item["tool_name"] == tool_name), None)
