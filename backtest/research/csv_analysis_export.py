"""CSV-engine post-run analysis pack (MyQuant analysis_export analogue).

Reads an already-written run dir (``trades.csv`` + ``daily_equity.csv``).
Does not re-simulate. Optional joins: scores, buy-state sidecar, ST, age.

Stable filenames under ``<run-dir>/analysis/`` — see
``docs/backtest/prompt-csv-human-analysis.md``.
Every bundle also writes ``字段说明.txt`` (copy of
``docs/backtest/csv-analysis-fields.txt`` plus this run's path and window).
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict, deque
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from backtest.research.topk_dropout_eligibility import (
    WINRATIO_LT,
    buy_state_oral_ok,
    load_age_min_buy_ymd,
    load_buy_state_sidecar,
    load_st_daily_by_day,
    st_codes_asof,
)
from backtest.research.topk_dropout_scores import (
    _bare_or_canon,
    load_scores_from_args,
)

FILL_SIDES = frozenset({"BUY", "SELL"})
MARK_SIDES = frozenset({"EOD_MARK"})
_REPO = Path(__file__).resolve().parents[2]
FIELDS_NOTE_NAME = "字段说明.txt"
FIELDS_NOTE_SRC = _REPO / "docs" / "backtest" / "csv-analysis-fields.txt"
IDENTITY_FIELDS_NOTE_SRC = _REPO / "docs" / "backtest" / "csv-analysis-identity-fields.txt"
HUMAN_ANALYSIS_NAME = "human_analysis.txt"
BUNDLE_CSV = (
    "nav_daily.csv",
    "trades_daily.csv",
    "round_trips.csv",
    "ledger_by_stock.csv",
    "pnl_by_stock.csv",
    "positions_daily.csv",
)
CSV_ENCODING = "utf-8-sig"


def _ymd(value) -> str:
    digits = "".join(ch for ch in str(value).strip() if ch.isdigit())
    if len(digits) < 8:
        raise ValueError(f"cannot parse YYYYMMDD: {value!r}")
    return digits[:8]


def _iso(ymd: str) -> str:
    return f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:8]}"


def _canon(raw) -> str:
    text = str(raw)
    return _bare_or_canon(text) or text.strip().upper()


def write_fields_note(
    out_dir: Path, *, run_dir: Path, nav: pd.DataFrame, has_identity: bool = False,
) -> Path:
    """Copy the repo field guide into the bundle, with this run's path and window."""
    if not FIELDS_NOTE_SRC.is_file():
        raise FileNotFoundError(f"fields note missing: {FIELDS_NOTE_SRC}")
    body = FIELDS_NOTE_SRC.read_text(encoding="utf-8")
    if has_identity:
        body += "\n\n" + IDENTITY_FIELDS_NOTE_SRC.read_text(encoding="utf-8")
    first = str(nav["date"].iloc[0]) if len(nav) else ""
    last = str(nav["date"].iloc[-1]) if len(nav) else ""
    header = f"本次导出\nrun_dir: {run_dir}\n窗口: {first} .. {last}\n\n"
    dest = Path(out_dir) / FIELDS_NOTE_NAME
    dest.write_text(header + body, encoding="utf-8", newline="\n")
    return dest


def _pct(value: float | None, *, signed: bool = False) -> str:
    if value is None or value != value:
        return "n/a"
    return f"{value:+.2%}" if signed else f"{value:.2%}"


def _money(value: float | None) -> str:
    if value is None or value != value:
        return "n/a"
    return f"{value:,.2f}"


def drawdown_and_win_rates(
    nav: pd.DataFrame,
    trips: pd.DataFrame,
    account: float | None,
) -> dict[str, Any]:
    """Max drawdown on nav, closed-lot win rate, and win rate by sell reason.

    A closed lot wins when realized_pnl > 0. An open lot wins when mtm_pnl > 0.
    The headline win rate counts closed lots only.
    """
    out: dict[str, Any] = {
        "return_on_account": None,
        "max_drawdown": None,
        "max_drawdown_date": None,
        "drawdown_peak_equity": None,
        "drawdown_trough_equity": None,
        "wins_closed": 0,
        "losses_closed": 0,
        "win_rate_closed": None,
        "wins_open": 0,
        "win_rate_with_open": None,
        "by_sell_reason": [],
    }
    if len(nav):
        equity = nav["equity"].astype(float)
        peak = equity.cummax()
        dd = equity / peak - 1.0
        i = int(dd.idxmin())
        last = float(equity.iloc[-1])
        out["max_drawdown"] = float(dd.iloc[i])
        out["max_drawdown_date"] = str(nav["date"].iloc[i])
        out["drawdown_peak_equity"] = float(peak.iloc[i])
        out["drawdown_trough_equity"] = float(equity.iloc[i])
        base = float(account) if account else float(equity.iloc[0])
        out["return_on_account"] = (last / base - 1.0) if base else None

    closed = trips.iloc[0:0]
    opened = trips.iloc[0:0]
    if len(trips) and "status" in trips.columns:
        closed = trips[trips["status"] == "closed"]
        opened = trips[trips["status"] == "open_eod"]
    wins_closed = int((closed["realized_pnl"] > 0).sum()) if len(closed) else 0
    losses_closed = int((closed["realized_pnl"] <= 0).sum()) if len(closed) else 0
    wins_open = int((opened["mtm_pnl"] > 0).sum()) if len(opened) else 0
    n_closed = int(len(closed))
    n_open = int(len(opened))
    out["wins_closed"] = wins_closed
    out["losses_closed"] = losses_closed
    out["wins_open"] = wins_open
    out["win_rate_closed"] = (wins_closed / n_closed) if n_closed else None
    denom = n_closed + n_open
    out["win_rate_with_open"] = ((wins_closed + wins_open) / denom) if denom else None
    rows = []
    if n_closed:
        grouped = closed.fillna({"sell_reason": ""}).groupby("sell_reason", sort=False)
        for reason, g in grouped:
            w = int((g["realized_pnl"] > 0).sum())
            rows.append(
                {
                    "sell_reason": str(reason),
                    "n": int(len(g)),
                    "wins": w,
                    "win_rate": w / len(g),
                    "realized_pnl": float(g["realized_pnl"].sum()),
                }
            )
        rows.sort(key=lambda r: (-r["n"], r["sell_reason"]))
    out["by_sell_reason"] = rows
    return out


def format_human_analysis(
    stats: Mapping[str, Any],
    *,
    n_closed: int,
    n_open: int,
) -> str:
    """Chinese readout of return, max drawdown, and win rate."""
    lines = [
        "盘后结果",
        f"总收益率(全资金): {_pct(stats.get('return_on_account'), signed=True)}",
        (
            f"最大回撤: {_pct(stats.get('max_drawdown'), signed=True)}，"
            f"出现在 {stats.get('max_drawdown_date')}："
            f"净值从峰值 {_money(stats.get('drawdown_peak_equity'))} "
            f"落到 {_money(stats.get('drawdown_trough_equity'))}。"
        ),
        (
            f"已平仓胜率: {_pct(stats.get('win_rate_closed'))}"
            f"（{stats.get('wins_closed')} 胜 / {n_closed} 笔）。"
            "realized_pnl > 0 算胜。期末未平不计入。"
        ),
        (
            f"含期末浮盈: {_pct(stats.get('win_rate_with_open'))}"
            f"（{int(stats.get('wins_closed') or 0) + int(stats.get('wins_open') or 0)} "
            f"/ {n_closed + n_open}）。未平以 mtm_pnl > 0 算胜。"
        ),
        "按卖因（仅已平）:",
    ]
    reasons = list(stats.get("by_sell_reason") or [])
    if not reasons:
        lines.append("  （无已平仓）")
    for row in reasons:
        lines.append(
            f"  {row['sell_reason']}  {row['n']} 笔  "
            f"胜率 {_pct(row['win_rate'])}  "
            f"盈亏 {_money(row['realized_pnl'])}"
        )
    return "\n".join(lines) + "\n"


def parse_account_from_summary(text: str) -> float | None:
    """``期末净值: 104,572,769.55 / 100,000,000`` → 1e8."""
    for line in text.splitlines():
        if "期末净值" not in line or "/" not in line:
            continue
        right = line.split("/", 1)[1]
        token = right.replace(",", "").split()
        if not token:
            continue
        try:
            return float(token[0])
        except ValueError:
            continue
    return None


def load_nav(run_dir: Path) -> pd.DataFrame:
    path = Path(run_dir) / "daily_equity.csv"
    if not path.is_file():
        raise FileNotFoundError(f"daily_equity.csv not found: {path}")
    eq = pd.read_csv(path)
    if eq.empty or "date" not in eq.columns or "equity" not in eq.columns:
        raise ValueError(f"daily_equity.csv needs date,equity: {path}")
    out = pd.DataFrame(
        {
            "date": eq["date"].map(lambda x: _iso(_ymd(x))),
            "ymd": eq["date"].map(_ymd),
            "equity": pd.to_numeric(eq["equity"], errors="raise"),
        }
    )
    peak = out["equity"].cummax()
    out["drawdown"] = out["equity"] / peak - 1.0
    return out


def load_trades(run_dir: Path) -> pd.DataFrame:
    path = Path(run_dir) / "trades.csv"
    if not path.is_file():
        raise FileNotFoundError(f"trades.csv not found: {path}")
    raw = pd.read_csv(path)
    if raw.empty:
        return raw
    cols = {str(c).strip().lower(): c for c in raw.columns}
    code_c = cols.get("code") or cols.get("symbol") or cols.get("instrument")
    if code_c is None or "side" not in cols or "date" not in cols:
        raise ValueError(f"trades.csv needs date, code/symbol, side: {path}")
    work = pd.DataFrame(
        {
            "ymd": raw[cols["date"]].map(_ymd),
            "code": raw[code_c].map(_canon),
            "side": raw[cols["side"]].astype(str).str.upper(),
            "price": pd.to_numeric(raw[cols["price"]], errors="coerce")
            if "price" in cols
            else float("nan"),
            "shares": pd.to_numeric(raw[cols["shares"]], errors="coerce")
            if "shares" in cols
            else float("nan"),
        }
    )
    if "notional" in cols:
        work["notional"] = pd.to_numeric(raw[cols["notional"]], errors="coerce")
    else:
        work["notional"] = work["price"] * work["shares"]
    if "commission" in cols:
        work["commission"] = pd.to_numeric(
            raw[cols["commission"]], errors="coerce"
        ).fillna(0.0)
    else:
        work["commission"] = 0.0
    if "reason" in cols:
        work["reason"] = raw[cols["reason"]].fillna("").astype(str)
    else:
        work["reason"] = ""
    work["date"] = work["ymd"].map(_iso)
    work["notional"] = work["notional"].fillna(work["price"] * work["shares"])
    if "position_id" in cols:
        identity = raw[cols["position_id"]].map(_position_id)
        if identity.any():
            work["position_id"] = identity
            if "lot" in cols:
                work["lot"] = _integer_lots(raw[cols["lot"]])
    return work.reset_index(drop=True)


def _position_id(value) -> str:
    return "" if pd.isna(value) else str(value).strip()


def _has_position_ids(trades: pd.DataFrame) -> bool:
    return "position_id" in trades and trades["position_id"].map(_position_id).any()


def _integer_lots(values: pd.Series) -> pd.Series:
    """Keep optional lot numbers as integers, including when some rows lack one."""
    try:
        return pd.to_numeric(values, errors="coerce").astype("Int64")
    except (TypeError, ValueError) as exc:
        raise ValueError("lot identifiers must be integers or empty") from exc


def _lot_id(value) -> int | None:
    if pd.isna(value):
        return None
    number = int(value)
    if number != value:
        raise ValueError("lot identifiers must be integers or empty")
    return number


def _matching_lot(q: deque, position_id: str, lot_id=None) -> int | None:
    """An identified sell stays in its position; an empty ID uses code FIFO."""
    candidates = [
        i for i, lot in enumerate(q)
        if not position_id or lot.get("position_id") == position_id
    ]
    if position_id and pd.notna(lot_id):
        exact = [i for i in candidates if q[i].get("lot") == lot_id]
        # A producer without BUY lot numbers can still use position FIFO.
        candidates = exact or [i for i in candidates if pd.isna(q[i].get("lot"))]
    return candidates[0] if candidates else None


def _sell_matches(
    q: deque, row: dict, *, ymd: str, buy_history: deque,
) -> Iterator[tuple[dict, dict]]:
    """Allocate identified fills by quantity; preserve legacy whole-lot FIFO."""
    identity = row.get("position_id", "")
    lot_id = row.get("lot")
    if not identity:
        if not q:
            raise SystemExit(f"unmatched SELL {row['code']} {ymd}")
        yield q.popleft(), row
        return
    remaining = row["shares"]
    last_matched = None
    while remaining > 1e-9:
        selected = _matching_lot(q, identity, lot_id)
        if selected is None:
            # Bonus shares need no extra purchase cost. Keep the original BUY
            # provenance even after its paid shares have all been matched.
            history = deque(reversed(buy_history))
            source = _matching_lot(history, identity, lot_id)
            if source is None:
                raise SystemExit(
                    f"unmatched SELL {row['code']} {ymd}: no recorded BUY for "
                    f"position_id={identity} lot={lot_id}"
                )
            matched = dict(last_matched if last_matched is not None else history[source])
            shares = remaining
            matched.update(shares=shares, buy_price=0.0, buy_notional=0.0, buy_commission=0.0)
        else:
            lot = q[selected]
            shares = min(remaining, lot["shares"])
            matched = dict(lot)
            fraction = shares / lot["shares"]
            for field in ("shares", "buy_notional", "buy_commission"):
                matched[field] *= fraction
                lot[field] -= matched[field]
            if lot["shares"] <= 1e-9:
                del q[selected]
            last_matched = matched
        fill = dict(row)
        fill["shares"] = shares
        fill["notional"] *= shares / row["shares"]
        fill["commission"] *= shares / row["shares"]
        yield matched, fill
        remaining -= shares


def _ranks(score_map: Mapping[str, float]) -> dict[str, int]:
    ranked = sorted(score_map.items(), key=lambda kv: (-kv[1], kv[0]))
    return {code: i + 1 for i, (code, _) in enumerate(ranked)}


def _score_lookup(
    by_day: Mapping[str, dict[str, float]],
    cache: dict[str, dict[str, int]],
    ymd: str,
    code: str,
) -> tuple[float | None, int | None, int]:
    smap = by_day.get(ymd) or {}
    if ymd not in cache:
        cache[ymd] = _ranks(smap) if smap else {}
    return smap.get(code), cache[ymd].get(code), len(smap)


def _cond_label(
    close: float, ma20: float, ma60: float, wr: float
) -> tuple[bool, bool, str]:
    cond1 = close < ma20 and close < ma60 and wr < WINRATIO_LT
    cond2 = close > ma20
    if cond1:
        label = "cond1_below_ma_and_wr_lt_0.10"
    elif cond2:
        label = "cond2_close_gt_ma20"
    else:
        label = "not_oral_ok"
    return cond1, cond2, label


def sidecar_fields(
    state_map: Mapping[tuple[str, str], tuple[float, float, float, float]] | None,
    code: str,
    ymd: str,
) -> dict[str, Any]:
    empty = {
        "sidecar_close": None,
        "ma20": None,
        "ma60": None,
        "winratio": None,
        "close_minus_ma20": None,
        "close_minus_ma60": None,
        "close_over_ma20": None,
        "close_over_ma60": None,
        "cond1_below_ma_wr": None,
        "cond2_close_gt_ma20": None,
        "buy_state_label": None,
        "buy_state_ok": None,
        "sidecar_hit": False,
    }
    if not state_map:
        return empty
    row = state_map.get((code, ymd))
    if row is None:
        return empty
    close, ma20, ma60, wr = row
    cond1, cond2, label = _cond_label(close, ma20, ma60, wr)
    return {
        "sidecar_close": close,
        "ma20": ma20,
        "ma60": ma60,
        "winratio": wr,
        "close_minus_ma20": close - ma20,
        "close_minus_ma60": close - ma60,
        "close_over_ma20": (close / ma20 - 1.0) if ma20 else None,
        "close_over_ma60": (close / ma60 - 1.0) if ma60 else None,
        "cond1_below_ma_wr": cond1,
        "cond2_close_gt_ma20": cond2,
        "buy_state_label": label,
        "buy_state_ok": buy_state_oral_ok(close, ma20, ma60, wr),
        "sidecar_hit": True,
    }


def _annotate_row(
    rec: pd.Series,
    *,
    scores_by_day: Mapping[str, dict[str, float]] | None,
    rank_cache: dict[str, dict[str, int]],
    state_map,
    st_by_day,
    age_map: Mapping[str, str],
    topk: int,
) -> dict[str, Any]:
    ymd = rec["ymd"]
    code = rec["code"]
    score = rank = n_scores = None
    if scores_by_day:
        score, rank, n_scores = _score_lookup(scores_by_day, rank_cache, ymd, code)
    is_st = None
    if st_by_day is not None:
        is_st = code in st_codes_asof(st_by_day, ymd)
    min_buy = age_map.get(code) if age_map else None
    age_ok = None if min_buy is None else ymd >= min_buy
    return {
        "date": rec["date"],
        "code": code,
        "side": rec["side"],
        "price": float(rec["price"]) if pd.notna(rec["price"]) else None,
        "shares": float(rec["shares"]) if pd.notna(rec["shares"]) else None,
        "notional": float(rec["notional"]) if pd.notna(rec["notional"]) else None,
        "commission": float(rec["commission"]) if pd.notna(rec["commission"]) else 0.0,
        "reason": rec["reason"],
        "score": score,
        "score_rank": rank,
        "score_universe": n_scores,
        "in_topk": rank is not None and rank <= int(topk),
        "is_st": is_st,
        "min_buy_ymd": min_buy,
        "age_ok": age_ok,
        **sidecar_fields(state_map, code, ymd),
    }


def pair_round_trips(
    trades: pd.DataFrame,
    nav: pd.DataFrame,
    *,
    scores_by_day=None,
    state_map=None,
    st_by_day=None,
    age_map: Mapping[str, str] | None = None,
    topk: int = 50,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Pair by position/lot when present, otherwise code FIFO; never resimulate."""
    rank_cache: dict[str, dict[str, int]] = {}
    age_map = age_map or {}
    cal_pos = {ymd: i for i, ymd in enumerate(nav["ymd"])}
    last_ymd = str(nav["ymd"].iloc[-1]) if len(nav) else None

    def hold_days(buy_ymd: str, sell_ymd: str | None) -> int | None:
        if sell_ymd is None:
            return None
        a, b = cal_pos.get(buy_ymd), cal_pos.get(sell_ymd)
        if a is None or b is None:
            return None
        return int(b - a)

    annotated: list[dict] = []
    opens: dict[str, deque] = defaultdict(deque)
    buy_history: dict[str, deque] = defaultdict(deque)
    eod: dict[str | tuple, dict] = {}
    trips: list[dict] = []
    ledger: list[dict] = []
    cum_realized: dict[str, float] = defaultdict(float)
    has_identity = _has_position_ids(trades)
    has_lot = has_identity and "lot" in trades

    cols = list(trades.columns)
    for rec in trades.itertuples(index=False):
        row = _annotate_row(
            pd.Series({c: getattr(rec, c) for c in cols}),
            scores_by_day=scores_by_day,
            rank_cache=rank_cache,
            state_map=state_map,
            st_by_day=st_by_day,
            age_map=age_map,
            topk=topk,
        )
        identity = _position_id(getattr(rec, "position_id", ""))
        lot_id = _lot_id(getattr(rec, "lot", None)) if has_lot else None
        extra = {"position_id": identity} if has_identity else {}
        if has_lot:
            extra["lot"] = lot_id
        row.update(extra)
        side = row["side"]
        if side in FILL_SIDES or side == "SKIP":
            annotated.append(row)
        code = row["code"]
        ymd = rec.ymd
        if side == "BUY":
            lot = {
                "code": code,
                "buy_date": row["date"],
                "buy_ymd": ymd,
                "buy_price": row["price"],
                "shares": row["shares"],
                "buy_notional": row["notional"],
                "buy_commission": row["commission"],
                "buy_score": row["score"],
                "buy_rank": row["score_rank"],
                "buy_in_topk": row["in_topk"],
                "is_st_buy_day": row["is_st"],
                "min_buy_ymd": row["min_buy_ymd"],
                "age_ok": row["age_ok"],
                "buy_sidecar_close": row["sidecar_close"],
                "buy_ma20": row["ma20"],
                "buy_ma60": row["ma60"],
                "buy_winratio": row["winratio"],
                "buy_close_minus_ma20": row["close_minus_ma20"],
                "buy_close_minus_ma60": row["close_minus_ma60"],
                "buy_close_over_ma20": row["close_over_ma20"],
                "buy_close_over_ma60": row["close_over_ma60"],
                "buy_cond1_below_ma_wr": row["cond1_below_ma_wr"],
                "buy_cond2_close_gt_ma20": row["cond2_close_gt_ma20"],
                "buy_state_label": row["buy_state_label"],
                "buy_state_ok": row["buy_state_ok"],
                "buy_sidecar_hit": row["sidecar_hit"],
                **extra,
            }
            recorded_lot = lot
            existing = _matching_lot(opens[code], identity, lot_id)
            if (identity and pd.notna(lot_id) and existing is not None
                    and opens[code][existing].get("lot") == lot_id):
                # Tail-window children share one ledger lot and one eventual exit.
                merged = opens[code][existing]
                merged["shares"] += lot["shares"]
                merged["buy_notional"] += lot["buy_notional"]
                merged["buy_commission"] += lot["buy_commission"]
                merged["buy_price"] = merged["buy_notional"] / merged["shares"]
                recorded_lot = merged
            else:
                opens[code].append(lot)
            if identity:
                # A copy must survive both quantity depletion and queue removal.
                buy_history[code].append(dict(recorded_lot))
            ledger.append(
                {
                    "date": row["date"],
                    "code": code,
                    "event": "buy",
                    "delta_amount": row["shares"],
                    "amount_after": sum(x["shares"] for x in opens[code]),
                    "price": row["price"],
                    "entry_price": row["price"],
                    "trade_value": row["notional"],
                    "est_cost": row["commission"],
                    "holding_days": 0,
                    "realized_pnl": 0.0,
                    "unrealized_pnl": 0.0,
                    "cum_realized_pnl": cum_realized[code],
                    "reason": row["reason"],
                    **extra,
                }
            )
        elif side == "SELL":
            for lot, fill in _sell_matches(
                opens[code], row, ymd=ymd, buy_history=buy_history[code],
            ):
                debit = (lot["buy_notional"] or 0.0) + (lot["buy_commission"] or 0.0)
                credit = (fill["notional"] or 0.0) - (fill["commission"] or 0.0)
                pnl = credit - debit
                cum_realized[code] += pnl
                trips.append(
                    {
                        **{k: v for k, v in lot.items() if k != "buy_ymd"},
                        "sell_date": fill["date"],
                        "status": "closed",
                        "hold_trading_days": hold_days(lot["buy_ymd"], ymd),
                        "sell_price": fill["price"],
                        "sell_notional": fill["notional"],
                        "sell_commission": fill["commission"],
                        "sell_reason": fill["reason"],
                        "sell_score": fill["score"],
                        "sell_rank": fill["score_rank"],
                        "realized_pnl": pnl,
                        "return_pct": pnl / debit if debit else None,
                        "mtm_pnl": None,
                        "sell_sidecar_close": fill["sidecar_close"],
                        "sell_ma20": fill["ma20"],
                        "sell_ma60": fill["ma60"],
                        "sell_winratio": fill["winratio"],
                    }
                )
                remain = sum(x["shares"] for x in opens[code])
                ledger.append(
                    {
                        "date": fill["date"],
                        "code": code,
                        "event": "sell",
                        "delta_amount": fill["shares"],
                        "amount_after": remain,
                        "price": fill["price"],
                        "entry_price": lot["buy_price"],
                        "trade_value": fill["notional"],
                        "est_cost": fill["commission"],
                        "holding_days": hold_days(lot["buy_ymd"], ymd),
                        "realized_pnl": pnl,
                        "unrealized_pnl": 0.0 if remain <= 1e-9 else None,
                        "cum_realized_pnl": cum_realized[code],
                        "reason": fill["reason"],
                        **({"position_id": lot.get("position_id", "")} if has_identity else {}),
                        **({"lot": lot.get("lot")} if has_lot else {}),
                    }
                )
        elif side == "EOD_MARK":
            mark_key = (code, identity, lot_id if pd.notna(lot_id) else None) if identity else code
            eod[mark_key] = {
                "ymd": ymd,
                "price": row["price"],
                "notional": row["notional"],
                "shares": row["shares"],
            }

    for code, q in opens.items():
        for lot in q:
            identity = lot.get("position_id", "")
            lot_id = lot.get("lot")
            mark_key = (code, identity, lot_id if pd.notna(lot_id) else None) if identity else code
            mark = eod.get(mark_key)
            if mark is None and identity:
                mark = eod.get((code, identity, None)) or eod.get(code)
            if mark and identity:
                # Marks may cover several lots; value each surviving lot once.
                mark = {**mark, "notional": lot["shares"] * mark["price"]}
            sell_ymd = mark["ymd"] if mark else last_ymd
            debit = (lot["buy_notional"] or 0.0) + (lot["buy_commission"] or 0.0)
            mtm = (
                (float(mark["notional"]) - debit)
                if mark and mark.get("notional") is not None
                else None
            )
            sell_fields = (
                sidecar_fields(state_map, code, sell_ymd)
                if sell_ymd
                else sidecar_fields(None, code, "")
            )
            score = rank = None
            if scores_by_day and sell_ymd:
                score, rank, _n = _score_lookup(
                    scores_by_day, rank_cache, sell_ymd, code
                )
            trips.append(
                {
                    **{k: v for k, v in lot.items() if k != "buy_ymd"},
                    "sell_date": _iso(sell_ymd) if sell_ymd else None,
                    "status": "open_eod",
                    "hold_trading_days": hold_days(lot["buy_ymd"], sell_ymd),
                    "sell_price": mark["price"] if mark else None,
                    "sell_notional": mark["notional"] if mark else None,
                    "sell_commission": 0.0,
                    "sell_reason": "EOD_MARK",
                    "sell_score": score,
                    "sell_rank": rank,
                    "realized_pnl": None,
                    "return_pct": (mtm / debit)
                    if (mtm is not None and debit)
                    else None,
                    "mtm_pnl": mtm,
                    "sell_sidecar_close": sell_fields["sidecar_close"],
                    "sell_ma20": sell_fields["ma20"],
                    "sell_ma60": sell_fields["ma60"],
                    "sell_winratio": sell_fields["winratio"],
                }
            )
            ledger.append(
                {
                    "date": _iso(sell_ymd) if sell_ymd else lot["buy_date"],
                    "code": code,
                    "event": "hold",
                    "delta_amount": 0.0,
                    "amount_after": lot["shares"],
                    "price": mark["price"] if mark else lot["buy_price"],
                    "entry_price": lot["buy_price"],
                    "trade_value": 0.0,
                    "est_cost": 0.0,
                    "holding_days": hold_days(lot["buy_ymd"], sell_ymd),
                    "realized_pnl": 0.0,
                    "unrealized_pnl": mtm,
                    "cum_realized_pnl": cum_realized[code],
                    "reason": "EOD_MARK",
                    **({"position_id": identity} if has_identity else {}),
                    **({"lot": lot_id} if has_lot else {}),
                }
            )

    trip_cols = [
        "code",
        "buy_date",
        "sell_date",
        "status",
        "hold_trading_days",
        "sell_reason",
        "buy_price",
        "sell_price",
        "shares",
        "buy_notional",
        "sell_notional",
        "buy_commission",
        "sell_commission",
        "realized_pnl",
        "mtm_pnl",
        "return_pct",
        "buy_score",
        "buy_rank",
        "buy_in_topk",
        "sell_score",
        "sell_rank",
        "buy_sidecar_close",
        "buy_ma20",
        "buy_ma60",
        "buy_winratio",
        "buy_close_minus_ma20",
        "buy_close_minus_ma60",
        "buy_close_over_ma20",
        "buy_close_over_ma60",
        "buy_cond1_below_ma_wr",
        "buy_cond2_close_gt_ma20",
        "buy_state_label",
        "buy_state_ok",
        "buy_sidecar_hit",
        "sell_sidecar_close",
        "sell_ma20",
        "sell_ma60",
        "sell_winratio",
        "is_st_buy_day",
        "min_buy_ymd",
        "age_ok",
    ]
    if has_identity:
        trip_cols.append("position_id")
    if has_lot:
        trip_cols.append("lot")
    trip_df = pd.DataFrame(trips)
    if trip_df.empty:
        trip_df = pd.DataFrame(columns=trip_cols)
    else:
        trip_df = trip_df[[c for c in trip_cols if c in trip_df.columns]]
        trip_df = trip_df.sort_values(
            ["buy_date", "buy_rank", "code"], kind="mergesort"
        )
    trades_df = pd.DataFrame(annotated)
    led_df = pd.DataFrame(ledger)
    if not led_df.empty:
        led_df = led_df.sort_values(["code", "date", "event"], kind="mergesort")
    if has_lot:
        for frame in (trades_df, trip_df, led_df):
            if "lot" in frame:
                frame["lot"] = _integer_lots(frame["lot"])
    return trades_df, trip_df, led_df.reset_index(drop=True)


def pnl_from_trips(trips: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "code",
        "round_trips",
        "open_lots",
        "wins",
        "losses",
        "realized_pnl",
        "unrealized_pnl",
        "total_pnl",
        "total_entry_value",
        "return_on_cost",
        "first_buy",
        "last_exit",
        "still_held",
    ]
    if trips.empty:
        return pd.DataFrame(columns=cols)
    rows = []
    for code, g in trips.groupby("code", sort=True):
        closed = g[g["status"] == "closed"]
        opened = g[g["status"] == "open_eod"]
        realized = float(closed["realized_pnl"].sum()) if len(closed) else 0.0
        mtm = float(opened["mtm_pnl"].sum()) if len(opened) else 0.0
        entry = float(g["buy_notional"].sum())
        rows.append(
            {
                "code": code,
                "round_trips": int(len(closed)),
                "open_lots": int(len(opened)),
                "wins": int((closed["realized_pnl"] > 0).sum()) if len(closed) else 0,
                "losses": int((closed["realized_pnl"] <= 0).sum())
                if len(closed)
                else 0,
                "realized_pnl": realized,
                "unrealized_pnl": mtm,
                "total_pnl": realized + mtm,
                "total_entry_value": entry,
                "return_on_cost": (realized + mtm) / entry if entry else None,
                "first_buy": g["buy_date"].min(),
                "last_exit": g["sell_date"].max(),
                "still_held": bool(len(opened)),
            }
        )
    return pd.DataFrame(rows).sort_values(
        "total_pnl", ascending=False, ignore_index=True
    )


def positions_daily(trades: pd.DataFrame, nav: pd.DataFrame) -> pd.DataFrame:
    """EOD holdings after each equity day's fills. Price = last fill or EOD_MARK."""
    if _has_position_ids(trades):
        return _positions_daily_by_position(trades, nav)
    by_day: dict[str, list] = defaultdict(list)
    for rec in trades.itertuples(index=False):
        by_day[rec.ymd].append(rec)
    held: dict[str, dict[str, Any]] = {}
    last_px: dict[str, float] = {}
    rows: list[dict] = []
    equity_map = dict(zip(nav["ymd"], nav["equity"]))
    for ymd in nav["ymd"]:
        for rec in by_day.get(ymd, []):
            side = rec.side
            code = rec.code
            if side == "BUY":
                slot = held.setdefault(
                    code,
                    {
                        "shares": 0.0,
                        "cost": 0.0,
                        "entry_ymd": ymd,
                        "buy_price": rec.price,
                    },
                )
                slot["shares"] += float(rec.shares)
                slot["cost"] += float(rec.notional) + float(rec.commission)
                if slot["shares"] and slot.get("entry_ymd") is None:
                    slot["entry_ymd"] = ymd
                    slot["buy_price"] = rec.price
                last_px[code] = float(rec.price)
            elif side == "SELL":
                slot = held.get(code)
                if slot is None:
                    continue
                slot["shares"] -= float(rec.shares)
                last_px[code] = float(rec.price)
                if slot["shares"] <= 1e-9:
                    held.pop(code, None)
            elif side == "EOD_MARK":
                last_px[code] = float(rec.price)
        total = float(equity_map.get(ymd, 0.0))
        pos = {d: i for i, d in enumerate(nav["ymd"])}
        for code, slot in sorted(held.items()):
            px = last_px.get(code, slot["buy_price"])
            mv = slot["shares"] * float(px)
            buy_i = pos.get(slot["entry_ymd"])
            now_i = pos.get(ymd)
            hd = (now_i - buy_i) if buy_i is not None and now_i is not None else None
            rows.append(
                {
                    "date": _iso(ymd),
                    "code": code,
                    "shares": slot["shares"],
                    "price": px,
                    "entry_price": slot["buy_price"],
                    "market_value": mv,
                    "weight": mv / total if total else None,
                    "holding_days": hd,
                }
            )
    return pd.DataFrame(rows)


def _positions_daily_by_position(trades: pd.DataFrame, nav: pd.DataFrame) -> pd.DataFrame:
    """Preserve the old position columns, with one row per code/position ID."""
    by_day: dict[str, list] = defaultdict(list)
    for rec in trades.itertuples(index=False):
        by_day[rec.ymd].append(rec)
    opens: dict[str, deque] = defaultdict(deque)
    last_px: dict[str, float] = {}
    rows: list[dict] = []
    cal_pos = {ymd: i for i, ymd in enumerate(nav["ymd"])}
    for day in nav.itertuples(index=False):
        for rec in by_day.get(day.ymd, []):
            identity = _position_id(getattr(rec, "position_id", ""))
            lot_id = _lot_id(getattr(rec, "lot", None))
            q = opens[rec.code]
            if rec.side == "BUY":
                lot = {
                    "position_id": identity,
                    "lot": lot_id,
                    "shares": float(rec.shares),
                    "entry_ymd": day.ymd,
                    "buy_price": float(rec.price),
                }
                existing = _matching_lot(q, identity, lot_id)
                if (identity and pd.notna(lot_id) and existing is not None
                        and q[existing].get("lot") == lot_id):
                    merged = q[existing]
                    cost = merged["buy_price"] * merged["shares"]
                    cost += lot["buy_price"] * lot["shares"]
                    merged["shares"] += lot["shares"]
                    merged["buy_price"] = cost / merged["shares"]
                else:
                    q.append(lot)
            elif rec.side == "SELL":
                remaining = float(rec.shares)
                while remaining > 1e-9:
                    selected = _matching_lot(q, identity, lot_id)
                    if selected is None:
                        # Pairing validates BUY provenance for excess bonus
                        # shares; do not turn their sale into negative holdings.
                        break
                    lot = q[selected]
                    sold = min(remaining, lot["shares"])
                    remaining -= sold
                    lot["shares"] -= sold
                    if lot["shares"] <= 1e-9:
                        del q[selected]
            if rec.side in FILL_SIDES or rec.side == "EOD_MARK":
                last_px[rec.code] = float(rec.price)
        for code, q in sorted(opens.items()):
            grouped: dict[str, list] = defaultdict(list)
            for lot in q:
                grouped[lot["position_id"]].append(lot)
            for identity, lots in grouped.items():
                shares = sum(lot["shares"] for lot in lots)
                first = lots[0]
                px = last_px.get(code, first["buy_price"])
                mv = shares * px
                rows.append({
                    "date": _iso(day.ymd),
                    "code": code,
                    "shares": shares,
                    "price": px,
                    "entry_price": first["buy_price"],
                    "market_value": mv,
                    "weight": mv / float(day.equity) if day.equity else None,
                    "holding_days": cal_pos[day.ymd] - cal_pos[first["entry_ymd"]],
                    "position_id": identity,
                })
    return pd.DataFrame(rows)


def daily_picks_frame(
    scores_by_day: Mapping[str, dict[str, float]],
    positions: pd.DataFrame,
    trades: pd.DataFrame,
    *,
    topk: int,
) -> pd.DataFrame:
    """MyQuant-style action labels. Filename scores = buy day (already pred_minus_one)."""
    if not scores_by_day or topk <= 0:
        return pd.DataFrame()
    held_by_day: dict[str, set[str]] = {}
    if not positions.empty:
        for d, g in positions.groupby("date"):
            held_by_day[_ymd(d)] = set(g["code"])
    bought_by_day: dict[str, set[str]] = defaultdict(set)
    for rec in trades.itertuples(index=False):
        if rec.side == "BUY":
            bought_by_day[rec.ymd].add(rec.code)
    rows: list[dict] = []
    for ymd, smap in sorted(scores_by_day.items()):
        ranked = sorted(smap.items(), key=lambda kv: (-kv[1], kv[0]))
        top = ranked[: int(topk)]
        top_set = {c for c, _ in top}
        held = held_by_day.get(ymd, set())
        bought = bought_by_day.get(ymd, set())
        extra = [c for c in held if c not in top_set]
        watch = [c for c, _ in top] + extra
        rank_map = {c: i + 1 for i, (c, _) in enumerate(ranked)}
        seen: set[str] = set()
        for code in watch:
            if code in seen:
                continue
            seen.add(code)
            in_top = code in top_set
            in_port = code in held
            if in_top and in_port and code in bought:
                action = "new_buy"
            elif in_top and in_port:
                action = "held"
            elif in_top:
                action = "missed"
            else:
                action = "held_not_topk"
            rows.append(
                {
                    "trade_date": _iso(ymd),
                    "rank": rank_map.get(code),
                    "code": code,
                    "score": smap.get(code),
                    "held": in_port,
                    "action": action,
                }
            )
    return pd.DataFrame(rows)


def write_bundle(
    run_dir: Path,
    out_dir: Path,
    *,
    scores_by_day=None,
    state_map=None,
    st_by_day=None,
    age_map=None,
    topk: int = 50,
    account: float | None = None,
    xlsx: bool = False,
) -> dict[str, Any]:
    run_dir = Path(run_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    nav = load_nav(run_dir)
    trades = load_trades(run_dir)
    summary_txt = (
        (run_dir / "summary.txt").read_text(encoding="utf-8")
        if (run_dir / "summary.txt").is_file()
        else ""
    )
    if account is None:
        account = parse_account_from_summary(summary_txt)
    if account is None and len(nav):
        # Fallback: first-day equity is post-cost; still better than silent 0.
        account = float(nav["equity"].iloc[0])

    trades_df, trip_df, led_df = pair_round_trips(
        trades,
        nav,
        scores_by_day=scores_by_day,
        state_map=state_map,
        st_by_day=st_by_day,
        age_map=age_map,
        topk=topk,
    )
    pnl_df = pnl_from_trips(trip_df)
    pos_df = positions_daily(trades, nav)
    picks_df = (
        daily_picks_frame(scores_by_day, pos_df, trades, topk=topk)
        if scores_by_day
        else pd.DataFrame()
    )
    if not picks_df.empty:
        window = set(nav["date"])
        picks_df = picks_df[picks_df["trade_date"].isin(window)].reset_index(drop=True)
    nav_out = nav.rename(columns={"equity": "total_value"}).drop(columns=["ymd"])

    frames = {
        "nav_daily": nav_out,
        "trades_daily": trades_df,
        "round_trips": trip_df,
        "ledger_by_stock": led_df,
        "pnl_by_stock": pnl_df,
        "positions_daily": pos_df,
    }
    if not picks_df.empty:
        frames["daily_picks"] = picks_df

    paths: dict[str, str] = {}
    for name, frame in frames.items():
        dest = out_dir / f"{name}.csv"
        frame.to_csv(dest, index=False, encoding=CSV_ENCODING)
        paths[name] = str(dest)

    closed = trip_df[trip_df["status"] == "closed"] if len(trip_df) else trip_df
    opened = trip_df[trip_df["status"] == "open_eod"] if len(trip_df) else trip_df
    realized = float(closed["realized_pnl"].sum()) if len(closed) else 0.0
    mtm = float(opened["mtm_pnl"].sum()) if len(opened) else 0.0
    pnl_total = realized + mtm
    nav_first = float(nav["equity"].iloc[0]) if len(nav) else None
    nav_last = float(nav["equity"].iloc[-1]) if len(nav) else None
    nav_delta = (nav_last - account) if (nav_last is not None and account) else None
    fills = trades[trades["side"].isin(FILL_SIDES)] if len(trades) else trades
    perf = drawdown_and_win_rates(nav, trip_df, account)
    n_closed = int(len(closed)) if len(trip_df) else 0
    n_open = int(len(opened)) if len(trip_df) else 0
    summary = {
        "run_dir": str(run_dir),
        "out_dir": str(out_dir),
        "account": account,
        "nav_first": nav_first,
        "nav_last": nav_last,
        "nav_delta": nav_delta,
        "return_on_account": perf["return_on_account"],
        "max_drawdown": perf["max_drawdown"],
        "max_drawdown_date": perf["max_drawdown_date"],
        "drawdown_peak_equity": perf["drawdown_peak_equity"],
        "drawdown_trough_equity": perf["drawdown_trough_equity"],
        "pnl_total": pnl_total,
        "realized_pnl": realized,
        "unrealized_pnl": mtm,
        "pnl_nav_diff": (pnl_total - nav_delta) if (nav_delta is not None) else None,
        "days": int(len(nav)),
        "buys": int((fills["side"] == "BUY").sum()) if len(fills) else 0,
        "sells": int((fills["side"] == "SELL").sum()) if len(fills) else 0,
        "round_trips": n_closed,
        "open_lots": n_open,
        "wins_closed": perf["wins_closed"],
        "losses_closed": perf["losses_closed"],
        "win_rate_closed": perf["win_rate_closed"],
        "wins_open": perf["wins_open"],
        "win_rate_with_open": perf["win_rate_with_open"],
        "by_sell_reason": perf["by_sell_reason"],
        "topk": int(topk),
        "has_scores": bool(scores_by_day),
        "has_buy_state": bool(state_map),
        "paths": paths,
    }
    analysis_text = format_human_analysis(perf, n_closed=n_closed, n_open=n_open)
    analysis_path = out_dir / HUMAN_ANALYSIS_NAME
    analysis_path.write_text(analysis_text, encoding="utf-8", newline="\n")
    paths["human_analysis"] = str(analysis_path)
    reason_df = pd.DataFrame(perf["by_sell_reason"])
    reason_path = out_dir / "win_by_reason.csv"
    reason_df.to_csv(reason_path, index=False, encoding=CSV_ENCODING)
    paths["win_by_reason"] = str(reason_path)
    note = write_fields_note(out_dir, run_dir=run_dir, nav=nav, has_identity=_has_position_ids(trades))
    paths["fields_note"] = str(note)

    if xlsx:
        xlsx_path = out_dir / "human_review.xlsx"
        with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
            for name, frame in frames.items():
                sheet = name[:31]
                frame.to_excel(writer, sheet_name=sheet, index=False)
                ws = writer.sheets[sheet]
                if len(frame):
                    ws.auto_filter.ref = ws.dimensions
                ws.freeze_panes = "A2"
            meta = {
                k: v for k, v in summary.items() if k not in {"paths", "by_sell_reason"}
            }
            pd.DataFrame([meta]).to_excel(writer, sheet_name="meta", index=False)
            pd.DataFrame({"line": analysis_text.splitlines()}).to_excel(
                writer, sheet_name="human_analysis", index=False
            )
            if len(reason_df):
                reason_df.to_excel(writer, sheet_name="win_by_reason", index=False)
        paths["xlsx"] = str(xlsx_path)

    paths["summary"] = str(out_dir / "summary.json")
    summary["paths"] = paths
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    return {"paths": paths, "summary": summary}


def parse_cli(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Export CSV-engine human-review pack from an existing run dir (no resimulate)."
    )
    p.add_argument(
        "--run-dir",
        type=Path,
        required=True,
        help="dir with trades.csv + daily_equity.csv",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="default: <run-dir>/analysis",
    )
    p.add_argument("--scores-dir", type=Path, default=None)
    p.add_argument("--pred-csv", type=Path, default=None)
    p.add_argument("--buy-state-file", type=Path, default=None)
    p.add_argument("--st-daily-file", type=Path, default=None)
    p.add_argument("--age-map-file", type=Path, default=None)
    p.add_argument("--age-days", type=int, default=60)
    p.add_argument("--topk", type=int, default=50)
    p.add_argument(
        "--account",
        type=float,
        default=None,
        help="override cash; else parse summary.txt",
    )
    p.add_argument("--xlsx", action="store_true", help="also write human_review.xlsx")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_cli(argv)
    run_dir = args.run_dir
    out_dir = args.out_dir or (run_dir / "analysis")
    scores_by_day = None
    if args.scores_dir is not None or args.pred_csv is not None:
        scores_by_day = load_scores_from_args(
            pred_csv=args.pred_csv, scores_dir=args.scores_dir
        )
    state_map = (
        load_buy_state_sidecar(args.buy_state_file) if args.buy_state_file else None
    )
    st_by_day = load_st_daily_by_day(args.st_daily_file) if args.st_daily_file else None
    age_map = (
        load_age_min_buy_ymd(
            args.age_map_file, age_days=args.age_days, calendar_ymd=None
        )
        if args.age_map_file
        else None
    )
    product = write_bundle(
        run_dir,
        out_dir,
        scores_by_day=scores_by_day,
        state_map=state_map,
        st_by_day=st_by_day,
        age_map=age_map,
        topk=args.topk,
        account=args.account,
        xlsx=bool(args.xlsx),
    )
    s = product["summary"]
    print(
        f"wrote {out_dir} trips={s['round_trips']} open={s['open_lots']} "
        f"pnl={s['pnl_total']:.2f} nav_delta={s['nav_delta']} "
        f"max_dd={s['max_drawdown']} win_rate={s['win_rate_closed']} "
        f"fields={FIELDS_NOTE_NAME}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
