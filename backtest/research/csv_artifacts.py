# -*- coding: utf-8 -*-
"""CSV backtest run artifacts: summarize / write / equity compare.

本模块按设计知晓两引擎工件命名约定（`csv_daily_{book}_{start}_{end}`）与对照语义；命名串是数据，不是对引擎代码的依赖。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import pandas as pd

from backtest.research.csv_ledger import SimState, chase_explained

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def summarize(
    st: SimState,
    total_cash: float,
    start: str,
    end: str,
    *,
    engine: str = "csv_daily_v6",
) -> str:
    eq = pd.DataFrame(st.equity_curve, columns=["date", "equity"])
    final = float(eq["equity"].iloc[-1]) if len(eq) else total_cash
    peak = eq["equity"].cummax()
    max_dd = float((eq["equity"] / peak - 1.0).min()) if len(eq) else 0.0
    invested = st.stats["invested_notional"]
    deployed = (final - total_cash) / invested if invested > 0 else float("nan")
    lines = [
        f"{engine} {start}..{end}",
        f"  期末净值: {final:,.2f} / {total_cash:,.0f}",
        f"  总收益率(全资金): {final / total_cash - 1:+.2%}",
        f"  动用资金收益率: {deployed:+.2%}"
        if invested > 0
        else "  动用资金收益率: n/a",
        f"  最大回撤: {max_dd:.2%}",
    ]
    stop_text = (
        f"{st.stats.get('stop_pct'):.0%}"
        if isinstance(st.stats.get("stop_pct"), (int, float))
        else "关闭"
    )
    if st.stats.get("sell_book") == "v8":
        arms = st.stats.get("band_arms", [0.06, 0.15, 0.50, 1.00])
        keeps = st.stats.get("band_keeps", [0.30, 0.60, 0.70, 0.80])
        b2 = float(st.stats.get("band2_abs_mult", 1.02))
        b3 = float(st.stats.get("band3_global_mult", 1.15))
        arms_txt = "/".join(f"{float(a):.0%}" for a in arms)
        keeps_txt = "/".join(f"{float(k):.0%}" for k in keeps)
        lines.append(
            f"  参数: 止损 {stop_text} | 涨幅比例回撤阶梯 arm={arms_txt} "
            f"keep={keeps_txt} | 档2底+{b2 - 1.0:.0%} | 档3全局底+{b3 - 1.0:.0%} "
            f"| T+1止盈豁免"
        )
    elif st.stats.get("sell_book") == "v9":
        lines.append(
            f"  参数: 止损 {stop_text} | 满持有 "
            f"{int(st.stats.get('max_hold', 20))} 日 force_sell"
        )
    elif st.stats.get("sell_book") in {"v6", "v10"} or "trail_t1" in st.stats:
        lines.append(
            f"  参数: 止损 {stop_text} | 锚 {st.stats['profit_base']:.0%} | "
            f"回撤 T+1 {st.stats['trail_t1']:.0%} / T+2 {st.stats['trail_t2']:.0%} / "
            f"T+3 {st.stats.get('trail_t3', 0):.0%} / T+4 {st.stats.get('trail_t4', 0):.0%} / "
            f"T+5+ {st.stats.get('trail_t5', st.stats.get('trail_t3', 0)):.0%}"
        )
    lines.extend(
        [
            f"  买入 {st.stats['buys']} | 涨停跳过 {st.stats['skip_limit_up']} | "
            f"追买 {st.stats.get('chase_buy', 0)} | 弃买 {st.stats.get('chase_abandon', 0)} | "
            f"已持跳过 {st.stats['skip_held']} | 加仓 {st.stats.get('add_lots', 0)}",
            f"  涨停分解: 追买 {st.stats.get('chase_buy', 0)} | "
            f"弃买 {st.stats.get('chase_abandon', 0)} | "
            f"追买日仍涨停 {st.stats.get('chase_skip_limit', 0)} | "
            f"缺行情 {st.stats.get('chase_no_bar', 0)} | "
            f"末日未追 {st.stats.get('chase_pending_eod', 0)} | "
            f"覆盖 {st.stats.get('chase_overwrite', 0)} | "
            f"买失败 {st.stats.get('chase_buy_fail', 0)} | "
            f"追买已持跳过 {st.stats.get('chase_skip_held', 0)} | "
            f"合计 {chase_explained(st)} / 涨停跳过 {st.stats['skip_limit_up']}",
            f"  卖出: 止损 {st.stats['sell_stop']} | 锚定回撤 {st.stats['sell_trail']} | "
            f"正利润回撤 {st.stats['sell_pos_trail']} | 止盈 {st.stats.get('sell_profit_take', 0)} | "
            f"开板 {st.stats.get('sell_open_board', 0)} | 强制 {st.stats.get('sell_force', 0)} | "
            f"均线 {st.stats.get('sell_ma', 0)}",
            f"  跌停顺延卖出 {st.stats['defer_sell_limit_down']} | 补充资金 {st.stats['supplementary_used']:,.0f}",
            f"  日线加载 {st.stats['bars_loaded']} | 池天数 {st.stats['pool_days']}",
        ]
    )
    if "sizing" in st.stats:
        lines.append(
            f"  sizing={st.stats['sizing']} | name_budget={st.stats['name_budget']:,.0f} | "
            f"skip_cash={st.stats.get('skip_cash', 0)} | "
            f"skip_cash_notional={st.stats.get('skip_cash_notional', 0):,.0f} | "
            f"chase_buy_fail_cash={st.stats.get('chase_buy_fail_cash', 0)} | "
            f"chase_buy_fail_shares={st.stats.get('chase_buy_fail_shares', 0)}"
        )
    if "buy_cost_rate" in st.stats:
        lines.append(
            f"  cost buy={st.stats['buy_cost_rate']:g} sell={st.stats['sell_cost_rate']:g} "
            f"min={st.stats.get('min_cost', 0):g}"
        )
    if "ration" in st.stats:
        lines.append(
            f"  ration={st.stats['ration']} | ration_seed={st.stats['ration_seed']}"
        )
    timing_parts = []
    for key, lab in (
        ("t_pool_s", "池"),
        ("t_daily_s", "日线"),
        ("t_minute_s", "分钟"),
        ("t_sim_s", "模拟"),
    ):
        if key in st.stats:
            timing_parts.append(f"{lab} {float(st.stats[key]):.1f}s")
    cache = st.stats.get("cache")
    if cache:
        timing_parts.append(f"缓存 {cache}")
    if timing_parts:
        lines.append("  耗时: " + " | ".join(timing_parts))
    missing = st.stats.get("codes_missing")
    if missing:
        lines.append(f"  缺行情 {int(missing)}")
    # E-R6 ex-div stats: print only when non-zero (keep np3_layering golden stable).
    for key, lab in (
        ("exdiv_adjusted_lots", "除权缩放 lots"),
        ("exdiv_prev_close_mapped", "除权 prev_close 映射"),
        ("exdiv_skipped_no_factor", "除权缺因子跳过"),
    ):
        val = st.stats.get(key)
        if val:
            lines.append(f"  {lab} {int(val)}")
    return "\n".join(lines)


def write_run_artifacts(out_dir: Path, st: SimState, text: str, help_lock: str) -> Path:
    """三件套：summary.txt / daily_equity.csv / trades.csv。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(st.trades).to_csv(
        out_dir / "trades.csv", index=False, encoding="utf-8"
    )
    pd.DataFrame(st.equity_curve, columns=["date", "equity"]).to_csv(
        out_dir / "daily_equity.csv", index=False, encoding="utf-8"
    )
    (out_dir / "summary.txt").write_text(
        text + "\n" + help_lock, encoding="utf-8", newline="\n"
    )
    print(f"wrote {out_dir}", flush=True)
    return out_dir


def find_daily_equity_csv(
    start: str,
    end: str,
    output_root: Optional[Path] = None,
    *,
    book: str,
) -> Optional[Path]:
    root = (
        Path(output_root) if output_root is not None else Path(REPO) / "backtest_output"
    )
    exact = root / f"csv_daily_{book}_{start}_{end}" / "daily_equity.csv"
    if exact.is_file():
        return exact
    found: list[tuple[str, Path]] = []
    for path in root.glob(f"csv_daily_{book}_{start}_*/daily_equity.csv"):
        found.append((path.parent.name.rsplit("_", 1)[-1], path))
    if not found:
        return None
    covering = [item for item in found if item[0] >= end]
    pool = covering or found
    pool.sort(key=lambda item: item[0])
    return pool[-1][1]


def format_equity_compare(
    this_curve: list,
    peer_csv: Path,
    *,
    this_label: str,
    peer_label: str = "csv_daily_v6",
    highlight: str = "20251104",
) -> str:
    this = pd.DataFrame(this_curve, columns=["date", "equity"])
    peer = pd.read_csv(peer_csv, encoding="utf-8")
    if (
        this.empty
        or peer.empty
        or "date" not in peer.columns
        or "equity" not in peer.columns
    ):
        return f"对照 {peer_label}: 对端净值表为空（{peer_csv}）"
    this["date"] = this["date"].astype(str)
    peer["date"] = peer["date"].astype(str)
    merged = this.merge(peer, on="date", suffixes=("_this", "_peer"))
    if merged.empty:
        return f"对照 {peer_label}: 无重叠交易日（{peer_csv}）"
    merged["gap"] = merged["equity_this"] - merged["equity_peer"]
    merged["gap_pct"] = merged["gap"] / merged["equity_peer"]
    first = merged.iloc[0]
    last = merged.iloc[-1]
    worst = merged.loc[merged["gap"].abs().idxmax()]
    lines = [
        f"对照 {peer_label}（{peer_csv.parent.name}）重叠 {len(merged)} 日 "
        f"{first['date']}..{last['date']}（双方均为 none 成交价，差来自卖点时钟）:",
        f"  首日 {this_label} {first['equity_this']:,.2f} vs {peer_label} "
        f"{first['equity_peer']:,.2f} 差 {first['gap']:+,.2f}",
        f"  末日 {this_label} {last['equity_this']:,.2f} vs {peer_label} "
        f"{last['equity_peer']:,.2f} 差 {last['gap']:+,.2f} ({last['gap_pct']:+.2%})",
        f"  最大绝对偏差 {worst['date']} {worst['gap']:+,.2f} ({worst['gap_pct']:+.2%})",
    ]
    hit = merged.loc[merged["date"] == highlight]
    if not hit.empty:
        row = hit.iloc[0]
        lines.append(
            f"  {highlight} {this_label} {row['equity_this']:,.2f} vs "
            f"{peer_label} {row['equity_peer']:,.2f} 差 {row['gap']:+,.2f}"
        )
    return "\n".join(lines)


def maybe_compare_daily(
    this_curve: list,
    start: str,
    end: str,
    *,
    this_label: str,
    output_root: Optional[Path] = None,
    book: Optional[str] = None,
) -> str:
    if not book:
        return ""
    peer = find_daily_equity_csv(start, end, output_root, book=book)
    if peer is None:
        return ""
    peer_label = f"csv_daily_{book}"
    return format_equity_compare(
        this_curve, peer, this_label=this_label, peer_label=peer_label
    )

