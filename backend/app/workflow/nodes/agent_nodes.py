from __future__ import annotations

from typing import Any

from app.agents.base import AgentExecutionResult
from app.workflow.state import TripPlanningState
from app.workflow.trace import append_trace


class AgentNodes:
    """LangGraph 中真实拆分的多 Agent 节点。

    每个方法只执行一个 Agent，并把该 Agent 的输出写回共享 state。这样 Stage Trace
    能看到 planner/retriever/executor/reviewer 的独立节点，而不是只有一个 run_agents。
    """

    def __init__(self, planner_service: Any) -> None:
        self._planner_service = planner_service

    def run_planner_agent(self, state: TripPlanningState) -> dict[str, Any]:
        """执行需求拆解 Agent，生成任务拆解和共享状态投影。"""
        result = self._planner_service._agent_service.run_planner(
            constraints=state["structured_constraints"],
            memory_context=state["memory_context"],
            task_profile=state["task_profile"],
        )
        return {
            "planner_agent_output": result,
            "agent_outputs": self._append_agent_output(state=state, result=result),
            "workflow_trace": append_trace(
                state,
                node="planner_agent",
                status="done",
                summary=result.summary,
                metadata={
                    "agent": result.name,
                    "tasks": len(result.payload.get("task_breakdown", [])),
                    "memory_highlights": len(result.payload.get("memory_highlights", [])),
                },
            ),
        }

    def run_retriever_agent(self, state: TripPlanningState) -> dict[str, Any]:
        """执行信息整理 Agent，汇总 RAG 与工具证据。"""
        result = self._planner_service._agent_service.run_retriever(
            retrieval_context=state["retrieval_context"],
            tool_results=state["tool_results"],
        )
        return {
            "retriever_agent_output": result,
            "agent_outputs": self._append_agent_output(state=state, result=result),
            "workflow_trace": append_trace(
                state,
                node="retriever_agent",
                status="done",
                summary=result.summary,
                metadata={
                    "agent": result.name,
                    "documents": len(state["retrieval_context"].get("retrieved_documents", [])),
                    "tools": len(state["tool_results"]),
                },
            ),
        }

    def run_executor_agent(self, state: TripPlanningState) -> dict[str, Any]:
        """执行方案生成 Agent，并把输出作为候选 final_plan。"""
        planner_output = state["planner_agent_output"]
        result = self._planner_service._agent_service.run_executor(
            constraints=state["structured_constraints"],
            tool_results=state["tool_results"],
            planner_payload=planner_output.payload,
            retrieval_context=state["retrieval_context"],
        )
        return {
            "executor_agent_output": result,
            "agent_outputs": self._append_agent_output(state=state, result=result),
            "final_plan": result.payload,
            "workflow_trace": append_trace(
                state,
                node="executor_agent",
                status="done",
                summary=result.summary,
                metadata={
                    "agent": result.name,
                    "days": len(result.payload.get("days", [])),
                    "budget": result.payload.get("summary", {}).get("totalBudget"),
                },
            ),
        }

    def run_reviewer_agent(self, state: TripPlanningState) -> dict[str, Any]:
        """执行 Agent 层结果检查，输出软校验结论。"""
        executor_output = state["executor_agent_output"]
        result = self._planner_service._agent_service.run_reviewer(
            constraints=state["structured_constraints"],
            executor_payload=executor_output.payload,
            tool_results=state["tool_results"],
        )
        return {
            "reviewer_agent_output": result,
            "agent_outputs": self._append_agent_output(state=state, result=result),
            "workflow_trace": append_trace(
                state,
                node="reviewer_agent",
                status="done" if result.payload.get("final_status") == "approved" else "warn",
                summary=result.summary,
                metadata={
                    "agent": result.name,
                    "final_status": result.payload.get("final_status"),
                    "within_budget": result.payload.get("within_budget"),
                    "pace_aligned": result.payload.get("pace_aligned"),
                },
            ),
        }

    def _append_agent_output(
        self,
        *,
        state: TripPlanningState,
        result: AgentExecutionResult,
    ) -> list[AgentExecutionResult]:
        return [*state.get("agent_outputs", []), result]
