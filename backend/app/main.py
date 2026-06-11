from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents.agent_service import AgentService
from app.api.routes import build_router
from app.config.settings import load_settings
from app.context.context_assembler import ContextAssembler
from app.context.session_context_service import SessionContextService
from app.db.repositories import MemoryRepository, SessionRunRepository
from app.db.sqlite import init_db
from app.graph import GraphExpansionService, GraphStore, ObsidianGraphLoader
from app.image_generation.service import ImageGenerationService
from app.integrations.amap_geo_service import AmapGeoService
from app.llm.openai_client import OpenAIPlannerClient
from app.media.static_files import CachedStaticFiles
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


def create_app() -> FastAPI:
    init_db()
    settings = load_settings()
    graph_store = GraphStore()
    graph_store.ensure_schema()
    if settings.knowledge_graph_enabled:
        graph_loader = ObsidianGraphLoader()
        vault_dir = Path(settings.knowledge_graph_vault_dir)
        if vault_dir.exists():
            nodes, edges = graph_loader.load_directory(vault_dir=vault_dir)
            graph_store.replace_all(nodes=nodes, edges=edges)
    graph_expansion_service = GraphExpansionService(graph_store=graph_store)
    skill_registry = SkillRegistry()
    script_runner = SkillScriptRunner()
    tool_service = ToolService(skill_registry=skill_registry, script_runner=script_runner)
    openai_client = OpenAIPlannerClient(settings)
    skill_selection_service = SkillSelectionService(openai_client=openai_client)

    memory_repository = MemoryRepository()
    session_run_repository = SessionRunRepository()
    memory_service = MemoryService(memory_repository)
    image_generation_service = ImageGenerationService(settings)
    amap_geo_service = AmapGeoService(settings)
    geo_presentation_service = GeoPresentationService(amap_geo_service=amap_geo_service)
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
        graph_expansion_service=graph_expansion_service,
    )

    app = FastAPI(title="Smart Trip Demo API")
    generated_media_dir = Path(settings.image_output_dir)
    generated_media_dir.mkdir(parents=True, exist_ok=True)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allowed_origins),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.mount("/media/generated", CachedStaticFiles(directory=str(generated_media_dir)), name="generated-media")
    app.state.amap_geo_service = amap_geo_service
    app.include_router(
        build_router(
            planner_service=planner_service,
            memory_service=memory_service,
            session_run_repository=session_run_repository,
            tool_service=tool_service,
            image_generation_service=image_generation_service,
            geo_presentation_service=geo_presentation_service,
        )
    )
    return app


app = create_app()
