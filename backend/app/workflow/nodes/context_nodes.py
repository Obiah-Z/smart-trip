from __future__ import annotations

from typing import Any

from app.workflow.state import TripPlanningState
from app.workflow.trace import append_trace


class ContextNodes:
    def __init__(self, planner_service: Any) -> None:
        self._planner_service = planner_service

    def load_memory(self, state: TripPlanningState) -> dict[str, Any]:
        service = self._planner_service
        memory_context_model = service._memory_service.load_context(
            user_id=state["user_id"],
            short_term_state=state["structured_constraints"],
        )
        memory_selection = service._memory_injection_service.select(
            long_term_memory=memory_context_model.long_term_memory,
            structured_constraints=state["structured_constraints"],
            user_input=state["message"],
        )
        memory_context = {
            "long_term_memory": memory_context_model.long_term_memory,
            "relevant_long_term_memory": memory_selection["relevant_long_term_memory"],
            "short_term_state": memory_context_model.short_term_state,
            "selection_reasons": memory_selection["selection_reasons"],
            "dropped_memory_count": memory_selection["dropped_memory_count"],
        }
        return {
            "memory_context": memory_context,
            "workflow_trace": append_trace(
                state,
                node="load_memory",
                status="done",
                summary="完成长期记忆读取与相关性筛选。",
                metadata={
                    "memory_total": len(memory_context["long_term_memory"]),
                    "memory_injected": len(memory_context["relevant_long_term_memory"]),
                },
            ),
        }

    def retrieve_knowledge(self, state: TripPlanningState) -> dict[str, Any]:
        service = self._planner_service
        task_profile = state["task_profile"]
        structured_constraints = state["structured_constraints"]
        if task_profile["needs_rag"]:
            retrieval_context = service._retrieval_service.retrieve(
                destination=structured_constraints["destination"],
                preferences=structured_constraints["preferences"],
                days=state["resolved_days"],
                budget=state["resolved_budget"],
                pace=structured_constraints["pace"],
                user_input=state["effective_message"],
            )
            status = "done"
            summary = "完成 RAG 知识检索与注入。"
        else:
            retrieval_context = {
                "query": "",
                "query_rewrite": {"source": "none", "query": "", "query_terms": [], "focus_keywords": [], "steps": []},
                "retrieval_steps": ["当前问题无需额外知识增强"],
                "ranking_signals": [],
                "retrieved_documents": [],
                "injected_knowledge": [],
            }
            status = "bypass"
            summary = "当前任务不需要 RAG，跳过检索。"
        return {
            "retrieval_context": retrieval_context,
            "workflow_trace": append_trace(
                state,
                node="retrieve_knowledge",
                status=status,
                summary=summary,
                metadata={
                    "needs_rag": task_profile["needs_rag"],
                    "documents": len(retrieval_context["retrieved_documents"]),
                },
            ),
        }

    def assemble_context(self, state: TripPlanningState) -> dict[str, Any]:
        service = self._planner_service
        assembled_context = service._context_assembler.assemble(
            user_input=state["message"],
            task_profile=state["task_profile"],
            session_context=state["session_context"],
            structured_constraints=state["structured_constraints"],
            memory_context=state["memory_context"],
            retrieval_context=state["retrieval_context"],
            selected_skills=state["selected_skills"],
            tool_results=state["tool_results"],
        )
        return {
            "assembled_context": assembled_context,
            "workflow_trace": append_trace(
                state,
                node="assemble_context",
                status="done",
                summary="完成模型上下文组装。",
                metadata={"prompt_sections": len(assembled_context.get("prompt_sections", []))},
            ),
        }
