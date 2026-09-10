# -*- coding: utf-8 -*-
"""研究面导入守卫（migration S2 收尾，2026-09-10）。

背景：吸收自 1.3 的研究面资产中，``backtest/research/engine.py`` 与
``backtest/research/chip/*`` 没有任何仓内消费者（引擎冒烟测试随 0f42cce
目录拆分指向 ``backtest.legacy.engine``），导入残差在 CI 上不可见——
engine 曾带 ``from common import TraceIdGenerator`` /
``from oskh_db.money_sqlite import ...`` 两处断链入库而全绿（codex R3 漏网件）。

契约：本仓持有的研究面入口模块必须可导入；分/元算术（移植自
``oskh_core.money_arithmetic``）保持「按分对齐」语义。
"""

from __future__ import annotations

import importlib

import pytest

# 无其他测试覆盖的吸收件（tr_filter / l2_analytics / parity 已有各自用例）。
_RESEARCH_FACE_MODULES = (
    "backtest.research.engine",
    "backtest.research.chip.evaluate_turnover_chip_factors",
    "backtest.research.chip.filter_chip_stocks",
    "backtest.research.chip.filter_stock_pool_by_chip",
    "backtest.research.chip.rolling_ic_chip_factors",
    "oskh_core.money_arithmetic",
    "oskh_core.a_share_symbol_normalize",
)


@pytest.mark.parametrize("module", _RESEARCH_FACE_MODULES)
def test_research_face_module_importable(module: str) -> None:
    importlib.import_module(module)


def test_engine_config_and_trace_id_wired() -> None:
    eng = importlib.import_module("backtest.research.engine")
    cfg = eng.BacktestConfig()
    assert cfg.commission_rate == pytest.approx(0.00005)
    assert hasattr(eng, "TraceIdGenerator") and hasattr(eng.TraceIdGenerator, "generate")


def test_money_arithmetic_fen_alignment() -> None:
    ma = importlib.import_module("oskh_core.money_arithmetic")
    # 按分对齐（HALF_UP 默认）：123.456 → 123.46 元 → 12346 分。
    assert ma.yuan_to_fen(ma.yuan_snap_fen(123.456)) == 12346
    assert ma.yuan_to_fen(20.0) == 2000
    assert ma.fen_to_yuan(2000) == pytest.approx(20.0)
    with pytest.raises(ValueError):
        ma.fen_to_yuan(None)  # NULL 金额不得隐式回退 0 元
