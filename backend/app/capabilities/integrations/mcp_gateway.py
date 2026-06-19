from __future__ import annotations

from typing import Any

from app.capabilities.mock.travel_engine import (
    load_travel_data,
    plan_route,
    select_attractions,
    select_hotels,
    weather_lookup,
)


class MockMCPGateway:
    def __init__(self) -> None:
        self._data = load_travel_data()

    def invoke(self, *, skill_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        destination = payload.get("destination", "")

        if skill_id == "weather.lookup":
            return weather_lookup(data=self._data, destination=destination)

        if skill_id == "attraction.search":
            return select_attractions(
                data=self._data,
                destination=destination,
                preferences=payload.get("preferences", []),
                days=int(payload.get("days", 3)),
                pace=str(payload.get("pace", "balanced")),
                excluded_attractions=payload.get("excluded_attractions", []) or [],
            )

        if skill_id == "hotel.search":
            return select_hotels(
                data=self._data,
                destination=destination,
                budget=int(payload.get("budget", 3000)),
                preferences=payload.get("preferences", []),
            )

        if skill_id == "route.plan":
            return plan_route(
                destination=destination,
                days=int(payload.get("days", 3)),
                pace=str(payload.get("pace", "balanced")),
                attraction_items=payload.get("attraction_items", []) or [],
                attraction_names=payload.get("attraction_names", []) or [f"{destination} 城市漫步"],
                excluded_attractions=payload.get("excluded_attractions", []) or [],
            )

        if skill_id == "knowledge.snapshot":
            return {
                "source": "mock_mcp",
                "status": "ok",
                "capability": "travel_knowledge_bridge",
            }

        raise KeyError(f"unsupported skill_id: {skill_id}")
