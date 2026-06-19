from app.core.config.settings import Settings
from app.capabilities.llm.openai_client import OpenAIPlannerClient


def test_extract_message_returns_empty_string_for_empty_choices() -> None:
    client = OpenAIPlannerClient(
        Settings(
            openai_mode="openai",
            openai_base_url="https://example.com/v1",
            openai_api_key="test-key",
            openai_model="gpt-5.4",
        )
    )

    assert client._extract_message({"choices": []}) == ""


def test_generate_plan_summary_falls_back_to_compact_prompt(monkeypatch) -> None:
    client = OpenAIPlannerClient(
        Settings(
            openai_mode="openai",
            openai_base_url="https://example.com/v1",
            openai_api_key="test-key",
            openai_model="gpt-5.4",
        )
    )
    calls: list[str] = []

    def fake_request_completion(*, prompt: str, system_prompt: str, temperature: float, max_tokens: int) -> str:
        calls.append(prompt)
        if len(calls) == 1:
            raise ValueError("LLM returned an empty message")
        return "fallback summary"

    monkeypatch.setattr(client, "_request_completion", fake_request_completion)

    result = client.generate_plan_summary(
        assembled_context={"prompt_sections": ["[Current User Request]\n杭州三日游"]},
        final_plan={"summary": {"destinationCity": "杭州"}},
    )

    assert result["mode"] == "openai"
    assert result["model"] == "gpt-5.4"
    assert result["llm_summary"] == "fallback summary"
    assert len(calls) == 2


def test_generate_plan_summary_sanitizes_embedded_json_blocks(monkeypatch) -> None:
    client = OpenAIPlannerClient(
        Settings(
            openai_mode="openai",
            openai_base_url="https://example.com/v1",
            openai_api_key="test-key",
            openai_model="gpt-5.4",
        )
    )

    def fake_request_completion(*, prompt: str, system_prompt: str, temperature: float, max_tokens: int) -> str:
        return "### 整体方案摘要\n- 杭州 5 天\n\n### 最终计划\n```json\n{\"days\": 5}\n```"

    monkeypatch.setattr(client, "_request_completion", fake_request_completion)

    result = client.generate_plan_summary(
        assembled_context={"prompt_sections": ["[Current User Request]\n杭州五日游"]},
        final_plan={"summary": {"destinationCity": "杭州", "days": 5}},
    )

    assert result["mode"] == "openai"
    assert "最终计划" not in result["llm_summary"]
    assert "```" not in result["llm_summary"]
    assert "{\"days\": 5}" not in result["llm_summary"]
