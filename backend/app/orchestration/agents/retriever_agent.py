from __future__ import annotations

from typing import Any

from app.orchestration.agents.base import AgentExecutionResult


class RetrieverAgent:
    """负责汇总 RAG 证据和工具调用轨迹。"""

    def run(
        self,
        *,
        retrieval_context: dict[str, Any],
        tool_results: list[dict[str, Any]],
    ) -> AgentExecutionResult:
        summary = f"召回 {len(retrieval_context['retrieved_documents'])} 条知识，并完成 {len(tool_results)} 个工具调用。"
        payload = {
            "knowledge": retrieval_context["injected_knowledge"],
            "tools": [item["tool_name"] for item in tool_results],
            "rerank_trace": [
                {
                    "id": item.get("id"),
                    "topic": item.get("topic"),
                    "score": item.get("score"),
                    "lexical_overlap": item.get("lexical_overlap"),
                    "preference_bonus": item.get("preference_bonus"),
                }
                for item in retrieval_context["retrieved_documents"]
            ],
        }
        return AgentExecutionResult(name="retriever_agent", summary=summary, payload=payload)
