from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.orchestration.agents.agent_service import AgentService
from app.api.routes import build_router
from app.core.config.settings import load_settings
from app.orchestration.context.context_assembler import ContextAssembler
from app.orchestration.context.session_context_service import SessionContextService
from app.core.db.repositories import MemoryRepository, SessionRunRepository
from app.core.db.sqlite import init_db
from app.knowledge.graph import GraphExpansionService, GraphStore, ObsidianGraphLoader
from app.capabilities.image_generation.service import ImageGenerationService
from app.capabilities.integrations.amap_geo_service import AmapGeoService
from app.capabilities.llm.openai_client import OpenAIPlannerClient
from app.core.media.static_files import CachedStaticFiles
from app.orchestration.memory.memory_extractor import MemoryExtractor
from app.orchestration.memory.memory_injection_service import MemoryInjectionService
from app.orchestration.memory.memory_service import MemoryService
from app.orchestration.planning.planner_service import PlannerService
from app.orchestration.planning.slot_extractor import SlotExtractor
from app.orchestration.planning.task_router import TaskRouter
from app.capabilities.presentation.geo_service import GeoPresentationService
from app.knowledge.retrieval.retrieval_service import RetrievalService
from app.capabilities.skills.skill_registry import SkillRegistry
from app.capabilities.skills.skill_script_runner import SkillScriptRunner
from app.capabilities.skills.skill_selection_service import SkillSelectionService
from app.capabilities.skills.tool_service import ToolService


def create_app() -> FastAPI:
    """创建 FastAPI 应用并完成后端依赖装配。

    这里使用显式依赖组装，而不是引入复杂 DI 容器：启动流程一眼可见，方便开发者定位
    SQLite、知识图谱、Skill、RAG、LLM、地图/图片服务和 PlannerService 的连接关系。
    """
    init_db()
    settings = load_settings()
    graph_store = GraphStore()
    graph_store.ensure_schema()
    if settings.knowledge_graph_enabled:
        # 知识图谱用于扩展“不要去某景点”的别名/关联点位；vault 不存在时保持空图，不影响主链路。
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
    slot_extractor = SlotExtractor()
    memory_extractor = MemoryExtractor(slot_extractor=slot_extractor)
    image_generation_service = ImageGenerationService(settings)
    amap_geo_service = AmapGeoService(settings)
    geo_presentation_service = GeoPresentationService(amap_geo_service=amap_geo_service)
    planner_service = PlannerService(
        slot_extractor=slot_extractor,
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
        memory_extractor=memory_extractor,
        geo_presentation_service=geo_presentation_service,
        image_generation_service=image_generation_service,
        graph_expansion_service=graph_expansion_service,
    )

    app = FastAPI(title="Smart Trip API")
    generated_media_dir = Path(settings.image_output_dir)
    generated_media_dir.mkdir(parents=True, exist_ok=True)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allowed_origins),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # 生成图片以静态文件方式暴露给前端；CachedStaticFiles 会处理浏览器缓存头。
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
            memory_extractor=memory_extractor,
        )
    )
    return app


app = create_app()
