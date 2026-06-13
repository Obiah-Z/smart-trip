from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DemoPlanRequest(BaseModel):
    """旅行咨询/规划主接口请求。"""

    user_id: str = Field(default="demo-user")
    session_id: str | None = None
    message: str


class AttractionImageGenerateRequest(BaseModel):
    """单个景点图片生成请求。"""

    destination: str
    attraction_name: str
    attraction_type: str | None = None
    area: str | None = None
    style: str = "travel_editorial"
    aspect: str = "landscape"
    time_of_day: str | None = None
    weather_hint: str | None = None
    user_preferences: list[str] = Field(default_factory=list)
    size: str | None = None
    quality: str | None = None
    output_format: str | None = None
    force_regenerate: bool = False


class AttractionImageGenerateResponse(BaseModel):
    """图片生成结果，包含本地静态资源路径和供应商请求信息。"""

    task_id: str
    status: str
    image_url: str
    local_path: str
    relative_path: str
    file_name: str
    asset_group: str
    destination_folder: str
    asset_key: str
    cache_hit: bool
    label: str
    prompt: str
    size: str
    quality: str
    output_format: str
    request_id: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class MemoryUpsertRequest(BaseModel):
    """手动写入 Memory 的请求。"""

    key: str
    value: str
    scope: str = "user_preference"


class MemoryItem(BaseModel):
    """长期 Memory 存储项。"""

    user_id: str
    key: str
    value: str
    scope: str
    updated_at: str


class MemoryUpdateItem(BaseModel):
    """本轮规划自动写回的 Memory 记录。"""

    key: str
    value: str
    scope: str


class StructuredConstraints(BaseModel):
    """后端解析出的本轮有效旅行约束。

    _followup_replan 是内部字段；通过 alias 暴露，保证前端调试时能看到它来自后端追问判断。
    """

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    destination: str | None
    days: int | None
    budget: int
    budget_policy: str | None = None
    target_budget: int | None = None
    pace: str
    preferences: list[str]
    excluded_attractions: list[str] = Field(default_factory=list)
    expanded_excluded_attractions: list[str] = Field(default_factory=list)
    revision_intent: dict[str, Any] = Field(default_factory=dict)
    followup_replan: bool = Field(default=False, alias="_followup_replan")


class ToolResult(BaseModel):
    """Skill/Tool 执行结果。"""

    tool_name: str
    display_name: str | None = None
    provider: str | None = None
    input: dict[str, Any]
    output: dict[str, Any]
    sandbox: dict[str, Any] | None = None


class AgentOutput(BaseModel):
    """多 Agent 阶段输出。"""

    agent: str
    summary: str
    payload: dict[str, Any]


class SkillDefinitionItem(BaseModel):
    """注册到系统中的 Skill 元数据。"""

    skill_id: str
    display_name: str
    description: str
    provider: str
    input_schema: dict[str, Any]
    example_payload: dict[str, Any]
    doc_path: str
    script_path: str
    trigger_keywords: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    priority: int = 100
    usage_examples: list[str] = Field(default_factory=list)
    sandbox_policy: dict[str, Any] = Field(default_factory=dict)


class SelectedSkillItem(BaseModel):
    """本轮被选择执行的 Skill 及选择原因。"""

    skill_id: str
    display_name: str
    reason: str
    source: str
    payload: dict[str, Any]


class SkillInvokeRequest(BaseModel):
    """手动调用 Skill 的请求体。"""

    payload: dict[str, Any]


class SessionRunListItem(BaseModel):
    """历史会话列表项。"""

    session_id: str
    user_id: str
    request_text: str
    created_at: str
    destination: str | None = None
    days: int | None = None
    summary: str | None = None
    task_type: str | None = None


class DemoPlanResponse(BaseModel):
    """旅行规划主接口响应。

    用户视图主要消费 final_plan 和 llm_output；开发调试视图消费 task_profile、
    session_context、retrieval_context、tool_results、agent_outputs 和 assembled_context。
    """

    session_id: str
    user_input: str
    task_profile: dict[str, Any]
    session_context: dict[str, Any]
    structured_constraints: StructuredConstraints
    memory_context: dict[str, Any]
    memory_updates: list[MemoryUpdateItem]
    retrieval_context: dict[str, Any]
    available_skills: list[SkillDefinitionItem]
    selected_skills: list[SelectedSkillItem]
    tool_results: list[ToolResult]
    agent_outputs: list[AgentOutput]
    assembled_context: dict[str, Any]
    final_plan: dict[str, Any]
    llm_output: dict[str, Any]
