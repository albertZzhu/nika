"""Ephemeral per-task workspace preparation and artifact collection."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from agent.sandbox.constants import (
    MANIFEST_FILENAME,
    RUN_FILENAME,
    RUNTIME_ENV_FILENAME,
)
from agent.utils.skills import resolve_skills_root

SANDBOX_RUN_DIRNAME = ".sandbox_run"
SKILLS_DIRNAME = "skills"
COLLECTED_WORKSPACES = (
    "codex_workspace",
    "claude_workspace",
    "codex_sdk_workspace",
    "claude_sdk_workspace",
)
COLLECTED_FILES = ("messages.jsonl", "submission.json")
_EPHEMERAL_DIR_NAMES = frozenset({"tmp", ".tmp"})
_SENSITIVE_NAMES = frozenset(
    {
        "auth.json",
        ".credentials.json",
        ".host_auth",
    }
)


@dataclass
class SandboxWorkspace:
    session_dir: Path
    workspace_dir: Path

    @property
    def manifest_path(self) -> Path:
        return self.workspace_dir / MANIFEST_FILENAME


def sandbox_workspace_dir(session_dir: str | Path) -> Path:
    return Path(session_dir).resolve() / SANDBOX_RUN_DIRNAME


def _ignore_ephemeral(_directory: str, names: list[str]) -> set[str]:
    """Skip ephemeral dirs and credential files that must not leave the sandbox."""
    ignored = {name for name in names if name in _EPHEMERAL_DIR_NAMES}
    ignored.update(name for name in names if name in _SENSITIVE_NAMES)
    return ignored


def prepare_workspace(
    *,
    session_dir: str | Path,
    manifest: dict,
    runtime_env: dict[str, str],
) -> SandboxWorkspace:
    """Create an isolated workspace with manifest, skills, and runtime env."""
    session_path = Path(session_dir).resolve()
    workspace = sandbox_workspace_dir(session_path)
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)

    (workspace / MANIFEST_FILENAME).write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    (workspace / RUNTIME_ENV_FILENAME).write_text(
        json.dumps(runtime_env, indent=2),
        encoding="utf-8",
    )

    # SDK agents run inside the microVM with NIKA_SESSION_DIR pointed at this
    # workspace; SessionStore is not available there, so mirror run.json in.
    run_src = session_path / RUN_FILENAME
    if run_src.is_file():
        shutil.copy2(run_src, workspace / RUN_FILENAME)

    skills_src = resolve_skills_root()
    skills_dst = workspace / SKILLS_DIRNAME
    if skills_src.is_dir():
        shutil.copytree(skills_src, skills_dst, dirs_exist_ok=True)

    return SandboxWorkspace(session_dir=session_path, workspace_dir=workspace)


def collect_artifacts(workspace: SandboxWorkspace) -> None:
    """Copy agent outputs from the sandbox workspace back to the session dir."""
    session_dir = workspace.session_dir
    for name in COLLECTED_FILES:
        src = workspace.workspace_dir / name
        if src.is_file():
            shutil.copy2(src, session_dir / name)

    for dirname in COLLECTED_WORKSPACES:
        src = workspace.workspace_dir / dirname
        if not src.is_dir():
            continue
        dst = session_dir / dirname
        if dst.exists():
            shutil.rmtree(dst)
        try:
            shutil.copytree(
                src,
                dst,
                ignore=_ignore_ephemeral,
                ignore_dangling_symlinks=True,
            )
        except shutil.Error:
            # Codex SDK leaves ephemeral binaries under .codex_home/tmp that may
            # vanish or reference microVM-only paths; keep other artifacts.
            if not dst.exists():
                raise

    manifest_src = workspace.manifest_path
    if manifest_src.is_file():
        shutil.copy2(manifest_src, session_dir / MANIFEST_FILENAME)


def cleanup_workspace(workspace: SandboxWorkspace) -> None:
    """Remove the ephemeral workspace directory."""
    if workspace.workspace_dir.is_dir():
        shutil.rmtree(workspace.workspace_dir, ignore_errors=True)
