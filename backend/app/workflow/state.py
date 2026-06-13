from __future__ import annotations

from typing import Any, TypedDict


class TripPlanningState(TypedDict, total=False):
    user_id: str
    session_id: str | None
    message: str
    active_session_id: str | None
    resolved_session_id: str
    slots: Any
    session_context: dict[str, Any]
    revision_intent: Any
    effective_message: str
    structured_constraints: dict[str, Any]
    resolved_days: int | None
    resolved_budget: int
    task_profile: dict[str, Any]
    missing_fields: list[str]
    memory_context: dict[str, Any]
    retrieval_context: dict[str, Any]
    selected_skill_items: list[Any]
    selected_skills: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    assembled_context: dict[str, Any]
    agent_outputs: list[Any]
    final_plan: dict[str, Any]
    plan_review: dict[str, Any]
    llm_output: dict[str, Any]
    memory_updates: list[dict[str, Any]]
    response: dict[str, Any]
    workflow_trace: list[dict[str, Any]]
