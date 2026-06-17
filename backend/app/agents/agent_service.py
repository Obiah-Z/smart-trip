from __future__ import annotations

from typing import Any

from app.agents.base import AgentExecutionResult
from app.agents.executor_agent import ExecutorAgent
from app.agents.planner_agent import PlannerAgent
from app.agents.retriever_agent import RetrieverAgent
from app.agents.reviewer_agent import ReviewerAgent


class AgentService:
    """多 Agent 协作的组合门面。

    具体职责已经拆到独立 Agent 类中；这里只保留四个 Agent 实例和独立调用入口。
    LangGraph 节点会分别调用 run_planner/run_retriever/run_executor/run_reviewer。
    """

    def __init__(self) -> None:
        self._planner_agent = PlannerAgent()
        self._retriever_agent = RetrieverAgent()
        self._executor_agent = ExecutorAgent()
        self._reviewer_agent = ReviewerAgent()

    def run_planner(
        self,
        *,
        constraints: dict[str, Any],
        memory_context: dict[str, Any],
        task_profile: dict[str, Any],
    ) -> AgentExecutionResult:
        """执行需求拆解 Agent。"""
        return self._planner_agent.run(
            constraints=constraints,
            memory_context=memory_context,
            task_profile=task_profile,
        )

    def run_retriever(
        self,
        *,
        retrieval_context: dict[str, Any],
        tool_results: list[dict[str, Any]],
    ) -> AgentExecutionResult:
        """执行信息整理 Agent。"""
        return self._retriever_agent.run(retrieval_context=retrieval_context, tool_results=tool_results)

    def run_executor(
        self,
        *,
        constraints: dict[str, Any],
        tool_results: list[dict[str, Any]],
        planner_payload: dict[str, Any],
        retrieval_context: dict[str, Any],
    ) -> AgentExecutionResult:
        """执行方案生成 Agent。"""
        return self._executor_agent.run(
            constraints=constraints,
            tool_results=tool_results,
            planner_payload=planner_payload,
            retrieval_context=retrieval_context,
        )

    def run_reviewer(
        self,
        *,
        constraints: dict[str, Any],
        executor_payload: dict[str, Any],
        tool_results: list[dict[str, Any]],
    ) -> AgentExecutionResult:
        """执行结果检查 Agent。"""
        return self._reviewer_agent.run(
            constraints=constraints,
            executor_payload=executor_payload,
            tool_results=tool_results,
        )
