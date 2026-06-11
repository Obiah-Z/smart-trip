from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any


@dataclass(frozen=True)
class SkillDefinition:
    skill_id: str
    display_name: str
    description: str
    provider: str
    input_schema: dict[str, Any]
    example_payload: dict[str, Any]
    doc_path: Path
    script_path: Path
    trigger_keywords: list[str]
    depends_on: list[str]
    priority: int
    usage_examples: list[str]
    sandbox_policy: dict[str, Any]


class SkillRegistry:
    def __init__(self) -> None:
        self._root = Path(__file__).resolve().parents[3]
        self._skills_root = self._root / "skills" / "public"
        self._skills = self._load_skills()
        self._by_id = {skill.skill_id: skill for skill in self._skills}

    def all(self) -> list[SkillDefinition]:
        return list(self._skills)

    def list_skills(self) -> list[dict[str, Any]]:
        return [
            {
                "skill_id": skill.skill_id,
                "display_name": skill.display_name,
                "description": skill.description,
                "provider": skill.provider,
                "input_schema": skill.input_schema,
                "example_payload": skill.example_payload,
                "doc_path": str(skill.doc_path),
                "script_path": str(skill.script_path),
                "trigger_keywords": skill.trigger_keywords,
                "depends_on": skill.depends_on,
                "priority": skill.priority,
                "usage_examples": skill.usage_examples,
                "sandbox_policy": skill.sandbox_policy,
            }
            for skill in self._skills
        ]

    def get(self, skill_id: str) -> SkillDefinition:
        return self._by_id[skill_id]

    def _load_skills(self) -> list[SkillDefinition]:
        skills: list[SkillDefinition] = []
        for doc_path in sorted(self._skills_root.glob("*/SKILL.md")):
            metadata, body = self._read_skill_doc(doc_path)
            script_path = doc_path.parent / "scripts" / "run.py"
            if not script_path.exists():
                continue

            skill_id = str(metadata.get("skill_id") or str(metadata.get("name", doc_path.parent.name)).replace("-", "."))
            skills.append(
                SkillDefinition(
                    skill_id=skill_id,
                    display_name=str(metadata.get("display_name") or skill_id),
                    description=str(metadata.get("description") or ""),
                    provider=str(metadata.get("provider") or "local_script"),
                    input_schema=self._expect_dict(metadata.get("input_schema")),
                    example_payload=self._expect_dict(metadata.get("example_payload")),
                    doc_path=doc_path,
                    script_path=script_path,
                    trigger_keywords=self._expect_list(metadata.get("trigger_keywords")),
                    depends_on=self._expect_list(metadata.get("depends_on")),
                    priority=int(metadata.get("priority", 100)),
                    usage_examples=self._extract_usage_examples(body),
                    sandbox_policy=self._expect_dict(metadata.get("sandbox_policy")),
                )
            )

        return sorted(skills, key=lambda item: (item.priority, item.skill_id))

    def _read_skill_doc(self, doc_path: Path) -> tuple[dict[str, Any], str]:
        text = doc_path.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            return {}, text

        parts = text.split("\n---\n", 1)
        if len(parts) != 2:
            return {}, text

        frontmatter_block = parts[0][4:]
        body = parts[1]
        metadata: dict[str, Any] = {}
        for raw_line in frontmatter_block.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            key, raw_value = line.split(":", 1)
            metadata[key.strip()] = self._parse_frontmatter_value(raw_value.strip())
        return metadata, body

    def _parse_frontmatter_value(self, raw_value: str) -> Any:
        if raw_value == "":
            return ""
        if raw_value[0] in "[{":
            return json.loads(raw_value)
        if raw_value.lower() in {"true", "false"}:
            return raw_value.lower() == "true"
        if re.fullmatch(r"-?\d+", raw_value):
            return int(raw_value)
        if re.fullmatch(r"-?\d+\.\d+", raw_value):
            return float(raw_value)
        if len(raw_value) >= 2 and raw_value[0] == raw_value[-1] and raw_value[0] in {'"', "'"}:
            return raw_value[1:-1]
        return raw_value

    def _extract_usage_examples(self, body: str) -> list[str]:
        heading = "## When to Use"
        if heading not in body:
            return []

        section = body.split(heading, 1)[1]
        next_heading = section.find("\n## ")
        if next_heading >= 0:
            section = section[:next_heading]

        examples: list[str] = []
        for raw_line in section.splitlines():
            line = raw_line.strip()
            if line.startswith("- "):
                examples.append(line[2:].strip().strip("“”"))
        return examples

    def _expect_dict(self, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def _expect_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value]
