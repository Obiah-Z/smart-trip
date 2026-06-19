from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import pathlib
import resource
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
from typing import Any

from app.capabilities.skills.skill_registry import SkillDefinition
from app.core.paths import data_dir


@dataclass(frozen=True)
class SandboxPolicy:
    """单个 Skill 的沙箱执行策略。"""

    timeout_seconds: int
    memory_mb: int
    cpu_seconds: int
    max_open_files: int
    allow_network: bool
    allow_subprocess: bool
    writable_roots: tuple[str, ...]


def sandbox_bootstrap() -> None:
    """在 Skill 子进程内启用沙箱限制。

    该函数通过 python -c bootstrap 在目标脚本执行前运行，因此能在脚本 import 后续库之前
    限制网络、子进程、写入路径和资源用量。
    """
    if os.getenv("SMART_TRIP_SANDBOX_ACTIVE") != "1":
        return

    policy = json.loads(os.environ["SMART_TRIP_SANDBOX_POLICY"])
    writable_roots = tuple(policy.get("writable_roots", []))

    if not policy.get("allow_network", False):
        _disable_network()
    if not policy.get("allow_subprocess", False):
        _disable_subprocess()

    _restrict_open(writable_roots=writable_roots)
    _apply_resource_limits(policy=policy)


def _apply_resource_limits(*, policy: dict[str, Any]) -> None:
    """使用系统 rlimit 限制 CPU、内存和文件句柄数量。"""
    memory_bytes = int(policy["memory_mb"]) * 1024 * 1024
    cpu_seconds = int(policy["cpu_seconds"])
    max_open_files = int(policy["max_open_files"])

    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
    resource.setrlimit(resource.RLIMIT_NOFILE, (max_open_files, max_open_files))


def _disable_network() -> None:
    def blocked_socket(*args: Any, **kwargs: Any) -> Any:
        raise PermissionError("sandbox policy blocks network access")

    socket.socket = blocked_socket  # type: ignore[assignment]
    socket.create_connection = blocked_socket  # type: ignore[assignment]


def _disable_subprocess() -> None:
    def blocked_popen(*args: Any, **kwargs: Any) -> Any:
        raise PermissionError("sandbox policy blocks subprocess spawning")

    subprocess.Popen = blocked_popen  # type: ignore[assignment]


def _restrict_open(*, writable_roots: tuple[str, ...]) -> None:
    """拦截常见写入 API，只允许写入临时目录或显式白名单目录。"""
    builtins_module = __import__("builtins")
    original_open = builtins_module.open
    original_mkdir = os.mkdir
    original_makedirs = os.makedirs
    original_rename = os.rename
    original_replace = os.replace
    original_remove = os.remove
    original_unlink = os.unlink
    original_rmdir = os.rmdir
    original_open_builtin = os.open
    original_pathlib_open = pathlib.Path.open

    writable_resolved = tuple(Path(root).resolve() for root in writable_roots)

    def is_write_mode(mode: str) -> bool:
        return any(flag in mode for flag in ("w", "a", "x", "+"))

    def is_write_flags(flags: int) -> bool:
        return bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC))

    def is_allowed(path_value: str | os.PathLike[str]) -> bool:
        try:
            resolved = Path(path_value).expanduser().resolve()
        except FileNotFoundError:
            resolved = Path(path_value).expanduser().resolve(strict=False)
        return any(resolved == root or root in resolved.parents for root in writable_resolved)

    def guarded_open(file: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        if is_write_mode(mode) and not is_allowed(file):
            raise PermissionError(f"sandbox policy blocks writing outside allowed roots: {file}")
        return original_open(file, mode, *args, **kwargs)

    def guarded_mkdir(path: str | bytes, mode: int = 0o777) -> None:
        if not is_allowed(path):
            raise PermissionError(f"sandbox policy blocks mkdir outside allowed roots: {path}")
        original_mkdir(path, mode)

    def guarded_makedirs(name: str, mode: int = 0o777, exist_ok: bool = False) -> None:
        if not is_allowed(name):
            raise PermissionError(f"sandbox policy blocks makedirs outside allowed roots: {name}")
        original_makedirs(name, mode=mode, exist_ok=exist_ok)

    def guarded_rename(src: str, dst: str) -> None:
        if not is_allowed(src) or not is_allowed(dst):
            raise PermissionError("sandbox policy blocks rename outside allowed roots")
        original_rename(src, dst)

    def guarded_replace(src: str, dst: str) -> None:
        if not is_allowed(src) or not is_allowed(dst):
            raise PermissionError("sandbox policy blocks replace outside allowed roots")
        original_replace(src, dst)

    def guarded_remove(path: str) -> None:
        if not is_allowed(path):
            raise PermissionError(f"sandbox policy blocks remove outside allowed roots: {path}")
        original_remove(path)

    def guarded_unlink(path: str, *args: Any, **kwargs: Any) -> None:
        if not is_allowed(path):
            raise PermissionError(f"sandbox policy blocks unlink outside allowed roots: {path}")
        original_unlink(path, *args, **kwargs)

    def guarded_rmdir(path: str) -> None:
        if not is_allowed(path):
            raise PermissionError(f"sandbox policy blocks rmdir outside allowed roots: {path}")
        original_rmdir(path)

    def guarded_os_open(path: str, flags: int, mode: int = 0o777) -> int:
        if is_write_flags(flags) and not is_allowed(path):
            raise PermissionError(f"sandbox policy blocks writing outside allowed roots: {path}")
        return original_open_builtin(path, flags, mode)

    def guarded_pathlib_open(self: pathlib.Path, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        if is_write_mode(mode) and not is_allowed(self):
            raise PermissionError(f"sandbox policy blocks writing outside allowed roots: {self}")
        return original_pathlib_open(self, mode, *args, **kwargs)

    builtins_module.open = guarded_open
    os.mkdir = guarded_mkdir  # type: ignore[assignment]
    os.makedirs = guarded_makedirs  # type: ignore[assignment]
    os.rename = guarded_rename  # type: ignore[assignment]
    os.replace = guarded_replace  # type: ignore[assignment]
    os.remove = guarded_remove  # type: ignore[assignment]
    os.unlink = guarded_unlink  # type: ignore[assignment]
    os.rmdir = guarded_rmdir  # type: ignore[assignment]
    os.open = guarded_os_open  # type: ignore[assignment]
    pathlib.Path.open = guarded_pathlib_open  # type: ignore[assignment]


class SkillSandboxRunner:
    """以独立受限子进程运行 Skill 脚本。"""

    DEFAULT_POLICY = SandboxPolicy(
        timeout_seconds=5,
        memory_mb=128,
        cpu_seconds=2,
        max_open_files=32,
        allow_network=False,
        allow_subprocess=False,
        writable_roots=(),
    )

    def run(self, *, definition: SkillDefinition, payload: dict[str, Any]) -> dict[str, Any]:
        """执行 Skill 并返回 output 与 sandbox 审计信息。"""
        policy = self._build_policy(definition=definition)
        temp_dir = Path(tempfile.mkdtemp(prefix=f"smart-trip-{definition.skill_id.replace('.', '-')}-"))
        command = [
            sys.executable,
            "-c",
            self._bootstrap_command(str(definition.script_path)),
            "--payload-json",
            json.dumps(payload, ensure_ascii=False),
        ]
        env = os.environ.copy()
        env["SMART_TRIP_SANDBOX_ACTIVE"] = "1"
        env["SMART_TRIP_SANDBOX_POLICY"] = json.dumps(
            {
                "timeout_seconds": policy.timeout_seconds,
                "memory_mb": policy.memory_mb,
                "cpu_seconds": policy.cpu_seconds,
                "max_open_files": policy.max_open_files,
                "allow_network": policy.allow_network,
                "allow_subprocess": policy.allow_subprocess,
                "writable_roots": [str(path) for path in (temp_dir, *[Path(item) for item in policy.writable_roots])],
            },
            ensure_ascii=False,
        )
        env["SMART_TRIP_SKILL_ENTRY"] = str(definition.script_path)
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                cwd=temp_dir,
                env=env,
                timeout=policy.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise RuntimeError(f"skill timed out after {policy.timeout_seconds}s: {definition.skill_id}") from exc

        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        if result.returncode != 0:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise RuntimeError(stderr or f"skill script failed: {definition.skill_id}")

        temp_dir_persisted = self._persist_if_non_empty(temp_dir=temp_dir)
        return {
            "output": json.loads(stdout),
            "sandbox": {
                "mode": "process_sandbox",
                "python_executable": sys.executable,
                "entry_script": str(definition.script_path),
                "timeout_seconds": policy.timeout_seconds,
                "memory_mb": policy.memory_mb,
                "cpu_seconds": policy.cpu_seconds,
                "max_open_files": policy.max_open_files,
                "allow_network": policy.allow_network,
                "allow_subprocess": policy.allow_subprocess,
                "writable_roots": [str(item) for item in policy.writable_roots],
                "working_directory": temp_dir_persisted,
                "stderr": stderr,
                "isolation_note": "skill 在独立受限子进程中运行，启用超时、资源限制、禁网和受控写入策略。",
            },
        }

    def _build_policy(self, *, definition: SkillDefinition) -> SandboxPolicy:
        """合并 Skill 自定义 sandbox_policy 和默认策略。"""
        metadata = definition.sandbox_policy or {}
        writable_roots = tuple(str(item) for item in metadata.get("writable_roots", []))
        return SandboxPolicy(
            timeout_seconds=int(metadata.get("timeout_seconds", self.DEFAULT_POLICY.timeout_seconds)),
            memory_mb=int(metadata.get("memory_mb", self.DEFAULT_POLICY.memory_mb)),
            cpu_seconds=int(metadata.get("cpu_seconds", self.DEFAULT_POLICY.cpu_seconds)),
            max_open_files=int(metadata.get("max_open_files", self.DEFAULT_POLICY.max_open_files)),
            allow_network=bool(metadata.get("allow_network", self.DEFAULT_POLICY.allow_network)),
            allow_subprocess=bool(metadata.get("allow_subprocess", self.DEFAULT_POLICY.allow_subprocess)),
            writable_roots=writable_roots,
        )

    def _bootstrap_command(self, script_path: str) -> str:
        """生成子进程启动命令：先启用 sandbox，再 runpy 执行 Skill 脚本。"""
        escaped_path = script_path.replace("\\", "\\\\").replace("'", "\\'")
        return (
            "import runpy;"
            "from app.capabilities.skills.skill_sandbox import sandbox_bootstrap;"
            "sandbox_bootstrap();"
            f"runpy.run_path('{escaped_path}', run_name='__main__')"
        )

    def _persist_if_non_empty(self, *, temp_dir: Path) -> str | None:
        """如果 Skill 在工作目录产生文件，则移动到 data/sandbox_runs 供审计。"""
        try:
            has_files = any(temp_dir.iterdir())
        except FileNotFoundError:
            return None
        if not has_files:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None

        artifact_root = data_dir() / "sandbox_runs"
        artifact_root.mkdir(parents=True, exist_ok=True)
        target_dir = artifact_root / temp_dir.name
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)
        shutil.move(str(temp_dir), str(target_dir))
        return str(target_dir)
