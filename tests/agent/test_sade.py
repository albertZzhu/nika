from __future__ import annotations
import pytest
import os
import sys
import unittest.mock
from agent.sdk.mcp import to_sdk_mcp_servers
from agent.community.sade.config import prepare_sade_sdk_env, sade_credentials_available
from agent.utils.phases import DIAGNOSIS
from nika.utils.session_store import SessionStore
from tests.agent._assertions import assert_submission_fields
from tests.support.integration_base import OrderedPipelineTestCase
from tests.support.integration_pipeline import (
    ClabCommonPipelineSteps,
    CommonPipelineSteps,
    _min3clos_prerequisites,
    load_test_env,
    sade_available,
)

load_test_env()


class SadeConfigTest:
    """Model and credential resolution for community.sade."""

    def test_prepare_env_maps_auth_token_to_api_key(self) -> None:
        with unittest.mock.patch.dict(
            os.environ,
            {
                "ANTHROPIC_AUTH_TOKEN": "tok",
                "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic",
            },
            clear=True,
        ):
            env = prepare_sade_sdk_env(session_id="sess-abc")
        assert env["ANTHROPIC_API_KEY"] == "tok"
        assert env["ANTHROPIC_BASE_URL"] == "https://api.deepseek.com/anthropic"
        assert env["NIKA_SESSION_ID"] == "sess-abc"

    def test_prepare_env_requires_credentials(self) -> None:
        with unittest.mock.patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError):
                prepare_sade_sdk_env(session_id="sess-abc")

    def test_sade_credentials_available_with_auth_token(self) -> None:
        with unittest.mock.patch.dict(
            os.environ, {"ANTHROPIC_AUTH_TOKEN": "tok"}, clear=True
        ):
            assert sade_credentials_available()


class SadeMcpAdapterTest:
    """MCP config adaptation for claude-agent-sdk."""

    def test_converts_transport_to_stdio_type(self) -> None:
        servers = to_sdk_mcp_servers(
            {
                "kathara_base_mcp_server": {
                    "transport": "stdio",
                    "command": "python3",
                    "args": ["/path/base.py"],
                    "env": {"NIKA_SESSION_ID": "sess-abc"},
                }
            }
        )
        srv = servers["kathara_base_mcp_server"]
        assert srv["type"] == "stdio"
        assert srv["command"] == sys.executable
        assert srv["args"] == ["/path/base.py"]
        assert srv["env"]["NIKA_SESSION_ID"] == "sess-abc"

    def test_multiple_servers_all_present(self) -> None:
        servers = to_sdk_mcp_servers(
            {
                "kathara_base_mcp_server": {
                    "command": "python3",
                    "args": ["/path/base.py"],
                },
                "task_mcp_server": {"command": "python3", "args": ["/path/task.py"]},
            }
        )
        assert "kathara_base_mcp_server" in servers
        assert "task_mcp_server" in servers


@pytest.mark.skipif(
    not sade_available(), reason="claude-agent-sdk + ANTHROPIC credentials required"
)
class SadeAgentPipelineTest(CommonPipelineSteps, OrderedPipelineTestCase):
    """Full pipeline with the SADE community agent."""

    def test_step_01_start_env(self) -> None:
        self._step_start_env()

    def test_step_02_inject_failure(self) -> None:
        self._step_inject_failure()

    def test_step_03_run_sade_agent(self) -> None:
        assert self.session_id is not None
        self._run_agent(agent_type="community.sade", max_steps=20)
        row = SessionStore().get_session(self.session_id)
        assert row.get("agent_type") == "community.sade"

    def test_step_04_check_messages(self) -> None:
        assert self.session_dir is not None
        messages = self._load_jsonl("messages.jsonl")
        agents = {e["agent"] for e in messages}
        assert DIAGNOSIS in agents
        tool_starts = [e for e in messages if e.get("event") == "tool_start"]
        assert tool_starts, "SADE must emit tool_start events"
        tool_names = [e.get("tool", {}).get("name", "") for e in tool_starts]
        assert any(("submit" in name for name in tool_names)), (
            "expected submit tool call"
        )
        llm_ends = [e for e in messages if e.get("event") == "llm_end"]
        assert llm_ends, "SADE must emit llm_end events"

    def test_step_05_check_submission(self) -> None:
        assert self.session_dir is not None
        assert (self.session_dir / "submission.json").exists()
        assert_submission_fields(self.session_dir)

    def test_step_06_session_close(self) -> None:
        self._step_close_and_verify("community.sade")

    def test_step_07_eval_metrics(self) -> None:
        self._step_eval_metrics()


@pytest.mark.skipif(
    not (_min3clos_prerequisites() and sade_available()),
    reason="containerlab/gnmic/Docker or SADE credentials not available",
)
class SadeClabPipelineTest(ClabCommonPipelineSteps, OrderedPipelineTestCase):
    """Full containerlab pipeline with the SADE community agent."""

    def test_step_01_start_env(self) -> None:
        self._step_start_env()

    def test_step_02_inject_failure(self) -> None:
        self._step_inject_failure()

    def test_step_03_run_sade_agent(self) -> None:
        assert self.session_id is not None
        self._run_agent(agent_type="community.sade", max_steps=20)
        row = SessionStore().get_session(self.session_id)
        assert row.get("agent_type") == "community.sade"

    def test_step_04_check_messages(self) -> None:
        assert self.session_dir is not None
        messages = self._load_jsonl("messages.jsonl")
        agents = {e["agent"] for e in messages}
        assert DIAGNOSIS in agents
        tool_starts = [e for e in messages if e.get("event") == "tool_start"]
        assert tool_starts, "SADE must emit tool_start events"

    def test_step_05_check_submission(self) -> None:
        assert self.session_dir is not None
        assert (self.session_dir / "submission.json").exists()
        assert_submission_fields(self.session_dir)

    def test_step_06_session_close(self) -> None:
        self._step_close_and_verify("community.sade")

    def test_step_07_eval_metrics(self) -> None:
        self._step_eval_metrics()
