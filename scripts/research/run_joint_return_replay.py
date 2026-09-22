"""Explicit-file CLI for joint-return R1 synthetic/frozen minute replay; no lake access."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backtest.research.joint_return_replay import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
