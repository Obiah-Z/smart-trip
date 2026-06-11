from __future__ import annotations

from typing import Any


class ContextAssembler:
    def assemble(
        self,
        *,
        user_input: str,
        task_profile: dict[str, Any],
        session_context: dict[str, Any],
        structured_constraints: dict[str, Any],
        memory_context: dict[str, Any],
        retrieval_context: dict[str, Any],
        selected_skills: list[dict[str, Any]],
        tool_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        destination = structured_constraints.get("destination") or "待确认"
        days = structured_constraints.get("days")
        budget = structured_constraints.get("budget", 0)
        prompt_sections = [
            "[System Role]\n你是一个旅行规划智能体，需要优先满足预算、天数和用户偏好。",
            f"[Current User Request]\n{user_input}",
            "[Task Analysis]\n"
            + "\n".join(
                [
                    f"- task_type: {task_profile['task_type']}",
                    f"- complexity: {task_profile['complexity']}",
                    f"- needs_rag: {task_profile['needs_rag']}",
                    f"- needs_tools: {task_profile['needs_tools']}",
                    f"- needs_multi_agent: {task_profile['needs_multi_agent']}",
                    f"- intent_summary: {task_profile['intent_summary']}",
                ]
            ),
            "[Structured Constraints]\n"
            + "\n".join(
                [
                    f"- destination: {destination}",
                    f"- days: {days if days is not None else '待确认'}",
                    f"- budget: {budget if budget > 0 else '未指定'}",
                    f"- pace: {structured_constraints['pace']}",
                    f"- preferences: {', '.join(structured_constraints['preferences'])}",
                ]
            ),
            "[Session Context]\n"
            + "\n".join(
                [
                    f"- session_found: {session_context['session_found']}",
                    f"- latest_summary: {session_context.get('latest_summary') or 'none'}",
                    f"- history_messages: {' | '.join(session_context.get('history_messages', [])) or 'none'}",
                ]
            ),
            "[Relevant Memory]\n"
            + (
                "\n".join([f"- {item['key']}: {item['value']}" for item in memory_context['relevant_long_term_memory']])
                or "- none"
            ),
            "[Memory Injection Strategy]\n"
            + (
                "\n".join([f"- {item}" for item in memory_context.get("selection_reasons", [])])
                or "- no explicit strategy"
            ),
            "[Retrieved Knowledge]\n"
            + ("\n".join([f"- {item}" for item in retrieval_context['injected_knowledge']]) or "- none"),
            "[Selected Skills]\n"
            + (
                "\n".join([f"- {item['skill_id']} ({item['source']}): {item['reason']}" for item in selected_skills])
                or "- none"
            ),
            "[Tool Evidence]\n"
            + "\n".join(
                [
                    f"- {item['tool_name']}: output={item['output']}; sandbox={item.get('sandbox', {}).get('mode', 'unknown')}"
                    for item in tool_results
                ]
            ),
            "[Output Contract]\n- 输出需满足预算、节奏、偏好约束，并显式引用知识或工具证据。",
        ]
        return {
            "prompt_sections": prompt_sections,
            "runtime_context": {
                "task_profile": task_profile,
                "session_context": session_context,
                "structured_constraints": structured_constraints,
                "memory_context": memory_context,
                "retrieval_context": retrieval_context,
                "selected_skills": selected_skills,
                "tool_results": tool_results,
            },
        }
