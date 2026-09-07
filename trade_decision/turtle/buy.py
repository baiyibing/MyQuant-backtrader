# -*- coding: utf-8 -*-
"""Minimal buy-side constants used by ``trade_decision.turtle.sell``.

Full turtle kernel / stop / capital modules stay in OSkhQuant1.3.
"""

from __future__ import annotations

from typing import Tuple

# xlsx two bands: entry x1.04 -> 30%, x1.1 -> 20%
TURTLE_ADD_BANDS: Tuple[Tuple[float, float], ...] = ((0.04, 0.3), (0.10, 0.2))
