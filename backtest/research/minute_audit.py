"""Opt-in execution sidecar; never changes the legacy state or CSV schema.

Scopes describe the real caller's decision clock, including legacy out-of-order
calls. Rows retain arrival order; the audit never sorts or recomputes cash.
"""

import json
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

_context = ContextVar("minute_execution_audit", default=None)


@contextmanager
def audit_scope(sink, *, decision_hm, phase, quote_hm=None, quote_for=None):
    token = _context.set((sink, decision_hm, phase, quote_hm, quote_for))
    try:
        yield
    finally:
        _context.reset(token)


def record_fill(state, trade, cash_before):
    context = _context.get()
    if context is None or context[0] is None:
        return
    sink, decision_hm, phase, quote_hm, quote_for = context
    if quote_for is not None:
        quote_hm = quote_for(trade["code"])
    elif quote_hm is None:
        quote_hm = decision_hm
    row = dict(trade)
    row.update(hm=decision_hm, decision_hm=decision_hm, quote_hm=quote_hm,
               phase=phase, cash_before=float(cash_before), cash_after=float(state.cash))
    if callable(sink):
        sink(row)
    else:
        sink.append(row)


def record_rejection(state, code, day, reason, price=None):
    """An attempted order without a fill, kept outside the old trades table."""
    if _context.get() is None or _context.get()[0] is None:
        return
    record_fill(state, {"date": day.strftime("%Y%m%d"), "code": code, "side": "SKIP",
                           "price": price, "shares": 0, "notional": 0., "commission": 0.,
                           "reason": reason}, state.cash)


def write_audit(path, events, *, engine, enabled):
    """Write an independent sidecar, with invocation order intact."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"engine": engine, "fix_minute_cash_order": bool(enabled),
               "order": "actual_invocation_order",
               "cash_order_policy": "chronological" if enabled else "legacy",
               "events": events}
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
