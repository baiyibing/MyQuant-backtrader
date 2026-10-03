"""Dedicated opt-in, read-only version1 minute bar scan CLI."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backtest.research.minute_bar_scan_host import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
