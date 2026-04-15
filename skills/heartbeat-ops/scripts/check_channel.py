"""Reference shim — delegates to ``coach_agents.scripts.check_channel``.

This file exists so Claude Code can locate the script from inside the
heartbeat-ops skill directory without reaching into the package layout.
"""
from __future__ import annotations

import sys

from coach_agents.scripts.check_channel import main

if __name__ == "__main__":
    sys.exit(main())
