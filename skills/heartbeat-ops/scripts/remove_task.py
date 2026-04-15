"""Reference shim — delegates to ``coach_agents.scripts.remove_task``."""
from __future__ import annotations

import sys

from coach_agents.scripts.remove_task import main

if __name__ == "__main__":
    sys.exit(main())
