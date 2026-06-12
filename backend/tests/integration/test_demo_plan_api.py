import os

import pytest
from fastapi.testclient import TestClient

os.environ["OPENAI_MODE"] = "mock"

from app.db import repositories as repository_module
from app.db import sqlite as sqlite_store
from app.main import app


pytestmark = [pytest.mark.integration, pytest.mark.slow]


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


def test_demo_plan_api_returns_pipeline() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-user",
            "message": "帮我规划一个杭州三日游，预算3000，节奏轻松一点，酒店尽量安静",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_profile"]["task_type"] == "travel_planning"
    assert payload["session_context"]["session_found"] is False
    assert payload["structured_constraints"]["destination"] == "杭州"
    assert payload["available_skills"]
    assert payload["selected_skills"]
    assert payload["memory_updates"]
    assert payload["tool_results"]
    assert payload["agent_outputs"]
    assert payload["final_plan"]["summary"]["destinationCity"] == "杭州"
    assert any(item["skill_id"] == "route.plan" for item in payload["selected_skills"])


def test_demo_plan_api_handles_negative_preferences() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-negative-user",
            "message": "帮我规划一个杭州三日游，预算3000，节奏紧张一点，酒店尽量嘈杂，不想吃本地特色",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["structured_constraints"]["pace"] == "intensive"
    assert "lively_hotel" in payload["structured_constraints"]["preferences"]
    assert "avoid_local_food" in payload["structured_constraints"]["preferences"]
    assert payload["memory_context"]["relevant_long_term_memory"] is not None
    assert any(item["key"] == "travel_pace" and item["value"] == "intensive" for item in payload["memory_updates"])
    assert all(item["type"] != "food" for item in payload["tool_results"][1]["output"]["attractions"])


def test_demo_plan_api_simple_attraction_query_does_not_trigger_route_plan() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-simple-query-user",
            "message": "杭州有哪些推荐的景点",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_profile"]["task_type"] == "travel_consulting"
    selected_ids = [item["skill_id"] for item in payload["selected_skills"]]
    assert "attraction.search" in selected_ids
    assert "route.plan" not in selected_ids
    assert payload["agent_outputs"] == []
    assert payload["llm_output"]["mode"] == "bypass"
    assert payload["final_plan"]["consultingType"] == "attraction"


def test_demo_plan_api_simple_weather_query_only_triggers_weather_lookup() -> None:
    os.environ["OPENAI_MODE"] = "mock"
    client = TestClient(app)

    response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-weather-query-user",
            "message": "杭州今天天气如何",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    selected_ids = [item["skill_id"] for item in payload["selected_skills"]]
    assert selected_ids == ["weather.lookup"]
    assert payload["agent_outputs"] == []
    assert payload["llm_output"]["mode"] == "bypass"
    assert payload["final_plan"]["consultingType"] == "weather"


def test_demo_plan_api_followup_itinerary_after_weather_query_inherits_session_destination() -> None:
    os.environ["OPENAI_MODE"] = "mock"
    client = TestClient(app)

    first_response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-weather-followup-destination-user",
            "message": "深圳天气怎么样",
        },
    )

    assert first_response.status_code == 200
    first_payload = first_response.json()
    assert first_payload["structured_constraints"]["destination"] == "深圳"
    assert first_payload["final_plan"]["consultingType"] == "weather"

    second_response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-weather-followup-destination-user",
            "session_id": first_payload["session_id"],
            "message": "帮我规划三天行程",
        },
    )

    assert second_response.status_code == 200
    payload = second_response.json()
    assert payload["session_context"]["session_found"] is True
    assert payload["structured_constraints"]["destination"] == "深圳"
    assert payload["structured_constraints"]["days"] == 3
    assert payload["task_profile"]["task_type"] == "travel_planning"
    assert payload["final_plan"]["summary"]["destinationCity"] == "深圳"


def test_demo_plan_api_requests_destination_instead_of_defaulting_to_hangzhou() -> None:
    os.environ["OPENAI_MODE"] = "mock"
    client = TestClient(app)

    response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-missing-destination-user",
            "message": "帮我规划三天行程",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["structured_constraints"]["destination"] is None
    assert payload["task_profile"]["task_type"] == "travel_consulting"
    assert payload["final_plan"]["consultingType"] == "clarification"
    assert payload["final_plan"]["missingFields"] == ["destination"]
    assert "请先告诉我你想去哪个城市" in payload["final_plan"]["consultingAnswer"]
    assert payload["selected_skills"] == []
    assert payload["tool_results"] == []


def test_demo_plan_api_can_resume_planning_after_destination_clarification() -> None:
    os.environ["OPENAI_MODE"] = "mock"
    client = TestClient(app)

    first_response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-clarification-resume-user",
            "message": "帮我规划三天行程",
        },
    )

    assert first_response.status_code == 200
    first_payload = first_response.json()
    assert first_payload["final_plan"]["consultingType"] == "clarification"

    second_response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-clarification-resume-user",
            "session_id": first_payload["session_id"],
            "message": "深圳",
        },
    )

    assert second_response.status_code == 200
    payload = second_response.json()
    assert payload["session_context"]["session_found"] is True
    assert payload["structured_constraints"]["destination"] == "深圳"
    assert payload["structured_constraints"]["days"] == 3
    assert payload["task_profile"]["task_type"] == "travel_planning"
    assert payload["final_plan"]["summary"]["destinationCity"] == "深圳"


def test_demo_plan_api_requests_days_when_planning_destination_without_trip_length() -> None:
    os.environ["OPENAI_MODE"] = "mock"
    client = TestClient(app)

    response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-missing-days-user",
            "message": "帮我规划杭州行程，想吃本地特色，酒店安静一点",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["structured_constraints"]["destination"] == "杭州"
    assert payload["structured_constraints"]["days"] is None
    assert payload["task_profile"]["task_type"] == "travel_consulting"
    assert payload["final_plan"]["consultingType"] == "clarification"
    assert payload["final_plan"]["missingFields"] == ["days"]
    assert "还缺少出行天数" in payload["final_plan"]["consultingAnswer"]
    assert payload["final_plan"]["suggestedReplies"] == ["2天", "3天", "4天", "5天"]
    assert payload["selected_skills"] == []
    assert payload["tool_results"] == []


def test_demo_plan_api_can_resume_planning_after_days_clarification() -> None:
    os.environ["OPENAI_MODE"] = "mock"
    client = TestClient(app)

    first_response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-days-clarification-resume-user",
            "message": "帮我规划杭州行程，酒店尽量安静",
        },
    )

    assert first_response.status_code == 200
    first_payload = first_response.json()
    assert first_payload["final_plan"]["consultingType"] == "clarification"
    assert first_payload["final_plan"]["missingFields"] == ["days"]

    second_response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-days-clarification-resume-user",
            "session_id": first_payload["session_id"],
            "message": "3天",
        },
    )

    assert second_response.status_code == 200
    payload = second_response.json()
    assert payload["session_context"]["session_found"] is True
    assert payload["structured_constraints"]["destination"] == "杭州"
    assert payload["structured_constraints"]["days"] == 3
    assert payload["task_profile"]["task_type"] == "travel_planning"
    assert payload["final_plan"]["summary"]["destinationCity"] == "杭州"
    assert payload["final_plan"]["summary"]["days"] == 3


def test_demo_plan_api_missing_budget_does_not_block_planning() -> None:
    os.environ["OPENAI_MODE"] = "mock"
    client = TestClient(app)

    response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-missing-budget-user",
            "message": "帮我规划一个杭州三日游，节奏轻松一点，想吃本地特色",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["structured_constraints"]["destination"] == "杭州"
    assert payload["structured_constraints"]["days"] == 3
    assert payload["structured_constraints"]["budget"] == 0
    assert payload["task_profile"]["task_type"] == "travel_planning"
    selected_ids = [item["skill_id"] for item in payload["selected_skills"]]
    assert "hotel.search" in selected_ids
    assert payload["final_plan"]["summary"]["destinationCity"] == "杭州"
    assert payload["final_plan"]["summary"]["days"] == 3
    assert payload["final_plan"]["days"]
    assert payload["final_plan"]["hotelRecommendation"]
    assert payload["final_plan"]["budget"]["transport"] >= 0


def test_demo_plan_api_supports_session_history_listing_and_delete() -> None:
    os.environ["OPENAI_MODE"] = "mock"
    client = TestClient(app)

    create_response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-history-user",
            "message": "杭州天气怎么样",
        },
    )

    assert create_response.status_code == 200
    created_payload = create_response.json()
    session_id = created_payload["session_id"]

    list_response = client.get("/api/demo/sessions", params={"user_id": "integration-history-user", "limit": 10})
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert any(item["session_id"] == session_id for item in list_payload)

    matched = next(item for item in list_payload if item["session_id"] == session_id)
    assert matched["destination"] == "杭州"
    assert matched["task_type"] == "travel_consulting"

    delete_response = client.delete(f"/api/demo/session/{session_id}")
    assert delete_response.status_code == 200

    missing_response = client.get(f"/api/demo/session/{session_id}")
    assert missing_response.status_code == 404


def test_demo_plan_api_session_history_prefers_planning_snapshot_over_latest_weather_followup() -> None:
    os.environ["OPENAI_MODE"] = "mock"
    client = TestClient(app)

    first_response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-history-planning-priority-user",
            "message": "帮我规划一个上海三日游，预算4000，节奏轻松一点",
        },
    )

    assert first_response.status_code == 200
    first_payload = first_response.json()
    assert first_payload["task_profile"]["task_type"] == "travel_planning"

    second_response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-history-planning-priority-user",
            "session_id": first_payload["session_id"],
            "message": "上海天气如何",
        },
    )

    assert second_response.status_code == 200
    second_payload = second_response.json()
    assert second_payload["task_profile"]["task_type"] == "travel_consulting"
    assert second_payload["final_plan"]["consultingType"] == "weather"

    list_response = client.get(
        "/api/demo/sessions",
        params={"user_id": "integration-history-planning-priority-user", "limit": 10},
    )
    assert list_response.status_code == 200
    list_payload = list_response.json()
    matched = next(item for item in list_payload if item["session_id"] == first_payload["session_id"])
    assert matched["task_type"] == "travel_planning"
    assert matched["destination"] == "上海"
    assert matched["days"] == 3

    get_response = client.get(f"/api/demo/session/{first_payload['session_id']}")
    assert get_response.status_code == 200
    get_payload = get_response.json()
    assert get_payload["response"]["task_profile"]["task_type"] == "travel_planning"
    assert get_payload["response"]["final_plan"]["summary"]["destinationCity"] == "上海"
    assert get_payload["response"]["final_plan"]["summary"]["days"] == 3


def test_demo_plan_api_followup_budget_update_reuses_session_and_replans() -> None:
    os.environ["OPENAI_MODE"] = "mock"
    client = TestClient(app)

    first_response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-followup-user",
            "message": "帮我规划一个杭州三日游，预算3000，节奏轻松一点，酒店尽量安静，想吃本地特色",
        },
    )

    assert first_response.status_code == 200
    first_payload = first_response.json()

    second_response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-followup-user",
            "session_id": first_payload["session_id"],
            "message": "帮我把预算提升到10000，主要是提升住宿舒适度",
        },
    )

    assert second_response.status_code == 200
    payload = second_response.json()
    assert payload["session_id"] == first_payload["session_id"]
    assert payload["session_context"]["session_found"] is True
    assert payload["task_profile"]["task_type"] == "travel_planning"
    assert payload["structured_constraints"]["destination"] == "杭州"
    assert payload["structured_constraints"]["days"] == 3
    assert payload["structured_constraints"]["budget"] == 10000
    assert payload["structured_constraints"]["pace"] == "relaxed"
    assert "comfortable_hotel" in payload["structured_constraints"]["preferences"]
    selected_ids = [item["skill_id"] for item in payload["selected_skills"]]
    assert "route.plan" in selected_ids
    assert "hotel.search" in selected_ids
    assert payload["final_plan"]["summary"]["destinationCity"] == "杭州"


def test_demo_plan_api_followup_budget_target_near_reuses_session_and_replans() -> None:
    os.environ["OPENAI_MODE"] = "mock"
    client = TestClient(app)

    first_response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-followup-budget-target-near-user",
            "message": "帮我规划一个杭州三日游，预算3000，节奏轻松一点，酒店尽量安静，想吃本地特色",
        },
    )

    assert first_response.status_code == 200
    first_payload = first_response.json()

    second_response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-followup-budget-target-near-user",
            "session_id": first_payload["session_id"],
            "message": "将总体预算尽可能贴近3000",
        },
    )

    assert second_response.status_code == 200
    payload = second_response.json()
    assert payload["session_id"] == first_payload["session_id"]
    assert payload["session_context"]["session_found"] is True
    assert payload["task_profile"]["task_type"] == "travel_planning"
    assert payload["structured_constraints"]["destination"] == "杭州"
    assert payload["structured_constraints"]["days"] == 3
    assert payload["structured_constraints"]["budget"] == 3000
    assert payload["structured_constraints"]["budget_policy"] == "target_near"
    assert payload["structured_constraints"]["target_budget"] == 3000
    assert payload["structured_constraints"]["_followup_replan"] is True
    assert payload["structured_constraints"]["revision_intent"]["revision_type"] == "budget_optimization"
    assert payload["final_plan"].get("consultingType") is None
    assert "没有匹配到可直接执行的轻量能力" not in payload["llm_output"]["llm_summary"]
    assert payload["final_plan"]["summary"]["destinationCity"] == "杭州"
    assert payload["final_plan"]["summary"]["days"] == 3
    assert abs(payload["final_plan"]["summary"]["totalBudget"] - 3000) <= 200
    assert any(item["label"] == "贴近预算" for item in payload["final_plan"]["budgetInsights"])


def test_demo_plan_api_supports_new_mock_city_pipeline() -> None:
    os.environ["OPENAI_MODE"] = "mock"
    client = TestClient(app)

    response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-xian-user",
            "message": "帮我规划一个西安三日游，预算3500，想看文化景点和博物馆，酒店尽量安静",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["structured_constraints"]["destination"] == "西安"
    assert payload["task_profile"]["task_type"] == "travel_planning"
    assert payload["retrieval_context"]["retrieved_documents"]
    assert any("西安" in item["content"] for item in payload["retrieval_context"]["retrieved_documents"])
    assert payload["tool_results"]
    assert payload["final_plan"]["summary"]["destinationCity"] == "西安"


def test_demo_plan_api_supports_xiamen_pipeline_with_citywalk_preferences() -> None:
    os.environ["OPENAI_MODE"] = "mock"
    client = TestClient(app)

    response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-xiamen-user",
            "message": "帮我规划一个厦门三日游，预算5000，节奏轻松一点，酒店尽量安静，想看海边和 citywalk，也想吃本地特色",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["structured_constraints"]["destination"] == "厦门"
    assert "citywalk" in payload["structured_constraints"]["preferences"]
    assert payload["retrieval_context"]["retrieved_documents"]
    assert any("厦门" in item["content"] for item in payload["retrieval_context"]["retrieved_documents"])
    assert payload["final_plan"]["summary"]["destinationCity"] == "厦门"


def test_demo_plan_api_supports_shenzhen_pipeline_with_expanded_mock_data() -> None:
    os.environ["OPENAI_MODE"] = "mock"
    client = TestClient(app)

    response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-shenzhen-user",
            "message": "帮我规划一个深圳四日游，预算6000，节奏轻松一点，酒店尽量安静，想看海边和 citywalk",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["structured_constraints"]["destination"] == "深圳"
    assert payload["structured_constraints"]["days"] == 4
    assert "citywalk" in payload["structured_constraints"]["preferences"]
    assert "nature" in payload["structured_constraints"]["preferences"]
    assert payload["retrieval_context"]["retrieved_documents"]
    assert any("深圳" in item["content"] for item in payload["retrieval_context"]["retrieved_documents"])
    assert payload["tool_results"]
    assert payload["final_plan"]["summary"]["destinationCity"] == "深圳"


def test_demo_plan_api_followup_comfort_update_keeps_five_day_session_state() -> None:
    os.environ["OPENAI_MODE"] = "mock"
    client = TestClient(app)

    first_response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-five-day-followup-user",
            "message": "帮我规划一个杭州5日游，预算3000，节奏轻松一点，酒店尽量安静，想吃本地特色",
        },
    )

    assert first_response.status_code == 200
    first_payload = first_response.json()
    assert first_payload["structured_constraints"]["days"] == 5
    assert first_payload["final_plan"]["summary"]["days"] == 5

    second_response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-five-day-followup-user",
            "session_id": first_payload["session_id"],
            "message": "酒店住得更舒适一点",
        },
    )

    assert second_response.status_code == 200
    payload = second_response.json()
    assert payload["session_context"]["session_found"] is True
    assert payload["structured_constraints"]["days"] == 5
    assert "comfortable_hotel" in payload["structured_constraints"]["preferences"]
    assert payload["final_plan"]["summary"]["days"] == 5
    assert len(payload["final_plan"]["days"]) == 5
    all_activities = [activity for day in payload["final_plan"]["days"] for activity in day.get("activities", [])]
    assert len(set(all_activities)) >= 5
    assert any(name in all_activities for name in {"九溪烟树", "西溪湿地", "小河直街", "良渚博物院"})
    assert payload["final_plan"]["hotelRecommendation"][0]["name"] == "西湖·栖岸隐庐酒店"


def test_demo_plan_api_followup_excluding_forbidden_city_spot_replans_without_reasking_days() -> None:
    os.environ["OPENAI_MODE"] = "mock"
    client = TestClient(app)

    first_response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-beijing-exclusion-followup-user",
            "message": "帮我规划一个北京5日游，预算5000，节奏轻松一点，酒店尽量安静",
        },
    )

    assert first_response.status_code == 200
    first_payload = first_response.json()
    assert first_payload["structured_constraints"]["destination"] == "北京"
    assert first_payload["structured_constraints"]["days"] == 5
    assert first_payload["task_profile"]["task_type"] == "travel_planning"

    second_response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-beijing-exclusion-followup-user",
            "session_id": first_payload["session_id"],
            "message": "不想要去逛故宫",
        },
    )

    assert second_response.status_code == 200
    payload = second_response.json()
    assert payload["session_id"] == first_payload["session_id"]
    assert payload["session_context"]["session_found"] is True
    assert payload["task_profile"]["task_type"] == "travel_planning"
    assert payload["structured_constraints"]["destination"] == "北京"
    assert payload["structured_constraints"]["days"] == 5
    assert payload["structured_constraints"]["excluded_attractions"] == ["故宫"]
    assert payload["final_plan"]["summary"]["destinationCity"] == "北京"
    assert payload["final_plan"]["summary"]["days"] == 5
    assert payload["final_plan"].get("consultingType") is None
    assert not payload["final_plan"].get("missingFields")

    all_activities = [activity for day in payload["final_plan"]["days"] for activity in day.get("activities", [])]
    recommendation_names = [item.get("name") for item in payload["final_plan"]["attractionRecommendations"]]
    assert "故宫" not in all_activities
    assert "故宫" not in recommendation_names


def test_demo_plan_api_followup_day_count_update_replans_with_existing_session_context() -> None:
    os.environ["OPENAI_MODE"] = "mock"
    client = TestClient(app)

    first_response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-followup-days-update-user",
            "message": "帮我规划一个北京5日游，预算5000，节奏均衡一点，酒店尽量安静",
        },
    )

    assert first_response.status_code == 200
    first_payload = first_response.json()
    assert first_payload["structured_constraints"]["destination"] == "北京"
    assert first_payload["structured_constraints"]["days"] == 5

    second_response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-followup-days-update-user",
            "session_id": first_payload["session_id"],
            "message": "改成4天",
        },
    )

    assert second_response.status_code == 200
    payload = second_response.json()
    assert payload["task_profile"]["task_type"] == "travel_planning"
    assert payload["structured_constraints"]["destination"] == "北京"
    assert payload["structured_constraints"]["days"] == 4
    assert payload["final_plan"]["summary"]["destinationCity"] == "北京"
    assert payload["final_plan"]["summary"]["days"] == 4
    assert len(payload["final_plan"]["days"]) == 4


def test_demo_plan_api_followup_preference_update_replans_without_reasking_trip_basics() -> None:
    os.environ["OPENAI_MODE"] = "mock"
    client = TestClient(app)

    first_response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-followup-preference-update-user",
            "message": "帮我规划一个上海三日游，预算4500，节奏均衡一点，酒店尽量安静",
        },
    )

    assert first_response.status_code == 200
    first_payload = first_response.json()
    assert first_payload["structured_constraints"]["destination"] == "上海"
    assert first_payload["structured_constraints"]["days"] == 3

    second_response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-followup-preference-update-user",
            "session_id": first_payload["session_id"],
            "message": "节奏轻松一点，多看博物馆",
        },
    )

    assert second_response.status_code == 200
    payload = second_response.json()
    assert payload["task_profile"]["task_type"] == "travel_planning"
    assert payload["structured_constraints"]["destination"] == "上海"
    assert payload["structured_constraints"]["days"] == 3
    assert payload["structured_constraints"]["pace"] == "relaxed"
    assert "museum" in payload["structured_constraints"]["preferences"]
    assert payload["final_plan"]["summary"]["destinationCity"] == "上海"


def test_demo_plan_api_followup_excluding_xihu_removes_related_hangzhou_lake_spots() -> None:
    os.environ["OPENAI_MODE"] = "mock"
    client = TestClient(app)

    first_response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-hangzhou-xihu-exclusion-user",
            "message": "帮我规划一个杭州5日游，预算5000，节奏轻松一点，酒店尽量安静，想吃本地特色",
        },
    )

    assert first_response.status_code == 200
    first_payload = first_response.json()
    assert first_payload["structured_constraints"]["destination"] == "杭州"
    assert first_payload["structured_constraints"]["days"] == 5

    second_response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-hangzhou-xihu-exclusion-user",
            "session_id": first_payload["session_id"],
            "message": "不想逛西湖",
        },
    )

    assert second_response.status_code == 200
    payload = second_response.json()
    assert payload["task_profile"]["task_type"] == "travel_planning"
    assert payload["structured_constraints"]["destination"] == "杭州"
    assert payload["structured_constraints"]["days"] == 5
    assert payload["structured_constraints"]["excluded_attractions"] == ["西湖"]
    assert "白堤孤山" in payload["structured_constraints"]["expanded_excluded_attractions"]

    all_activities = [activity for day in payload["final_plan"]["days"] for activity in day.get("activities", [])]
    recommendation_names = [item.get("name") for item in payload["final_plan"]["attractionRecommendations"]]
    disallowed = {"西湖", "白堤孤山"}
    assert not disallowed.intersection(all_activities)
    assert not disallowed.intersection(recommendation_names)


def test_demo_plan_api_followup_excluding_xihu_without_session_id_auto_resumes_recent_plan() -> None:
    os.environ["OPENAI_MODE"] = "mock"
    client = TestClient(app)

    first_response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-hangzhou-xihu-auto-resume-user",
            "message": "帮我规划一个杭州三日游，预算3000，节奏轻松一点，酒店尽量安静，想吃本地特色",
        },
    )

    assert first_response.status_code == 200
    first_payload = first_response.json()
    assert first_payload["structured_constraints"]["destination"] == "杭州"
    assert first_payload["structured_constraints"]["days"] == 3

    second_response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-hangzhou-xihu-auto-resume-user",
            "message": "不想逛西湖",
        },
    )

    assert second_response.status_code == 200
    payload = second_response.json()
    assert payload["session_id"] == first_payload["session_id"]
    assert payload["session_context"]["session_found"] is True
    assert payload["task_profile"]["task_type"] == "travel_planning"
    assert payload["structured_constraints"]["destination"] == "杭州"
    assert payload["structured_constraints"]["days"] == 3
    assert payload["structured_constraints"]["excluded_attractions"] == ["西湖"]
    assert payload["final_plan"]["summary"]["destinationCity"] == "杭州"
    assert payload["final_plan"]["summary"]["days"] == 3
    assert payload["final_plan"].get("consultingType") is None

    all_activities = [activity for day in payload["final_plan"]["days"] for activity in day.get("activities", [])]
    recommendation_names = [item.get("name") for item in payload["final_plan"]["attractionRecommendations"]]
    disallowed = {"西湖", "白堤孤山"}
    assert not disallowed.intersection(all_activities)
    assert not disallowed.intersection(recommendation_names)


def test_demo_plan_api_followup_budget_target_near_without_session_id_auto_resumes_recent_plan() -> None:
    os.environ["OPENAI_MODE"] = "mock"
    client = TestClient(app)

    first_response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-budget-target-near-auto-resume-user",
            "message": "帮我规划一个杭州三日游，预算3000，节奏轻松一点，酒店尽量安静，想吃本地特色",
        },
    )

    assert first_response.status_code == 200
    first_payload = first_response.json()
    assert first_payload["structured_constraints"]["destination"] == "杭州"
    assert first_payload["structured_constraints"]["days"] == 3

    second_response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-budget-target-near-auto-resume-user",
            "message": "总花费尽量接近3000",
        },
    )

    assert second_response.status_code == 200
    payload = second_response.json()
    assert payload["session_id"] == first_payload["session_id"]
    assert payload["session_context"]["session_found"] is True
    assert payload["task_profile"]["task_type"] == "travel_planning"
    assert payload["structured_constraints"]["destination"] == "杭州"
    assert payload["structured_constraints"]["days"] == 3
    assert payload["structured_constraints"]["budget_policy"] == "target_near"
    assert payload["structured_constraints"]["target_budget"] == 3000
    assert payload["final_plan"].get("consultingType") is None
    assert abs(payload["final_plan"]["summary"]["totalBudget"] - 3000) <= 200


def test_demo_plan_api_followup_excluding_chengdu_spot_without_session_id_auto_resumes_recent_plan() -> None:
    os.environ["OPENAI_MODE"] = "mock"
    client = TestClient(app)

    first_response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-chengdu-spot-auto-resume-user",
            "message": "帮我规划一个成都三日游，预算3000，节奏轻松一点，酒店尽量安静，想吃本地特色",
        },
    )

    assert first_response.status_code == 200
    first_payload = first_response.json()
    assert first_payload["structured_constraints"]["destination"] == "成都"
    assert first_payload["structured_constraints"]["days"] == 3

    second_response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-chengdu-spot-auto-resume-user",
            "message": "不要去武侯祠",
        },
    )

    assert second_response.status_code == 200
    payload = second_response.json()
    assert payload["session_id"] == first_payload["session_id"]
    assert payload["session_context"]["session_found"] is True
    assert payload["task_profile"]["task_type"] == "travel_planning"
    assert payload["structured_constraints"]["destination"] == "成都"
    assert payload["structured_constraints"]["days"] == 3
    assert payload["structured_constraints"]["excluded_attractions"] == ["武侯祠"]
    assert payload["final_plan"]["summary"]["destinationCity"] == "成都"
    assert payload["final_plan"]["summary"]["days"] == 3
    assert payload["final_plan"].get("consultingType") is None


def test_demo_plan_api_followup_excluding_spot_with_replan_words_auto_resumes_recent_plan() -> None:
    os.environ["OPENAI_MODE"] = "mock"
    client = TestClient(app)

    first_response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-chengdu-exclusion-replan-words-user",
            "message": "帮我规划一个成都三日游，预算3000，节奏轻松一点，酒店尽量安静，想吃本地特色",
        },
    )

    assert first_response.status_code == 200
    first_payload = first_response.json()
    assert first_payload["structured_constraints"]["destination"] == "成都"
    assert first_payload["structured_constraints"]["days"] == 3

    second_response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-chengdu-exclusion-replan-words-user",
            "message": "不要去武侯祠，请重新规划一下",
        },
    )

    assert second_response.status_code == 200
    payload = second_response.json()
    assert payload["session_id"] == first_payload["session_id"]
    assert payload["session_context"]["session_found"] is True
    assert payload["task_profile"]["task_type"] == "travel_planning"
    assert payload["structured_constraints"]["destination"] == "成都"
    assert payload["structured_constraints"]["days"] == 3
    assert payload["structured_constraints"]["excluded_attractions"] == ["武侯祠"]
    assert payload["final_plan"]["summary"]["destinationCity"] == "成都"
    assert payload["final_plan"]["summary"]["days"] == 3
    assert payload["final_plan"].get("consultingType") is None


def test_demo_plan_api_followup_negative_spot_without_action_verb_auto_resumes_recent_plan() -> None:
    os.environ["OPENAI_MODE"] = "mock"
    client = TestClient(app)

    first_response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-chengdu-negative-spot-no-verb-user",
            "message": "帮我规划一个成都三日游，预算3000，节奏轻松一点，酒店尽量安静，想吃本地特色",
        },
    )

    assert first_response.status_code == 200
    first_payload = first_response.json()
    assert first_payload["structured_constraints"]["destination"] == "成都"
    assert first_payload["structured_constraints"]["days"] == 3

    second_response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-chengdu-negative-spot-no-verb-user",
            "message": "不想武侯祠，请重新规划一下",
        },
    )

    assert second_response.status_code == 200
    payload = second_response.json()
    assert payload["session_id"] == first_payload["session_id"]
    assert payload["session_context"]["session_found"] is True
    assert payload["task_profile"]["task_type"] == "travel_planning"
    assert payload["structured_constraints"]["destination"] == "成都"
    assert payload["structured_constraints"]["days"] == 3
    assert payload["structured_constraints"]["excluded_attractions"] == ["武侯祠"]
    assert payload["final_plan"]["summary"]["destinationCity"] == "成都"
    assert payload["final_plan"]["summary"]["days"] == 3
    assert payload["final_plan"].get("consultingType") is None


def test_demo_plan_api_followup_excluding_city_prefixed_chengdu_spot_auto_resumes_recent_plan() -> None:
    os.environ["OPENAI_MODE"] = "mock"
    client = TestClient(app)

    first_response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-chengdu-prefixed-spot-auto-resume-user",
            "message": "帮我规划一个成都三日游，预算3000，节奏轻松一点，酒店尽量安静，想吃本地特色",
        },
    )

    assert first_response.status_code == 200
    first_payload = first_response.json()
    assert first_payload["structured_constraints"]["destination"] == "成都"
    assert first_payload["structured_constraints"]["days"] == 3

    second_response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-chengdu-prefixed-spot-auto-resume-user",
            "message": "不想去成都大熊猫繁育研究基地",
        },
    )

    assert second_response.status_code == 200
    payload = second_response.json()
    assert payload["session_id"] == first_payload["session_id"]
    assert payload["session_context"]["session_found"] is True
    assert payload["task_profile"]["task_type"] == "travel_planning"
    assert payload["structured_constraints"]["destination"] == "成都"
    assert payload["structured_constraints"]["days"] == 3
    assert payload["structured_constraints"]["excluded_attractions"] == ["成都大熊猫繁育研究基地"]
    assert payload["final_plan"]["summary"]["destinationCity"] == "成都"
    assert payload["final_plan"]["summary"]["days"] == 3
    assert payload["final_plan"].get("consultingType") is None


def test_demo_plan_api_supports_sanya_family_pipeline() -> None:
    os.environ["OPENAI_MODE"] = "mock"
    client = TestClient(app)

    response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-sanya-family-user",
            "message": "帮我规划一个三亚四日游，预算9000，节奏轻松一点，酒店尽量安静，适合亲子",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["structured_constraints"]["destination"] == "三亚"
    assert payload["structured_constraints"]["days"] == 4
    assert "family" in payload["structured_constraints"]["preferences"]
    assert payload["retrieval_context"]["retrieved_documents"]
    assert any(item["topic"] == "family" for item in payload["retrieval_context"]["retrieved_documents"])
    assert payload["final_plan"]["summary"]["destinationCity"] == "三亚"
    assert payload["final_plan"]["summary"]["days"] == 4
    assert payload["final_plan"]["hotelRecommendation"]
    assert "family_friendly" in payload["final_plan"]["hotelRecommendation"][0]["tags"]


def test_demo_plan_api_rainy_day_family_consulting_uses_attraction_flow() -> None:
    os.environ["OPENAI_MODE"] = "mock"
    client = TestClient(app)

    response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-rainy-family-user",
            "message": "上海下雨天适合带娃去哪玩",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    selected_ids = [item["skill_id"] for item in payload["selected_skills"]]
    assert payload["task_profile"]["task_type"] == "travel_consulting"
    assert payload["llm_output"]["mode"] == "bypass"
    assert selected_ids == ["attraction.search"]
    assert payload["final_plan"]["consultingType"] == "attraction"
    assert "上海" in payload["final_plan"]["consultingAnswer"]


def test_demo_session_open_hydrates_legacy_map_visual_for_shanghai_consulting() -> None:
    os.environ["OPENAI_MODE"] = "mock"
    client = TestClient(app)

    response = client.post(
        "/api/demo/plan",
        json={
            "user_id": "integration-legacy-map-hydration-user",
            "message": "上海有哪些推荐的景点",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    session_id = payload["session_id"]
    assert session_id

    from app.db.repositories import SessionRunRepository

    run_repository = SessionRunRepository()
    runs = run_repository.list_session_runs(session_id=session_id)
    assert runs
    latest = runs[0]
    latest_response = latest["response"]
    assert latest_response["final_plan"]["visual"]["map"]["markers"]

    latest_response["final_plan"].pop("visual", None)
    raw_records = run_repository._list_all_runs(user_id="integration-legacy-map-hydration-user")
    target_run_id = latest["run_id"]
    for record in raw_records:
        if record["run_id"] == target_run_id:
            record["response"]["final_plan"].pop("visual", None)

    from app.db.sqlite import SESSION_RUNS_PATH, save_json_records, sqlite_available
    import json as _json

    if sqlite_available():
        from app.db.sqlite import get_connection

        with get_connection() as connection:
            connection.execute(
                "UPDATE session_runs SET response_json = ? WHERE run_id = ?",
                (_json.dumps(latest_response, ensure_ascii=False), target_run_id),
            )
            connection.commit()
    else:
        persisted = []
        for record in raw_records:
            if record["run_id"] == target_run_id:
                persisted.append(
                    {
                        "run_id": record["run_id"],
                        "session_id": record["session_id"],
                        "user_id": record["user_id"],
                        "request_text": record["request_text"],
                        "response_json": _json.dumps(record["response"], ensure_ascii=False),
                        "created_at": record["created_at"],
                    }
                )
            else:
                persisted.append(
                    {
                        "run_id": record["run_id"],
                        "session_id": record["session_id"],
                        "user_id": record["user_id"],
                        "request_text": record["request_text"],
                        "response_json": _json.dumps(record["response"], ensure_ascii=False),
                        "created_at": record["created_at"],
                    }
                )
        save_json_records(SESSION_RUNS_PATH, persisted)

    hydrated = client.get(f"/api/demo/session/{session_id}")
    assert hydrated.status_code == 200
    hydrated_payload = hydrated.json()
    map_data = hydrated_payload["response"]["final_plan"]["visual"]["map"]
    assert map_data["destination"] == "上海"
    assert len(map_data["markers"]) >= 3
