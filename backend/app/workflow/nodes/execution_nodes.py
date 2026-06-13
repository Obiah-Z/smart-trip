from __future__ import annotations

from typing import Any

from app.workflow.reviewer import PlanReviewer
from app.workflow.state import TripPlanningState
from app.workflow.trace import append_trace


class ExecutionNodes:
    """Skill、Agent 和 Reviewer 执行节点。

    这一组节点会真正调用外部能力或内部业务能力。输入阶段只判断“该不该做”，这里负责
    根据任务画像执行 Skill、多 Agent 规划，并对最终计划做一致性校验和必要修复。
    """

    def __init__(self, planner_service: Any, reviewer: PlanReviewer) -> None:
        self._planner_service = planner_service
        self._reviewer = reviewer

    def run_skills(self, state: TripPlanningState) -> dict[str, Any]:
        """按语义选择并执行 Skill。

        selected_skill_items 是选择器的解释结果；selected_skills 是给前端和 Context 使用的
        可展示结构；tool_results 是后续 RAG/Agent/咨询回答真正消费的工具输出。
        """
        service = self._planner_service
        task_profile = state["task_profile"]
        structured_constraints = state["structured_constraints"]
        if task_profile["needs_tools"]:
            selected_skill_items = service._skill_selection_service.select(
                user_input=state["effective_message"],
                structured_constraints=structured_constraints,
                available_skills=service._tool_service.list_skill_definitions(),
            )
        else:
            selected_skill_items = []

        tool_results: list[dict[str, Any]] = []
        selected_skills: list[dict[str, Any]] = []
        for item in selected_skill_items:
            payload = service._tool_service.build_payload(
                skill_id=item.skill_id,
                structured_constraints=structured_constraints,
                tool_results=tool_results,
            )
            tool_result = service._tool_service.run_skill(skill_id=item.skill_id, payload=payload)
            tool_results.append(tool_result)
            selected_skills.append(
                {
                    "skill_id": item.skill_id,
                    "display_name": tool_result["display_name"],
                    "reason": item.reason,
                    "source": item.source,
                    "payload": payload,
                }
            )

        return {
            "selected_skill_items": selected_skill_items,
            "selected_skills": selected_skills,
            "tool_results": tool_results,
            "workflow_trace": append_trace(
                state,
                node="run_skills",
                status="done" if selected_skills else "bypass",
                summary="完成 Skill 选择与工具执行。" if selected_skills else "当前任务没有执行 Skill。",
                metadata={
                    "needs_tools": task_profile["needs_tools"],
                    "skills": [item["skill_id"] for item in selected_skills],
                    "tool_results": len(tool_results),
                },
            ),
        }

    def run_agents(self, state: TripPlanningState) -> dict[str, Any]:
        """执行多 Agent 协作，并把 executor_agent 的 payload 作为候选最终方案。"""
        service = self._planner_service
        agent_outputs = service._agent_service.run(
            constraints=state["structured_constraints"],
            retrieval_context=state["retrieval_context"],
            tool_results=state["tool_results"],
            memory_context=state["memory_context"],
            task_profile=state["task_profile"],
        )
        final_plan = next(item.payload for item in agent_outputs if item.name == "executor_agent")
        return {
            "agent_outputs": agent_outputs,
            "final_plan": final_plan,
            "workflow_trace": append_trace(
                state,
                node="run_agents",
                status="done",
                summary="完成 planner/retriever/executor/reviewer 多 Agent 协作。",
                metadata={"agents": [item.name for item in agent_outputs]},
            ),
        }

    def review_plan(self, state: TripPlanningState) -> dict[str, Any]:
        """检查最终方案是否违反硬约束，例如排除景点仍被安排进路线。"""
        review = self._reviewer.build_review(
            final_plan=state["final_plan"],
            structured_constraints=state["structured_constraints"],
        )
        status = "warn" if review["needs_attention"] else "done"
        return {
            "plan_review": review,
            "workflow_trace": append_trace(
                state,
                node="review_plan",
                status=status,
                summary=review["summary"],
                metadata={
                    "needs_repair": review["needs_repair"],
                    "needs_attention": review["needs_attention"],
                    "issues": [item["name"] for item in review["issues"]],
                },
            ),
        }

    def repair_plan(self, state: TripPlanningState) -> dict[str, Any]:
        """对 Reviewer 发现的可修复问题做局部修复，而不是整条链路重跑。"""
        final_plan = self._reviewer.apply_repairs(
            final_plan=state["final_plan"],
            structured_constraints=state["structured_constraints"],
            review=state["plan_review"],
        )
        repaired_review = self._reviewer.build_review(
            final_plan=final_plan,
            structured_constraints=state["structured_constraints"],
        )
        repair_notes = self._reviewer.build_repair_notes(
            original_review=state["plan_review"],
            repaired_review=repaired_review,
        )
        final_plan = {
            **final_plan,
            "workflowRepair": {
                "applied": True,
                "notes": repair_notes,
                "remainingIssues": repaired_review["issues"],
            },
        }
        return {
            "final_plan": final_plan,
            "plan_review": repaired_review,
            "workflow_trace": append_trace(
                state,
                node="repair_plan",
                status="done" if not repaired_review["needs_repair"] else "warn",
                summary="已根据 LangGraph Reviewer 结果完成局部修复。",
                metadata={
                    "notes": repair_notes,
                    "remaining_issues": [item["name"] for item in repaired_review["issues"]],
                },
            ),
        }
