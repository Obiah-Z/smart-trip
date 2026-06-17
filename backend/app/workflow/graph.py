from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from app.workflow.nodes import AgentNodes, ContextNodes, ExecutionNodes, InputNodes, ResponseNodes
from app.workflow.reviewer import PlanReviewer
from app.workflow.state import TripPlanningState


class TripPlanningWorkflow:
    """旅行规划主流程的 LangGraph 拓扑。

    这个类只负责声明“节点如何串起来”和“分支条件如何跳转”，不承载具体业务逻辑。
    具体的槽位提取、Memory、RAG、Skill、Agent、持久化都放在各个 node 或 PlannerService
    依赖中，便于开发者按阶段排查链路。
    """

    def __init__(self, planner_service: Any) -> None:
        self._planner_service = planner_service
        self._reviewer = PlanReviewer()
        self._input_nodes = InputNodes(planner_service)
        self._context_nodes = ContextNodes(planner_service)
        self._execution_nodes = ExecutionNodes(planner_service, self._reviewer)
        self._agent_nodes = AgentNodes(planner_service)
        self._response_nodes = ResponseNodes(planner_service)
        self._graph = self._build_graph()

    def run(self, *, user_id: str, session_id: str | None, message: str) -> dict[str, Any]:
        """以一次用户输入为起点执行完整图，并只向上层返回最终 API 响应。"""
        state = self._graph.invoke(
            {
                "user_id": user_id,
                "session_id": session_id,
                "message": message,
                "workflow_trace": [],
            }
        )
        return state["response"]

    def _build_graph(self):
        """声明工作流节点和条件边。

        主路径：
        prepare_request -> resolve_constraints -> load_memory -> retrieve_knowledge ->
        run_skills -> assemble_context -> planner_agent -> retriever_agent ->
        executor_agent -> reviewer_agent -> review_plan ->
        enrich_and_summarize -> persist_planning_response。

        特殊路径：
        - 缺少目的地/天数时直接进入 clarification 响应。
        - 轻量咨询在 Skill/RAG 后直接生成咨询回答，不进入多 Agent 规划。
        - Reviewer 发现硬约束冲突时进入 repair_plan 做局部修复。
        """
        graph = StateGraph(TripPlanningState)
        graph.add_node("prepare_request", self._input_nodes.prepare_request)
        graph.add_node("resolve_constraints", self._input_nodes.resolve_constraints)
        graph.add_node("build_clarification_response", self._input_nodes.build_clarification_response)
        graph.add_node("load_memory", self._context_nodes.load_memory)
        graph.add_node("retrieve_knowledge", self._context_nodes.retrieve_knowledge)
        graph.add_node("run_skills", self._execution_nodes.run_skills)
        graph.add_node("build_consulting_response", self._response_nodes.build_consulting_response)
        graph.add_node("assemble_context", self._context_nodes.assemble_context)
        graph.add_node("planner_agent", self._agent_nodes.run_planner_agent)
        graph.add_node("retriever_agent", self._agent_nodes.run_retriever_agent)
        graph.add_node("executor_agent", self._agent_nodes.run_executor_agent)
        graph.add_node("reviewer_agent", self._agent_nodes.run_reviewer_agent)
        graph.add_node("review_plan", self._execution_nodes.review_plan)
        graph.add_node("repair_plan", self._execution_nodes.repair_plan)
        graph.add_node("enrich_and_summarize", self._response_nodes.enrich_and_summarize)
        graph.add_node("persist_planning_response", self._response_nodes.persist_planning_response)

        graph.add_edge(START, "prepare_request")
        graph.add_edge("prepare_request", "resolve_constraints")
        graph.add_conditional_edges(
            "resolve_constraints",
            self._route_after_constraints,
            {
                "clarify": "build_clarification_response",
                "continue": "load_memory",
            },
        )
        graph.add_edge("build_clarification_response", END)
        graph.add_edge("load_memory", "retrieve_knowledge")
        graph.add_edge("retrieve_knowledge", "run_skills")
        graph.add_conditional_edges(
            "run_skills",
            self._route_after_skills,
            {
                "consulting": "build_consulting_response",
                "planning": "assemble_context",
            },
        )
        graph.add_edge("build_consulting_response", END)
        graph.add_edge("assemble_context", "planner_agent")
        graph.add_edge("planner_agent", "retriever_agent")
        graph.add_edge("retriever_agent", "executor_agent")
        graph.add_edge("executor_agent", "reviewer_agent")
        graph.add_edge("reviewer_agent", "review_plan")
        graph.add_conditional_edges(
            "review_plan",
            self._route_after_review,
            {
                "repair": "repair_plan",
                "continue": "enrich_and_summarize",
            },
        )
        graph.add_edge("repair_plan", "enrich_and_summarize")
        graph.add_edge("enrich_and_summarize", "persist_planning_response")
        graph.add_edge("persist_planning_response", END)
        return graph.compile()

    def _route_after_constraints(self, state: TripPlanningState) -> Literal["clarify", "continue"]:
        """约束仍不完整时停止规划，先让用户补充关键信息。"""
        return "clarify" if state.get("missing_fields") else "continue"

    def _route_after_skills(self, state: TripPlanningState) -> Literal["consulting", "planning"]:
        """轻量咨询不需要完整路线规划，避免天气/景点问答走慢链路。"""
        task_profile = state.get("task_profile") or {}
        return "consulting" if task_profile.get("task_type") == "travel_consulting" else "planning"

    def _route_after_review(self, state: TripPlanningState) -> Literal["repair", "continue"]:
        """Reviewer 只在发现可自动修复的硬问题时触发 repair 节点。"""
        review = state.get("plan_review") or {}
        return "repair" if review.get("needs_repair") else "continue"
