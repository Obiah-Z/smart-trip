from __future__ import annotations

from typing import Any

from app.skills.skill_registry import SkillDefinition
from app.skills.skill_sandbox import SkillSandboxRunner


class SkillScriptRunner:
    """Skill 脚本执行门面。

    当前所有脚本都走沙箱执行；保留这一层是为了以后支持远程 Skill、MCP Skill 或不同运行器。
    """

    def __init__(self) -> None:
        self._sandbox_runner = SkillSandboxRunner()

    def run(self, *, definition: SkillDefinition, payload: dict[str, Any]) -> dict[str, Any]:
        return self._sandbox_runner.run(definition=definition, payload=payload)
