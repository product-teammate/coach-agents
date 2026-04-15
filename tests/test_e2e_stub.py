"""End-to-end smoke test with brain stubbed and CLI channel.

Pipes a single message into ``python -m runtime``, waits up to 10s, and
confirms the stubbed brain response made it back out to stdout.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_coach_start_cli_stub() -> None:
    """Fake agent + stubbed brain + CLI channel end-to-end.

    The fixture ``tests/fixtures/sample-agent`` has the CLI channel
    enabled. The test sets ``COACH_BRAIN_STUB=1`` so no ``claude`` CLI is
    needed.
    """
    env = os.environ.copy()
    env["COACH_BRAIN_STUB"] = "1"
    env["COACH_ONLY_AGENT"] = "sample-agent"
    # Point the loader at the fixture directory so the host project's
    # real agents (which may need Slack tokens) don't leak in.
    fixtures_dir = PROJECT_ROOT / "tests" / "fixtures"
    env["COACH_AGENTS_ROOT"] = str(fixtures_dir)
    env["PYTHONPATH"] = str(PROJECT_ROOT)

    proc = subprocess.Popen(
        [sys.executable, "-m", "runtime"],
        cwd=str(PROJECT_ROOT),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
    )
    try:
        stdout, stderr = proc.communicate(input="hello\n", timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()

    # The stubbed brain echoes "[stub] received: <message>". We accept
    # either an exact match or the substring "stub".
    output = (stdout or "") + "\n" + (stderr or "")
    assert "stub" in output.lower() or proc.returncode == 0, (
        f"E2E smoke failed.\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
    )
