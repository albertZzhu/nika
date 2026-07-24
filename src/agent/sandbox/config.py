"""Sandbox execution configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ENV_SANDBOX_ENV_FILE = "NIKA_SANDBOX_ENV_FILE"
ENV_SANDBOX_KEEP = "NIKA_SANDBOX_KEEP"
ENV_SANDBOX_CPUS = "NIKA_SANDBOX_CPUS"
ENV_SANDBOX_MEMORY = "NIKA_SANDBOX_MEMORY"
ENV_SANDBOX_OFFLINE_SDK_WHEELS = "NIKA_SANDBOX_OFFLINE_SDK_WHEELS"
ENV_SANDBOX_UPSTREAM_PROXY = "NIKA_SANDBOX_UPSTREAM_PROXY"

ENV_SANDBOX_EXECUTION = "NIKA_SANDBOX_EXECUTION"
ENV_SESSION_DIR = "NIKA_SESSION_DIR"
ENV_GATEWAY_URL = "NIKA_MCP_GATEWAY_URL"
ENV_GATEWAY_AGENT_URL = "NIKA_MCP_GATEWAY_AGENT_URL"

SANDBOX_GATEWAY_HOST_BRIDGE = "host.docker.internal"


def _repo_root() -> Path:
    from nika.config import _REPO_ROOT

    return _REPO_ROOT


def _default_sandbox_env_file() -> Path:
    return _repo_root() / ".env"


@dataclass(frozen=True)
class SandboxConfig:
    env_file: Path
    keep_container: bool
    cpus: str | None
    memory: str | None
    offline_sdk_wheels: bool


def sandbox_gateway_agent_host(network: str | None = None) -> str:
    """Return the MCP gateway hostname reachable from a Docker Sandbox."""
    _ = network
    return SANDBOX_GATEWAY_HOST_BRIDGE


def load_sandbox_env_values(*paths: Path) -> dict[str, str]:
    """Merge key/value pairs from optional sandbox env files (later paths win)."""
    from dotenv import dotenv_values

    merged: dict[str, str] = {}
    for path in paths:
        if not path.is_file():
            continue
        merged.update({k: v for k, v in dotenv_values(path).items() if v is not None})
    return merged


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.environ.get(key, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def resolve_sandbox_config(
    *,
    env_file: str | Path | None = None,
    keep_container: bool | None = None,
    cpus: str | None = None,
    memory: str | None = None,
    offline_sdk_wheels: bool | None = None,
) -> SandboxConfig:
    """Resolve sandbox settings from CLI flags and environment."""
    env_path_raw = env_file or os.environ.get(ENV_SANDBOX_ENV_FILE, "").strip()
    resolved_env_file = (
        Path(env_path_raw) if env_path_raw else _default_sandbox_env_file()
    )
    if not resolved_env_file.is_absolute():
        resolved_env_file = (_repo_root() / resolved_env_file).resolve()

    resolved_keep = (
        keep_container if keep_container is not None else _env_bool(ENV_SANDBOX_KEEP)
    )
    resolved_cpus = cpus or os.environ.get(ENV_SANDBOX_CPUS, "").strip() or None
    resolved_memory = memory or os.environ.get(ENV_SANDBOX_MEMORY, "").strip() or None
    resolved_offline_wheels = (
        offline_sdk_wheels
        if offline_sdk_wheels is not None
        else _env_bool(ENV_SANDBOX_OFFLINE_SDK_WHEELS)
    )

    return SandboxConfig(
        env_file=resolved_env_file,
        keep_container=resolved_keep,
        cpus=resolved_cpus,
        memory=resolved_memory,
        offline_sdk_wheels=resolved_offline_wheels,
    )
