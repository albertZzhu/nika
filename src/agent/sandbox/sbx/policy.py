"""Sandbox network policy helpers for MCP gateway and LLM API access."""

from __future__ import annotations

import logging
import re
import subprocess

from agent.sandbox.sbx.client import (
    SBX_BIN,
    ensure_sbx_ready,
    run_sbx_checked,
    run_sbx_optional,
)

logger = logging.getLogger(__name__)

_MCP_POLICY_PREFIX = "nika-mcp-"

# DeepSeek is used for sandbox API-key mode (Codex + Claude). The default
# balanced policy does not allow it, which surfaces as HTTP 403
# "Blocked by network policy: domain api.deepseek.com:443".
_LLM_NETWORK_HOSTS = ("api.deepseek.com",)

# Needed when SDK agents install deps from PyPI (offline wheels disabled).
_PYPI_NETWORK_HOSTS = (
    "pypi.org",
    "files.pythonhosted.org",
    "pypi.python.org",
)


def mcp_policy_resource(port: int) -> str:
    return f"localhost:{port}"


def ensure_llm_network_policy() -> None:
    """Allow outbound LLM API hosts needed for NIKA sandbox agents."""
    ensure_sbx_ready()
    for host in _LLM_NETWORK_HOSTS:
        proc = run_sbx_optional(["policy", "allow", "network", host])
        if proc.returncode != 0:
            combined = f"{proc.stdout}\n{proc.stderr}".lower()
            if "already" in combined:
                continue
            logger.warning(
                "Failed to allow sbx network host %s: %s",
                host,
                (proc.stderr or proc.stdout).strip(),
            )


def ensure_pypi_network_policy() -> None:
    """Allow PyPI hosts for in-sandbox SDK package installs."""
    ensure_sbx_ready()
    for host in _PYPI_NETWORK_HOSTS:
        proc = run_sbx_optional(["policy", "allow", "network", host])
        if proc.returncode != 0:
            combined = f"{proc.stdout}\n{proc.stderr}".lower()
            if "already" in combined:
                continue
            logger.warning(
                "Failed to allow sbx network host %s: %s",
                host,
                (proc.stderr or proc.stdout).strip(),
            )


def allow_mcp_gateway(*, sandbox_name: str, port: int) -> str:
    """Allow a sandbox to reach the host MCP gateway on *port*."""
    ensure_sbx_ready()
    resource = mcp_policy_resource(port)
    run_sbx_checked(
        [
            "policy",
            "allow",
            "network",
            "--sandbox",
            sandbox_name,
            resource,
        ]
    )
    return resource


def deny_mcp_gateway(*, sandbox_name: str, port: int) -> None:
    """Revoke MCP gateway access for a sandbox."""
    resource = mcp_policy_resource(port)
    # ``sbx policy deny`` can hang against a stopped/missing sandbox; bound it.
    try:
        subprocess.run(
            [
                SBX_BIN,
                "policy",
                "deny",
                "network",
                "--sandbox",
                sandbox_name,
                resource,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
    except subprocess.TimeoutExpired:
        logger.warning(
            "Timed out denying MCP gateway policy for %s (%s)",
            sandbox_name,
            resource,
        )


def sanitize_sandbox_name(session_id: str) -> str:
    """Return an sbx-compatible sandbox name for *session_id*."""
    cleaned = re.sub(r"[^a-zA-Z0-9.\-+]", "-", session_id.strip())
    cleaned = cleaned.strip(".-+") or "session"
    return f"nika-{cleaned}"[:128]
