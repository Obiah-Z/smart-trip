from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.core.config.settings import Settings
from app.capabilities.skills.skill_registry import SkillDefinition


SYSTEM_PROMPT = (
    "你是一个旅行规划智能体。"
    "请基于给定的结构化约束、记忆、检索知识和工具结果，输出紧凑、可信、可执行的旅行方案摘要。"
    "严格以 final_plan 为准，不要根据用户原始问题补全与 final_plan 冲突的天数、预算或景点。"
    "不要输出 JSON、代码块、Markdown fenced code 或“最终计划”原始结构。"
)
SKILL_SELECTION_SYSTEM_PROMPT = (
    "你是旅行智能体的技能选择器。"
    "你只能从给定技能目录中选择技能。"
    "返回 JSON，不要返回额外说明。"
)


class OpenAIPlannerClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def enabled(self) -> bool:
        return self._settings.openai_mode == "openai" and bool(self._settings.openai_api_key)

    def generate_plan_summary(self, *, assembled_context: dict[str, Any], final_plan: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled():
            return {
                "mode": "mock",
                "llm_summary": "当前为离线 mock 模式，结果由本地规则与工具链路生成。",
            }

        prompt_variants = [
            self._build_full_prompt(assembled_context=assembled_context, final_plan=final_plan),
            self._build_compact_prompt(final_plan=final_plan),
        ]
        message = None
        last_error = None
        for prompt in prompt_variants:
            try:
                message = self._request_completion(
                    prompt=prompt,
                    system_prompt=SYSTEM_PROMPT,
                    temperature=0.4,
                    max_tokens=1200,
                )
                if message:
                    break
            except (ValueError, KeyError, IndexError, json.JSONDecodeError, httpx.HTTPError) as exc:
                last_error = exc

        if not message:
            return {
                "mode": "fallback",
                "model": self._settings.openai_model,
                "llm_summary": self._build_fallback_summary(final_plan=final_plan),
                "fallback_reason": str(last_error) if last_error is not None else "LLM returned no message content",
            }

        return {
            "mode": "openai",
            "model": self._settings.openai_model,
            "llm_summary": self._sanitize_summary_text(message),
        }

    def select_skills(
        self,
        *,
        user_input: str,
        structured_constraints: dict[str, Any],
        available_skills: list[SkillDefinition],
    ) -> list[dict[str, Any]]:
        prompt = self._build_skill_selection_prompt(
            user_input=user_input,
            structured_constraints=structured_constraints,
            available_skills=available_skills,
        )
        message = self._request_completion(
            prompt=prompt,
            system_prompt=SKILL_SELECTION_SYSTEM_PROMPT,
            temperature=0.1,
            max_tokens=900,
        )
        return self._parse_skill_selection_message(message)

    def _build_full_prompt(self, *, assembled_context: dict[str, Any], final_plan: dict[str, Any]) -> str:
        context_sections = "\n\n".join(assembled_context.get("prompt_sections", []))
        return (
            f"以下是本次旅行规划上下文：\n{context_sections}\n\n"
            f"以下是当前结构化旅行方案：\n{final_plan}\n\n"
            "请严格以 final_plan.summary.days 和 final_plan.days 为准输出，不要自行补全额外天数。"
            "请输出：1）整体方案摘要；2）是否满足预算与节奏；3）两条优化建议。"
            "要求精炼，若包含按天信息，每一天最多只写一行。"
            "不要附带“最终计划”或 JSON。"
        )

    def _build_compact_prompt(self, *, final_plan: dict[str, Any]) -> str:
        return (
            "请基于以下旅行方案输出：1）整体摘要；2）是否满足预算与节奏；3）两条优化建议。"
            "严格以方案中的天数和按天安排为准，不要自行扩写不存在的天数。"
            "要求精炼，若包含按天信息，每一天最多只写一行。不要输出 JSON 或代码块。\n"
            f"{final_plan}"
        )

    def _build_skill_selection_prompt(
        self,
        *,
        user_input: str,
        structured_constraints: dict[str, Any],
        available_skills: list[SkillDefinition],
    ) -> str:
        skill_catalog = [
            {
                "skill_id": skill.skill_id,
                "display_name": skill.display_name,
                "description": skill.description,
                "trigger_keywords": skill.trigger_keywords,
                "depends_on": skill.depends_on,
                "input_schema": skill.input_schema,
                "usage_examples": skill.usage_examples,
            }
            for skill in available_skills
        ]
        return (
            "请根据用户当前问题，从给定技能目录中选择真正需要执行的技能。"
            "正常旅行规划通常会优先考虑景点、路线、酒店和天气；"
            "只有用户在询问系统能力、MCP、外部知识桥接时才选择 knowledge.snapshot。"
            "如果选择 route.plan，但它依赖 attraction.search，也可以只返回 route.plan，系统会自动补依赖。"
            "返回格式必须是 JSON："
            '{"selected_skills":[{"skill_id":"route.plan","reason":"用户要求按天行程"}]}\n\n'
            f"用户问题：{user_input}\n"
            f"结构化约束：{json.dumps(structured_constraints, ensure_ascii=False)}\n"
            f"技能目录：{json.dumps(skill_catalog, ensure_ascii=False)}"
        )

    def _build_fallback_summary(self, *, final_plan: dict[str, Any]) -> str:
        summary = final_plan.get("summary", {})
        budget = final_plan.get("budget", {})
        destination = summary.get("destinationCity", "目的地")
        days = summary.get("days", "若干")
        total_budget = summary.get("totalBudget", "待定")
        tags = " / ".join(summary.get("tags", [])) or "常规出行"
        return (
            f"当前 LLM 生成链路已降级为本地摘要。"
            f"{destination}{days}天行程已生成，预计总预算 {total_budget} CNY，"
            f"偏好标签为 {tags}。"
            f"当前预算拆分为：交通 {budget.get('transport', '待定')}、"
            f"住宿 {budget.get('accommodation', '待定')}、餐饮 {budget.get('food', '待定')}、"
            f"门票 {budget.get('tickets', '待定')}。"
            "如需更自然的总结文本，可在外部模型服务恢复后重新生成。"
        )

    def _request_completion(
        self,
        *,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        payload = {
            "model": self._settings.openai_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "stream": False,
            "max_tokens": max_tokens,
        }
        with httpx.Client(timeout=60.0, trust_env=False) as client:
            response = client.post(
                f"{self._settings.openai_base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._settings.openai_api_key}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        response.raise_for_status()
        data = self._decode_response(response)
        message = self._extract_message(data)
        if not message:
            raise ValueError("LLM returned an empty message")
        return message

    def _parse_skill_selection_message(self, message: str) -> list[dict[str, Any]]:
        data = self._extract_json_payload(message)
        if isinstance(data, dict):
            selected_skills = data.get("selected_skills", [])
            if isinstance(selected_skills, list):
                return [item for item in selected_skills if isinstance(item, dict)]
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        raise ValueError("Invalid skill selection response")

    def _decode_response(self, response: httpx.Response) -> dict[str, Any]:
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            return response.json()

        text = response.text.strip()
        if text.startswith("data:"):
            for line in reversed(text.splitlines()):
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if not payload or payload == "[DONE]":
                    continue
                return json.loads(payload)

        return json.loads(text)

    def _extract_message(self, data: dict[str, Any]) -> str:
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            message = choices[0].get("message", {})
            content = message.get("content")
            if isinstance(content, str):
                return content.strip()
        return ""

    def _extract_json_payload(self, text: str) -> Any:
        stripped = text.strip()
        fenced_match = re.search(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", stripped, re.DOTALL)
        if fenced_match:
            return json.loads(fenced_match.group(1))

        for start_char, end_char in (("{", "}"), ("[", "]")):
            start = stripped.find(start_char)
            end = stripped.rfind(end_char)
            if start >= 0 and end > start:
                candidate = stripped[start : end + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    continue
        raise ValueError("No JSON payload found in model response")

    def _sanitize_summary_text(self, text: str) -> str:
        sanitized = text.strip()
        sanitized = re.split(r"\n#{1,6}\s*最终计划", sanitized, maxsplit=1)[0]
        sanitized = re.split(r"\n\*\*最终计划\*\*", sanitized, maxsplit=1)[0]
        sanitized = re.split(r"\n最终计划[:：]", sanitized, maxsplit=1)[0]
        sanitized = re.sub(r"```(?:json)?[\s\S]*?```", "", sanitized)
        sanitized = sanitized.split("```", 1)[0].strip()
        return sanitized
