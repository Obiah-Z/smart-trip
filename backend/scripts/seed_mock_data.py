from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agents.agent_service import AgentService
from app.config.settings import load_settings
from app.context.context_assembler import ContextAssembler
from app.context.session_context_service import SessionContextService
from app.image_generation.service import ImageGenerationService
from app.integrations.amap_geo_service import AmapGeoService
from app.llm.openai_client import OpenAIPlannerClient
from app.memory.memory_injection_service import MemoryInjectionService
from app.memory.memory_service import MemoryService
from app.planning.planner_service import PlannerService
from app.planning.slot_extractor import SlotExtractor
from app.planning.task_router import TaskRouter
from app.presentation.geo_service import GeoPresentationService
from app.retrieval.retrieval_service import RetrievalService
from app.skills.skill_registry import SkillRegistry
from app.skills.skill_script_runner import SkillScriptRunner
from app.skills.skill_selection_service import SkillSelectionService
from app.skills.tool_service import ToolService
from app.db.repositories import MemoryRepository, SessionRunRepository
from app.db.sqlite import MEMORY_PATH, SESSION_RUNS_PATH, get_connection, init_db, save_json_records, sqlite_available


@dataclass(frozen=True)
class SeedTurn:
    message: str
    reuse_previous_session: bool = False


@dataclass(frozen=True)
class SeedScenario:
    user_id: str
    turns: list[SeedTurn]


MANUAL_MEMORY_ITEMS = [
    {"user_id": "manual-family-user", "key": "hotel_style", "value": "prefer_quiet_location", "scope": "travel_preference"},
    {"user_id": "manual-family-user", "key": "preference_quiet_hotel", "value": "quiet_hotel", "scope": "travel_preference"},
    {"user_id": "manual-family-user", "key": "preference_local_food", "value": "local_food", "scope": "travel_preference"},
    {"user_id": "manual-family-user", "key": "preference_nature", "value": "nature", "scope": "travel_preference"},
    {"user_id": "manual-family-user", "key": "preference_family", "value": "family", "scope": "travel_preference"},
    {"user_id": "manual-family-user", "key": "travel_pace", "value": "relaxed", "scope": "travel_preference"},
    {"user_id": "manual-business-user", "key": "hotel_style", "value": "prefer_quiet_location", "scope": "travel_preference"},
    {"user_id": "manual-business-user", "key": "preference_quiet_hotel", "value": "quiet_hotel", "scope": "travel_preference"},
    {"user_id": "manual-business-user", "key": "preference_metro", "value": "metro", "scope": "travel_preference"},
    {"user_id": "manual-business-user", "key": "travel_pace", "value": "balanced", "scope": "travel_preference"},
    {"user_id": "manual-citywalk-user", "key": "hotel_style", "value": "prefer_lively_location", "scope": "travel_preference"},
    {"user_id": "manual-citywalk-user", "key": "preference_quiet_hotel", "value": "avoid_quiet_hotel", "scope": "travel_preference"},
    {"user_id": "manual-citywalk-user", "key": "preference_food", "value": "food", "scope": "travel_preference"},
    {"user_id": "manual-citywalk-user", "key": "preference_citywalk", "value": "citywalk", "scope": "travel_preference"},
    {"user_id": "manual-citywalk-user", "key": "travel_pace", "value": "intensive", "scope": "travel_preference"},
    {"user_id": "manual-rail-user", "key": "preference_high_speed_rail", "value": "high_speed_rail", "scope": "travel_preference"},
    {"user_id": "manual-rail-user", "key": "preference_local_food", "value": "avoid_local_food", "scope": "travel_preference"},
    {"user_id": "manual-rail-user", "key": "travel_pace", "value": "balanced", "scope": "travel_preference"},
    {"user_id": "manual-museum-user", "key": "preference_museum", "value": "museum", "scope": "travel_preference"},
    {"user_id": "manual-museum-user", "key": "preference_culture", "value": "culture", "scope": "travel_preference"},
    {"user_id": "manual-museum-user", "key": "hotel_style", "value": "prefer_quiet_location", "scope": "travel_preference"},
    {"user_id": "manual-museum-user", "key": "travel_pace", "value": "balanced", "scope": "travel_preference"},
    {"user_id": "manual-coast-user", "key": "preference_nature", "value": "nature", "scope": "travel_preference"},
    {"user_id": "manual-coast-user", "key": "preference_citywalk", "value": "citywalk", "scope": "travel_preference"},
    {"user_id": "manual-coast-user", "key": "hotel_style", "value": "prefer_quiet_location", "scope": "travel_preference"},
    {"user_id": "manual-coast-user", "key": "travel_pace", "value": "relaxed", "scope": "travel_preference"},
]


SCENARIOS = [
    SeedScenario(
        user_id="demo-user",
        turns=[
            SeedTurn("帮我规划一个杭州三日游，预算3000，节奏轻松一点，酒店尽量安静，想吃本地特色"),
            SeedTurn("把预算提高到10000，主要是提升住宿舒适度，酒店继续安静一点", reuse_previous_session=True),
        ],
    ),
    SeedScenario(
        user_id="family-user",
        turns=[
            SeedTurn("帮我规划一个苏州三日游，预算4500，节奏轻松一点，酒店尽量安静，想吃本地特色，也想多看自然景点"),
            SeedTurn("把预算调整到6000，主要提升住宿舒适度，还是希望安静一点", reuse_previous_session=True),
        ],
    ),
    SeedScenario(
        user_id="citywalk-user",
        turns=[
            SeedTurn("帮我规划一个上海两日游，预算5000，节奏紧凑一点，酒店尽量热闹，想吃美食，也想多走citywalk"),
            SeedTurn("把预算提高到7000，酒店继续热闹一点，住得舒服一些", reuse_previous_session=True),
        ],
    ),
    SeedScenario(
        user_id="business-user",
        turns=[
            SeedTurn("帮我规划一个北京两日游，预算4000，节奏紧凑一点，酒店尽量安静，地铁方便一点"),
            SeedTurn("把预算提升到6000，主要升级住宿舒适度，交通还是以地铁为主", reuse_previous_session=True),
        ],
    ),
    SeedScenario(
        user_id="culture-user",
        turns=[
            SeedTurn("帮我规划一个西安三日游，预算3500，节奏轻松一点，酒店尽量安静，想看文化景点和博物馆"),
            SeedTurn("把预算提高到5000，主要提升住宿舒适度，酒店还是安静一点", reuse_previous_session=True),
        ],
    ),
    SeedScenario(
        user_id="budget-user",
        turns=[
            SeedTurn("帮我规划一个成都三日游，预算2500，节奏轻松一点，尽量坐高铁，不想吃本地特色"),
            SeedTurn("把预算调整到3200，还是尽量控制花费，酒店安静一点", reuse_previous_session=True),
        ],
    ),
    SeedScenario(
        user_id="foodie-user",
        turns=[
            SeedTurn("帮我规划一个广州三日游，预算4000，节奏紧凑一点，酒店尽量热闹，想吃本地特色和美食"),
        ],
    ),
    SeedScenario(
        user_id="consulting-weather-user",
        turns=[
            SeedTurn("重庆今天天气如何"),
        ],
    ),
    SeedScenario(
        user_id="consulting-attraction-user",
        turns=[
            SeedTurn("西安有哪些推荐的文化景点"),
        ],
    ),
    SeedScenario(
        user_id="coast-user",
        turns=[
            SeedTurn("帮我规划一个厦门三日游，预算5000，节奏轻松一点，酒店尽量安静，想看海边和 citywalk，也想吃本地特色"),
            SeedTurn("把预算提高到7000，主要提升住宿舒适度，最好还能住海边一点", reuse_previous_session=True),
        ],
    ),
    SeedScenario(
        user_id="museum-user",
        turns=[
            SeedTurn("帮我规划一个南京两日游，预算3500，想看博物馆和文化景点，酒店安静一点"),
        ],
    ),
    SeedScenario(
        user_id="sanya-family-user",
        turns=[
            SeedTurn("帮我规划一个三亚四日游，预算9000，节奏轻松一点，酒店尽量安静，适合亲子"),
            SeedTurn("把预算提高到12000，主要升级亲子酒店的舒适度，还是想住安静一点", reuse_previous_session=True),
        ],
    ),
    SeedScenario(
        user_id="rainy-family-consulting-user",
        turns=[
            SeedTurn("上海下雨天适合带娃去哪玩"),
        ],
    ),
]


def build_planner_service() -> tuple[PlannerService, MemoryService]:
    init_db()
    settings = load_settings()
    skill_registry = SkillRegistry()
    script_runner = SkillScriptRunner()
    tool_service = ToolService(skill_registry=skill_registry, script_runner=script_runner)
    openai_client = OpenAIPlannerClient(settings)
    skill_selection_service = SkillSelectionService(openai_client=openai_client)
    memory_repository = MemoryRepository()
    session_run_repository = SessionRunRepository()
    memory_service = MemoryService(memory_repository)
    image_generation_service = ImageGenerationService(settings)
    geo_presentation_service = GeoPresentationService(
        amap_geo_service=AmapGeoService(settings)
    )
    planner_service = PlannerService(
        slot_extractor=SlotExtractor(),
        memory_service=memory_service,
        retrieval_service=RetrievalService(settings=settings),
        tool_service=tool_service,
        agent_service=AgentService(),
        context_assembler=ContextAssembler(),
        session_run_repository=session_run_repository,
        openai_client=openai_client,
        skill_selection_service=skill_selection_service,
        task_router=TaskRouter(),
        session_context_service=SessionContextService(session_run_repository),
        memory_injection_service=MemoryInjectionService(),
        geo_presentation_service=geo_presentation_service,
        image_generation_service=image_generation_service,
    )
    return planner_service, memory_service


def reset_stores() -> None:
    save_json_records(MEMORY_PATH, [])
    save_json_records(SESSION_RUNS_PATH, [])

    if sqlite_available():
        with get_connection() as connection:
            connection.execute("DELETE FROM user_memory")
            connection.execute("DELETE FROM session_runs")
            connection.commit()


def export_sqlite_snapshots() -> None:
    if not sqlite_available():
        return

    with get_connection() as connection:
        memory_rows = connection.execute(
            "SELECT user_id, key, value, scope, updated_at FROM user_memory ORDER BY user_id ASC, key ASC"
        ).fetchall()
        session_rows = connection.execute(
            "SELECT session_id, user_id, request_text, response_json, created_at FROM session_runs ORDER BY created_at ASC"
        ).fetchall()

    save_json_records(MEMORY_PATH, [dict(row) for row in memory_rows])
    save_json_records(SESSION_RUNS_PATH, [dict(row) for row in session_rows])


def seed_manual_memories(memory_service: MemoryService) -> None:
    for item in MANUAL_MEMORY_ITEMS:
        memory_service.upsert_memory(**item)


def seed_scenarios(planner_service: PlannerService) -> list[dict[str, str]]:
    generated: list[dict[str, str]] = []

    for scenario in SCENARIOS:
        session_id: str | None = None
        for turn in scenario.turns:
            response = planner_service.run(
                user_id=scenario.user_id,
                session_id=session_id if turn.reuse_previous_session else None,
                message=turn.message,
            )
            session_id = response["session_id"]
            generated.append(
                {
                    "user_id": scenario.user_id,
                    "session_id": session_id,
                    "task_type": response["task_profile"]["task_type"],
                    "message": turn.message,
                }
            )

    return generated


def print_summary(generated_runs: list[dict[str, str]]) -> None:
    memory_records = MEMORY_PATH.read_text(encoding="utf-8")
    session_records = SESSION_RUNS_PATH.read_text(encoding="utf-8")
    print("mock data seeded")
    print(f"- scenarios: {len(SCENARIOS)}")
    print(f"- generated runs: {len(generated_runs)}")
    print(f"- memory snapshot bytes: {len(memory_records)}")
    print(f"- session snapshot bytes: {len(session_records)}")
    print("- users:")
    for user_id in sorted({item["user_id"] for item in generated_runs} | {item["user_id"] for item in MANUAL_MEMORY_ITEMS}):
        print(f"  - {user_id}")


def main() -> None:
    os.environ["OPENAI_MODE"] = "mock"
    reset_stores()
    planner_service, memory_service = build_planner_service()
    seed_manual_memories(memory_service)
    generated_runs = seed_scenarios(planner_service)
    export_sqlite_snapshots()
    print_summary(generated_runs)


if __name__ == "__main__":
    main()
