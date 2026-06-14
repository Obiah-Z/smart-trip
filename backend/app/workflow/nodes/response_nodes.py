from __future__ import annotations

from typing import Any

from app.workflow.state import TripPlanningState
from app.workflow.trace import append_trace, attach_workflow_trace


class ResponseNodes:
    """响应生成与持久化节点。

    这里把前面阶段产物转换成前端需要的最终响应：轻咨询直接返回短答案，完整规划会补充
    地图/图片资产、LLM 摘要、Memory 写回和会话运行记录。
    """

    def __init__(self, planner_service: Any) -> None:
        self._planner_service = planner_service

    def build_consulting_response(self, state: TripPlanningState) -> dict[str, Any]:
        """为天气、景点推荐等轻咨询生成响应，并绕过多 Agent 规划。"""
        service = self._planner_service
        response = service._build_consulting_response(
            resolved_session_id=state["resolved_session_id"],
            user_id=state["user_id"],
            message=state["message"],
            task_profile=state["task_profile"],
            session_context=state["session_context"],
            structured_constraints=state["structured_constraints"],
            memory_context=state["memory_context"],
            retrieval_context=state["retrieval_context"],
            selected_skills=state["selected_skills"],
            tool_results=state["tool_results"],
        )
        trace = append_trace(
            state,
            node="build_consulting_response",
            status="done",
            summary="识别为轻量咨询，生成咨询响应并结束本轮。",
            metadata={"consulting_type": response.get("final_plan", {}).get("consultingType")},
        )
        return {
            "response": attach_workflow_trace(response=response, trace=trace),
            "workflow_trace": trace,
        }

    def enrich_and_summarize(self, state: TripPlanningState) -> dict[str, Any]:
        """为完整规划结果补充地图/图片展示数据、LLM 摘要和长期偏好写回。"""
        service = self._planner_service
        final_plan = service._geo_presentation_service.enrich_final_plan(
            final_plan=state["final_plan"],
            structured_constraints=state["structured_constraints"],
        )
        final_plan = service._image_generation_service.enrich_plan_visual_assets(final_plan=final_plan)
        llm_output = service._openai_client.generate_plan_summary(
            assembled_context=state["assembled_context"],
            final_plan=final_plan,
        )
        memory_writeback_source = service._resolve_memory_writeback_source(state=state)
        memory_updates = service._memory_service.persist_extracted_signals(
            user_id=state["user_id"],
            signal_names=[item["name"] for item in memory_writeback_source["signals"]],
            pace=memory_writeback_source["pace"],
            pace_explicit=memory_writeback_source["pace_explicit"],
            source_text=memory_writeback_source["source_text"],
            session_id=state.get("resolved_session_id"),
            followup_replan=bool(state["structured_constraints"].get("_followup_replan")),
        )
        return {
            "final_plan": final_plan,
            "llm_output": llm_output,
            "memory_updates": memory_updates,
            "workflow_trace": append_trace(
                state,
                node="enrich_and_summarize",
                status="done",
                summary="完成地图/图片增强、LLM 摘要与 Memory 写回。",
                metadata={
                    "llm_mode": llm_output.get("mode"),
                    "memory_updates": len(memory_updates),
                },
            ),
        }

    def persist_planning_response(self, state: TripPlanningState) -> dict[str, Any]:
        """统一组装 API 响应并保存本轮运行记录。"""
        service = self._planner_service
        response = {
            "session_id": state["resolved_session_id"],
            "user_input": state["message"],
            "task_profile": state["task_profile"],
            "session_context": state["session_context"],
            "structured_constraints": state["structured_constraints"],
            "memory_context": state["memory_context"],
            "memory_updates": state["memory_updates"],
            "retrieval_context": state["retrieval_context"],
            "available_skills": service._tool_service.list_skills(),
            "selected_skills": state["selected_skills"],
            "tool_results": state["tool_results"],
            "agent_outputs": [
                {"agent": item.name, "summary": item.summary, "payload": item.payload}
                for item in state["agent_outputs"]
            ],
            "assembled_context": state["assembled_context"],
            "final_plan": state["final_plan"],
            "llm_output": state["llm_output"],
        }
        trace = append_trace(
            state,
            node="persist_planning_response",
            status="done",
            summary="完成会话运行记录持久化。",
            metadata={"session_id": state["resolved_session_id"]},
        )
        response = attach_workflow_trace(response=response, trace=trace)
        service._session_run_repository.save_run(
            session_id=state["resolved_session_id"],
            user_id=state["user_id"],
            request_text=state["message"],
            response=response,
        )
        return {
            "response": response,
            "workflow_trace": trace,
        }
