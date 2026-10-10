"""Read-only pending SELL diagnostics, separate from account state and stats.

Events describe observations, not fills or promises to retry. Open rows are
snapshots of actual ledger/cursor orders remaining after the final session.
The CSV's detail is the path; event since/last timestamps both equal ds/hm.
Open since is the first observation of that order, last its latest observation.
Missing-session hm is blank. These runtime lists are excluded from asdict.
"""
from backtest.research.csv_ledger import held_fill_key, lot_identity, _ymd, hit_limit_down, s8_open_groups

HEADER = ["kind", "code", "shares", "reason", "since_ds", "since_hm",
          "last_ds", "last_hm", "detail"]


def side_path(reason):
    return ("step_stop" if reason.startswith("stop_loss:step") else
            "scale_out" if reason.startswith("scale_out:") else "peak_dd_clear")


def record_sell_pending(st, *, ds, hm, code, shares=None, path="held", reason, key=None):
    event = dict(ds=_ymd(ds), hm=hm, code=code, shares=shares, path=path, reason=reason)
    st.sell_pending_events.append(event)
    if key is not None:
        history = st._sell_pending_history
        if reason == "next_bar_open_queued" or key not in history:
            history[key] = [event, event]
        else:
            history[key][1] = event


def record_limit(st, code, shares, day, hm, opening, limits, *, path="held", key=None):
    record_sell_pending(st, ds=day, hm=hm, code=code, shares=shares, path=path, key=key,
                        reason="limit_down_open" if limits[1] > 0 and hit_limit_down(opening, limits[1])
                        else "limit_down_fill")


def pending_callback(st, code, pos, day, *, path="held", key=None, shares=None):
    key = held_fill_key(pos) if key is None else key
    def observe(reason, hm):
        record_sell_pending(st, ds=day, hm=hm, code=code, shares=pos.shares if shares is None else shares(),
                            path=path, reason=reason, key=key)
    return observe


def pending_orders(st):
    """Yield only orders still owned by the existing engine/ledger."""
    states = getattr(st, "held_fill_states", {})
    for code, lots in st.positions.items():
        # The entry anchor may already have sold while its T+1 tail survives.
        latched = {key for key, group in s8_open_groups(st, code)
                   if group.first_lot.pending_exit}
        groups = {}
        for pos in lots:
            key = held_fill_key(pos)
            groups.setdefault(key, []).append(pos)
        for key, members in groups.items():
            state = states.get(key, {})
            if state.get("pending") or key in latched or any(p.pending_exit for p in members):
                yield key, code, sum(p.shares for p in members), "held"
            for order in state.get("side_pending", []):
                target, reason, wanted = order[:3]
                path = side_path(reason)
                yield (key, path, lot_identity(target)), code, wanted if wanted is not None else target.shares, path
    for code, (_, wanted) in st.book_state.get("turtle_pending", {}).items():
        if st.positions.get(code):
            yield ("turtle", code), code, wanted, "v9_2_turtle"


def carry_session(st, ds, bars_for_code):
    # Reuse the engine's day spans; never rescan whole minute histories.
    frames = {}
    for key, code, shares, path in pending_orders(st):
        if code not in frames:
            frames[code] = bars_for_code(code)
        bars = frames[code]
        has_bars = bars is not None and not bars.empty
        record_sell_pending(st, ds=ds, hm=int(bars["hm"].iloc[-1]) if has_bars else None,
                            code=code, shares=shares, path=path, key=key,
                            reason="no_next_bar" if has_bars else "suspended_no_bar")


def finish_pending_sells(st):
    st.sell_pending_open = []
    for key, code, shares, path in pending_orders(st):
        first, last = st._sell_pending_history.get(key, [{}, {}])
        st.sell_pending_open.append(dict(code=code, shares=shares,
            reason=last.get("reason", "no_next_bar"), since_ds=first.get("ds", ""),
            since_hm=first.get("hm"), last_ds=last.get("ds", ""),
            last_hm=last.get("hm"), detail=path))


def artifact_rows(st):
    for event in st.sell_pending_events:
        yield dict(kind="event", code=event["code"], shares=event["shares"],
                   reason=event["reason"], since_ds=event["ds"], since_hm=event["hm"],
                   last_ds=event["ds"], last_hm=event["hm"], detail=event["path"])
    for row in st.sell_pending_open:
        yield dict(kind="open", **row)
