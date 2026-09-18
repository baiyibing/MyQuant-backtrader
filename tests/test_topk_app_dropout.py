# -*- coding: utf-8 -*-
from pathlib import Path

import pandas as pd
import pytest

from backtest.research.csv_pool import parse_pool_csv, parse_pool_csv_entries
from backtest.research.topk_app_dropout import (
    BOOK_TAG,
    intersect_app_qlib,
    load_pred_frame,
    overlap_stats,
    qlib_topn_by_buy_day,
    ranked_day_codes,
    write_topk_app_dropout_pool,
)


def test_book_tag_is_not_a_csv_strategy_choice():
    from backtest.research.csv_strategy_books import normalize_csv_strategy

    with pytest.raises(ValueError, match="unsupported"):
        normalize_csv_strategy(BOOK_TAG)


def test_new_runner_parser_is_not_strategy7():
    from backtest.research.csv_minute_backtest_topk_app_dropout import (
        DEFAULT_CASH_TOTAL,
        build_parser,
    )
    from backtest.research.csv_minute_backtest_v7 import (
        build_parser as v7_parser,
    )

    help_text = build_parser().format_help()
    assert "topk_app_dropout" in help_text
    assert build_parser().get_default("cash_total") == DEFAULT_CASH_TOTAL
    assert DEFAULT_CASH_TOTAL == 500_000_000.0
    v7_help = v7_parser().format_help()
    assert "Strategy 7 turtle" in v7_help
    assert "topk_app_dropout" not in v7_help
    assert v7_parser().get_default("cash_total") == 21_000_000.0


def test_pred_minus_one_maps_to_next_pred_day():
    pred = pd.DataFrame(
        {
            "datetime": ["2026-01-05", "2026-01-05", "2026-01-06", "2026-01-06"],
            "instrument": ["SZ000001", "SZ000002", "SZ000001", "SH600000"],
            "score": [0.9, 0.1, 0.2, 0.8],
        }
    )
    pred["datetime"] = pd.to_datetime(pred["datetime"])
    top = qlib_topn_by_buy_day(pred, topk=1, asof="pred_minus_one")
    assert list(top) == ["20260106"]
    assert top["20260106"] == ["000001"]


def test_intersect_keeps_app_order_and_names(tmp_path: Path):
    app = tmp_path / "app"
    app.mkdir()
    (app / "20260106.csv").write_text(
        "000002,乙\n000001,甲\n600000,丙\n",
        encoding="utf-8",
        newline="\n",
    )
    qlib = {"20260106": ["000001", "600000"]}
    days = intersect_app_qlib(app, qlib, start="20260106", end="20260106")
    assert [c for c, _ in days["20260106"]] == ["000001.SZ", "600000.SH"]
    assert days["20260106"][0][1] == "甲"


def test_day_without_qlib_cross_section_is_omitted(tmp_path: Path):
    app = tmp_path / "app"
    app.mkdir()
    (app / "20260105.csv").write_text("000001,甲\n", encoding="utf-8", newline="\n")
    assert intersect_app_qlib(app, {}, start="20260105", end="20260105") == {}


def test_write_pool_keeps_names_and_refuses_stock_pool(tmp_path: Path, repo_root=None):
    repo = Path(__file__).resolve().parents[1]
    days = {"20260106": [("000001.SZ", "平安银行")]}
    out = tmp_path / "exports" / "topk_app_dropout"
    written = write_topk_app_dropout_pool(days, out, repo=repo)
    assert written[0].read_text(encoding="utf-8") == "000001,平安银行\n"
    assert parse_pool_csv_entries(written[0]) == [("000001.SZ", "平安银行")]
    assert parse_pool_csv(written[0]) == ["000001.SZ"]
    with pytest.raises(ValueError, match="stock_pool"):
        write_topk_app_dropout_pool(days, repo / "stock_pool", repo=repo)


def test_overlap_stats_empty_majority():
    stats = overlap_stats({"a": [], "b": [("000001.SZ", "")], "c": []})
    assert stats["days"] == 3
    assert stats["hit_days"] == 1
    assert stats["empty_days"] == 2
    assert stats["intersect_max"] == 1


def test_ranked_day_codes_dedupes_bare():
    day = pd.DataFrame(
        {
            "instrument": ["SZ000001", "000001", "SH600000"],
            "score": [0.5, 0.9, 0.8],
        }
    )
    assert ranked_day_codes(day) == ["000001", "600000"]


def test_load_pred_frame_requires_columns(tmp_path: Path):
    p = tmp_path / "pred.csv"
    p.write_text("datetime,instrument\n2026-01-05,SZ000001\n", encoding="utf-8")
    with pytest.raises(ValueError, match="score"):
        load_pred_frame(p)
