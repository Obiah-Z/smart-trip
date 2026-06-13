from __future__ import annotations

from typing import Any

from app.workflow.state import TripPlanningState


def append_trace(
    state: TripPlanningState,
    *,
    node: str,
    status: str,
    summary: str,
    metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    trace = list(state.get("workflow_trace", []))
    trace.append(
        {
            "node": node,
            "status": status,
            "summary": summary,
            "metadata": metadata or {},
        }
    )
    return trace


def attach_workflow_trace(*, response: dict[str, Any], trace: list[dict[str, Any]]) -> dict[str, Any]:
    assembled_context = dict(response.get("assembled_context") or {})
    runtime_context = dict(assembled_context.get("runtime_context") or {})
    runtime_context["workflow_engine"] = "langgraph"
    runtime_context["workflow_trace"] = trace
    assembled_context["runtime_context"] = runtime_context
    return {
        **response,
        "assembled_context": assembled_context,
    }
