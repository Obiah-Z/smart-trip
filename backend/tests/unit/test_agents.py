from app.agents.executor_agent import ExecutorAgent
from app.agents.planner_agent import PlannerAgent
from app.agents.retriever_agent import RetrieverAgent
from app.agents.reviewer_agent import ReviewerAgent


def test_planner_agent_builds_task_projection() -> None:
    result = PlannerAgent().run(
        constraints={
            "destination": "杭州",
            "days": 3,
            "budget": 3000,
            "pace": "relaxed",
            "preferences": ["quiet_hotel"],
        },
        memory_context={"relevant_long_term_memory": [{"key": "hotel_style", "value": "quiet"}]},
        task_profile={"task_type": "travel_planning", "needs_multi_agent": True},
    )

    assert result.name == "planner_agent"
    assert "杭州" in result.summary
    assert result.payload["constraints"]["destination"] == "杭州"
    assert result.payload["memory_highlights"] == [{"key": "hotel_style", "value": "quiet"}]
    assert "structured_constraints" in result.payload["shared_state_projection"]


def test_retriever_agent_summarizes_rag_and_tools() -> None:
    result = RetrieverAgent().run(
        retrieval_context={
            "injected_knowledge": ["西湖适合轻松游览"],
            "retrieved_documents": [
                {
                    "id": "doc-1",
                    "topic": "classic",
                    "score": 0.91,
                    "lexical_overlap": 3,
                    "preference_bonus": 1,
                }
            ],
        },
        tool_results=[{"tool_name": "weather.lookup"}, {"tool_name": "route.plan"}],
    )

    assert result.name == "retriever_agent"
    assert result.payload["knowledge"] == ["西湖适合轻松游览"]
    assert result.payload["tools"] == ["weather.lookup", "route.plan"]
    assert result.payload["rerank_trace"][0]["id"] == "doc-1"


def test_executor_agent_builds_final_plan_from_tool_results() -> None:
    constraints = {
        "destination": "杭州",
        "days": 3,
        "budget": 3000,
        "pace": "relaxed",
        "preferences": ["quiet_hotel", "local_food"],
        "budget_policy": None,
        "target_budget": 3000,
    }
    tool_results = [
        {
            "tool_name": "route.plan",
            "provider": "mock",
            "output": {
                "days": [
                    {"day": 1, "theme": "西湖慢游", "area": "西湖", "activities": ["西湖", "知味观"]},
                    {"day": 2, "theme": "寺院文化", "area": "灵隐", "activities": ["灵隐寺"]},
                    {"day": 3, "theme": "城市散步", "area": "湖滨", "activities": ["湖滨步行街"]},
                ]
            },
        },
        {
            "tool_name": "hotel.search",
            "provider": "mock",
            "output": {
                "nightly_budget": 600,
                "hotels": [
                    {
                        "name": "西湖静居酒店",
                        "area": "西湖",
                        "pricePerNight": 500,
                        "quiet": True,
                        "tags": ["quiet_hotel"],
                        "rating": 4.8,
                    }
                ],
            },
        },
        {
            "tool_name": "weather.lookup",
            "provider": "mock",
            "output": {"summary": "多云 22-28℃", "advice": "适合步行"},
        },
        {
            "tool_name": "attraction.search",
            "provider": "mock",
            "output": {
                "attractions": [
                    {
                        "name": "西湖",
                        "area": "西湖",
                        "type": "nature",
                        "tags": ["classic"],
                        "cost": 0,
                        "durationHours": 2,
                    },
                    {
                        "name": "知味观",
                        "area": "西湖",
                        "type": "food",
                        "tags": ["food", "local_food"],
                        "cost": 80,
                        "durationHours": 1,
                    },
                ]
            },
        },
    ]

    result = ExecutorAgent().run(
        constraints=constraints,
        tool_results=tool_results,
        planner_payload={"task_breakdown": []},
        retrieval_context={"retrieved_documents": [], "injected_knowledge": []},
    )

    assert result.name == "executor_agent"
    assert result.payload["summary"]["destinationCity"] == "杭州"
    assert result.payload["summary"]["days"] == 3
    assert result.payload["hotelRecommendation"][0]["name"] == "西湖静居酒店"
    assert result.payload["foodRecommendations"][0]["name"] == "知味观"
    assert result.payload["dailyGuide"][0]["paceLabel"] == "轻松"
    assert result.payload["weather"][0]["summary"] == "多云 22-28℃"


def test_reviewer_agent_uses_audit_result_when_available() -> None:
    result = ReviewerAgent().run(
        constraints={"budget": 3000, "pace": "relaxed", "days": 3},
        executor_payload={"summary": {"totalBudget": 2600}},
        tool_results=[
            {
                "tool_name": "weather.lookup",
                "output": {"summary": "多云"},
            },
            {
                "tool_name": "itinerary.audit",
                "output": {
                    "safe_to_present": True,
                    "summary": "审计通过",
                    "audit_status": "passed",
                    "passed_checks": [{"name": "budget_within_limit", "passed": True}],
                    "issues": [],
                    "warnings": [],
                    "recommendations": ["保持当前安排"],
                },
            },
        ],
    )

    assert result.name == "reviewer_agent"
    assert result.summary == "审计通过"
    assert result.payload["final_status"] == "approved"
    assert result.payload["weather_summary"] == "多云"
    assert result.payload["recommendations"] == ["保持当前安排"]
