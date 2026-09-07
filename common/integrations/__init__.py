# -*- coding: utf-8 -*-
"""
``common.integrations`` — I/O adapters and execution-side wiring (Redis ``qmt_ops``, QMT session,
order_ops, risk fuse runtime, RSRS indicator wiring for ``trade_decision``, hkcodex calendar probe for resolve).

**Infra** lives under :mod:`common.infra`; **domain contracts** in :mod:`oskh_core`. Import stable
surfaces explicitly from ``common.integrations.<module>`` (e.g. ``qmt_market_ops_client``).
Order-ops dispatch plane: :mod:`oskh_core.order_intent_dispatch`.
"""

__all__: list[str] = []
