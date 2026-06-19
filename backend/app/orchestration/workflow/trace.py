from __future__ import annotations

from typing import Any

from app.orchestration.workflow.state import TripPlanningState


def append_trace(
    state: TripPlanningState,
    *,
    node: str,
    status: str,
    summary: str,
    metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """追加一个节点级运行记录，供前端开发调试视图展示 Stage Trace。

    trace 是不可变式追加：每个节点返回新的 list，避免 LangGraph 状态在多个节点间被
    原地修改后出现难以追踪的副作用。
    """
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
    """把工作流 trace 注入 API 响应的 runtime_context。

    用户视图不会直接展示这些字段；开发调试视图依赖它判断当前请求是否走了澄清、
    轻咨询、RAG、Skill、多 Agent 或 repair 分支。
    """
    assembled_context = dict(response.get("assembled_context") or {})
    runtime_context = dict(assembled_context.get("runtime_context") or {})
    runtime_context["workflow_engine"] = "langgraph"
    runtime_context["workflow_trace"] = trace
    assembled_context["runtime_context"] = runtime_context
    return {
        **response,
        "assembled_context": assembled_context,
    }
