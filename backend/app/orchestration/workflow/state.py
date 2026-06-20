from __future__ import annotations

from typing import Any, TypedDict


class TripPlanningState(TypedDict, total=False):
    """LangGraph 在各节点之间传递的共享状态。

    字段按执行阶段逐步补齐：输入阶段写入 slots/session_context，Context 阶段写入
    memory/retrieval，执行阶段写入 tools/agents/final_plan，响应阶段写入 response。
    total=False 允许节点只返回自己负责更新的字段。
    """

    # 当前请求归属的用户 ID，用于读取和写入长期 Memory。
    user_id: str
    # 前端传入的会话 ID；首轮请求可能为空。
    session_id: str | None
    # 用户本轮原始输入，不做上下文恢复或改写。
    message: str
    # 从请求或历史中识别出的当前活跃会话 ID。
    active_session_id: str | None
    # 本轮最终使用的会话 ID；为空时由系统生成。
    resolved_session_id: str
    # SlotExtractor 的原始抽取结果，保留目的地、天数、预算、偏好等未合并状态。
    slots: Any
    # 从历史 session runs 恢复出的会话基线、上一版主方案和最近交互。
    session_context: dict[str, Any]
    # 用户是否在修改上一轮方案，例如调预算、换酒店、排除景点。
    revision_intent: Any
    # 结合追问恢复后的有效输入，供路由、Skill 选择和 RAG 查询使用。
    effective_message: str
    # 合并本轮 slots、会话基线和追问意图后的结构化硬约束。
    structured_constraints: dict[str, Any]
    # 最终确认或继承到的行程天数；缺失时用于澄清判断。
    resolved_days: int | None
    # 最终确认或继承到的预算；未提供时通常为 0 或默认预算。
    resolved_budget: int
    # TaskRouter 生成的任务画像，决定走轻咨询、完整规划、工具链路还是澄清。
    task_profile: dict[str, Any]
    # 当前任务仍缺少的必要字段，例如目的地或天数。
    missing_fields: list[str]
    # MemoryInjectionService 生成的可注入记忆上下文和筛选解释。
    memory_context: dict[str, Any]
    # RetrievalService 返回的 RAG 查询、召回文档、注入知识和 ranking signals。
    retrieval_context: dict[str, Any]
    # SkillSelectionService 返回的内部选择结果，包含 skill_id、reason 和 source。
    selected_skill_items: list[Any]
    # 面向前端和 Context 的 Skill 展示结构，包含已选择 Skill、原因和 payload。
    selected_skills: list[dict[str, Any]]
    # ToolService 执行 Skill 后返回的结构化工具结果列表。
    tool_results: list[dict[str, Any]]
    # ContextAssembler 组装出的 prompt sections 和 runtime_context。
    assembled_context: dict[str, Any]
    # AgentService 汇总的多 Agent 阶段输出列表。
    agent_outputs: list[Any]
    # Planner Agent 的单独输出，便于调试任务拆解结果。
    planner_agent_output: Any
    # Retriever Agent 的单独输出，便于调试知识和工具证据整理。
    retriever_agent_output: Any
    # Executor Agent 的单独输出，通常包含候选 final_plan。
    executor_agent_output: Any
    # Reviewer Agent 的单独输出，便于调试一致性检查结果。
    reviewer_agent_output: Any
    # 最终结构化旅行方案，是用户视图消费的核心结果。
    final_plan: dict[str, Any]
    # PlanReviewer 对 final_plan 的硬约束审计结果和修复建议。
    plan_review: dict[str, Any]
    # LLM 对 final_plan 的自然语言摘要、模型信息和 fallback 状态。
    llm_output: dict[str, Any]
    # 本轮写回长期 Memory 的偏好记录。
    memory_updates: list[dict[str, Any]]
    # 最终 API 响应体，包含用户结果和开发调试信息。
    response: dict[str, Any]
    # 工作流阶段追踪记录，供开发调试视图展示 Route/Memory/RAG/Skill/Agent/Output。
    workflow_trace: list[dict[str, Any]]
