#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI entry for the unified-exit precheck reporter (PR #88 §9.7).

See ``backtest.research.unified_exit_precheck`` for the library API.

Usage:
    D:/anaconda3/envs/vanna312/python.exe scripts/research/report_unified_exit_precheck.py
    D:/anaconda3/envs/vanna312/python.exe scripts/research/report_unified_exit_precheck.py \\
        --start 20251023 --end 20260909 --out-json backtest_output/unified_exit_precheck.json
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backtest.research.unified_exit_precheck import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
