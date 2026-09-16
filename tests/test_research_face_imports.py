# -*- coding: utf-8 -*-
"""研究面导入守卫（migration S2 收尾，2026-09-10；H4 向量化篱笆 2026-09-15）。

背景：吸收自 1.3 的研究面资产中，``backtest/research/engine.py`` 与
``backtest/research/chip/*`` 没有任何仓内消费者（引擎冒烟测试随 0f42cce
目录拆分指向 ``backtest.legacy.engine``），导入残差在 CI 上不可见——
engine 曾带 ``from common import TraceIdGenerator`` /
``from oskh_db.money_sqlite import ...`` 两处断链入库而全绿（codex R3 漏网件）。

契约：本仓持有的研究面入口模块必须可导入；分/元算术（移植自
``oskh_core.money_arithmetic``）保持「按分对齐」语义。

Cerebro 已退场（2026-09-16）：研究面全部 Python 文件均不得导入
``backtrader`` / ``bt``，零例外（含 chip 及未来新增模块）。研究入口与
向量化 CSV 主路径也不得通过传递依赖把 backtrader 拉入导入图。
"""

from __future__ import annotations

import ast
import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

# 旧其他测试覆盖的吸收件（tr_filter / l2_analytics / parity 已有各自用例）。
_RESEARCH_FACE_MODULES = (
    "backtest.research.engine",
    "backtest.research.chip.evaluate_turnover_chip_factors",
    "backtest.research.chip.filter_chip_stocks",
    "backtest.research.chip.filter_stock_pool_by_chip",
    "backtest.research.chip.rolling_ic_chip_factors",
    "oskh_core.money_arithmetic",
    "oskh_core.a_share_symbol_normalize",
)

# H4：向量化 research 主路径 —— 不得强制 / 顺带加载 backtrader。
_VECTORIZED_RESEARCH_FACE = (
    "backtest.research.csv_daily_backtest",
    "backtest.research.csv_minute_backtest",
    "backtest.research.csv_simulate_loop",
    "backtest.research.csv_common",
    "backtest.research.csv_strategy_books",
    "backtest.research.csv_artifacts",
    "backtest.research.csv_daily_loader",
)

_BT_NAMES = frozenset({"backtrader", "bt"})


@pytest.mark.parametrize("module", _RESEARCH_FACE_MODULES)
def test_research_face_module_importable(module: str) -> None:
    importlib.import_module(module)


@pytest.mark.parametrize("module", _VECTORIZED_RESEARCH_FACE)
def test_vectorized_research_face_importable(module: str) -> None:
    importlib.import_module(module)


def _subprocess_import_no_backtrader(module: str) -> subprocess.CompletedProcess[str]:
    """Fresh interpreter: import ``module`` and fail if backtrader entered ``sys.modules``."""
    probe = (
        "import importlib, sys\n"
        f"importlib.import_module({module!r})\n"
        "bt = [k for k in sys.modules if k == 'backtrader' or k.startswith('backtrader.')]\n"
        "raise SystemExit(0 if not bt else f'backtrader pulled: {bt!r}')\n"
    )
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-c", probe],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.mark.parametrize("module", _RESEARCH_FACE_MODULES + _VECTORIZED_RESEARCH_FACE)
def test_vectorized_research_face_no_backtrader(module: str) -> None:
    """主路径导入不得要求或顺带加载 backtrader（子进程隔离，免测试顺序污染）。"""
    r = _subprocess_import_no_backtrader(module)
    assert r.returncode == 0, (
        f"module={module}\nstdout:\n{r.stdout}\nstderr:\n{r.stderr}"
    )


def _direct_import_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                roots.add(node.module.split(".", 1)[0])
            # relative imports stay inside package; not backtrader
    return roots


@pytest.mark.parametrize(
    "path",
    sorted((REPO / "backtest" / "research").rglob("*.py")),
    ids=lambda path: path.relative_to(REPO).as_posix(),
)
def test_research_face_ast_no_backtrader(path: Path) -> None:
    """静态：研究面所有 Python 文件、任意导入节点，零例外。"""
    roots = _direct_import_roots(path)
    bad = roots & _BT_NAMES
    assert not bad, f"{path.relative_to(REPO)} directly imports {sorted(bad)}"


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


def test_csv_minute_ast_no_csv_daily_import() -> None:
    """N-R6 持久围栏：minute 不得再 from-import csv_daily_backtest。"""
    path = REPO / "backtest" / "research" / "csv_minute_backtest.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    hits = [
        node
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module
        and node.module.endswith("csv_daily_backtest")
    ]
    assert hits == [], f"minute→daily import residual: {hits!r}"

