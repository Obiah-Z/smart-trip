import os

import pytest
from fastapi.testclient import TestClient

os.environ["OPENAI_MODE"] = "mock"

from app.db import repositories as repository_module
from app.db import sqlite as sqlite_store
from app.main import app


pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "smart_trip.sqlite3"
    memory_path = tmp_path / "memory_store.json"
    session_runs_path = tmp_path / "session_runs_store.json"

    monkeypatch.setattr(sqlite_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(sqlite_store, "DB_PATH", db_path)
    monkeypatch.setattr(sqlite_store, "MEMORY_PATH", memory_path)
    monkeypatch.setattr(sqlite_store, "SESSION_RUNS_PATH", session_runs_path)
    monkeypatch.setattr(repository_module, "MEMORY_PATH", memory_path)
    monkeypatch.setattr(repository_module, "SESSION_RUNS_PATH", session_runs_path)
    sqlite_store.init_db()


def post_plan(client: TestClient, *, user_id: str, message: str, session_id: str | None = None) -> dict:
    payload = {"user_id": user_id, "message": message}
    if session_id:
        payload["session_id"] = session_id
    response = client.post("/api/demo/plan", json=payload)
    assert response.status_code == 200
    return response.json()


def test_plan_api_generates_core_itinerary_pipeline() -> None:
    client = TestClient(app)

    payload = post_plan(
        client,
        user_id="smoke-plan-user",
        message="帮我规划一个杭州三日游，预算3000，节奏轻松一点，酒店尽量安静",
    )

    assert payload["task_profile"]["task_type"] == "travel_planning"
    assert payload["structured_constraints"]["destination"] == "杭州"
    assert payload["structured_constraints"]["days"] == 3
    assert payload["final_plan"]["summary"]["destinationCity"] == "杭州"
    assert payload["final_plan"]["summary"]["days"] == 3
    assert any(item["skill_id"] == "route.plan" for item in payload["selected_skills"])
    runtime_context = payload["assembled_context"]["runtime_context"]
    assert runtime_context["workflow_engine"] == "langgraph"
    trace_nodes = [item["node"] for item in runtime_context["workflow_trace"]]
    assert trace_nodes == [
        "prepare_request",
        "resolve_constraints",
        "load_memory",
        "retrieve_knowledge",
        "run_skills",
        "assemble_context",
        "run_agents",
        "review_plan",
        "enrich_and_summarize",
        "persist_planning_response",
    ]


def test_plan_api_weather_query_bypasses_route_planning() -> None:
    client = TestClient(app)

    payload = post_plan(
        client,
        user_id="smoke-weather-user",
        message="杭州今天天气如何",
    )

    selected_ids = [item["skill_id"] for item in payload["selected_skills"]]
    assert payload["task_profile"]["task_type"] == "travel_consulting"
    assert selected_ids == ["weather.lookup"]
    assert payload["agent_outputs"] == []
    assert payload["final_plan"]["consultingType"] == "weather"
    trace_nodes = [
        item["node"]
        for item in payload["assembled_context"]["runtime_context"]["workflow_trace"]
    ]
    assert "build_consulting_response" in trace_nodes
    assert "assemble_context" not in trace_nodes
    assert "run_agents" not in trace_nodes


def test_plan_api_missing_destination_requests_clarification() -> None:
    client = TestClient(app)

    payload = post_plan(
        client,
        user_id="smoke-missing-destination-user",
        message="帮我规划三天行程",
    )

    assert payload["structured_constraints"]["destination"] is None
    assert payload["task_profile"]["task_type"] == "travel_consulting"
    assert payload["final_plan"]["consultingType"] == "clarification"
    assert payload["final_plan"]["missingFields"] == ["destination"]
    assert payload["selected_skills"] == []
    trace_nodes = [
        item["node"]
        for item in payload["assembled_context"]["runtime_context"]["workflow_trace"]
    ]
    assert trace_nodes == [
        "prepare_request",
        "resolve_constraints",
        "build_clarification_response",
    ]


def test_plan_api_resumes_after_days_clarification() -> None:
    client = TestClient(app)

    first_payload = post_plan(
        client,
        user_id="smoke-days-clarification-user",
        message="帮我规划杭州行程，酒店尽量安静",
    )
    assert first_payload["final_plan"]["missingFields"] == ["days"]

    payload = post_plan(
        client,
        user_id="smoke-days-clarification-user",
        session_id=first_payload["session_id"],
        message="3天",
    )

    assert payload["session_context"]["session_found"] is True
    assert payload["structured_constraints"]["destination"] == "杭州"
    assert payload["structured_constraints"]["days"] == 3
    assert payload["task_profile"]["task_type"] == "travel_planning"
    assert payload["final_plan"]["summary"]["days"] == 3


def test_plan_api_followup_budget_update_reuses_session() -> None:
    client = TestClient(app)

    first_payload = post_plan(
        client,
        user_id="smoke-followup-budget-user",
        message="帮我规划一个杭州三日游，预算3000，节奏轻松一点，酒店尽量安静，想吃本地特色",
    )
    payload = post_plan(
        client,
        user_id="smoke-followup-budget-user",
        session_id=first_payload["session_id"],
        message="帮我把预算提升到10000，主要是提升住宿舒适度",
    )

    assert payload["session_id"] == first_payload["session_id"]
    assert payload["structured_constraints"]["destination"] == "杭州"
    assert payload["structured_constraints"]["days"] == 3
    assert payload["structured_constraints"]["budget"] == 10000
    assert "comfortable_hotel" in payload["structured_constraints"]["preferences"]
    assert payload["task_profile"]["task_type"] == "travel_planning"


def test_plan_api_followup_excluded_spot_replans_without_reasking_days() -> None:
    client = TestClient(app)

    first_payload = post_plan(
        client,
        user_id="smoke-excluded-spot-user",
        message="帮我规划一个北京5日游，预算5000，节奏轻松一点，酒店尽量安静",
    )
    payload = post_plan(
        client,
        user_id="smoke-excluded-spot-user",
        session_id=first_payload["session_id"],
        message="不想要去逛故宫",
    )

    assert payload["session_context"]["session_found"] is True
    assert payload["structured_constraints"]["destination"] == "北京"
    assert payload["structured_constraints"]["days"] == 5
    assert payload["structured_constraints"]["excluded_attractions"] == ["故宫"]
    assert payload["task_profile"]["task_type"] == "travel_planning"
    assert not payload["final_plan"].get("missingFields")

    all_activities = [activity for day in payload["final_plan"]["days"] for activity in day.get("activities", [])]
    assert "故宫" not in all_activities


def test_plan_api_langgraph_repair_node_cleans_excluded_spot_from_final_plan() -> None:
    client = TestClient(app)

    first_payload = post_plan(
        client,
        user_id="smoke-langgraph-repair-user",
        message="帮我规划一个杭州三日游，预算3000，节奏轻松一点，酒店尽量安静",
    )
    payload = post_plan(
        client,
        user_id="smoke-langgraph-repair-user",
        session_id=first_payload["session_id"],
        message="不想去西湖",
    )

    trace_nodes = [
        item["node"]
        for item in payload["assembled_context"]["runtime_context"]["workflow_trace"]
    ]
    all_activities = [
        activity
        for day in payload["final_plan"]["days"]
        for activity in day.get("activities", [])
    ]

    assert "repair_plan" in trace_nodes
    assert payload["final_plan"]["workflowRepair"]["applied"] is True
    assert "西湖" not in all_activities
    assert "断桥" not in all_activities
    assert payload["final_plan"]["workflowRepair"]["remainingIssues"] == []
