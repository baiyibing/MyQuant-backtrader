#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI entry for unified-exit Mode B grid (assembly / evaluate / report).

Usage (host with F lake; Slice E — not a merge gate)::

    D:/anaconda3/envs/vanna312/python.exe scripts/research/run_unified_exit_modeb.py \\
        --pool-dir stock_pool --start 20251023 --end 20260909

Codex VM: synthetic fixtures only via the library API / pytest.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backtest.research.unified_exit_modeb import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
