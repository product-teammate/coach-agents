"""Reference shim — delegates to ``coach_agents.scripts.list_tasks``."""
from __future__ import annotations

import sys

from coach_agents.scripts.list_tasks import main

if __name__ == "__main__":
    sys.exit(main())
