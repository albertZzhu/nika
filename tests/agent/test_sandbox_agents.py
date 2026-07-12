from __future__ import annotations

import pytest
import json
import os
from pathlib import Path
from agent.utils.phases import DIAGNOSIS, SUBMISSION
from nika.utils.session_store import SessionStore
from tests.agent._assertions import assert_phase_messages, assert_submission_fields
from tests.agent.sandbox_support import docker_available
from tests.support.integration_base import OrderedPipelineTestCase
from tests.support.integration_pipeline import (
    CommonPipelineSteps,
    claude_cli_available,
    claude_sdk_available,
    codex_cli_available,
    codex_sdk_available,
    load_test_env,
)

load_test_env()
if Path(".env.sandbox.local").is_file():
    os.environ.setdefault("NIKA_SANDBOX_NETWORK", "host")
CODEX_MODEL = "gpt-5.4-mini"
CLAUDE_MODEL = "claude-sonnet-4-20250514"
MAX_STEPS = 20
_SANDBOX_SKIP = not docker_available()


class SandboxAgentPipelineBase(CommonPipelineSteps, OrderedPipelineTestCase):
    agent_type: str = ""
    model: str = ""

    def test_step_01_start_env(self) -> None:
        self._step_start_env()

    def test_step_02_inject_failure(self) -> None:
        self._step_inject_failure()

    def test_step_03_run_sandbox_agent(self) -> None:
        assert self.session_id is not None
        self._run_agent(
            agent_type=self.agent_type,
            model=self.model,
            max_steps=MAX_STEPS,
            sandbox=True,
        )
        row = SessionStore().get_session(self.session_id)
        assert row.get("agent_type") == self.agent_type

    def test_step_04_check_sandbox_artifacts(self) -> None:
        assert self.session_dir is not None
        manifest = self.session_dir / "sandbox_manifest.json"
        assert manifest.is_file()
        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert data["agent_type"] == self.agent_type
        assert "OPENAI_API_KEY" not in manifest.read_text(encoding="utf-8")
        assert "ANTHROPIC_API_KEY" not in manifest.read_text(encoding="utf-8")
        messages = self._load_jsonl("messages.jsonl")
        assert_phase_messages(messages, require_diagnosis_tools=True)
        agents = {e["agent"] for e in messages}
        assert DIAGNOSIS in agents
        assert SUBMISSION in agents

    def test_step_05_check_submission(self) -> None:
        assert self.session_dir is not None
        assert (self.session_dir / "submission.json").exists()
        assert_submission_fields(self.session_dir)

    def test_step_06_session_close(self) -> None:
        self._step_close_and_verify(self.agent_type)

    def test_step_07_eval_metrics(self) -> None:
        self._step_eval_metrics()


@pytest.mark.skipif(_SANDBOX_SKIP, reason="Docker sandbox image not available")
@pytest.mark.skipif(not codex_cli_available(), reason="Codex CLI credentials required")
class SandboxCodexCliPipelineTest(SandboxAgentPipelineBase):
    agent_type = "local_cli.codex_cli"
    model = CODEX_MODEL


@pytest.mark.skipif(_SANDBOX_SKIP, reason="Docker sandbox image not available")
@pytest.mark.skipif(
    not claude_cli_available(), reason="Claude CLI credentials required"
)
class SandboxClaudeCliPipelineTest(SandboxAgentPipelineBase):
    agent_type = "local_cli.claude_cli"
    model = CLAUDE_MODEL


@pytest.mark.skipif(_SANDBOX_SKIP, reason="Docker sandbox image not available")
@pytest.mark.skipif(not codex_sdk_available(), reason="Codex SDK credentials required")
class SandboxCodexSdkPipelineTest(SandboxAgentPipelineBase):
    agent_type = "sdk.codex_sdk"
    model = CODEX_MODEL


@pytest.mark.skipif(_SANDBOX_SKIP, reason="Docker sandbox image not available")
@pytest.mark.skipif(
    not claude_sdk_available(), reason="Claude SDK credentials required"
)
class SandboxClaudeSdkPipelineTest(SandboxAgentPipelineBase):
    agent_type = "sdk.claude_sdk"
    model = CLAUDE_MODEL
