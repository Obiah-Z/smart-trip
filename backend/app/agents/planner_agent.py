from __future__ import annotations

from typing import Any

from app.agents.base import AgentExecutionResult


class PlannerAgent:
    """负责需求拆解和共享状态投影。"""

    def run(
        self,
        *,
        constraints: dict[str, Any],
        memory_context: dict[str, Any],
        task_profile: dict[str, Any],
    ) -> AgentExecutionResult:
        budget_label = f"{constraints['budget']} 元" if (constraints.get("budget") or 0) > 0 else "未指定"
        summary = f"已识别 {constraints['destination']} {constraints['days']} 天行程，预算 {budget_label}。"
        payload = {
            "task_breakdown": ["读取记忆", "检索知识", "调用工具", "生成行程", "做一致性检查"],
            "constraints": constraints,
            "memory_highlights": memory_context.get("relevant_long_term_memory", []),
            "task_profile": task_profile,
            "shared_state_projection": ["structured_constraints", "relevant_long_term_memory", "session_context"],
        }
        return AgentExecutionResult(name="planner_agent", summary=summary, payload=payload)
