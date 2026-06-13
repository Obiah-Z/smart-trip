from __future__ import annotations

import uuid
from typing import Any

from app.workflow.state import TripPlanningState
from app.workflow.trace import append_trace, attach_workflow_trace


class InputNodes:
    """输入与路由前置节点。

    这一组节点负责把自然语言请求转成后续节点可消费的结构化状态，包括槽位、会话、
    追问意图、任务类型和缺失字段。它们不做 RAG/Tool/Agent 执行。
    """

    def __init__(self, planner_service: Any) -> None:
        self._planner_service = planner_service

    def prepare_request(self, state: TripPlanningState) -> dict[str, Any]:
        """提取槽位并确定本轮应该挂靠的 session。

        如果前端没有显式传 session_id，但用户输入明显是“继续修改上一份规划”，这里会尝试
        自动恢复最近一次规划会话，避免追问时丢失目的地/天数等基线条件。
        """
        service = self._planner_service
        message = state["message"]
        user_id = state["user_id"]
        slots = service._slot_extractor.extract(message)
        active_session_id = state.get("session_id") or service._resolve_implicit_session_id(
            user_id=user_id,
            message=message,
            slots=slots,
        )
        resolved_session_id = active_session_id or f"session-{uuid.uuid4().hex[:8]}"
        session_context = service._session_context_service.load(session_id=active_session_id)
        return {
            "slots": slots,
            "active_session_id": active_session_id,
            "resolved_session_id": resolved_session_id,
            "session_context": session_context,
            "workflow_trace": append_trace(
                state,
                node="prepare_request",
                status="done",
                summary="完成槽位提取与会话上下文加载。",
                metadata={
                    "session_found": session_context.get("session_found", False),
                    "implicit_session": bool(active_session_id and not state.get("session_id")),
                },
            ),
        }

    def resolve_constraints(self, state: TripPlanningState) -> dict[str, Any]:
        """合并当前输入、历史会话和修订意图，得到本轮有效约束。

        这是任务路由前最关键的节点：它决定本轮是缺信息需要澄清、简单咨询可轻量回答，
        还是需要进入完整旅行规划链路。
        """
        service = self._planner_service
        message = state["message"]
        slots = state["slots"]
        session_context = state["session_context"]
        revision_intent = service._revision_intent_resolver.analyze(
            message=message,
            slots=slots,
            session_context=session_context,
        )
        effective_message = service._resolve_effective_message(
            message=message,
            slots=slots,
            session_context=session_context,
        )
        structured_constraints = service._resolve_structured_constraints(
            slots=slots,
            session_context=session_context,
            message=message,
            revision_intent=revision_intent,
        )
        structured_constraints = service._expand_structured_constraints(
            structured_constraints=structured_constraints,
        )
        task_profile_model = service._resolve_task_profile(
            message=effective_message,
            slots=slots,
            structured_constraints=structured_constraints,
            session_context=session_context,
            revision_intent=revision_intent,
        )
        task_profile = {
            "task_type": task_profile_model.task_type,
            "complexity": task_profile_model.complexity,
            "needs_rag": task_profile_model.needs_rag,
            "needs_tools": task_profile_model.needs_tools,
            "needs_multi_agent": task_profile_model.needs_multi_agent,
            "intent_summary": task_profile_model.intent_summary,
            "evidence": task_profile_model.evidence,
        }
        finalized_session_context = service._finalize_session_context(
            session_context={
                **session_context,
                "effective_structured_constraints": structured_constraints,
                "revision_intent": revision_intent.to_dict(),
            },
            structured_constraints=structured_constraints,
            message=message,
        )
        missing_fields = service._resolve_missing_fields(
            task_profile=task_profile,
            structured_constraints=structured_constraints,
            session_context=finalized_session_context,
        )
        return {
            "revision_intent": revision_intent,
            "effective_message": effective_message,
            "structured_constraints": structured_constraints,
            "resolved_days": structured_constraints["days"],
            "resolved_budget": structured_constraints["budget"],
            "task_profile": task_profile,
            "session_context": finalized_session_context,
            "missing_fields": missing_fields,
            "workflow_trace": append_trace(
                state,
                node="resolve_constraints",
                status="warn" if missing_fields else "done",
                summary="完成追问意图识别、约束合并与任务路由。",
                metadata={
                    "task_type": task_profile["task_type"],
                    "missing_fields": missing_fields,
                    "followup_replan": structured_constraints.get("_followup_replan", False),
                },
            ),
        }

    def build_clarification_response(self, state: TripPlanningState) -> dict[str, Any]:
        """生成澄清问题并结束本轮图执行。"""
        service = self._planner_service
        response = service._build_clarification_response(
            resolved_session_id=state["resolved_session_id"],
            user_id=state["user_id"],
            message=state["message"],
            task_profile=state["task_profile"],
            session_context=state["session_context"],
            structured_constraints=state["structured_constraints"],
            missing_fields=state["missing_fields"],
        )
        trace = append_trace(
            state,
            node="build_clarification_response",
            status="done",
            summary="信息不足，生成澄清响应并结束本轮。",
            metadata={"missing_fields": state["missing_fields"]},
        )
        return {
            "response": attach_workflow_trace(response=response, trace=trace),
            "workflow_trace": trace,
        }
