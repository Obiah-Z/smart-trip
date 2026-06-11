from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DemoPlanRequest(BaseModel):
    user_id: str = Field(default="demo-user")
    session_id: str | None = None
    message: str


class AttractionImageGenerateRequest(BaseModel):
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
    key: str
    value: str
    scope: str = "user_preference"


class MemoryItem(BaseModel):
    user_id: str
    key: str
    value: str
    scope: str
    updated_at: str


class MemoryUpdateItem(BaseModel):
    key: str
    value: str
    scope: str


class StructuredConstraints(BaseModel):
    destination: str | None
    days: int | None
    budget: int
    pace: str
    preferences: list[str]
    excluded_attractions: list[str] = Field(default_factory=list)
    expanded_excluded_attractions: list[str] = Field(default_factory=list)


class ToolResult(BaseModel):
    tool_name: str
    display_name: str | None = None
    provider: str | None = None
    input: dict[str, Any]
    output: dict[str, Any]
    sandbox: dict[str, Any] | None = None


class AgentOutput(BaseModel):
    agent: str
    summary: str
    payload: dict[str, Any]


class SkillDefinitionItem(BaseModel):
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
    skill_id: str
    display_name: str
    reason: str
    source: str
    payload: dict[str, Any]


class SkillInvokeRequest(BaseModel):
    payload: dict[str, Any]


class SessionRunListItem(BaseModel):
    session_id: str
    user_id: str
    request_text: str
    created_at: str
    destination: str | None = None
    days: int | None = None
    summary: str | None = None
    task_type: str | None = None


class DemoPlanResponse(BaseModel):
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
