from __future__ import annotations

import pytest
from tests.agent.sandbox_support import (
    docker_available,
    run_security_probe_with_gateway,
)


@pytest.mark.skipif(not docker_available(), reason="docker not available")
class SandboxSecurityIntegrationTest:
    def test_security_probe_with_gateway(self) -> None:
        run_security_probe_with_gateway()
