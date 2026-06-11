from __future__ import annotations

from typing import Any

from app.skills.skill_registry import SkillDefinition
from app.skills.skill_sandbox import SkillSandboxRunner


class SkillScriptRunner:
    def __init__(self) -> None:
        self._sandbox_runner = SkillSandboxRunner()

    def run(self, *, definition: SkillDefinition, payload: dict[str, Any]) -> dict[str, Any]:
        return self._sandbox_runner.run(definition=definition, payload=payload)
