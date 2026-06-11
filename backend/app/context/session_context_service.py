from __future__ import annotations

from typing import Any

from app.db.repositories import SessionRunRepository


class SessionContextService:
    def __init__(self, repository: SessionRunRepository) -> None:
        self._repository = repository

    def load(self, *, session_id: str | None) -> dict[str, Any]:
        if not session_id:
            return {
                "session_found": False,
                "history_messages": [],
                "latest_structured_constraints": None,
                "latest_summary": None,
                "initial_request_text": None,
                "session_baseline_constraints": None,
            }

        session_runs = self._repository.list_session_runs(session_id=session_id)
        if not session_runs:
            return {
                "session_found": False,
                "history_messages": [],
                "latest_structured_constraints": None,
                "latest_summary": None,
                "initial_request_text": None,
                "session_baseline_constraints": None,
            }

        latest_run = session_runs[0]
        display_run = self._repository.get_run(session_id=session_id) or latest_run
        latest_response = latest_run.get("response", {})
        response = display_run.get("response", {})
        stored_session_context = response.get("session_context") or latest_response.get("session_context") or {}
        final_plan = response.get("final_plan", {})
        summary = final_plan.get("summary", {})
        latest_summary = None
        destination = summary.get("destinationCity")
        days = summary.get("days")
        if destination and days:
            latest_summary = f"上一次在该会话中生成了 {destination} {days} 天方案。"

        history_messages = [run.get("request_text", "") for run in reversed(session_runs) if run.get("request_text")]
        if not history_messages:
            fallback_history = stored_session_context.get("history_messages")
            if isinstance(fallback_history, list):
                history_messages = [item for item in fallback_history if isinstance(item, str) and item.strip()]

        initial_request_text = stored_session_context.get("initial_request_text")
        if not initial_request_text and history_messages:
            initial_request_text = history_messages[0]

        return {
            "session_found": True,
            "history_messages": history_messages,
            "latest_structured_constraints": response.get("structured_constraints"),
            "latest_summary": latest_summary,
            "latest_task_profile": response.get("task_profile"),
            "latest_final_plan": response.get("final_plan", {}),
            "latest_memory_updates": response.get("memory_updates", []),
            "initial_request_text": initial_request_text,
            "session_baseline_constraints": stored_session_context.get("session_baseline_constraints"),
            "latest_run_task_profile": latest_response.get("task_profile"),
            "latest_run_final_plan": latest_response.get("final_plan", {}),
            "latest_run_structured_constraints": latest_response.get("structured_constraints"),
        }
