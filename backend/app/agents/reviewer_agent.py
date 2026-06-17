from __future__ import annotations

from typing import Any

from app.agents.base import AgentExecutionResult, TOOL_NAME_MAP, tool_result


class ReviewerAgent:
    """负责 Agent 层结果检查和软校验。"""

    def run(
        self,
        *,
        constraints: dict[str, Any],
        executor_payload: dict[str, Any],
        tool_results: list[dict[str, Any]],
    ) -> AgentExecutionResult:
        budget_limit = constraints.get("budget") or 0
        within_budget = True if budget_limit <= 0 else executor_payload["summary"]["totalBudget"] <= budget_limit + 600
        pace_aligned = constraints["pace"] != "intensive" or constraints["days"] >= 2
        weather_result = tool_result(tool_results, TOOL_NAME_MAP["weather"])
        weather_summary = weather_result["output"]["summary"] if weather_result is not None else "未查询天气"
        audit_result = tool_result(tool_results, TOOL_NAME_MAP["audit"])
        if audit_result is not None:
            audit_payload = audit_result["output"]
            final_status = "approved" if audit_payload.get("safe_to_present") else "needs_review"
            return AgentExecutionResult(
                name="reviewer_agent",
                summary=str(audit_payload.get("summary") or "已完成行程一致性审计。"),
                payload={
                    "within_budget": not any(
                        item.get("name") == "budget_within_limit"
                        for item in audit_payload.get("issues", [])
                    ),
                    "pace_aligned": not any(
                        item.get("name") == "pace_density_aligned"
                        for item in [*audit_payload.get("issues", []), *audit_payload.get("warnings", [])]
                    ),
                    "weather_summary": weather_summary,
                    "final_status": final_status,
                    "audit_status": audit_payload.get("audit_status"),
                    "validation_checks": audit_payload.get("passed_checks", []),
                    "issues": audit_payload.get("issues", []),
                    "warnings": audit_payload.get("warnings", []),
                    "recommendations": audit_payload.get("recommendations", []),
                },
            )
        summary = "方案已通过预算与节奏校验。" if within_budget and pace_aligned else "方案需要进一步人工调整。"
        payload = {
            "within_budget": within_budget,
            "pace_aligned": pace_aligned,
            "weather_summary": weather_summary,
            "final_status": "approved" if within_budget and pace_aligned else "needs_review",
            "validation_checks": [
                {"name": "budget_guardrail", "passed": within_budget},
                {"name": "pace_alignment", "passed": pace_aligned},
                {"name": "weather_context_available", "passed": weather_result is not None},
            ],
        }
        return AgentExecutionResult(name="reviewer_agent", summary=summary, payload=payload)
