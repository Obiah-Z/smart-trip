from __future__ import annotations

from copy import deepcopy

from fastapi import APIRouter, HTTPException

from app.db.sqlite import get_storage_status
from app.image_generation.client import ImageGenerationError
from app.models.schemas import (
    AttractionImageGenerateRequest,
    AttractionImageGenerateResponse,
    DemoPlanRequest,
    DemoPlanResponse,
    MemoryItem,
    MemoryUpsertRequest,
    SessionRunListItem,
    SkillDefinitionItem,
    SkillInvokeRequest,
)


def _hydrate_legacy_visual(response: dict, geo_presentation_service) -> dict:
    final_plan = response.get("final_plan")
    structured_constraints = response.get("structured_constraints") or {}
    if not isinstance(final_plan, dict):
        return response

    map_payload = ((final_plan.get("visual") or {}).get("map") or {})
    has_usable_map = bool(map_payload.get("center")) and bool(map_payload.get("markers"))
    if has_usable_map:
        return response

    summary = final_plan.get("summary") or {}
    destination = summary.get("destinationCity") or structured_constraints.get("destination")
    if not destination:
        return response

    upgraded_response = dict(response)
    upgraded_response["final_plan"] = geo_presentation_service.enrich_final_plan(
        final_plan=final_plan,
        structured_constraints=structured_constraints,
    )
    return upgraded_response


def _hydrate_legacy_run_visual(run: dict, geo_presentation_service) -> dict:
    hydrated = deepcopy(run)
    response = hydrated.get("response")
    if isinstance(response, dict):
        hydrated["response"] = _hydrate_legacy_visual(response, geo_presentation_service)

    latest_run = hydrated.get("latest_run")
    if isinstance(latest_run, dict):
        latest_response = latest_run.get("response")
        if isinstance(latest_response, dict):
            latest_run["response"] = _hydrate_legacy_visual(latest_response, geo_presentation_service)
            hydrated["latest_run"] = latest_run
    return hydrated


def build_router(
    *,
    planner_service,
    memory_service,
    session_run_repository,
    tool_service,
    image_generation_service,
    geo_presentation_service,
) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/api/debug/storage")
    def storage_status() -> dict:
        return get_storage_status()

    @router.post("/api/demo/plan", response_model=DemoPlanResponse)
    def demo_plan(request: DemoPlanRequest) -> DemoPlanResponse:
        payload = planner_service.run(user_id=request.user_id, session_id=request.session_id, message=request.message)
        return DemoPlanResponse(**payload)

    @router.post("/api/images/attraction/generate", response_model=AttractionImageGenerateResponse)
    def generate_attraction_image(request: AttractionImageGenerateRequest) -> AttractionImageGenerateResponse:
        if not image_generation_service.enabled():
            raise HTTPException(status_code=503, detail="image generation service is not configured")
        try:
            payload = image_generation_service.generate_attraction_image(
                destination=request.destination,
                attraction_name=request.attraction_name,
                attraction_type=request.attraction_type,
                area=request.area,
                style=request.style,
                aspect=request.aspect,
                time_of_day=request.time_of_day,
                weather_hint=request.weather_hint,
                user_preferences=request.user_preferences,
                size=request.size,
                quality=request.quality,
                output_format=request.output_format,
                force_regenerate=request.force_regenerate,
            )
        except ImageGenerationError as exc:
            raise HTTPException(
                status_code=exc.status_code or 502,
                detail={
                    "message": str(exc),
                    "request_id": exc.request_id,
                    "error_code": exc.error_code,
                    "error_type": exc.error_type,
                },
            ) from exc
        return AttractionImageGenerateResponse(**payload)

    @router.get("/api/demo/session/{session_id}")
    def get_session(session_id: str) -> dict:
        run = session_run_repository.get_run(session_id=session_id)
        if run is None:
            raise HTTPException(status_code=404, detail="session not found")
        return _hydrate_legacy_run_visual(run, geo_presentation_service)

    @router.get("/api/demo/sessions", response_model=list[SessionRunListItem])
    def list_sessions(user_id: str | None = None, limit: int = 20) -> list[SessionRunListItem]:
        runs = [
            _hydrate_legacy_run_visual(run, geo_presentation_service)
            for run in session_run_repository.list_runs(user_id=user_id, limit=limit)
        ]
        items: list[SessionRunListItem] = []
        for run in runs:
            response = run.get("response", {})
            final_plan = response.get("final_plan", {})
            summary = final_plan.get("summary", {})
            llm_output = response.get("llm_output", {})
            items.append(
                SessionRunListItem(
                    session_id=run["session_id"],
                    user_id=run["user_id"],
                    request_text=run["request_text"],
                    created_at=run["created_at"],
                    destination=summary.get("destinationCity"),
                    days=summary.get("days"),
                    summary=llm_output.get("llm_summary") or final_plan.get("consultingAnswer"),
                    task_type=(response.get("task_profile") or {}).get("task_type"),
                )
            )
        return items

    @router.delete("/api/demo/session/{session_id}")
    def delete_session(session_id: str) -> dict[str, str]:
        deleted = session_run_repository.delete_run(session_id=session_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="session not found")
        return {"status": "ok"}

    @router.get("/api/skills", response_model=list[SkillDefinitionItem])
    def list_skills() -> list[SkillDefinitionItem]:
        return [SkillDefinitionItem(**item) for item in tool_service.list_skills()]

    @router.post("/api/skills/{skill_id}/invoke")
    def invoke_skill(skill_id: str, request: SkillInvokeRequest) -> dict:
        try:
            return tool_service.run_skill(skill_id=skill_id, payload=request.payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/api/memory/{user_id}", response_model=list[MemoryItem])
    def list_memory(user_id: str) -> list[MemoryItem]:
        return [MemoryItem(**item) for item in memory_service.list_memories(user_id=user_id)]

    @router.put("/api/memory/{user_id}")
    def upsert_memory(user_id: str, request: MemoryUpsertRequest) -> dict[str, str]:
        memory_service.upsert_memory(user_id=user_id, key=request.key, value=request.value, scope=request.scope)
        return {"status": "ok"}

    return router
