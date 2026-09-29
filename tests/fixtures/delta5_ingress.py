"""Invented complete sessions; oracle side never imports the ingress mapper.

Source construction iterates physical START intervals; native construction
independently enumerates literal END keys. No real security data is represented.
"""

from copy import deepcopy

import pandas as pd

CODE = "600000.SH"
SOURCE_SYMBOL = "SYNTH_A"
DAYS = ("20260901", "20260902", "20260903", "20260904")
UNIT = "raw_shares_incremental"


def fixture(*, days=1, label="START", encoding="local_wall", volume=2500,
            overrides=None, prices=None, suspended=(), signals=(0,), budget=5000,
            oracle=None, cell="M2"):
    overrides, prices = overrides or {}, prices or [10.] * days
    sessions = list(DAYS[:days])
    reference = "20260831"
    pool = {DAYS[i]: [CODE] for i in signals}
    source = {
        "kind": "synthetic", "schema": "d5_synthetic_source_v1",
        "publisher": "data-free arithmetic fixture", "snapshot_id": "synthetic-20260929-v1",
        "evidence_id": "invented-full-session-no-events-v1",
        "unit": UNIT, "price_domain": "raw", "incremental": True, "float_exact": True,
        "label": label, "time_encoding": encoding,
        "interval_policy": "physical_one_minute_no_auction_duplication",
        "availability_rule": "explicit_record_publication_time",
        "start": sessions[0], "end": sessions[-1], "reference_day": reference,
        "calendar": [reference, *sessions], "sessions": sessions,
        "no_events": {"start": reference, "end": sessions[-1], "events": [],
                      "evidence_id": "invented-full-session-no-events-v1"},
        "instruments": {SOURCE_SYMBOL: {"engine_symbol": CODE, "name": "合成主板A",
                        "board": "mainboard", "ordinary": True, "is_st": False,
                        "listed_from": reference, "listed_through": sessions[-1]}},
        "status": {SOURCE_SYMBOL: {d: "suspended" if i in suspended else "active"
                                   for i, d in enumerate(sessions)}},
        "pool": deepcopy(pool), "minute": [], "daily": [],
    }

    def encoded(ts):
        if encoding == "utc_instant":
            return ts.tz_localize("Asia/Shanghai").tz_convert("UTC").isoformat()
        if encoding == "utc_wall":
            return ts.tz_localize("UTC").isoformat()
        return ts.isoformat()

    for i, day in enumerate(sessions):
        if i in suspended:
            continue
        for start_hm in (*range(570, 690), *range(780, 900)):
            change = overrides.get((i, start_hm + 1), {})
            begin = pd.Timestamp(day) + pd.Timedelta(minutes=start_hm)
            end = begin + pd.Timedelta(minutes=1)
            px = change.get("price", prices[i])
            v = change.get("volume", volume)
            o = change.get("open", px)
            source["minute"].append({
                "symbol": SOURCE_SYMBOL, "begin": encoded(begin), "end": encoded(end),
                "timestamp": encoded(begin if label == "START" else end),
                "available_at": encoded(end + pd.Timedelta(seconds=change.get("delay_seconds", 0))),
                "volume": v, "volume_state": "zero" if v == 0 else "positive",
                "open": float(o), "high": float(max(o, px)),
                "low": float(min(o, px)), "close": float(px),
            })
    for day, px in zip([reference, *sessions], [prices[0], *prices]):
        source["daily"].append({"symbol": SOURCE_SYMBOL, "day": day,
                                **{k: float(px) for k in ("open", "high", "low", "close")}})

    # Separate expected-input construction: already normalized, no mapper calls.
    native = {"minute": {}, "daily": {CODE: []}, "samples": [], "pool": deepcopy(pool),
              "names": {CODE: "合成主板A"}, "start": sessions[0], "end": sessions[-1]}
    for i, day in enumerate(sessions):
        for close_hm in (*range(571, 691), *range(781, 901)):
            change = overrides.get((i, close_hm), {})
            if i in suspended:
                native["samples"].append([CODE, day, close_hm, None])
                continue
            px = float(change.get("price", prices[i]))
            op = float(change.get("open", px))
            native["minute"].setdefault(CODE, []).append({
                "time": f"{day[:4]}-{day[4:6]}-{day[6:]}T{close_hm // 60:02}:{close_hm % 60:02}:00",
                "ymd": day, "hm": close_hm, "open": op, "high": max(op, px),
                "low": min(op, px), "close": px,
            })
            delay = change.get("delay_seconds", 0)
            native["samples"].append([CODE, day, close_hm,
                                      [int(change.get("volume", volume)), close_hm + (delay + 59) // 60, UNIT]])
    for day, px in zip([reference, *sessions], [prices[0], *prices]):
        native["daily"][CODE].append({"day": f"{day[:4]}-{day[4:6]}-{day[6:]}",
                                      **{k: float(px) for k in ("open", "high", "low", "close")}})
    return {"source": source, "native": native, "cell": cell,
            "scope": "complete synthetic sessions; explicit per-case arithmetic oracle",
            "parameters": {"total_cash": 100000., "daily_quota": float(budget),
                           "name_budget": float(budget), "stop_pct": .05,
                           "buy_cost_rate": .0015, "sell_cost_rate": .0015, "min_cost": 5.,
                           "take_profit_mode": "disabled"},
            "oracle": {"fills": [["BUY", 200, 10., 5.]] if oracle is None else oracle}}
