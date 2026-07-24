from __future__ import annotations

import json
import os
from unittest.mock import patch

from agent.sandbox.env import format_env_for_log
from agent.sandbox.mcp_manifest import build_sandbox_mcp_servers
from agent.sandbox.redact import redact_text
from agent.sandbox.sdk_context import resolve_sdk_session_fields
from agent.sandbox.session_dir import resolve_agent_session_dir


def test_sandbox_logs_and_commands_redact_secrets() -> None:
    env = format_env_for_log(
        {"OPENAI_API_KEY": "sk-test-secret", "NIKA_AGENT_TYPE": "mock"}
    )
    command = redact_text("OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz")

    assert env == {
        "OPENAI_API_KEY": "***REDACTED***",
        "NIKA_AGENT_TYPE": "mock",
    }
    assert "REDACTED" in command
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in command


def test_sandbox_mcp_servers_use_gateway_and_session_header() -> None:
    servers = build_sandbox_mcp_servers(
        session_id="sess-1",
        scenario_name="simple_bgp",
        backend="kathara",
        gateway_agent_url="http://host.docker.internal:40207",
    )

    assert servers
    assert all(server["transport"] == "http" for server in servers.values())
    assert all(
        server["url"].startswith("http://host.docker.internal:40207/mcp/")
        for server in servers.values()
    )
    assert all(
        server["headers"]["NIKA-Session-Id"] == "sess-1" for server in servers.values()
    )


def test_sdk_session_fields_are_read_from_sandbox_manifest(tmp_path) -> None:
    (tmp_path / "sandbox_manifest.json").write_text(
        json.dumps({"scenario_name": "simple_bgp"}),
        encoding="utf-8",
    )
    with patch.dict(
        os.environ,
        {"NIKA_SANDBOX_EXECUTION": "1", "NIKA_SESSION_DIR": str(tmp_path)},
        clear=False,
    ):
        session_dir, scenario = resolve_sdk_session_fields("sess-1")

    assert session_dir == str(tmp_path.resolve())
    assert scenario == "simple_bgp"


def test_resolve_agent_session_dir_uses_sandbox_run_for_cli_exec() -> None:
    with patch.dict(
        os.environ,
        {
            "NIKA_SBX_SANDBOX_NAME": "nika-test",
            "NIKA_SESSION_DIR": "/tmp/.sandbox_run",
        },
        clear=True,
    ):
        assert (
            resolve_agent_session_dir("/tmp/results/session")
            == "/tmp/.sandbox_run"
        )
