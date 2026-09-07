# -*- coding: utf-8 -*-
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent
readme = """# chip index

See turnover_resistance.md section 4.6 for cross-script turnover alignment.

Verify: scripts/research/verify_turnover_resistance_alignment.py
"""
(REPO / "docs/backtest/chip/README.md").write_text(readme, encoding="utf-8", newline="\n")
print("ok")
