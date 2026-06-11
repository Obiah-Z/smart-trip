from app.planning.task_router import TaskRouter


def test_task_router_marks_complex_itinerary_request() -> None:
    router = TaskRouter()

    profile = router.analyze(
        "帮我规划一个杭州三日游，预算3000，节奏紧张一点，酒店尽量嘈杂，不想吃本地特色",
        days=3,
        preferences=["lively_hotel", "avoid_local_food"],
    )

    assert profile.task_type == "travel_planning"
    assert profile.complexity == "complex"
    assert profile.needs_rag is True
    assert profile.needs_tools is True
    assert profile.needs_multi_agent is True


def test_task_router_marks_simple_attraction_query_as_consulting() -> None:
    router = TaskRouter()

    profile = router.analyze(
        "杭州有哪些推荐的景点",
        days=1,
        preferences=[],
    )

    assert profile.task_type == "travel_consulting"
    assert profile.complexity == "simple"
    assert profile.needs_rag is True
    assert profile.needs_tools is True
    assert profile.needs_multi_agent is False


def test_task_router_can_force_followup_update_into_planning() -> None:
    router = TaskRouter()

    profile = router.force_planning_profile(
        message="帮我把预算提升到10000，主要是提升住宿舒适度",
        days=3,
        preferences=["quiet_hotel", "local_food", "comfortable_hotel"],
    )

    assert profile.task_type == "travel_planning"
    assert profile.needs_rag is True
    assert profile.needs_tools is True
    assert profile.needs_multi_agent is True


def test_task_router_marks_family_consulting_as_simple_consulting() -> None:
    router = TaskRouter()

    profile = router.analyze(
        "三亚有哪些适合亲子出游的景点",
        days=1,
        preferences=["family"],
    )

    assert profile.task_type == "travel_consulting"
    assert profile.complexity == "simple"
    assert profile.needs_rag is True
    assert profile.needs_tools is True
    assert profile.needs_multi_agent is False


def test_task_router_marks_rainy_day_family_query_as_consulting() -> None:
    router = TaskRouter()

    profile = router.analyze(
        "上海下雨天适合带娃去哪玩",
        days=1,
        preferences=["family", "rainy_day"],
    )

    assert profile.task_type == "travel_consulting"
    assert profile.complexity == "simple"
    assert profile.needs_rag is True
    assert profile.needs_tools is True
    assert profile.needs_multi_agent is False
