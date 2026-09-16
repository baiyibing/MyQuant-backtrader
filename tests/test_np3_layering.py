# -*- coding: utf-8 -*-
"""NP3 engine-layering data-free tests (P4 fake-green weld)."""

from __future__ import annotations

from pathlib import Path

from backtest.research.csv_artifacts import maybe_compare_daily, summarize
from backtest.research.csv_ledger import SimState


def _strip_nondeterministic(text: str) -> str:
    """Drop timing / cache lines that are not byte-stable across runs."""
    keep = []
    for line in text.splitlines():
        if line.startswith("  耗时:"):
            continue
        keep.append(line)
    return "\n".join(keep)


def test_summarize_deterministic_full_text_golden() -> None:
    st = SimState()
    st.equity_curve = [("20251103", 21_000_000.0), ("20251104", 21_100_000.0)]
    st.stats["invested_notional"] = 1_000_000.0
    st.stats["buys"] = 2
    st.stats["skip_limit_up"] = 1
    st.stats["sell_book"] = "v8"
    st.stats["stop_pct"] = 0.30
    st.stats["band_arms"] = [0.06, 0.15, 0.50, 1.00]
    st.stats["band_keeps"] = [0.30, 0.60, 0.70, 0.80]
    st.stats["band2_abs_mult"] = 1.02
    st.stats["band3_global_mult"] = 1.15
    st.stats["sizing"] = "per_name"
    st.stats["name_budget"] = 1_000_000.0
    st.stats["skip_cash"] = 1
    st.stats["skip_cash_notional"] = 500_000.0
    st.stats["chase_buy_fail_cash"] = 0
    st.stats["chase_buy_fail_shares"] = 0
    st.stats["ration"] = "file_order"
    st.stats["ration_seed"] = 0
    st.stats["t_sim_s"] = 1.25
    st.stats["bars_loaded"] = 10
    st.stats["pool_days"] = 2
    text = _strip_nondeterministic(
        summarize(st, 21_000_000.0, "20251103", "20251104", engine="csv_daily_v8")
    )
    golden = "\n".join(
        [
            "csv_daily_v8 20251103..20251104",
            "  期末净值: 21,100,000.00 / 21,000,000",
            "  总收益率(全资金): +0.48%",
            "  动用资金收益率: +10.00%",
            "  最大回撤: 0.00%",
            "  参数: 止损 30% | 涨幅比例回撤阶梯 arm=6%/15%/50%/100% keep=30%/60%/70%/80% | 档2底+2% | 档3全局底+15% | T+1止盈豁免",
            "  买入 2 | 涨停跳过 1 | 追买 0 | 弃买 0 | 已持跳过 0 | 加仓 0",
            "  涨停分解: 追买 0 | 弃买 0 | 追买日仍涨停 0 | 缺行情 0 | 末日未追 0 | "
            "覆盖 0 | 买失败 0 | 追买已持跳过 0 | 合计 0 / 涨停跳过 1",
            "  卖出: 止损 0 | 锚定回撤 0 | 正利润回撤 0 | 止盈 0 | 开板 0 | 强制 0 | 均线 0",
            "  跌停顺延卖出 0 | 补充资金 0",
            "  日线加载 10 | 池天数 2",
            "  sizing=per_name | name_budget=1,000,000 | skip_cash=1 | "
            "skip_cash_notional=500,000 | chase_buy_fail_cash=0 | chase_buy_fail_shares=0",
            "  ration=file_order | ration_seed=0",
        ]
    )
    assert text == golden


def test_maybe_compare_daily_peer_caption(tmp_path: Path) -> None:
    peer_dir = tmp_path / "csv_daily_v8_20251103_20251104"
    peer_dir.mkdir(parents=True)
    (peer_dir / "daily_equity.csv").write_text(
        "date,equity\n20251103,21000000.0\n20251104,21100000.0\n",
        encoding="utf-8",
        newline="\n",
    )
    this_curve = [("20251103", 21_000_000.0), ("20251104", 21_050_000.0)]
    text = maybe_compare_daily(
        this_curve,
        "20251103",
        "20251104",
        this_label="csv_minute_v8",
        output_root=tmp_path,
        book="v8",
    )
    assert "对照 csv_daily_v8" in text
    assert "csv_daily_v8_20251103_20251104" in text
    assert "重叠 2 日" in text
    assert "csv_minute_v8" in text
    # empty book → silent
    assert maybe_compare_daily(this_curve, "20251103", "20251104", this_label="x") == ""
    # missing peer → silent
    assert (
        maybe_compare_daily(
            this_curve,
            "20251103",
            "20251104",
            this_label="x",
            output_root=tmp_path,
            book="missing",
        )
        == ""
    )


def test_warn_stale_period_env_monkeypatch(monkeypatch, capsys) -> None:
    from backtest.research.csv_daily_loader import _PERIOD_ENV_KEYS, warn_stale_period_env

    for k in _PERIOD_ENV_KEYS:
        monkeypatch.delenv(k, raising=False)
    warn_stale_period_env()
    assert capsys.readouterr().out == ""

    monkeypatch.setenv("OSKH_PERIOD_1D_ROOT", "/tmp/fake")
    warn_stale_period_env()
    out = capsys.readouterr().out
    assert "OSKH_PERIOD_1D_ROOT" in out
    assert "lake may ignore" in out
    assert ".authority" in out

